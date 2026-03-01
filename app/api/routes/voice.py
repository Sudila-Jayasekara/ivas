"""
Voice Assessment WebSocket Route

Provides a WebSocket endpoint for voice-based assessment sessions.
STT and TTS are handled entirely in the browser via the Web Speech API.
The server classifies student intent before deciding whether to evaluate
or respond conversationally.

WebSocket URL:
    WS /api/v1/assessments/sessions/{session_id}/voice

Client -> Server message types:
    {"type": "start_session", "question_instance_id": "<uuid>", "question_text": "..."}
        - Sent once after connecting. Provides the first question context.

    {"type": "submit_answer", "question_instance_id": "<uuid>", "text": "..."}
        - The transcribed speech (from browser SpeechRecognition).
          The server classifies the intent before evaluating.

Server -> Client message types:
    {"type": "instructor_response", "message": "...", "intent": "...",
     "repeat_question": "..." | null}
        - Conversational response when the student asks for clarification,
          a repeat, or a topic question (no scoring).

    {"type": "evaluation", "score": 7.5, "feedback": "...", "misconceptions": [...]}
        - LLM evaluation result for an actual answer attempt.

    {"type": "next_question",
     "question_instance_id": "...", "question_text": "...",
     "competency": "...", "difficulty": 2, "is_follow_up": false}
        - The next question (browser speaks it via speechSynthesis).

    {"type": "session_complete",
     "final_score": 25.0, "max_score": 30.0, "message": "...",
     "competency_summary": [...]}
        - Assessment is finished.

    {"type": "error", "message": "..."}
        - Non-fatal error (client can retry).
"""

import asyncio
import logging
from functools import partial

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app import database
from app.models.assessment import AssessmentQuestionInstance
from app.models.question import Question
from app.services.assessment_service import AssessmentService
from app.services.voice_service import StudentIntent, voice_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assessments", tags=["voice"])


async def _lookup_question_text(question_instance_id: str) -> str:
    """Fetch question text from DB when start_session was not sent."""
    assert database.async_session_factory is not None
    async with database.async_session_factory() as db:
        result = await db.execute(
            select(AssessmentQuestionInstance).where(
                AssessmentQuestionInstance.id == question_instance_id
            )
        )
        inst = result.scalar_one_or_none()
        if not inst:
            return ""
        if inst.follow_up_question_text:
            return inst.follow_up_question_text
        q_result = await db.execute(
            select(Question).where(Question.id == inst.question_id)
        )
        q_obj = q_result.scalar_one_or_none()
        return q_obj.question_text if q_obj else ""


@router.websocket("/sessions/{session_id}/voice")
async def voice_assessment(websocket: WebSocket, session_id: str) -> None:
    """Conversational voice assessment endpoint (STT/TTS in browser)."""
    await websocket.accept()
    logger.info("Voice session started: %s", session_id)

    # Per-connection state
    current_question_text = ""
    current_qiid = ""

    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")

            # ── Client sends first question context ────────────────────
            if msg_type == "start_session":
                current_question_text = msg.get("question_text", "")
                current_qiid = msg.get("question_instance_id", "")
                logger.info("Session context set: qiid=%s", current_qiid)
                continue

            # ── Student speaks ─────────────────────────────────────────
            if msg_type != "submit_answer":
                await websocket.send_json(
                    {"type": "error", "message": f"Unknown message type: {msg_type}"}
                )
                continue

            text = (msg.get("text") or "").strip()
            question_instance_id: str = msg.get("question_instance_id", "")

            if not text:
                await websocket.send_json(
                    {"type": "error", "message": "Empty answer received"}
                )
                continue

            # Track which question we're on
            if question_instance_id:
                current_qiid = question_instance_id

            # Ensure we have the current question text for classification
            if not current_question_text and current_qiid:
                current_question_text = await _lookup_question_text(current_qiid)

            # ── Classify intent (runs LLM in thread pool) ─────────────
            loop = asyncio.get_event_loop()
            classification = await loop.run_in_executor(
                None,
                partial(
                    voice_service.classify_intent,
                    student_text=text,
                    question_text=current_question_text,
                ),
            )

            logger.info(
                "Intent: %s (%.0f%%) for: %s",
                classification.intent.value,
                classification.confidence * 100,
                text[:80],
            )

            # ── Non-answer intents: respond conversationally ───────────
            if classification.intent != StudentIntent.ANSWER_ATTEMPT:
                if classification.intent in (
                    StudentIntent.CLARIFICATION_REQUEST,
                    StudentIntent.TOPIC_QUESTION,
                ):
                    response_text = await loop.run_in_executor(
                        None,
                        partial(
                            voice_service.generate_conversational_response,
                            intent=classification.intent,
                            student_text=text,
                            question_text=current_question_text,
                        ),
                    )
                else:
                    response_text = voice_service.generate_conversational_response(
                        intent=classification.intent,
                        student_text=text,
                        question_text=current_question_text,
                    )

                repeat_q = None
                if classification.intent in (
                    StudentIntent.REPEAT_REQUEST,
                    StudentIntent.OFF_TOPIC,
                ):
                    repeat_q = current_question_text

                await websocket.send_json({
                    "type": "instructor_response",
                    "message": response_text,
                    "intent": classification.intent.value,
                    "repeat_question": repeat_q,
                })
                continue

            # ── Answer attempt: run through assessment pipeline ────────
            try:
                assert database.async_session_factory is not None
                async with database.async_session_factory() as db:
                    try:
                        svc = AssessmentService(db)
                        result = await svc.submit_response(
                            session_id=session_id,
                            question_instance_id=question_instance_id,
                            response_text=text,
                            response_type="audio",
                            transcript_text=text,
                        )
                        await db.commit()
                    except Exception:
                        await db.rollback()
                        raise
            except ValueError as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
                continue

            # Send evaluation result
            await websocket.send_json({
                "type": "evaluation",
                "score": result.evaluation_score,
                "feedback": result.feedback_text,
                "misconceptions": result.detected_misconceptions or [],
            })

            # Session complete
            if result.is_complete:
                await websocket.send_json({
                    "type": "session_complete",
                    "final_score": result.final_score,
                    "max_score": result.max_score,
                    "message": result.message,
                    "competency_summary": result.competency_summary or [],
                })
                break

            # Next question — update tracked context
            nq = result.next_question
            current_question_text = nq.question_text
            current_qiid = nq.question_instance_id

            await websocket.send_json({
                "type": "next_question",
                "question_instance_id": nq.question_instance_id,
                "question_text": nq.question_text,
                "competency": nq.competency,
                "difficulty": nq.difficulty,
                "is_follow_up": nq.is_follow_up,
            })

    except WebSocketDisconnect:
        logger.info("Voice session disconnected: %s", session_id)
    except Exception as exc:
        logger.error("Voice session unexpected error (%s): %r", session_id, exc, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": "Internal server error"})
        except Exception:
            pass
