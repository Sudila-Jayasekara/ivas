"""
Questions API Router

Handles HTTP requests for question generation and retrieval:
  API 4 — POST /assignments/{id}/questions/generate
  API 5 — GET  /assignments/{id}/questions
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.api.deps import get_question_service
from app.schemas.question import (
    GenerateQuestionsResponse,
    QuestionOut,
)
from app.services.question_service import QuestionService

router = APIRouter(tags=["questions"])


# --- API 4: Generate questions from saved grading criteria ---

@router.post(
    "/assignments/{assignment_id}/questions/generate",
    response_model=GenerateQuestionsResponse,
    status_code=201,
)
async def generate_questions(
    assignment_id: str,
    criteria_id: Optional[str] = Query(None, description="Generate questions for a specific grading criterion only"),
    assignment_text: Optional[str] = Query(None, description="Original assignment text for context-aware question generation"),
    svc: QuestionService = Depends(get_question_service),
):
    try:
        result = await svc.generate_questions(assignment_id, criteria_id=criteria_id, assignment_text=assignment_text or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return GenerateQuestionsResponse(
        assignment_id=assignment_id,
        question_ids=result["question_ids"],
        total_generated=result["total_generated"],
    )


# --- API 5: List questions for an assignment ---

@router.get("/assignments/{assignment_id}/questions")
async def get_questions(
    assignment_id: str,
    status: Optional[str] = Query(None),
    competency: Optional[str] = Query(None),
    svc: QuestionService = Depends(get_question_service),
):
    questions = await svc.get_questions_by_assignment(
        assignment_id, status=status, competency=competency
    )
    data = [QuestionOut.model_validate(q) for q in questions]
    return {"data": data, "count": len(data)}
