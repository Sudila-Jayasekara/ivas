"""
Voice Assessment WebSocket Route

Provides a WebSocket endpoint for voice-based assessment sessions.
STT and TTS are handled entirely in the browser via the Web Speech API.
ALL student speech goes to the LLM for intent classification — the server
never uses regex or manual parsing to decide what the student meant.

VOICE BIOMETRIC VERIFICATION:
    If the student has an enrolled voiceprint AND the client sends audio_data
    (base64 WAV) alongside text, every message is verified against the stored
    voiceprint in the background. If verification fails repeatedly, the session
    is flagged and the student is warned.

WebSocket URL:
    WS /api/v1/assessments/sessions/{session_id}/voice

Client -> Server message types:
    {"type": "start_session", "question_instance_id": "<uuid>", "question_text": "..."}
        - Sent once after connecting. Provides the first question context.

    {"type": "message", "text": "...", "audio_data": "<base64 WAV optional>"}
    {"type": "submit_answer", "text": "...", "question_instance_id": "...", "audio_data": "..."}
        - Any student speech. Both types are accepted — the LLM classifies
          the intent (answer, clarification, repeat, topic question, etc.).
        - audio_data is optional base64-encoded WAV for voice biometric verification.

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

    {"type": "voice_verification", "passed": true, "similarity": 0.87,
     "message": "...", "consecutive_failures": 0}
        - Voice biometric verification result (sent after each audio check).

    {"type": "voice_verification_warning", "message": "...",
     "consecutive_failures": 3}
        - Sent when consecutive failures reach the threshold — session flagged.

    {"type": "error", "message": "..."}
        - Non-fatal error (client can retry).
"""

import asyncio
import logging
from datetime import datetime, timezone
from functools import partial
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select

from app import database
from app.models.assessment import AssessmentQuestionInstance, AssessmentSession, StudentResponse
from app.models.question import Question
from app.models.voiceprint import VoiceVerificationLog
from app.repositories.voiceprint_repository import VoiceprintRepository
from app.services.assessment_service import AssessmentService
from app.services.conversation_context import build_conversation_context, MAX_CLARIFICATIONS_BEFORE_ESCALATION
from app.services.voice_service import StudentIntent, voice_service
from app.services.voice_biometric_service import (
    MAX_CONSECUTIVE_FAILURES,
    VERIFICATION_THRESHOLD,
    compute_embedding_from_audio,
    verify_speaker,
)
from app.services.tts_service import generate_audio_b64

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assessments", tags=["voice"])


# ── Voice biometric helpers ────────────────────────────────────────────


async def _load_voiceprint_for_session(session_id: str) -> tuple[str | None, list[float] | None]:
    """Look up the student_id from the session and load their active voiceprint.

    Returns (student_id, embedding) or (None, None) if not enrolled.
    """
    assert database.async_session_factory is not None
    async with database.async_session_factory() as db:
        result = await db.execute(
            select(AssessmentSession.student_id).where(AssessmentSession.id == session_id)
        )
        row = result.first()
        if not row:
            return None, None
        student_id = row[0]

        repo = VoiceprintRepository(db)
        vp = await repo.find_active_by_student(student_id)
        if not vp:
            return student_id, None
        return student_id, vp.embedding


async def _run_voice_verification(
    websocket: WebSocket,
    session_id: str,
    student_id: str,
    stored_embedding: list[float],
    audio_b64: str,
    consecutive_failure_count: int,
) -> int:
    """Run speaker verification in background and send result to client.

    Returns the updated consecutive failure count.
    """
    loop = asyncio.get_running_loop()

    try:
        live_emb = await loop.run_in_executor(
            None, partial(compute_embedding_from_audio, audio_b64)
        )
    except ValueError as e:
        logger.debug("Biometric check skipped (bad audio): %s", e)
        return consecutive_failure_count

    passed, score = verify_speaker(live_emb, stored_embedding)

    if passed:
        consecutive_failure_count = 0
    else:
        consecutive_failure_count += 1

    # Store audit log
    try:
        assert database.async_session_factory is not None
        async with database.async_session_factory() as db:
            repo = VoiceprintRepository(db)
            log = VoiceVerificationLog(
                id=str(uuid4()),
                session_id=session_id,
                student_id=student_id,
                similarity_score=score,
                threshold=VERIFICATION_THRESHOLD,
                passed=passed,
                consecutive_failures=consecutive_failure_count,
            )
            await repo.create_verification_log(log)
            await db.commit()
    except Exception as e:
        logger.error("Failed to store verification log: %s", e)

    # Notify client of verification result
    await websocket.send_json({
        "type": "voice_verification",
        "passed": passed,
        "similarity": round(score, 4),
        "message": "Identity verified." if passed else "Voice mismatch detected.",
        "consecutive_failures": consecutive_failure_count,
    })

    # Send warning if consecutive failures reach threshold
    if consecutive_failure_count >= MAX_CONSECUTIVE_FAILURES:
        warning_msg = (
            "Warning: Voice biometric verification has failed multiple times. "
            "This session has been flagged for review. "
            "Please ensure only you are speaking during the assessment."
        )
        warning_audio = await generate_audio_b64(warning_msg)
        await websocket.send_json({
            "type": "voice_verification_warning",
            "message": warning_msg,
            "consecutive_failures": consecutive_failure_count,
            "audio_b64": warning_audio,
        })
        logger.warning(
            "Session %s flagged: %d consecutive voice verification failures",
            session_id, consecutive_failure_count,
        )

    return consecutive_failure_count


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


