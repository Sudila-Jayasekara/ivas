from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_db
from app.services.assignment_service import AssignmentService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/assignments", tags=["assignments"])

async def get_assignment_service(session: AsyncSession = Depends(get_db)) -> AssignmentService:
    return AssignmentService(session)

@router.get("")
async def list_assignments(svc: AssignmentService = Depends(get_assignment_service)):
    assignments = await svc.list_assignments()
    return {"data": assignments, "count": len(assignments)}

@router.get("/{assignment_id}")
async def get_assignment(assignment_id: str, svc: AssignmentService = Depends(get_assignment_service)):
    a = await svc.get_assignment(assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return a
