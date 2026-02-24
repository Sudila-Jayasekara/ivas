"""
Question Service

Business logic for question generation (API 4) and retrieval (API 5).
Questions are generated from saved GradingCriteria rows via the QuestionGenerator (LLM).
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question
from app.repositories.grading_criteria_repository import GradingCriteriaRepository
from app.repositories.question_repository import QuestionRepository
from app.services.question_generator import question_generator

logger = logging.getLogger(__name__)


class QuestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.question_repo = QuestionRepository(session)
        self.criteria_repo = GradingCriteriaRepository(session)

    # ------------------------------------------------------------------
    # Generate (API 4)
    # ------------------------------------------------------------------

    async def generate_questions(self, assignment_id: str) -> dict:
        logger.info("Starting question generation for assignment=%s", assignment_id)

        # Fetch saved grading criteria
        criteria_rows = await self.criteria_repo.find_by_assignment_id(assignment_id)
        if not criteria_rows:
            raise ValueError(
                f"No grading criteria found for assignment {assignment_id}. "
                "Generate grading criteria first (POST /assignments/{id}/grading-criteria/generate)."
            )

        # Convert ORM rows to dicts for the generator
        criteria_dicts = [
            {
                "competency": c.competency,
                "difficulty_level": c.difficulty_level,
                "level_label": c.level_label,
                "level_description": c.level_description,
                "marking_criteria": c.marking_criteria,
                "programming_language": c.programming_language,
                "learning_objectives": c.learning_objectives,
            }
            for c in criteria_rows
        ]

        ai_questions = await asyncio.to_thread(
            question_generator.generate_questions,
            criteria_rows=criteria_dicts,
        )

        question_ids: list[str] = []
        for q in ai_questions:
            question = Question(
                assignment_id=assignment_id,
                question_text=q.question_text,
                competency=q.competency,
                difficulty=q.difficulty,
                expected_answer=q.expected_answer,
                max_points=q.max_points,
                status="draft",
            )
            try:
                question = await self.question_repo.create(question)
                question_ids.append(question.id)
            except Exception as e:
                logger.error("Failed to create question: %s", e)
                continue

        logger.info(
            "Questions stored: assignment=%s total=%d", assignment_id, len(question_ids)
        )
        return {"question_ids": question_ids, "total_generated": len(question_ids)}

    # ------------------------------------------------------------------
    # Read (API 5)
    # ------------------------------------------------------------------

    async def get_questions_by_assignment(
        self,
        assignment_id: str,
        status: str | None = None,
        competency: str | None = None,
    ) -> list[Question]:
        return await self.question_repo.find_by_assignment_id_with_filters(
            assignment_id, status=status, competency=competency
        )

    async def get_question(self, question_id: str) -> Question | None:
        return await self.question_repo.find_by_id(question_id)
