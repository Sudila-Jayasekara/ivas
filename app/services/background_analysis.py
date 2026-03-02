"""
Background Analysis Service

Runs Layer 3 (deep analysis) as a fire-and-forget background task.
Uses its own DB session so the real-time response path is not blocked.

Usage in assessment_service:
    asyncio.create_task(
        run_background_analysis(response_id, question_text, ...)
    )
"""

import asyncio
import logging

from app.database import async_session_factory
from app.models.assessment import StudentResponse
from app.services.evaluation_service import evaluation_service

from sqlalchemy import select

logger = logging.getLogger(__name__)


async def run_background_analysis(
    response_id: str,
    question_text: str,
    expected_answer: str,
    student_answer: str,
    competency: str,
    difficulty: int,
    score: float,
    max_points: int,
    feedback: str,
) -> None:
    """
    Fire-and-forget background task: runs Layer 3 deep analysis via LLM
    and writes results (justification, misconceptions, understanding level)
    back to the StudentResponse record in DB.

    Uses its own async DB session — safe to run independently of the request.
    """
    try:
        # Run LLM deep analysis in a thread (LLM calls are synchronous)
        deep_result = await asyncio.to_thread(
            evaluation_service.deep_analyze,
            question_text=question_text,
            expected_answer=expected_answer,
            student_answer=student_answer,
            competency=competency,
            difficulty=difficulty,
            score=score,
            max_points=max_points,
            feedback=feedback,
        )

        # Write results to DB using a fresh session
        if async_session_factory is None:
            logger.error("Background analysis: DB not initialised, skipping write for response %s", response_id)
            return

        async with async_session_factory() as db_session:
            async with db_session.begin():
                result = await db_session.execute(
                    select(StudentResponse).where(StudentResponse.id == response_id)
                )
                resp = result.scalar_one_or_none()
                if resp is None:
                    logger.error("Background analysis: response %s not found", response_id)
                    return

                # Update with deep analysis results
                resp.score_justification = deep_result.justification

                # Merge misconceptions: keep any from Layer 2, add new ones from Layer 3
                existing = resp.detected_misconceptions or []
                new_misconceptions = deep_result.misconceptions or []
                merged = list(dict.fromkeys(existing + new_misconceptions))  # deduplicate, preserve order
                resp.detected_misconceptions = merged

                resp.deep_analysis = {
                    "understanding_level": deep_result.understanding_level,
                    "suggestions": deep_result.suggestions,
                    "detailed_justification": deep_result.justification,
                    "detailed_misconceptions": new_misconceptions,
                }

        logger.info(
            "Background analysis complete for response %s: understanding=%s, misconceptions=%d",
            response_id, deep_result.understanding_level, len(merged),
        )

    except Exception as e:
        logger.error(
            "Background analysis failed for response %s: %s",
            response_id, e, exc_info=True,
        )
