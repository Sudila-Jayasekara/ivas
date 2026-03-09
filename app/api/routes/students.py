"""
Students API Router

Handles HTTP requests specifically for the Student portal. Endpoints here fetch
student-specific data, such as their past assessment sessions and performance,
by querying the AssessmentService.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_assessment_service
from app.schemas.mock import StudentOut
from app.services.assessment_service import AssessmentService

router = APIRouter(prefix="/students", tags=["students"])

# For "forget all about moc", we serve student profiles from here.
# In a real app, this would be a StudentService + DB table.
STUDENTS = {
    "4220e987-8f0b-4196-b691-6c33620d4238": StudentOut(
        id="4220e987-8f0b-4196-b691-6c33620d4238",
        name="Alice Johnson",
        course_id="course-001",
    ),
    "stud-002": StudentOut(id="stud-002", name="Bob Williams", course_id="course-001"),
}


@router.get("")
async def list_students():
    items = list(STUDENTS.values())
    return {"data": items, "count": len(items)}


@router.get("/{student_id}")
async def get_student(student_id: str):
    s = STUDENTS.get(student_id)
    if not s:
        return {"error": "student not found", "id": student_id}
    return s


@router.get("/{student_id}/sessions")
async def get_student_sessions(
    student_id: str,
    status: Optional[str] = Query(None),
    svc: AssessmentService = Depends(get_assessment_service),
):
    sessions = await svc.get_student_sessions(student_id, status)
    return {"data": sessions, "count": len(sessions)}