async def _is_duplicate_response(question_instance_id: str) -> bool:
    """Check if an answer-type response was already submitted for this question instance.

    Conversational exchanges (clarification, repeat, topic) do NOT count as
    duplicate answers — only actual answer attempts and pipeline-processed
    responses count.
    """
    assert database.async_session_factory is not None
    # voice_intents that represent conversational exchanges (not answers)
    conversational_intents = (
        "clarification_request", "repeat_request", "topic_question",
    )
    async with database.async_session_factory() as db:
        result = await db.execute(
            select(func.count())
            .select_from(StudentResponse)
            .where(
                StudentResponse.question_instance_id == question_instance_id,
                # Exclude conversational exchanges from duplicate check
                ~StudentResponse.voice_intent.in_(conversational_intents)
                | StudentResponse.voice_intent.is_(None),
            )
        )
        return (result.scalar() or 0) > 0


async def _find_next_unanswered_question(
    session_id: str,
) -> dict | None:
    """Find the next question instance in this session that has no answer-type response yet.

    Conversational exchanges (clarification, repeat, topic) do NOT count as
    answers — a question is only 'answered' when an actual answer attempt
    or pipeline-processed response exists.
    """
    assert database.async_session_factory is not None
    conversational_intents = (
        "clarification_request", "repeat_request", "topic_question",
    )
    async with database.async_session_factory() as db:
        # Get all question instances for the session, ordered by sequence
        inst_result = await db.execute(
            select(AssessmentQuestionInstance)
            .where(AssessmentQuestionInstance.session_id == session_id)
            .order_by(AssessmentQuestionInstance.sequence_number.asc())
        )
        instances = list(inst_result.scalars().all())

        if not instances:
            return None

        # Get question instance IDs that have answer-type responses
        resp_result = await db.execute(
            select(StudentResponse.question_instance_id).where(
                StudentResponse.session_id == session_id,
                # Only count non-conversational responses as "answered"
                ~StudentResponse.voice_intent.in_(conversational_intents)
                | StudentResponse.voice_intent.is_(None),
            )
        )
        answered_ids = {row[0] for row in resp_result.all()}

        # Find first unanswered instance
        for inst in instances:
            if inst.id not in answered_ids:
                # Get question text
                q_text = inst.follow_up_question_text
                if not q_text:
                    q_result = await db.execute(
                        select(Question).where(Question.id == inst.question_id)
                    )
                    q_obj = q_result.scalar_one_or_none()
                    q_text = q_obj.question_text if q_obj else ""

                return {
                    "question_instance_id": inst.id,
                    "question_text": q_text,
                    "competency": inst.competency,
                    "difficulty": inst.difficulty,
                    "is_follow_up": inst.parent_instance_id is not None,
                }

        return None


async def _store_conversational_exchange(
    session_id: str,
    question_instance_id: str,
    student_text: str,
    instructor_response: str,
    voice_intent: str,
) -> None:
    """Store a conversational exchange (clarification, repeat, topic question) in the DB.

    These are NOT answer attempts — they are stored for full conversation audit
    but do not trigger evaluation or affect scoring.
    """
    assert database.async_session_factory is not None
    async with database.async_session_factory() as db:
        # Look up student_id from session
        result = await db.execute(
            select(AssessmentSession.student_id).where(
                AssessmentSession.id == session_id
            )
        )
        row = result.first()
        student_id = row[0] if row else "unknown"

        resp = StudentResponse(
            id=str(uuid4()),
            question_instance_id=question_instance_id,
            session_id=session_id,
            student_id=student_id,
            response_text=student_text,
            response_type="audio",
            transcript_text=student_text,
            submitted_at=datetime.now(timezone.utc),
            response_time_seconds=0,
            # No evaluation for conversational exchanges
            evaluation_score=None,
            feedback_text=instructor_response,
            detected_misconceptions=None,
            input_classification="conversational",
            voice_intent=voice_intent,
        )
        db.add(resp)
        await db.commit()


