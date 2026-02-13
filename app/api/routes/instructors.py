from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_assessment_service
from app.services.assessment_service import AssessmentService

router = APIRouter(prefix="/instructors", tags=["instructors"])


@router.get("/{instructor_id}/assessments")
async def get_instructor_assessments(
    instructor_id: str,
    assignment_ids: Optional[str] = Query(None),
    assignment_id: Optional[str] = Query(None),
    student_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    svc: AssessmentService = Depends(get_assessment_service),
):
    aid_list: list[str] | None = None
    if assignment_ids:
        aid_list = [a.strip() for a in assignment_ids.split(",")]

    sd: datetime | None = None
    ed: datetime | None = None
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
        except ValueError:
            pass
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
        except ValueError:
            pass

    assessments = await svc.get_instructor_assessments(
        assignment_ids=aid_list,
        assignment_id=assignment_id,
        student_id=student_id,
        status=status,
        start_date=sd,
        end_date=ed,
    )
    return {"data": assessments, "count": len(assessments)}
