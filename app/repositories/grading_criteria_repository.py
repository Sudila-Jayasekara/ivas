"""
Grading Criteria Repository

Data access layer for GradingCriteria models. Provides CRUD operations for
grading criteria rows associated with an assignment.
"""

from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grading_criteria import GradingCriteria


class GradingCriteriaRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, criteria: GradingCriteria) -> GradingCriteria:
        self.session.add(criteria)
        await self.session.flush()
        await self.session.refresh(criteria)
        return criteria

    async def create_batch(self, criteria_list: list[GradingCriteria]) -> list[GradingCriteria]:
        self.session.add_all(criteria_list)
        await self.session.flush()
        return criteria_list

    async def find_by_id(self, criteria_id: str) -> Optional[GradingCriteria]:
        result = await self.session.execute(
            select(GradingCriteria).where(GradingCriteria.id == criteria_id)
        )
        return result.scalar_one_or_none()

    async def find_by_assignment_id(self, assignment_id: str) -> list[GradingCriteria]:
        result = await self.session.execute(
            select(GradingCriteria)
            .where(GradingCriteria.assignment_id == assignment_id)
            .order_by(GradingCriteria.difficulty_level)
        )
        return list(result.scalars().all())

    async def update(self, criteria: GradingCriteria) -> GradingCriteria:
        await self.session.merge(criteria)
        await self.session.flush()
        return criteria

    async def delete_by_assignment_id(self, assignment_id: str) -> int:
        """Delete all criteria for an assignment (e.g. before regenerating). Returns row count."""
        result = await self.session.execute(
            delete(GradingCriteria).where(GradingCriteria.assignment_id == assignment_id)
        )
        await self.session.flush()
        return result.rowcount
