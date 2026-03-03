"""
Assessment Service

Core business logic for conducting an assessment session. It orchestrates
the flow between a student requesting an assessment to the LLM generating
questions and evaluating answers. This service uses a layered LLM architecture:

  Layer 1 — Input Guard: LLM classifies input (abuse / non_answer / genuine_attempt)
  Layer 2 — Quick Evaluation: LLM scores + feedback (real-time, for branching)
  Layer 3 — Deep Analysis: LLM justification + misconceptions (background task)

No regex is used for content classification — all intelligence is LLM-driven.
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import (
    AssessmentQuestionInstance,
    AssessmentSession,
    ResponseCompetencyLink,
    StudentResponse,
)
from app.models.question import Question
from app.schemas.assessment import (
    AssessmentTranscriptOut,
    ExchangeOut,
    InstructorAssessmentSummary,
    QuestionInstanceOut,
    QuestionWithContext,
    SessionDetailsOut,
    SessionOut,
    StudentResponseOut,
    StudentSessionSummary,
    SubmitResponseResponse,
    TriggerAssessmentRequest,
    TriggerAssessmentResponse,
)
from app.services.evaluation_service import evaluation_service
from app.services.background_analysis import run_background_analysis
from app.services.conversation_context import build_conversation_context

logger = logging.getLogger(__name__)

# --- Session & question flow limits ---
MAX_TOTAL_EXCHANGES = 30        # Hard cap on total exchanges in a session
MAX_EXCHANGES_PER_QUESTION = 3  # Max exchanges (root + follow-ups + re-asks) per bank question
MAX_FOLLOW_UP_DEPTH = 1         # Max Socratic follow-ups per question chain
MAX_REASK_COUNT = 1             # Max re-asks for low-score responses


class AssessmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Score computation (called when session completes)
    # ------------------------------------------------------------------

    async def _compute_session_scores(
        self, session_obj: AssessmentSession
    ) -> None:
        """Aggregate per-response scores into session-level final_score and competency_summary."""
        result = await self.session.execute(
            select(StudentResponse).where(
                StudentResponse.session_id == session_obj.id
            )
        )
        responses = list(result.scalars().all())

        # Fetch question instances to map response → competency + max_points
        inst_result = await self.session.execute(
            select(AssessmentQuestionInstance).where(
                AssessmentQuestionInstance.session_id == session_obj.id
            )
        )
        instances = {i.id: i for i in inst_result.scalars().all()}

        # Fetch questions for max_points
        q_ids = [i.question_id for i in instances.values()]
        if q_ids:
            q_result = await self.session.execute(
                select(Question).where(Question.id.in_(q_ids))
            )
            questions_map = {q.id: q for q in q_result.scalars().all()}
        else:
            questions_map = {}

        # Build per-competency aggregation
        competency_data: dict[str, dict] = {}  # comp -> {scored, max, count}
        total_scored = 0.0
        total_max = 0.0

        for resp in responses:
            inst = instances.get(resp.question_instance_id)
            if not inst:
                continue
            comp = inst.competency or "General"
            q = questions_map.get(inst.question_id)
            max_pts = float(q.max_points) if q else 10.0
            scored = float(resp.evaluation_score) if resp.evaluation_score is not None else 0.0

            total_scored += scored
            total_max += max_pts

            if comp not in competency_data:
                competency_data[comp] = {"scored": 0.0, "max": 0.0, "count": 0}
            competency_data[comp]["scored"] += scored
            competency_data[comp]["max"] += max_pts
            competency_data[comp]["count"] += 1

        session_obj.final_score = round(total_scored, 2)
        session_obj.max_score = round(total_max, 2)

        # competency_summary: list of {competency, scored, max, percentage}
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
        session_obj.competency_summary = summary
        await self.session.flush()

    # ------------------------------------------------------------------
    # Exchange counting helpers
    # ------------------------------------------------------------------

    # Conversational voice intents that should NOT count as answer exchanges
    _CONVERSATIONAL_INTENTS = ("clarification_request", "repeat_request", "topic_question")

    async def _count_total_exchanges(self, session_id: str) -> int:
        """Count total answer-type responses (exchanges) in the session.

        Conversational exchanges (clarification, repeat, topic) are excluded.
        """
        result = await self.session.execute(
            select(func.count())
            .select_from(StudentResponse)
            .where(
                StudentResponse.session_id == session_id,
                ~StudentResponse.voice_intent.in_(self._CONVERSATIONAL_INTENTS)
                | StudentResponse.voice_intent.is_(None),
            )
        )
        return result.scalar() or 0

    async def _count_exchanges_for_question(
        self, session_id: str, instance: AssessmentQuestionInstance
    ) -> int:
        """Count total exchanges for the same bank question chain."""
        root_id = instance.parent_instance_id or instance.id
        result = await self.session.execute(
            select(func.count())
            .select_from(AssessmentQuestionInstance)
            .where(
                AssessmentQuestionInstance.session_id == session_id,
                (AssessmentQuestionInstance.id == root_id)
                | (AssessmentQuestionInstance.parent_instance_id == root_id),
            )
        )
        return result.scalar() or 0

    async def _count_reasks_for_question(
        self, session_id: str, instance: AssessmentQuestionInstance
    ) -> int:
        """Count re-asks (depth=0 children) for the same bank question chain."""
        root_id = instance.parent_instance_id or instance.id
        result = await self.session.execute(
            select(func.count())
            .select_from(AssessmentQuestionInstance)
            .where(
                AssessmentQuestionInstance.session_id == session_id,
                AssessmentQuestionInstance.parent_instance_id == root_id,
                AssessmentQuestionInstance.follow_up_depth == 0,
            )
        )
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # Re-ask the current question (new instance to avoid duplicate check)
    # ------------------------------------------------------------------

    async def _reask_current_question(
        self,
        session_id: str,
        instance: AssessmentQuestionInstance,
        session_obj: AssessmentSession,
        resp: StudentResponse,
        question_text: str,
        now: datetime,
    ) -> SubmitResponseResponse:
        """Create a new question instance for the same question and return it."""
        root_id = instance.parent_instance_id or instance.id
        seq_result = await self.session.execute(
            select(func.count())
            .select_from(AssessmentQuestionInstance)
            .where(AssessmentQuestionInstance.session_id == session_id)
        )
        total_instances = seq_result.scalar() or 0

        reask_id = str(uuid4())
        reask_inst = AssessmentQuestionInstance(
            id=reask_id,
            session_id=session_id,
            question_id=instance.question_id,
            sequence_number=total_instances + 1,
            asked_at=now,
            competency=instance.competency,
            difficulty=instance.difficulty,
            follow_up_depth=0,
            parent_instance_id=root_id,
            follow_up_question_text=question_text,
        )
        self.session.add(reask_inst)
        await self.session.flush()

        next_ctx = QuestionWithContext(
            question_id=instance.question_id,
            question_instance_id=reask_id,
            question_text=question_text,
            competency=instance.competency,
            difficulty=instance.difficulty,
            code_context=session_obj.code_context or "",
            question_type="re_ask",
        )
        return SubmitResponseResponse(
            response_id=resp.id,
            next_question=next_ctx,
            is_complete=False,
            evaluation_score=resp.evaluation_score,
            feedback_text=resp.feedback_text,
            detected_misconceptions=resp.detected_misconceptions or [],
        )

    # ------------------------------------------------------------------
    # Advance to next bank question (or complete session)
    # ------------------------------------------------------------------

    async def _advance_to_next_question(
        self,
        session_id: str,
        session_obj: AssessmentSession,
        resp: StudentResponse,
        now: datetime,
    ) -> SubmitResponseResponse:
        """Move to the next bank question, or complete the session if done."""
        # Get already-asked question IDs (all instances, including follow-ups)
        asked_result = await self.session.execute(
            select(AssessmentQuestionInstance.question_id).where(
                AssessmentQuestionInstance.session_id == session_id
            )
        )
        asked_ids = [row[0] for row in asked_result.all()]

        # Find next approved question
        next_q_result = await self.session.execute(
            select(Question)
            .where(
                Question.assignment_id == session_obj.assignment_id,
                Question.status == "approved",
                Question.id.notin_(asked_ids),
            )
            .order_by(Question.difficulty.asc())
            .limit(1)
        )
        next_question = next_q_result.scalar_one_or_none()

        if next_question is None:
            session_obj.status = "completed"
            session_obj.completed_at = now
            await self._compute_session_scores(session_obj)
            await self.session.flush()
            return SubmitResponseResponse(
                response_id=resp.id,
                is_complete=True,
                message="No more questions available. Assessment completed.",
                evaluation_score=resp.evaluation_score,
                feedback_text=resp.feedback_text,
                detected_misconceptions=resp.detected_misconceptions,
                final_score=session_obj.final_score,
                max_score=session_obj.max_score,
                competency_summary=session_obj.competency_summary,
            )

        seq_result = await self.session.execute(
            select(func.count())
            .select_from(AssessmentQuestionInstance)
            .where(AssessmentQuestionInstance.session_id == session_id)
        )
        total_instances = seq_result.scalar() or 0

        new_instance_id = str(uuid4())
        new_instance = AssessmentQuestionInstance(
            id=new_instance_id,
            session_id=session_id,
            question_id=next_question.id,
            sequence_number=total_instances + 1,
            asked_at=now,
            competency=next_question.competency or "",
            difficulty=next_question.difficulty,
        )
        self.session.add(new_instance)
        await self.session.flush()

        next_ctx = QuestionWithContext(
            question_id=next_question.id,
            question_instance_id=new_instance_id,
            question_text=next_question.question_text,
            competency=next_question.competency or "",
            difficulty=next_question.difficulty,
            code_context=session_obj.code_context or "",
            question_type="new",
        )

        return SubmitResponseResponse(
            response_id=resp.id,
            next_question=next_ctx,
            is_complete=False,
            evaluation_score=resp.evaluation_score,
            feedback_text=resp.feedback_text,
            detected_misconceptions=resp.detected_misconceptions,
        )

    # ------------------------------------------------------------------
    # Trigger
    # ------------------------------------------------------------------

    async def trigger_assessment(
        self, req: TriggerAssessmentRequest
    ) -> TriggerAssessmentResponse:
        now = datetime.now(timezone.utc)
        session_id = str(uuid4())

        session_obj = AssessmentSession(
            id=session_id,
            student_id=req.student_id,
            assignment_id=req.assignment_id,
            status="in_progress",
            trigger_reason="task_completion",
            started_at=now,
            code_context=req.code_context,
        )
        self.session.add(session_obj)
        await self.session.flush()

        # Find first approved question for the assignment
        stmt = (
            select(Question)
            .where(
                Question.assignment_id == req.assignment_id,
                Question.status == "approved",
            )
            .order_by(Question.difficulty.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        question = result.scalar_one_or_none()

        if question is None:
            return TriggerAssessmentResponse(
                session_id=session_id, status="completed"
            )

        instance_id = str(uuid4())
        instance = AssessmentQuestionInstance(
            id=instance_id,
            session_id=session_id,
            question_id=question.id,
            sequence_number=1,
            asked_at=now,
            competency=question.competency or "",
            difficulty=question.difficulty,
        )
        self.session.add(instance)
        await self.session.flush()

        first_q = QuestionWithContext(
            question_id=question.id,
            question_instance_id=instance_id,
            question_text=question.question_text,
            competency=question.competency or "",
            difficulty=question.difficulty,
            code_context=req.code_context,
        )

        return TriggerAssessmentResponse(
            session_id=session_id,
            first_question=first_q,
            total_questions=1,
            status="in_progress",
        )

    # ------------------------------------------------------------------
    # Submit response
    # ------------------------------------------------------------------

    async def check_duplicate_response(self, question_instance_id: str) -> bool:
        """Return True if duplicate exists."""
        result = await self.session.execute(
            select(func.count())
            .select_from(StudentResponse)
            .where(StudentResponse.question_instance_id == question_instance_id)
        )
        return (result.scalar() or 0) > 0

    async def submit_response(
        self,
        session_id: str,
        question_instance_id: str,
        response_text: str,
        response_type: str,
        transcript_text: str | None = None,
        voice_intent: str | None = None,
    ) -> SubmitResponseResponse:
        now = datetime.now(timezone.utc)

        # Fetch session
        result = await self.session.execute(
            select(AssessmentSession).where(AssessmentSession.id == session_id)
        )
        session_obj = result.scalar_one_or_none()
        if session_obj is None:
            raise ValueError("session not found")
        if session_obj.status != "in_progress":
            raise ValueError("session is not in progress")

        # Fetch question instance
        result = await self.session.execute(
            select(AssessmentQuestionInstance).where(
                AssessmentQuestionInstance.id == question_instance_id,
                AssessmentQuestionInstance.session_id == session_id,
            )
        )
        instance = result.scalar_one_or_none()
        if instance is None:
            raise ValueError("invalid question instance")

        response_time = int((now - instance.asked_at).total_seconds())

        # Fetch question object (needed for all paths)
        question_result = await self.session.execute(
            select(Question).where(Question.id == instance.question_id)
        )
        question_obj = question_result.scalar_one_or_none()

        # Determine the question text that was actually asked
        asked_text = instance.follow_up_question_text or (
            question_obj.question_text if question_obj else ""
        )

        # Create response record (always, for audit trail)
        resp = StudentResponse(
            id=str(uuid4()),
            question_instance_id=question_instance_id,
            session_id=session_id,
            student_id=session_obj.student_id,
            response_text=response_text,
            response_type=response_type,
            transcript_text=transcript_text,
            submitted_at=now,
            response_time_seconds=response_time,
            voice_intent=voice_intent,
        )
        self.session.add(resp)
        await self.session.flush()

        # --- Global exchange cap ---
        total_exchanges = await self._count_total_exchanges(session_id)
        if total_exchanges >= MAX_TOTAL_EXCHANGES:
            resp.evaluation_score = 0.0
            resp.feedback_text = "Session exchange limit reached."
            resp.input_classification = "exchange_limit"
            session_obj.status = "completed"
            session_obj.completed_at = now
            await self._compute_session_scores(session_obj)
            await self.session.flush()
            return SubmitResponseResponse(
                response_id=resp.id,
                is_complete=True,
                message="Assessment completed — exchange limit reached.",
                evaluation_score=0.0,
                feedback_text="Session exchange limit reached.",
                final_score=session_obj.final_score,
                max_score=session_obj.max_score,
                competency_summary=session_obj.competency_summary,
            )

        # ══════════════════════════════════════════════════════════════
        # Build conversation history for context-aware LLM calls
        # ══════════════════════════════════════════════════════════════
        conv_ctx = await build_conversation_context(
            self.session, question_instance_id
        )
        conversation_history = conv_ctx.history_text

        # ══════════════════════════════════════════════════════════════
        # LAYER 1 — LLM Input Guard
        # ══════════════════════════════════════════════════════════════
        guard_result = await asyncio.to_thread(
            evaluation_service.classify_input,
            student_answer=response_text,
            question_text=asked_text,
            conversation_history=conversation_history,
        )
        resp.input_classification = guard_result.action
        await self.session.flush()

        # Helper: check if we've hit the per-question exchange cap
        question_exchanges = await self._count_exchanges_for_question(
            session_id, instance
        )
        at_exchange_cap = question_exchanges >= MAX_EXCHANGES_PER_QUESTION

        if guard_result.action == "warn_and_reask":
            resp.evaluation_score = 0.0
            resp.feedback_text = guard_result.warning or guard_result.reason
            resp.detected_misconceptions = []
            resp.score_justification = f"Input guard: {guard_result.reason}"
            await self.session.flush()

            # If exchange cap hit, advance; otherwise re-ask same question
            if at_exchange_cap:
                return await self._advance_to_next_question(
                    session_id, session_obj, resp, now
                )
            return await self._reask_current_question(
                session_id, instance, session_obj, resp, asked_text, now
            )

        if guard_result.action == "teach_and_skip":
            # Student has no content to evaluate — teach the concept and move on
            resp.evaluation_score = 0.0
            resp.detected_misconceptions = []
            resp.score_justification = f"Input guard: {guard_result.reason}"

            if question_obj and question_obj.expected_answer:
                teaching_hint = await asyncio.to_thread(
                    evaluation_service.generate_teaching_hint,
                    question_text=asked_text,
                    expected_answer=question_obj.expected_answer,
                    competency=instance.competency,
                    conversation_history=conversation_history,
                )
                resp.feedback_text = teaching_hint
            else:
                resp.feedback_text = "That's okay! Let's move on to the next question."

            await self.session.flush()
            return await self._advance_to_next_question(
                session_id, session_obj, resp, now
            )

        # ══════════════════════════════════════════════════════════════
        # LAYER 2 — LLM Quick Evaluation (real-time)
        # ══════════════════════════════════════════════════════════════
        eval_result = None
        if question_obj:
            eval_result = await asyncio.to_thread(
                evaluation_service.evaluate,
                question_text=asked_text,
                expected_answer=question_obj.expected_answer or "",
                student_answer=response_text,
                competency=instance.competency,
                difficulty=instance.difficulty,
                max_points=question_obj.max_points,
                code_context=session_obj.code_context or "",
            )
            resp.evaluation_score = eval_result.score
            resp.feedback_text = eval_result.feedback
            resp.detected_misconceptions = eval_result.misconceptions
            resp.score_justification = eval_result.justification
            await self.session.flush()

            # Populate response_competency_links
            for comp, comp_score in eval_result.competency_scores.items():
                link = ResponseCompetencyLink(
                    id=str(uuid4()),
                    response_id=resp.id,
                    competency=comp,
                    score=comp_score,
                    question_id=instance.question_id,
                )
                self.session.add(link)
            await self.session.flush()

            # ══════════════════════════════════════════════════════════
            # LAYER 3 — Background Deep Analysis (fire & forget)
            # ══════════════════════════════════════════════════════════
            asyncio.create_task(
                run_background_analysis(
                    response_id=resp.id,
                    question_text=asked_text,
                    expected_answer=question_obj.expected_answer or "",
                    student_answer=response_text,
                    competency=instance.competency,
                    difficulty=instance.difficulty,
                    score=eval_result.score,
                    max_points=question_obj.max_points,
                    feedback=eval_result.feedback,
                )
            )

        # --- Per-question exchange cap ---
        question_exchanges = await self._count_exchanges_for_question(
            session_id, instance
        )
        if question_exchanges >= MAX_EXCHANGES_PER_QUESTION:
            return await self._advance_to_next_question(
                session_id, session_obj, resp, now
            )

        # --- Routing based on LLM's next_action ---
        action = eval_result.next_action if eval_result else "advance"

        # --- Socratic follow-up check ---
        should_follow_up = (
            action == "follow_up"
            and question_obj is not None
            and instance.follow_up_depth < MAX_FOLLOW_UP_DEPTH
        )

        if should_follow_up:
            follow_up_text = await asyncio.to_thread(
                evaluation_service.generate_follow_up,
                question_text=asked_text,
                student_answer=response_text,
                feedback=eval_result.feedback,
                competency=instance.competency,
                misconceptions=eval_result.misconceptions,
                code_context=session_obj.code_context or "",
                conversation_history=conversation_history,
            )

            if follow_up_text:
                root_id = instance.parent_instance_id or instance.id
                seq_result = await self.session.execute(
                    select(func.count())
                    .select_from(AssessmentQuestionInstance)
                    .where(AssessmentQuestionInstance.session_id == session_id)
                )
                total_instances = seq_result.scalar() or 0

                fu_instance_id = str(uuid4())
                fu_instance = AssessmentQuestionInstance(
                    id=fu_instance_id,
                    session_id=session_id,
                    question_id=instance.question_id,
                    sequence_number=total_instances + 1,
                    asked_at=now,
                    competency=instance.competency,
                    difficulty=instance.difficulty,
                    follow_up_depth=instance.follow_up_depth + 1,
                    parent_instance_id=root_id,
                    follow_up_question_text=follow_up_text,
                )
                self.session.add(fu_instance)
                await self.session.flush()

                next_ctx = QuestionWithContext(
                    question_id=instance.question_id,
                    question_instance_id=fu_instance_id,
                    question_text=follow_up_text,
                    competency=instance.competency,
                    difficulty=instance.difficulty,
                    code_context=session_obj.code_context or "",
                    is_follow_up=True,
                    question_type="follow_up",
                )

                return SubmitResponseResponse(
                    response_id=resp.id,
                    next_question=next_ctx,
                    is_complete=False,
                    evaluation_score=resp.evaluation_score,
                    feedback_text=resp.feedback_text,
                    detected_misconceptions=resp.detected_misconceptions,
                )

        # --- Re-ask check ---
        if action == "re_ask" and question_obj:
            reask_count = await self._count_reasks_for_question(
                session_id, instance
            )
            if reask_count < MAX_REASK_COUNT:
                    root_id = instance.parent_instance_id or instance.id
                    seq_result = await self.session.execute(
                        select(func.count())
                        .select_from(AssessmentQuestionInstance)
                        .where(AssessmentQuestionInstance.session_id == session_id)
                    )
                    total_instances = seq_result.scalar() or 0

                    reask_instance_id = str(uuid4())
                    reask_instance = AssessmentQuestionInstance(
                        id=reask_instance_id,
                        session_id=session_id,
                        question_id=instance.question_id,
                        sequence_number=total_instances + 1,
                        asked_at=now,
                        competency=instance.competency,
                        difficulty=instance.difficulty,
                        follow_up_depth=0,
                        parent_instance_id=root_id,
                        follow_up_question_text=question_obj.question_text,
                    )
                    self.session.add(reask_instance)
                    await self.session.flush()

                    next_ctx = QuestionWithContext(
                        question_id=instance.question_id,
                        question_instance_id=reask_instance_id,
                        question_text=question_obj.question_text,
                        competency=instance.competency,
                        difficulty=instance.difficulty,
                        code_context=session_obj.code_context or "",
                        is_follow_up=True,
                        question_type="re_ask",
                    )

                    return SubmitResponseResponse(
                        response_id=resp.id,
                        next_question=next_ctx,
                        is_complete=False,
                        message="Let's try this question again. Take your time and give it your best shot.",
                        evaluation_score=resp.evaluation_score,
                        feedback_text=resp.feedback_text,
                        detected_misconceptions=resp.detected_misconceptions,
                    )

        # --- Normal flow: advance to next bank question ---
        return await self._advance_to_next_question(
            session_id, session_obj, resp, now
        )

    # ------------------------------------------------------------------
    # Get session
    # ------------------------------------------------------------------

    async def get_session(self, session_id: str) -> SessionDetailsOut | None:
        result = await self.session.execute(
            select(AssessmentSession).where(AssessmentSession.id == session_id)
        )
        session_obj = result.scalar_one_or_none()
        if session_obj is None:
            return None

        q_result = await self.session.execute(
            select(AssessmentQuestionInstance)
            .where(AssessmentQuestionInstance.session_id == session_id)
            .order_by(AssessmentQuestionInstance.sequence_number.asc())
        )
        questions = list(q_result.scalars().all())

        r_result = await self.session.execute(
            select(StudentResponse)
            .where(StudentResponse.session_id == session_id)
            .order_by(StudentResponse.submitted_at.asc())
        )
        responses = list(r_result.scalars().all())

        # Count only answer-type responses (not conversational exchanges)
        _conversational = {"clarification_request", "repeat_request", "topic_question"}
        answered = sum(
            1 for r in responses if r.voice_intent not in _conversational
        )

        return SessionDetailsOut(
            session=SessionOut.model_validate(session_obj),
            questions_asked=[QuestionInstanceOut.model_validate(q) for q in questions],
            responses=[StudentResponseOut.model_validate(r) for r in responses],
            total_questions=len(questions),
            answered_questions=answered,
        )

    # ------------------------------------------------------------------
    # Student sessions
    # ------------------------------------------------------------------

    async def get_student_sessions(
        self, student_id: str, status: str | None = None
    ) -> list[StudentSessionSummary]:
        stmt = select(AssessmentSession).where(
            AssessmentSession.student_id == student_id
        )
        if status:
            stmt = stmt.where(AssessmentSession.status == status)
        stmt = stmt.order_by(AssessmentSession.started_at.desc())

        result = await self.session.execute(stmt)
        sessions = list(result.scalars().all())

        summaries: list[StudentSessionSummary] = []
        for sess in sessions:
            q_count = await self.session.execute(
                select(func.count())
                .select_from(AssessmentQuestionInstance)
                .where(AssessmentQuestionInstance.session_id == sess.id)
            )
            r_count = await self.session.execute(
                select(func.count())
                .select_from(StudentResponse)
                .where(StudentResponse.session_id == sess.id)
            )
            summaries.append(
                StudentSessionSummary(
                    session_id=sess.id,
                    assignment_id=sess.assignment_id,
                    status=sess.status,
                    started_at=sess.started_at,
                    completed_at=sess.completed_at,
                    questions_asked=q_count.scalar() or 0,
                    responses_given=r_count.scalar() or 0,
                )
            )
        return summaries

    # ------------------------------------------------------------------
    # Abandon
    # ------------------------------------------------------------------

    async def abandon_session(self, session_id: str) -> None:
        result = await self.session.execute(
            select(AssessmentSession).where(AssessmentSession.id == session_id)
        )
        session_obj = result.scalar_one_or_none()
        if session_obj is None:
            raise ValueError("session not found")
        if session_obj.status != "in_progress":
            raise ValueError("can only abandon in-progress sessions")

        session_obj.status = "abandoned"
        session_obj.completed_at = datetime.now(timezone.utc)
        await self.session.flush()

    # ------------------------------------------------------------------
    # Instructor assessments
    # ------------------------------------------------------------------

    async def get_instructor_assessments(
        self,
        assignment_ids: list[str] | None = None,
        assignment_id: str | None = None,
        student_id: str | None = None,
        status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[InstructorAssessmentSummary]:
        stmt = select(AssessmentSession)

        if assignment_ids:
            stmt = stmt.where(AssessmentSession.assignment_id.in_(assignment_ids))
        if assignment_id:
            stmt = stmt.where(AssessmentSession.assignment_id == assignment_id)
        if student_id:
            stmt = stmt.where(AssessmentSession.student_id == student_id)
        if status:
            stmt = stmt.where(AssessmentSession.status == status)
        if start_date:
            stmt = stmt.where(AssessmentSession.started_at >= start_date)
        if end_date:
            stmt = stmt.where(AssessmentSession.started_at <= end_date)

        stmt = stmt.order_by(AssessmentSession.started_at.desc())
        result = await self.session.execute(stmt)
        sessions = list(result.scalars().all())

        summaries: list[InstructorAssessmentSummary] = []
        for sess in sessions:
            q_count = await self.session.execute(
                select(func.count())
                .select_from(AssessmentQuestionInstance)
                .where(AssessmentQuestionInstance.session_id == sess.id)
            )
            r_count = await self.session.execute(
                select(func.count())
                .select_from(StudentResponse)
                .where(StudentResponse.session_id == sess.id)
            )
            summaries.append(
                InstructorAssessmentSummary(
                    session_id=sess.id,
                    student_id=sess.student_id,
                    assignment_id=sess.assignment_id,
                    status=sess.status,
                    started_at=sess.started_at,
                    completed_at=sess.completed_at,
                    questions_asked=q_count.scalar() or 0,
                    responses_given=r_count.scalar() or 0,
                )
            )
        return summaries

    # ------------------------------------------------------------------
    # Transcript
    # ------------------------------------------------------------------

    async def get_assessment_transcript(
        self, session_id: str
    ) -> AssessmentTranscriptOut | None:
        result = await self.session.execute(
            select(AssessmentSession).where(AssessmentSession.id == session_id)
        )
        session_obj = result.scalar_one_or_none()
        if session_obj is None:
            return None

        inst_result = await self.session.execute(
            select(AssessmentQuestionInstance)
            .where(AssessmentQuestionInstance.session_id == session_id)
            .order_by(AssessmentQuestionInstance.sequence_number.asc())
        )
        instances = list(inst_result.scalars().all())
        inst_map = {inst.id: inst for inst in instances}

        # Fetch ALL responses (including conversational) ordered chronologically
        resp_result = await self.session.execute(
            select(StudentResponse)
            .where(StudentResponse.session_id == session_id)
            .order_by(StudentResponse.submitted_at.asc())
        )
        all_responses = list(resp_result.scalars().all())

        # Group responses by question_instance_id
        from collections import defaultdict
        responses_by_inst: dict[str, list[StudentResponse]] = defaultdict(list)
        for r in all_responses:
            responses_by_inst[r.question_instance_id].append(r)

        # Pre-fetch question texts for all instances
        question_cache: dict[str, str] = {}
        for inst in instances:
            if inst.question_id not in question_cache:
                q_result = await self.session.execute(
                    select(Question).where(Question.id == inst.question_id)
                )
                question = q_result.scalar_one_or_none()
                question_cache[inst.question_id] = (
                    question.question_text if question else ""
                )

        exchanges: list[ExchangeOut] = []
        for inst in instances:
            # Use follow-up text if present, otherwise bank question text
            display_text = inst.follow_up_question_text or question_cache.get(
                inst.question_id, ""
            )

            # Determine question_type: new / follow_up / re_ask
            if inst.parent_instance_id is None:
                q_type = "new"
            elif inst.follow_up_depth > 0:
                q_type = "follow_up"
            else:
                q_type = "re_ask"

            inst_responses = responses_by_inst.get(inst.id, [])

            if not inst_responses:
                # Question was asked but no response yet
                exchanges.append(ExchangeOut(
                    question_text=display_text,
                    competency=inst.competency,
                    difficulty=inst.difficulty,
                    asked_at=inst.asked_at,
                    is_follow_up=inst.parent_instance_id is not None,
                    question_type=q_type,
                ))
            else:
                # Emit one exchange per response (conversational + answer)
                for resp in inst_responses:
                    exchanges.append(ExchangeOut(
                        question_text=display_text,
                        competency=inst.competency,
                        difficulty=inst.difficulty,
                        student_answer=resp.response_text,
                        asked_at=inst.asked_at,
                        answered_at=resp.submitted_at,
                        response_time_seconds=resp.response_time_seconds,
                        evaluation_score=resp.evaluation_score,
                        feedback_text=resp.feedback_text,
                        detected_misconceptions=resp.detected_misconceptions,
                        score_justification=resp.score_justification,
                        voice_intent=resp.voice_intent,
                        is_follow_up=inst.parent_instance_id is not None,
                        question_type=q_type,
                    ))

        return AssessmentTranscriptOut(
            session_id=session_obj.id,
            student_id=session_obj.student_id,
            assignment_id=session_obj.assignment_id,
            status=session_obj.status,
            started_at=session_obj.started_at,
            completed_at=session_obj.completed_at,
            code_context=session_obj.code_context or "",
            exchanges=exchanges,
            final_score=session_obj.final_score,
            max_score=session_obj.max_score,
            competency_summary=session_obj.competency_summary,
        )
