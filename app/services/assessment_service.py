"""
Assessment Service

Core business logic for conducting an assessment session. It orchestrates
the flow between a student requesting an assessment to the LLM generating
questions and evaluating answers. This service:
1. Triggers an assessment (creates a session and fetches the first question).
2. Submits responses (records student answers, calculates time taken, gets the next question).
3. Evaluates when the assessment is complete.
4. Returns session transcripts for instructors.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
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

logger = logging.getLogger(__name__)


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
        )
        self.session.add(resp)
        await self.session.flush()

        # --- LLM Evaluation ---
        question_result = await self.session.execute(
            select(Question).where(Question.id == instance.question_id)
        )
        question_obj = question_result.scalar_one_or_none()

        # Determine the question text that was actually asked
        asked_text = instance.follow_up_question_text or (
            question_obj.question_text if question_obj else ""
        )

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

        # Count only root (bank) questions toward the session limit
        count_result = await self.session.execute(
            select(func.count())
            .select_from(AssessmentQuestionInstance)
            .where(
                AssessmentQuestionInstance.session_id == session_id,
                AssessmentQuestionInstance.parent_instance_id.is_(None),
            )
        )
        asked_count = count_result.scalar() or 0

        # --- Socratic follow-up check ---
        MAX_FOLLOW_UP_DEPTH = 2

        should_follow_up = (
            eval_result is not None
            and question_obj is not None
            and instance.follow_up_depth < MAX_FOLLOW_UP_DEPTH
            and evaluation_service.is_partial_understanding(
                eval_result.score, float(question_obj.max_points)
            )
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
            )

            if follow_up_text:
                # Determine root instance for the chain
                root_id = instance.parent_instance_id or instance.id

                # Get current total sequence number
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
                    question_id=instance.question_id,  # same bank question
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
                )

                return SubmitResponseResponse(
                    response_id=resp.id,
                    next_question=next_ctx,
                    is_complete=False,
                    evaluation_score=resp.evaluation_score,
                    feedback_text=resp.feedback_text,
                    detected_misconceptions=resp.detected_misconceptions,
                )

        # --- Normal flow: check completion or pick next bank question ---

        if asked_count >= 3:
            session_obj.status = "completed"
            session_obj.completed_at = now
            await self._compute_session_scores(session_obj)
            await self.session.flush()
            return SubmitResponseResponse(
                response_id=resp.id,
                is_complete=True,
                message="Assessment completed",
                evaluation_score=resp.evaluation_score,
                feedback_text=resp.feedback_text,
                detected_misconceptions=resp.detected_misconceptions,
                final_score=session_obj.final_score,
                max_score=session_obj.max_score,
                competency_summary=session_obj.competency_summary,
            )

        # Get already asked question IDs
        asked_result = await self.session.execute(
            select(AssessmentQuestionInstance.question_id).where(
                AssessmentQuestionInstance.session_id == session_id
            )
        )
        asked_ids = [row[0] for row in asked_result.all()]

        # Find next question
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

        new_instance_id = str(uuid4())
        new_instance = AssessmentQuestionInstance(
            id=new_instance_id,
            session_id=session_id,
            question_id=next_question.id,
            sequence_number=asked_count + 1,
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

        return SessionDetailsOut(
            session=SessionOut.model_validate(session_obj),
            questions_asked=[QuestionInstanceOut.model_validate(q) for q in questions],
            responses=[StudentResponseOut.model_validate(r) for r in responses],
            total_questions=len(questions),
            answered_questions=len(responses),
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

        resp_result = await self.session.execute(
            select(StudentResponse).where(StudentResponse.session_id == session_id)
        )
        responses = list(resp_result.scalars().all())
        response_map = {r.question_instance_id: r for r in responses}

        exchanges: list[ExchangeOut] = []
        for inst in instances:
            q_result = await self.session.execute(
                select(Question).where(Question.id == inst.question_id)
            )
            question = q_result.scalar_one_or_none()

            # Use follow-up text if present, otherwise bank question text
            display_text = inst.follow_up_question_text or (
                question.question_text if question else ""
            )

            exchange = ExchangeOut(
                question_text=display_text,
                competency=inst.competency,
                difficulty=inst.difficulty,
                asked_at=inst.asked_at,
                is_follow_up=inst.parent_instance_id is not None,
            )

            resp = response_map.get(inst.id)
            if resp:
                exchange.student_answer = resp.response_text
                exchange.answered_at = resp.submitted_at
                exchange.response_time_seconds = resp.response_time_seconds
                exchange.evaluation_score = resp.evaluation_score
                exchange.feedback_text = resp.feedback_text
                exchange.detected_misconceptions = resp.detected_misconceptions

            exchanges.append(exchange)

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
