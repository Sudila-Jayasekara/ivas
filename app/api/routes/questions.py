from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.api.deps import get_question_service
from app.schemas.question import (
    ApproveQuestionRequest,
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
    QuestionOut,
    QuestionWithRubricOut,
    SetQuestionTypeRequest,
    UpdateQuestionRequest,
)
from app.services.question_service import QuestionService

router = APIRouter(tags=["questions"])


# --- Generate ---

@router.post(
    "/assignments/{assignment_id}/generate-questions",
    response_model=GenerateQuestionsResponse,
    status_code=201,
)
async def generate_questions(
    assignment_id: str,
    req: GenerateQuestionsRequest,
    svc: QuestionService = Depends(get_question_service),
):
    result = await svc.generate_questions(assignment_id, req)
    return GenerateQuestionsResponse(
        assignment_id=assignment_id,
        question_ids=result["question_ids"],
        total_generated=result["total_generated"],
    )


# --- List by assignment ---

@router.get("/assignments/{assignment_id}/questions")
async def get_questions(
    assignment_id: str,
    status: Optional[str] = Query(None),
    competency: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    detailed: bool = Query(False, description="Include rubric data"),
    svc: QuestionService = Depends(get_question_service),
):
    questions = await svc.get_questions_by_assignment(
        assignment_id, status, competency, type
    )
    if detailed:
        data = [QuestionWithRubricOut.model_validate(q) for q in questions]
    else:
        data = [QuestionOut.model_validate(q) for q in questions]
    return {"data": data, "count": len(data)}


# --- List by assignment with rubrics ---

@router.get("/assignments/{assignment_id}/questions/detailed")
async def get_questions_with_rubrics(
    assignment_id: str,
    status: Optional[str] = Query(None),
    competency: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    svc: QuestionService = Depends(get_question_service),
):
    questions = await svc.get_questions_by_assignment(
        assignment_id, status, competency, type
    )
    data = [QuestionWithRubricOut.model_validate(q) for q in questions]
    return {"data": data, "count": len(data)}


# --- Single question ---

@router.get("/questions/{question_id}", response_model=QuestionOut)
async def get_question(
    question_id: str,
    svc: QuestionService = Depends(get_question_service),
):
    q = await svc.get_question(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="question not found")
    return QuestionOut.model_validate(q)


# --- Single question with rubric ---

@router.get("/questions/{question_id}/detailed", response_model=QuestionWithRubricOut)
async def get_question_with_rubric(
    question_id: str,
    svc: QuestionService = Depends(get_question_service),
):
    q = await svc.get_question(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="question not found")
    return QuestionWithRubricOut.model_validate(q)


# --- Update ---

@router.patch("/questions/{question_id}", response_model=QuestionOut)
async def update_question(
    question_id: str,
    req: UpdateQuestionRequest,
    svc: QuestionService = Depends(get_question_service),
):
    q = await svc.update_question(question_id, req)
    if not q:
        raise HTTPException(status_code=404, detail="question not found")
    return QuestionOut.model_validate(q)


# --- Archive ---

@router.delete("/questions/{question_id}")
async def delete_question(
    question_id: str,
    svc: QuestionService = Depends(get_question_service),
):
    await svc.archive_question(question_id)
    return {"message": "question archived"}


# --- Approve ---

@router.put("/questions/{question_id}/approve")
async def approve_question(
    question_id: str,
    req: ApproveQuestionRequest,
    svc: QuestionService = Depends(get_question_service),
):
    ok = await svc.approve_question(question_id, req.approved_by)
    if not ok:
        raise HTTPException(status_code=404, detail="question not found")
    return {"message": "question approved"}


# --- Set type ---

@router.put("/questions/{question_id}/type")
async def set_question_type(
    question_id: str,
    req: SetQuestionTypeRequest,
    svc: QuestionService = Depends(get_question_service),
):
    await svc.set_question_type(question_id, req.type)
    return {"message": "question type updated"}


# --- History ---

@router.get("/questions/{question_id}/history")
async def get_question_history(
    question_id: str,
    svc: QuestionService = Depends(get_question_service),
):
    history = await svc.get_question_history(question_id)
    data = [
        {
            "id": h.id,
            "question_id": h.question_id,
            "edited_by": h.edited_by,
            "changes_json": h.changes_json,
            "timestamp": h.timestamp,
        }
        for h in history
    ]
    return {"data": data, "count": len(data)}
