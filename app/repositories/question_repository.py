"""
Question Repository

Data access layer for Question models. Provides CRUD operations for questions,
such as creating new generated/manual questions, retrieving questions by assignment,
updating question details, and archiving (soft-delete). These methods interact
directly with the database session and return SQLAlchemy ORM objects to the Services.
"""

from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question, QuestionStatus, QuestionType


class QuestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, question: Question) -> Question:
        self.session.add(question)
        await self.session.flush()
        await self.session.refresh(question)
        return question

    async def create_batch(self, questions: list[Question]) -> list[Question]:
        self.session.add_all(questions)
        await self.session.flush()
        return questions

    async def find_by_id(self, question_id: str) -> Optional[Question]:
        result = await self.session.execute(
            select(Question).where(Question.id == question_id)
        )
        return result.scalar_one_or_none()

    async def find_by_assignment_id(self, assignment_id: str) -> list[Question]:
        result = await self.session.execute(
            select(Question).where(Question.assignment_id == assignment_id)
        )
        return list(result.scalars().all())

    async def find_by_assignment_id_with_filters(
        self,
        assignment_id: str,
        status: Optional[str] = None,
        competency: Optional[str] = None,
        question_type: Optional[str] = None,
    ) -> list[Question]:
        stmt = select(Question).where(Question.assignment_id == assignment_id)

        if status:
            stmt = stmt.where(Question.status == status)
        if competency:
            stmt = stmt.where(Question.competency == competency)
        if question_type:
            stmt = stmt.where(Question.question_type == question_type)

        stmt = stmt.order_by(Question.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, question: Question) -> Question:
        await self.session.merge(question)
        await self.session.flush()
        return question

    async def update_status(self, question_id: str, status: QuestionStatus) -> None:
        await self.session.execute(
            update(Question)
            .where(Question.id == question_id)
            .values(status=status)
        )
        await self.session.flush()

    async def update_type(self, question_id: str, q_type: QuestionType) -> None:
        await self.session.execute(
            update(Question)
            .where(Question.id == question_id)
            .values(question_type=q_type)
        )
        await self.session.flush()

    async def soft_delete(self, question_id: str) -> None:
        await self.update_status(question_id, QuestionStatus.archived)
