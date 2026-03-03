"""
Conversation Context Builder

Builds a compact conversation history string from the DB for injection into
LLM prompts.  Every LLM call should receive conversation history so it can
adapt its responses based on what has already happened.

Usage:
    ctx = await build_conversation_context(session, question_instance_id)
    # ctx.history_text  -> formatted string for prompt injection
    # ctx.clarification_count -> how many times the student asked for help
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import (
    AssessmentQuestionInstance,
    StudentResponse,
)
from app.models.question import Question

logger = logging.getLogger(__name__)

# After this many clarification requests on the same question, escalate
MAX_CLARIFICATIONS_BEFORE_ESCALATION = 3


@dataclass
class ConversationContext:
    """Compact representation of the conversation so far for this question."""

    history_text: str = ""
    clarification_count: int = 0
    exchange_count: int = 0
    should_escalate: bool = False


async def build_conversation_context(
    db: AsyncSession,
    question_instance_id: str,
    *,
    include_parent_chain: bool = True,
) -> ConversationContext:
    """Build conversation history for a specific question instance.

    Parameters
    ----------
    db : AsyncSession
        Active database session.
    question_instance_id : str
        The current question instance to build context for.
    include_parent_chain : bool
        If True, include history from parent question instances
        (follow-up chains) for richer context.

    Returns
    -------
    ConversationContext
        Contains the formatted history text, clarification count,
        and whether escalation is recommended.
    """
    try:
        # Collect all instance IDs in the chain (current + parents)
        instance_ids = [question_instance_id]
        if include_parent_chain:
            instance_ids = await _get_instance_chain(db, question_instance_id)

        # Fetch the question text for context
        question_text = await _get_question_text(db, question_instance_id)

        # Fetch all responses for these instances, ordered chronologically
        result = await db.execute(
            select(StudentResponse)
            .where(StudentResponse.question_instance_id.in_(instance_ids))
            .order_by(StudentResponse.submitted_at.asc())
        )
        responses = list(result.scalars().all())

        if not responses:
            return ConversationContext()

        # Build the history
        lines: list[str] = []
        clarification_count = 0

        if question_text:
            lines.append(f"[Instructor asked]: \"{question_text}\"")

        for resp in responses:
            # Student's message
            lines.append(f"[Student said]: \"{resp.response_text}\"")

            # What the system did
            intent = resp.voice_intent or ""
            classification = resp.input_classification or ""

            if intent in ("clarification_request", "topic_question"):
                clarification_count += 1
                if resp.feedback_text:
                    lines.append(f"[Instructor explained]: \"{resp.feedback_text}\"")
            elif intent == "repeat_request":
                lines.append("[System]: Repeated the question")
            elif classification == "teach_and_skip":
                if resp.feedback_text:
                    lines.append(f"[Instructor taught]: \"{resp.feedback_text}\"")
            elif classification == "warn_and_reask":
                if resp.feedback_text:
                    lines.append(f"[Instructor warned]: \"{resp.feedback_text}\"")
            elif resp.evaluation_score is not None:
                lines.append(
                    f"[System scored]: {resp.evaluation_score}/10"
                )
                if resp.feedback_text:
                    lines.append(f"[Instructor feedback]: \"{resp.feedback_text}\"")

        should_escalate = clarification_count >= MAX_CLARIFICATIONS_BEFORE_ESCALATION

        history_text = ""
        if lines:
            history_text = (
                "CONVERSATION SO FAR (this question):\n"
                + "\n".join(lines)
            )

        return ConversationContext(
            history_text=history_text,
            clarification_count=clarification_count,
            exchange_count=len(responses),
            should_escalate=should_escalate,
        )

    except Exception as e:
        logger.error("Failed to build conversation context: %s", e, exc_info=True)
        return ConversationContext()


async def _get_instance_chain(
    db: AsyncSession, question_instance_id: str
) -> list[str]:
    """Walk up the parent chain to get all related instance IDs."""
    ids: list[str] = []
    current_id = question_instance_id

    for _ in range(10):  # Safety limit
        ids.append(current_id)
        result = await db.execute(
            select(AssessmentQuestionInstance.parent_instance_id).where(
                AssessmentQuestionInstance.id == current_id
            )
        )
        row = result.first()
        if not row or not row[0]:
            break
        current_id = row[0]

    return ids


async def _get_question_text(
    db: AsyncSession, question_instance_id: str
) -> str:
    """Get the question text for an instance (follow-up text or bank text)."""
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
    q = q_result.scalar_one_or_none()
    return q.question_text if q else ""
