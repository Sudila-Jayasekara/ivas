"""
Grading Criteria API Router

Handles HTTP requests for grading criteria management:
  API 1 — POST /assignments/{id}/grading-criteria/generate
  API 2 — GET  /assignments/{id}/grading-criteria
  API 3 — PATCH /grading-criteria/{id}
"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_grading_criteria_service
from app.schemas.grading_criteria import (
    GenerateGradingCriteriaRequest,
    GenerateGradingCriteriaResponse,
    GradingCriteriaOut,
    UpdateGradingCriteriaRequest,
)
from app.services.grading_criteria_service import GradingCriteriaService

router = APIRouter(tags=["grading-criteria"])


# --- API 1: Generate grading criteria from assignment text ---

@router.post(
    "/assignments/{assignment_id}/grading-criteria/generate",
    response_model=GenerateGradingCriteriaResponse,
    status_code=201,
)
async def generate_grading_criteria(
    assignment_id: str,
    req: GenerateGradingCriteriaRequest,
    svc: GradingCriteriaService = Depends(get_grading_criteria_service),
):
    try:
        result = await svc.generate(assignment_id, req.assignment_text)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=502, detail=str(e))

    return GenerateGradingCriteriaResponse(
        assignment_id=assignment_id,
        criteria_ids=result["criteria_ids"],
        total_generated=result["total_generated"],
    )


# --- API 2: List grading criteria for an assignment ---

@router.get("/assignments/{assignment_id}/grading-criteria")
async def get_grading_criteria(
    assignment_id: str,
    svc: GradingCriteriaService = Depends(get_grading_criteria_service),
):
    rows = await svc.get_by_assignment(assignment_id)
    data = [GradingCriteriaOut.model_validate(r) for r in rows]
    return {"data": data, "count": len(data)}


# --- API 3: Update a single grading criterion ---

@router.patch(
    "/grading-criteria/{criteria_id}",
    response_model=GradingCriteriaOut,
)
async def update_grading_criteria(
    criteria_id: str,
    req: UpdateGradingCriteriaRequest,
    svc: GradingCriteriaService = Depends(get_grading_criteria_service),
):
    updates = req.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    row = await svc.update(criteria_id, updates)
    if not row:
        raise HTTPException(status_code=404, detail="grading criteria not found")

    return GradingCriteriaOut.model_validate(row)
