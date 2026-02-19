import json
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import (
    Question,
    QuestionEditHistory,
    QuestionSource,
    QuestionStatus,
    QuestionType,
    Rubric,
)
from app.repositories.edit_history_repository import EditHistoryRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.rubric_repository import RubricRepository
from app.schemas.question import GenerateQuestionsRequest, UpdateQuestionRequest
from app.services.question_generator import question_generator

logger = logging.getLogger(__name__)


class QuestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.question_repo = QuestionRepository(session)
        self.rubric_repo = RubricRepository(session)
        self.edit_history_repo = EditHistoryRepository(session)

    # ------------------------------------------------------------------
    # Generate
    # ------------------------------------------------------------------

    async def generate_questions(
        self, assignment_id: str, req: GenerateQuestionsRequest
    ) -> dict:
        logger.info(
            "Starting question generation for assignment=%s competencies=%s",
            assignment_id,
            req.competencies,
        )

        # Fetch existing questions for this assignment so the LLM can avoid duplicates
        existing_db_questions = await self.question_repo.find_by_assignment_id(assignment_id)
        existing_for_dedup = [
            {
                "competency": q.competency,
                "difficulty": q.difficulty,
                "question_text": q.question_text,
            }
            for q in existing_db_questions
            if q.status != "archived"
        ]
        logger.info(
            "Found %d existing questions for assignment=%s (used for deduplication)",
            len(existing_for_dedup),
            assignment_id,
        )

        ai_questions = question_generator.generate_questions(
            title=req.title,
            competencies=req.competencies,
            learning_objectives=req.learning_objectives,
            difficulty_min=req.difficulty_min,
            difficulty_max=req.difficulty_max,
            num_questions_per_competency=req.num_questions_per_competency,
            programming_language=req.programming_language,
            existing_questions=existing_for_dedup if existing_for_dedup else None,
        )

        question_ids: list[str] = []
        for q in ai_questions:
            # Final safety check: ensure difficulty is within requested range
            clamped_difficulty = max(
                req.difficulty_min, min(req.difficulty_max, q.difficulty)
            )
            if clamped_difficulty != q.difficulty:
                logger.warning(
                    "Question difficulty %d outside range %d-%d, clamped to %d",
                    q.difficulty, req.difficulty_min, req.difficulty_max, clamped_difficulty,
                )

            question = Question(
                assignment_id=assignment_id,
                question_text=q.question_text,
                competency=q.competency,
                difficulty=clamped_difficulty,
                source=QuestionSource.ai_generated,
                status=QuestionStatus.draft,
                question_type=QuestionType.required,
            )
            try:
                question = await self.question_repo.create(question)
            except Exception as e:
                logger.error("Failed to create question: %s", e)
                continue

            grading_criteria = q.rubric.grading_criteria
            try:
                grading_criteria_parsed = json.loads(grading_criteria)
            except (json.JSONDecodeError, TypeError):
                grading_criteria_parsed = grading_criteria

            rubric = Rubric(
                question_id=question.id,
                expected_key_concepts=q.expected_key_concepts,
                grading_criteria=grading_criteria_parsed,
                max_points=q.rubric.max_points,
            )
            try:
                await self.rubric_repo.create(rubric)
            except Exception as e:
                logger.error("Failed to create rubric for question %s: %s", question.id, e)

            question_ids.append(question.id)

        logger.info(
            "Questions stored: assignment=%s total=%d", assignment_id, len(question_ids)
        )
        return {"question_ids": question_ids, "total_generated": len(question_ids)}

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_questions_by_assignment(
        self,
        assignment_id: str,
        status: str | None = None,
        competency: str | None = None,
        question_type: str | None = None,
    ) -> list[Question]:
        return await self.question_repo.find_by_assignment_id_with_filters(
            assignment_id, status, competency, question_type
        )

    async def get_question(self, question_id: str) -> Question | None:
        return await self.question_repo.find_by_id(question_id)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_question(
        self, question_id: str, req: UpdateQuestionRequest
    ) -> Question | None:
        question = await self.question_repo.find_by_id(question_id)
        if not question:
            return None

        changes: dict = {}

        if req.question_text is not None and req.question_text != question.question_text:
            changes["question_text"] = {
                "old": question.question_text,
                "new": req.question_text,
            }
            question.question_text = req.question_text

        if req.competency is not None and req.competency != question.competency:
            changes["competency"] = {
                "old": question.competency,
                "new": req.competency,
            }
            question.competency = req.competency

        if req.difficulty is not None and req.difficulty != question.difficulty:
            changes["difficulty"] = {
                "old": question.difficulty,
                "new": req.difficulty,
            }
            question.difficulty = req.difficulty

        question.last_modified_by = req.modified_by
        question = await self.question_repo.update(question)

        if changes:
            history = QuestionEditHistory(
                question_id=question.id,
                edited_by=req.modified_by,
                changes_json=changes,
                timestamp=datetime.now(timezone.utc),
            )
            try:
                await self.edit_history_repo.create(history)
            except Exception as e:
                logger.error("Failed to log edit history: %s", e)

        return question

    # ------------------------------------------------------------------
    # Approve / Type / Archive / History
    # ------------------------------------------------------------------

    async def approve_question(self, question_id: str, approved_by: str) -> bool:
        question = await self.question_repo.find_by_id(question_id)
        if not question:
            return False
        question.status = QuestionStatus.approved
        question.last_modified_by = approved_by
        await self.question_repo.update(question)
        return True

    async def set_question_type(self, question_id: str, q_type: str) -> bool:
        await self.question_repo.update_type(question_id, QuestionType(q_type))
        return True

    async def archive_question(self, question_id: str) -> bool:
        await self.question_repo.soft_delete(question_id)
        return True

    async def get_question_history(
        self, question_id: str
    ) -> list[QuestionEditHistory]:
        return await self.edit_history_repo.find_by_question_id(question_id)
