"""
Rubric Repository

Data access layer for Rubric models. Handles operations for creating and updating
grading rubrics associated with questions. Called by the QuestionService when
new questions are generated along with their rubrics.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Rubric


class RubricRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, rubric: Rubric) -> Rubric:
        self.session.add(rubric)
        await self.session.flush()
        await self.session.refresh(rubric)
        return rubric

    async def create_batch(self, rubrics: list[Rubric]) -> list[Rubric]:
        self.session.add_all(rubrics)
        await self.session.flush()
        return rubrics

    async def find_by_question_id(self, question_id: str) -> Optional[Rubric]:
        result = await self.session.execute(
            select(Rubric).where(Rubric.question_id == question_id)
        )
        return result.scalar_one_or_none()

    async def update(self, rubric: Rubric) -> Rubric:
        await self.session.merge(rubric)
        await self.session.flush()
        return rubric