@router.websocket("/sessions/{session_id}/voice")
async def voice_assessment(websocket: WebSocket, session_id: str) -> None:
    """Conversational voice assessment endpoint (STT/TTS in browser).

    Every piece of student speech is sent to the LLM for intent classification.
    The server never guesses intent via regex — the LLM decides whether the
    student is answering, asking for clarification, requesting a repeat, etc.

    BIOMETRIC VERIFICATION:
    If the student has an enrolled voiceprint and the client sends audio_data
    (base64 WAV) with each message, the system verifies speaker identity
    in the background. If verification fails 3+ times consecutively, the
    session is flagged and the student is warned.
    """
    await websocket.accept()
    logger.info("Voice session started: %s", session_id)

    # Per-connection state
    current_question_text = ""
    current_qiid = ""

    # Voice biometric state — loaded once on session start
    bio_student_id: str | None = None
    bio_stored_embedding: list[float] | None = None
    bio_consecutive_failures: int = 0
    bio_loaded = False

    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type", "")

            # ── Client sends first question context ────────────────────
            if msg_type == "start_session":
                current_question_text = msg.get("question_text", "")
                current_qiid = msg.get("question_instance_id", "")
                logger.info("Session context set: qiid=%s", current_qiid)

                # Load voiceprint for biometric verification (once per session)
                if not bio_loaded:
                    bio_loaded = True
                    try:
                        bio_student_id, bio_stored_embedding = (
                            await _load_voiceprint_for_session(session_id)
                        )
                        if bio_stored_embedding:
                            logger.info(
                                "Voice biometric active for student %s in session %s",
                                bio_student_id, session_id,
                            )
                            await websocket.send_json({
                                "type": "voice_verification",
                                "passed": True,
                                "similarity": 1.0,
                                "message": "Voice biometric verification is active for this session.",
                                "consecutive_failures": 0,
                            })
                        else:
                            logger.info(
                                "No voiceprint enrolled for session %s — biometric verification disabled",
                                session_id,
                            )
                    except Exception as e:
                        logger.warning("Failed to load voiceprint: %s", e)

                
                # Automatically speak the first question to the student
                if current_question_text:
                    try:
                        first_audio_b64 = await generate_audio_b64(current_question_text)
                        await websocket.send_json({
                            "type": "instructor_response",
                            "message": current_question_text,
                            "intent": "greeting",
                            "repeat_question": None,
                            "audio_b64": first_audio_b64,
                        })
                    except Exception as e:
                        logger.error("Failed to generate TTS for first question: %s", e)
                continue

            # ── Accept any text from the student ───────────────────────
            # Both "message" and "submit_answer" are treated the same way:
            # the text goes straight to the LLM for intent classification.
            if msg_type not in ("message", "submit_answer"):
                # Unknown type — still try to extract text; if none, skip
                if not msg.get("text", "").strip():
                    await websocket.send_json(
                        {"type": "error", "message": f"Unknown message type: {msg_type}"}
                    )
                    continue

            text = (msg.get("text") or "").strip()
            question_instance_id: str = msg.get("question_instance_id", "")
            audio_data: str = msg.get("audio_data", "")

            if not text:
                await websocket.send_json(
                    {"type": "error", "message": "No speech detected. Please try again."}
                )
                continue

            # ── Voice biometric verification (background) ──────────────
            # If the student has an enrolled voiceprint and audio_data was sent,
            # verify that the speaker matches the enrolled student.
            if bio_stored_embedding and audio_data and bio_student_id:
                try:
                    bio_consecutive_failures = await _run_voice_verification(
                        websocket=websocket,
                        session_id=session_id,
                        student_id=bio_student_id,
                        stored_embedding=bio_stored_embedding,
                        audio_b64=audio_data,
                        consecutive_failure_count=bio_consecutive_failures,
                    )
                except Exception as e:
                    logger.warning("Biometric verification error: %s", e)

            # Track which question we're on
            if question_instance_id:
                current_qiid = question_instance_id

            # Ensure we have the current question text for classification
            if not current_question_text and current_qiid:
                current_question_text = await _lookup_question_text(current_qiid)

            # ── Build conversation context from DB ─────────────────────
            conv_history_text = ""
            conv_should_escalate = False
            if current_qiid:
                try:
                    assert database.async_session_factory is not None
                    async with database.async_session_factory() as ctx_db:
                        conv_ctx = await build_conversation_context(
                            ctx_db, current_qiid
                        )
                        conv_history_text = conv_ctx.history_text
                        conv_should_escalate = conv_ctx.should_escalate
                except Exception as e:
                    logger.warning("Failed to build conversation context: %s", e)

            # ── Send ALL speech to the LLM for intent classification ───
            loop = asyncio.get_running_loop()
            classification = await loop.run_in_executor(
                None,
                partial(
                    voice_service.classify_intent,
                    student_text=text,
                    question_text=current_question_text,
                    conversation_history=conv_history_text,
                ),
            )

            logger.info(
                "Intent: %s (%.0f%%) for: %s",
                classification.intent.value,
                classification.confidence * 100,
                text[:80],
            )

            # ── Non-answer intents: only conversational ones stay here ──
            # PROCEED_REQUEST and OFF_TOPIC are routed through submit_response
            # so they get stored in DB and handled by the assessment pipeline
            # (Input Guard classifies, stores, teaches or re-asks).
            if classification.intent in (
                StudentIntent.CLARIFICATION_REQUEST,
                StudentIntent.REPEAT_REQUEST,
                StudentIntent.TOPIC_QUESTION,
            ):
                # ── Clarification escalation ────────────────────────────
                # If the student has asked for clarification too many times,
                # stop looping and route through the assessment pipeline
                # which will teach the concept and advance.
                if (
                    classification.intent == StudentIntent.CLARIFICATION_REQUEST
                    and conv_should_escalate
                ):
                    logger.info(
                        "Clarification escalation triggered for qiid=%s (count >= %d)",
                        current_qiid, MAX_CLARIFICATIONS_BEFORE_ESCALATION,
                    )
                    # Route through assessment pipeline as "proceed_request"
                    # so it teaches and moves on
                    classification = classification.__class__(
                        intent=StudentIntent.PROCEED_REQUEST,
                        confidence=1.0,
                    )
                    # Fall through to the answer/pipeline path below
                else:
                    response_text = await loop.run_in_executor(
                        None,
                        partial(
                            voice_service.generate_conversational_response,
                            intent=classification.intent,
                            student_text=text,
                            question_text=current_question_text,
                            conversation_history=conv_history_text,
                        ),
                    )

                    repeat_q = None
                    if classification.intent == StudentIntent.REPEAT_REQUEST:
                        repeat_q = current_question_text

                    audio_b64 = await generate_audio_b64(response_text)
                    
                    await websocket.send_json({
                        "type": "instructor_response",
                        "message": response_text,
                        "intent": classification.intent.value,
                        "repeat_question": repeat_q,
                        "audio_b64": audio_b64,
                    })

                    # Store conversational exchange in DB (fire & forget)
                    if current_qiid:
                        asyncio.create_task(
                            _store_conversational_exchange(
                                session_id=session_id,
                                question_instance_id=current_qiid,
                                student_text=text,
                                instructor_response=response_text,
                                voice_intent=classification.intent.value,
                            )
                        )

                    continue

            # ── Answer attempt: run through assessment pipeline ────────
            effective_qiid = question_instance_id or current_qiid
            if not effective_qiid:
                # No question context yet — ask the LLM to respond helpfully
                # instead of throwing a hard error.
                await websocket.send_json({
                    "type": "instructor_response",
                    "message": (
                        "I heard you, but I don't have a question loaded yet. "
                        "Please wait for the first question before answering."
                    ),
                    "intent": "waiting",
                    "repeat_question": None,
                })
                continue

            # ── Duplicate check — advance to next question instead of getting stuck ──
            if await _is_duplicate_response(effective_qiid):
                logger.warning(
                    "Duplicate response for qiid=%s — finding next question",
                    effective_qiid,
                )
                next_q = await _find_next_unanswered_question(session_id)
                if next_q and next_q["question_instance_id"] != effective_qiid:
                    # Advance to the next unanswered question
                    current_qiid = next_q["question_instance_id"]
                    current_question_text = next_q["question_text"]
                    
                    msg_text = "I've already recorded your answer for that question. Here's the next one."
                    audio_b64 = await generate_audio_b64(msg_text)
                    
                    await websocket.send_json({
                        "type": "instructor_response",
                        "message": msg_text,
                        "intent": "duplicate",
                        "repeat_question": None,
                        "audio_b64": audio_b64,
                    })
                    
                    next_audio_b64 = await generate_audio_b64(next_q["question_text"])
                    await websocket.send_json({
                        "type": "next_question",
                        "question_instance_id": next_q["question_instance_id"],
                        "question_text": next_q["question_text"],
                        "competency": next_q["competency"],
                        "difficulty": next_q["difficulty"],
                        "is_follow_up": next_q["is_follow_up"],
                        "audio_b64": next_audio_b64,
                    })
                else:
                    # All questions answered — wrap up
                    msg_text = "I've already recorded your answer. It looks like you've answered all the questions!"
                    audio_b64 = await generate_audio_b64(msg_text)
                    await websocket.send_json({
                        "type": "instructor_response",
                        "message": msg_text,
                        "intent": "duplicate",
                        "repeat_question": None,
                        "audio_b64": audio_b64,
                    })
                continue

            # ── Submit + evaluate (LLM calls run in thread pool) ───────
            try:
                assert database.async_session_factory is not None
                async with database.async_session_factory() as db:
                    try:
                        svc = AssessmentService(db)
                        result = await svc.submit_response(
                            session_id=session_id,
                            question_instance_id=effective_qiid,
                            response_text=text,
                            response_type="audio",
                            transcript_text=text,
                            voice_intent=classification.intent.value,
                        )
                        await db.commit()
                    except Exception:
                        await db.rollback()
                        raise
            except ValueError as exc:
                # Graceful handling — send a friendly message, not raw error
                error_msg = str(exc)
                logger.warning("Assessment pipeline ValueError: %s", error_msg)
                friendly = "Something went wrong processing your answer. "
                if "not found" in error_msg:
                    friendly += "The session may have expired. Please reconnect."
                elif "not in progress" in error_msg:
                    friendly += "This assessment has already been completed."
                elif "invalid question" in error_msg:
                    friendly += "There was a question tracking issue. Please continue speaking."
                else:
                    friendly += "Please try again."
                audio_b64 = await generate_audio_b64(friendly)
                await websocket.send_json({
                    "type": "instructor_response",
                    "message": friendly,
                    "intent": "error_recovery",
                    "repeat_question": current_question_text or None,
                    "audio_b64": audio_b64,
                })
                continue
            except Exception as exc:
                logger.error("Unexpected error in submit_response: %r", exc, exc_info=True)
                msg_text = "I had trouble processing that. Could you please repeat your answer?"
                audio_b64 = await generate_audio_b64(msg_text)
                await websocket.send_json({
                    "type": "instructor_response",
                    "message": msg_text,
                    "intent": "error_recovery",
                    "repeat_question": current_question_text or None,
                    "audio_b64": audio_b64,
                })
                continue

            # Send evaluation result
            # Optional: Generate TTS for the feedback itself
            feedback_audio_b64 = None
            if result.feedback_text:
                feedback_audio_b64 = await generate_audio_b64(result.feedback_text)
            
            await websocket.send_json({
                "type": "evaluation",
                "score": result.evaluation_score,
                "feedback": result.feedback_text,
                "misconceptions": result.detected_misconceptions or [],
                "audio_b64": feedback_audio_b64,
            })

            # Session complete
            if result.is_complete:
                audio_b64 = await generate_audio_b64(f"Assessment complete. Your final score is {result.final_score} out of {result.max_score}")
                await websocket.send_json({
                    "type": "session_complete",
                    "final_score": result.final_score,
                    "max_score": result.max_score,
                    "message": result.message,
                    "competency_summary": result.competency_summary or [],
                    "audio_b64": audio_b64,
                })
                break

            # Next question — update tracked context
            nq = result.next_question
            if nq is None:
                # Edge case: not complete but no next question — treat as complete
                logger.warning("No next question but session not marked complete")
                audio_b64 = await generate_audio_b64("Assessment completed.")
                await websocket.send_json({
                    "type": "session_complete",
                    "final_score": result.final_score or 0,
                    "max_score": result.max_score or 0,
                    "message": "Assessment completed.",
                    "competency_summary": result.competency_summary or [],
                    "audio_b64": audio_b64,
                })
                break

            current_question_text = nq.question_text
            current_qiid = nq.question_instance_id

            next_audio_b64 = await generate_audio_b64(nq.question_text)

            await websocket.send_json({
                "type": "next_question",
                "question_instance_id": nq.question_instance_id,
                "question_text": nq.question_text,
                "competency": nq.competency,
                "difficulty": nq.difficulty,
                "is_follow_up": nq.is_follow_up,
                "audio_b64": next_audio_b64,
            })

    except WebSocketDisconnect:
        logger.info("Voice session disconnected: %s", session_id)
    except Exception as exc:
        logger.error("Voice session unexpected error (%s): %r", session_id, exc, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": "Internal server error"})
        except Exception:
            pass
