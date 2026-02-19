from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_assessment_service
from app.services.assessment_service import AssessmentService

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/{student_id}/sessions")
async def get_student_sessions(
    student_id: str,
    status: Optional[str] = Query(None),
    svc: AssessmentService = Depends(get_assessment_service),
):
    sessions = await svc.get_student_sessions(student_id, status)
    return {"data": sessions, "count": len(sessions)}
