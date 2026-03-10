"""
Live Viva WebSocket Route

Real-time voice-to-voice viva assessment using Gemini Live API.
The student speaks naturally and Gemini responds as a real instructor.
No buttons, no clicking — just a conversation.

Protocol:
    Client → Server:
        JSON:   {"type": "start", "assignment_id": "...", "student_id": "...", "student_name": "..."}
        Binary: Raw PCM audio chunks (16kHz, 16-bit, mono)
        JSON:   {"type": "end"}

    Server → Client:
        JSON:   {"type": "ready", "session_id": "...", "total_questions": 5}
        JSON:   {"type": "thinking"}
        Binary: PCM audio from Gemini (24kHz, 16-bit, mono) — one complete turn
        JSON:   {"type": "turn_end"}
        JSON:   {"type": "evaluating"}  — viva conversation done, evaluating all responses
        JSON:   {"type": "complete", "session_id": "...", "final_score": 35, "max_score": 50, ...}
        JSON:   {"type": "error", "message": "..."}
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.genai import types
from sqlalchemy import select

from app import database
from app.models.assessment import (
    AssessmentQuestionInstance,
    AssessmentSession,
    ResponseCompetencyLink,
    StudentResponse,
)
from app.models.question import Question
from app.services.gemini_live_service import (
    QuestionInfo,
    build_live_config,
    build_viva_system_prompt,
    create_gemini_client,
)
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assessments", tags=["live-viva"])


# ── DB helpers ─────────────────────────────────────────────────────────


async def load_questions_for_assignment(assignment_id: str) -> list[QuestionInfo]:
    """Load all approved questions for an assignment."""
    assert database.async_session_factory is not None
    async with database.async_session_factory() as db:
        result = await db.execute(
            select(Question)
            .where(
                Question.assignment_id == assignment_id,
                Question.status == "approved",
            )
            .order_by(Question.difficulty.asc())
        )
        rows = list(result.scalars().all())

    questions = []
    for i, q in enumerate(rows, 1):
        questions.append(QuestionInfo(
            index=i,
            question_text=q.question_text,
            expected_answer=q.expected_answer or "",
            competency=q.competency or "General",
            difficulty=q.difficulty,
            question_id=q.id,
            max_points=float(q.max_points) if q.max_points else 10.0,
        ))
    return questions


async def get_assignment_title(assignment_id: str) -> str:
    """Get assignment title from mock data or return a fallback."""
    mock_titles = {
        "assign-001": "Introduction to Loops",
        "assign-002": "Recursion Fundamentals",
    }
    return mock_titles.get(assignment_id, f"Assignment {assignment_id}")


async def create_live_session(
    student_id: str,
    assignment_id: str,
) -> str:
    """Create an assessment session in DB for the live viva."""
    assert database.async_session_factory is not None
    session_id = str(uuid4())
    now = datetime.now(timezone.utc)

    async with database.async_session_factory() as db:
        session_obj = AssessmentSession(
            id=session_id,
            student_id=student_id,
            assignment_id=assignment_id,
            status="in_progress",
            trigger_reason="live_viva",
            started_at=now,
        )
        db.add(session_obj)
        await db.commit()

    return session_id


async def store_live_evaluation(
    session_id: str,
    question: QuestionInfo,
    score: float,
    feedback: str,
    student_answer: str,
    misconceptions: list[str],
    sequence_number: int,
) -> None:
    """Store a question evaluation from the live viva."""
    assert database.async_session_factory is not None
    now = datetime.now(timezone.utc)

    async with database.async_session_factory() as db:
        # Create question instance
        instance_id = str(uuid4())
        instance = AssessmentQuestionInstance(
            id=instance_id,
            session_id=session_id,
            question_id=question.question_id,
            sequence_number=sequence_number,
            asked_at=now,
            competency=question.competency,
            difficulty=question.difficulty,
        )
        db.add(instance)
        await db.flush()

        # Create student response
        response_id = str(uuid4())
        resp = StudentResponse(
            id=response_id,
            question_instance_id=instance_id,
            session_id=session_id,
            student_id="",  # Will be set from session
            response_text=student_answer,
            response_type="audio",
            transcript_text=student_answer,
            submitted_at=now,
            response_time_seconds=0,
            evaluation_score=score,
            feedback_text=feedback,
            detected_misconceptions=misconceptions if misconceptions else None,
            input_classification="live_viva",
            voice_intent="answer_attempt",
        )

        # Get student_id from session
        result = await db.execute(
            select(AssessmentSession.student_id).where(
                AssessmentSession.id == session_id
            )
        )
        row = result.first()
        if row:
            resp.student_id = row[0]

        db.add(resp)
        await db.flush()

        # Competency link
        link = ResponseCompetencyLink(
            id=str(uuid4()),
            response_id=response_id,
            competency=question.competency,
            score=score,
            question_id=question.question_id,
        )
        db.add(link)
        await db.commit()


async def complete_live_session(session_id: str) -> dict:
    """Mark session as complete and compute final scores."""
    assert database.async_session_factory is not None

    async with database.async_session_factory() as db:
        # Fetch session
        result = await db.execute(
            select(AssessmentSession).where(AssessmentSession.id == session_id)
        )
        session_obj = result.scalar_one_or_none()
        if not session_obj:
            return {"final_score": 0, "max_score": 0, "competency_summary": []}

        # Fetch all responses
        resp_result = await db.execute(
            select(StudentResponse).where(
                StudentResponse.session_id == session_id
            )
        )
        responses = list(resp_result.scalars().all())

        # Fetch question instances
        inst_result = await db.execute(
            select(AssessmentQuestionInstance).where(
                AssessmentQuestionInstance.session_id == session_id
            )
        )
        instances = {i.id: i for i in inst_result.scalars().all()}

        # Compute scores
        total_scored = 0.0
        total_max = 0.0
        competency_data: dict[str, dict] = {}

        for resp in responses:
            inst = instances.get(resp.question_instance_id)
            if not inst:
                continue
            comp = inst.competency or "General"
            max_pts = 10.0
            scored = float(resp.evaluation_score) if resp.evaluation_score is not None else 0.0

            total_scored += scored
            total_max += max_pts

            if comp not in competency_data:
                competency_data[comp] = {"scored": 0.0, "max": 0.0, "count": 0}
            competency_data[comp]["scored"] += scored
            competency_data[comp]["max"] += max_pts
            competency_data[comp]["count"] += 1

        # Build summary
        summary = []
        for comp, d in competency_data.items():
            pct = round((d["scored"] / d["max"]) * 100, 1) if d["max"] > 0 else 0.0
            summary.append({
                "competency": comp,
                "scored": round(d["scored"], 2),
                "max": round(d["max"], 2),
                "percentage": pct,
                "questions_count": d["count"],
            })

        # Update session
        session_obj.status = "completed"
        session_obj.completed_at = datetime.now(timezone.utc)
        session_obj.final_score = round(total_scored, 2)
        session_obj.max_score = round(total_max, 2)
        session_obj.competency_summary = summary
        await db.commit()

        return {
            "final_score": round(total_scored, 2),
            "max_score": round(total_max, 2),
            "competency_summary": summary,
        }


# ── WebSocket endpoint ─────────────────────────────────────────────────


@router.websocket("/sessions/live")
async def live_viva(websocket: WebSocket) -> None:
    """Live voice-to-voice viva via Gemini Live API.

    Fully bidirectional audio streaming. Gemini's built-in VAD handles all
    turn-taking — it knows when the student is speaking vs silent and
    responds automatically. No manual turn gating needed.
    """
    await websocket.accept()
    logger.info("Live viva WebSocket connected")

    session_id = None
    session_complete = False
    scores: list[dict] = []

    try:
        # ── Wait for start message ──────────────────────────────────
        start_msg = await websocket.receive_json()
        if start_msg.get("type") != "start":
            await websocket.send_json({"type": "error", "message": "Expected 'start' message"})
            await websocket.close()
            return

        assignment_id = start_msg.get("assignment_id", "")
        student_id = start_msg.get("student_id", "")
        student_name = start_msg.get("student_name", "Student")

        if not assignment_id or not student_id:
            await websocket.send_json({"type": "error", "message": "Missing assignment_id or student_id"})
            await websocket.close()
            return

        # ── Load questions ──────────────────────────────────────────
        questions = await load_questions_for_assignment(assignment_id)
        if not questions:
            await websocket.send_json({"type": "error", "message": "No questions found for this assignment"})
            await websocket.close()
            return

        assignment_title = await get_assignment_title(assignment_id)

        # ── Create assessment session ───────────────────────────────
        session_id = await create_live_session(student_id, assignment_id)

        # ── Build Gemini Live config ────────────────────────────────
        system_prompt = build_viva_system_prompt(
            assignment_title=assignment_title,
            student_name=student_name,
            questions=questions,
        )
        config = build_live_config(system_prompt)

        # ── Connect to Gemini Live ──────────────────────────────────
        client = create_gemini_client()

        await websocket.send_json({
            "type": "ready",
            "session_id": session_id,
            "total_questions": len(questions),
        })

        async with client.aio.live.connect(
            model=settings.gemini_live_model,
            config=config,
        ) as gemini_session:
            logger.info("Gemini Live connected for session %s", session_id)

            # Kick off the greeting — Gemini speaks first
            await gemini_session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part(text="[The student has just sat down. Begin the viva now — greet them warmly and ask the first question.]")],
                ),
                turn_complete=True,
            )
            logger.info("Sent initial prompt to trigger greeting")

            # ── Two concurrent tasks: proxy audio bidirectionally ───
            # No gating — Gemini VAD handles turn-taking automatically.
            # Audio flows continuously in both directions.

            mic_chunks_sent = 0

            async def client_to_gemini():
                """Forward all audio from Flutter → Gemini. Always."""
                nonlocal session_complete, mic_chunks_sent
                try:
                    while not session_complete:
                        try:
                            msg = await websocket.receive()
                        except Exception as e:
                            logger.info("Client WebSocket receive failed: %s", e)
                            session_complete = True
                            break
                        if msg.get("type") == "websocket.disconnect":
                            logger.info("Client disconnected (clean close)")
                            session_complete = True
                            break
                        if "bytes" in msg and msg["bytes"]:
                            mic_chunks_sent += 1
                            if mic_chunks_sent <= 3 or mic_chunks_sent % 100 == 0:
                                logger.info("Mic chunk #%d (%d bytes)", mic_chunks_sent, len(msg["bytes"]))
                            try:
                                await gemini_session.send_realtime_input(
                                    audio=types.Blob(
                                        data=msg["bytes"],
                                        mime_type="audio/pcm;rate=16000",
                                    )
                                )
                            except Exception as e:
                                logger.error("send_realtime_input failed: %s", e)
                                session_complete = True
                                break
                        elif "text" in msg:
                            data = json.loads(msg["text"])
                            if data.get("type") == "end":
                                logger.info("Client requested end")
                                try:
                                    await gemini_session.send_client_content(
                                        turns=types.Content(
                                            role="user",
                                            parts=[types.Part(text=(
                                                "[The student has ended the session. "
                                                "Wrap up immediately with a brief closing remark, "
                                                "then call complete_assessment with evaluations for "
                                                "all questions discussed so far. For questions not "
                                                "asked yet, give a score of 0.]"
                                            ))],
                                        ),
                                        turn_complete=True,
                                    )
                                except Exception as e:
                                    logger.error("Failed to send end prompt: %s", e)
                                    session_complete = True
                                break
                            elif data.get("type") == "mic_off":
                                # Student stopped mic — explicitly signal end of turn
                                # so Gemini processes the answer and asks the next question.
                                # (Just stopping audio isn't "silence" — it's nothing, and
                                #  Gemini's VAD would wait forever for more audio.)
                                logger.info("Mic off — signalling turn complete to Gemini")
                                try:
                                    await gemini_session.send_client_content(
                                        turn_complete=True,
                                    )
                                except Exception as e:
                                    logger.error("Failed to send turn_complete: %s", e)
                            elif data.get("type") == "message":
                                # Text message from simulator client (no mic)
                                text = data.get("text", "").strip()
                                if text:
                                    logger.info("Text message from client: %s", text[:80])
                                    try:
                                        await gemini_session.send_client_content(
                                            turns=types.Content(
                                                role="user",
                                                parts=[types.Part(text=text)],
                                            ),
                                            turn_complete=True,
                                        )
                                    except Exception as e:
                                        logger.error("Failed to send text message: %s", e)
                except Exception as e:
                    logger.error("client_to_gemini error: %s", e)
                    session_complete = True

            async def gemini_to_client():
                """Forward Gemini audio → Flutter, handle tool calls and interruptions."""
                nonlocal session_complete
                gemini_speaking = False
                audio_buffer = bytearray()
                AUDIO_BUFFER_THRESHOLD = 16000  # ~0.33s of 24kHz 16-bit mono

                async def flush_audio():
                    nonlocal audio_buffer
                    if audio_buffer:
                        try:
                            await websocket.send_bytes(bytes(audio_buffer))
                        except Exception as e:
                            logger.error("Failed to send audio to client: %s", e)
                            nonlocal session_complete
                            session_complete = True
                            return
                        audio_buffer.clear()

                try:
                    async for response in gemini_session.receive():
                        if session_complete:
                            break

                        # ── Audio / content from Gemini ─────────────
                        if response.server_content:
                            sc = response.server_content

                            # Buffer audio chunks and send in batches
                            if sc.model_turn:
                                for part in sc.model_turn.parts:
                                    if (part.inline_data is not None and
                                            part.inline_data.data is not None):
                                        if not gemini_speaking:
                                            gemini_speaking = True
                                            try:
                                                await websocket.send_json({"type": "gemini_speaking"})
                                            except Exception as e:
                                                logger.error("Failed to send gemini_speaking to client: %s", e)
                                                session_complete = True
                                                break
                                        audio_buffer.extend(part.inline_data.data)
                                        if len(audio_buffer) >= AUDIO_BUFFER_THRESHOLD:
                                            await flush_audio()

                            # Gemini finished a turn
                            if sc.turn_complete:
                                await flush_audio()
                                logger.info("Gemini turn complete")
                                gemini_speaking = False
                                try:
                                    await websocket.send_json({"type": "turn_end"})
                                except Exception as e:
                                    logger.error("Failed to send turn_end to client: %s", e)
                                    session_complete = True
                                    break

                            # Student interrupted Gemini (barge-in)
                            if getattr(sc, 'interrupted', False):
                                await flush_audio()
                                logger.info("Gemini interrupted by student")
                                gemini_speaking = False
                                try:
                                    await websocket.send_json({"type": "interrupted"})
                                except Exception as e:
                                    logger.error("Failed to send interrupted to client: %s", e)
                                    session_complete = True
                                    break

                            # Input transcription (what Gemini heard the student say)
                            if hasattr(sc, 'input_transcription') and sc.input_transcription:
                                text = getattr(sc.input_transcription, 'text', '')
                                if text:
                                    logger.info("Student said: %s", text[:200])
                                    try:
                                        await websocket.send_json({
                                            "type": "transcript",
                                            "text": text,
                                        })
                                    except Exception as e:
                                        logger.error("Failed to send transcript to client: %s", e)
                                        session_complete = True
                                        break

                        # ── Tool calls (scoring) ────────────────────
                        if response.tool_call:
                            for fc in response.tool_call.function_calls:
                                logger.info("Tool call: %s", fc.name)

                                if fc.name == "complete_assessment":
                                    try:
                                        await websocket.send_json({"type": "evaluating"})
                                    except Exception as e:
                                        logger.error("Failed to send evaluating to client: %s", e)
                                        session_complete = True
                                        break

                                    args = fc.args or {}
                                    evaluations = args.get("evaluations", [])
                                    overall_feedback = str(args.get("overall_feedback", ""))

                                    logger.info(
                                        "Received %d evaluations (feedback: %s)",
                                        len(evaluations), overall_feedback[:100],
                                    )

                                    for eval_data in evaluations:
                                        q_index = int(eval_data.get("question_index", 0))
                                        score = float(eval_data.get("score", 0))
                                        score = max(0.0, min(10.0, score))
                                        feedback = str(eval_data.get("feedback", ""))
                                        student_answer = str(eval_data.get("student_answer_summary", ""))
                                        misconceptions = eval_data.get("misconceptions", []) or []

                                        if 1 <= q_index <= len(questions):
                                            question = questions[q_index - 1]
                                            try:
                                                await store_live_evaluation(
                                                    session_id=session_id,
                                                    question=question,
                                                    score=score,
                                                    feedback=feedback,
                                                    student_answer=student_answer,
                                                    misconceptions=misconceptions,
                                                    sequence_number=q_index,
                                                )
                                            except Exception as e:
                                                logger.error("Failed to store eval: %s", e)

                                            scores.append({
                                                "question_number": q_index,
                                                "score": score,
                                            })

                                    try:
                                        completion = await complete_live_session(session_id)
                                    except Exception as e:
                                        logger.error("Failed to complete session: %s", e)
                                        completion = {
                                            "final_score": sum(s["score"] for s in scores),
                                            "max_score": len(questions) * 10.0,
                                            "competency_summary": [],
                                        }

                                    try:
                                        await websocket.send_json({
                                            "type": "complete",
                                            "session_id": session_id,
                                            "final_score": completion["final_score"],
                                            "max_score": completion["max_score"],
                                            "competency_summary": completion["competency_summary"],
                                        })
                                    except Exception as e:
                                        logger.error("Failed to send complete to client: %s", e)

                                    await gemini_session.send_tool_response(
                                        function_responses=[types.FunctionResponse(
                                            id=fc.id,
                                            name=fc.name,
                                            response={"status": "completed"},
                                        )]
                                    )

                                    session_complete = True
                                    break

                except Exception as e:
                    logger.error("gemini_to_client error: %s", e, exc_info=True)
                    if not session_complete:
                        try:
                            await websocket.send_json({
                                "type": "error",
                                "message": "Connection to AI instructor lost.",
                            })
                        except Exception:
                            pass

            await asyncio.gather(
                client_to_gemini(),
                gemini_to_client(),
                return_exceptions=True,
            )

    except WebSocketDisconnect:
        logger.info("Live viva disconnected: %s", session_id)
    except ValueError as e:
        logger.error("Live viva config error: %s", e)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    except Exception as e:
        logger.error("Live viva unexpected error: %s", e, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": f"{type(e).__name__}: {e}"})
        except Exception:
            pass
    finally:
        # If session was started but not completed, mark as abandoned
        if session_id and not session_complete:
            try:
                assert database.async_session_factory is not None
                async with database.async_session_factory() as db:
                    result = await db.execute(
                        select(AssessmentSession).where(
                            AssessmentSession.id == session_id
                        )
                    )
                    session_obj = result.scalar_one_or_none()
                    if session_obj and session_obj.status == "in_progress":
                        session_obj.status = "abandoned"
                        session_obj.completed_at = datetime.now(timezone.utc)
                        await db.commit()
            except Exception as e:
                logger.error("Failed to mark session as abandoned: %s", e)
