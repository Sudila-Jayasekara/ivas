"""
Edit History Repository

Data access layer for QuestionEditHistory models. Functions in this repository
are called by the Services layer to record changes made to questions over time
by instructors, and to retrieve the history of a specific question.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import QuestionEditHistory


class EditHistoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, history: QuestionEditHistory) -> QuestionEditHistory:
        self.session.add(history)
        await self.session.flush()
        await self.session.refresh(history)
        return history

    async def find_by_question_id(
        self, question_id: str
    ) -> list[QuestionEditHistory]:
        result = await self.session.execute(
            select(QuestionEditHistory)
            .where(QuestionEditHistory.question_id == question_id)
            .order_by(QuestionEditHistory.timestamp.desc())
        )
        return list(result.scalars().all())
