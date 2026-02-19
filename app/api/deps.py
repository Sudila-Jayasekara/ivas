from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services.assessment_service import AssessmentService
from app.services.question_service import QuestionService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


async def get_question_service(
    session: AsyncSession = Depends(get_db),
) -> QuestionService:
    return QuestionService(session)


async def get_assessment_service(
    session: AsyncSession = Depends(get_db),
) -> AssessmentService:
    return AssessmentService(session)
