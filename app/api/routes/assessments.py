from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_assessment_service
from app.schemas.assessment import (
    SubmitResponseRequest,
    TriggerAssessmentRequest,
)
from app.services.assessment_service import AssessmentService

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.post("/trigger")
async def trigger_assessment(
    req: TriggerAssessmentRequest,
    svc: AssessmentService = Depends(get_assessment_service),
):
    resp = await svc.trigger_assessment(req)
    return resp


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    svc: AssessmentService = Depends(get_assessment_service),
):
    details = await svc.get_session(session_id)
    if details is None:
        raise HTTPException(status_code=404, detail="session not found")
    return details


@router.post("/sessions/{session_id}/respond")
async def submit_response(
    session_id: str,
    req: SubmitResponseRequest,
    svc: AssessmentService = Depends(get_assessment_service),
):
    # Check duplicate
    is_dup = await svc.check_duplicate_response(req.question_instance_id)
    if is_dup:
        raise HTTPException(
            status_code=409,
            detail="response already submitted for this question",
        )

    try:
        resp = await svc.submit_response(
            session_id=session_id,
            question_instance_id=req.question_instance_id,
            response_text=req.response_text,
            response_type=req.response_type,
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        if "not in progress" in msg:
            raise HTTPException(status_code=400, detail=msg)
        raise HTTPException(status_code=500, detail=msg)

    return resp


@router.get("/sessions/{session_id}/transcript")
async def get_assessment_transcript(
    session_id: str,
    svc: AssessmentService = Depends(get_assessment_service),
):
    transcript = await svc.get_assessment_transcript(session_id)
    if transcript is None:
        raise HTTPException(status_code=404, detail="session not found")
    return transcript


@router.put("/sessions/{session_id}/abandon")
async def abandon_session(
    session_id: str,
    svc: AssessmentService = Depends(get_assessment_service),
):
    try:
        await svc.abandon_session(session_id)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        if "can only abandon" in msg:
            raise HTTPException(status_code=400, detail=msg)
        raise HTTPException(status_code=500, detail=msg)

    return {"message": "Session abandoned successfully"}
