"""
Question API Schemas

Pydantic models for question generation (from grading criteria) and retrieval.
"""

from datetime import datetime

from pydantic import BaseModel, Field


# --- AI generation (API 4) ---

class GeneratedQuestionAI(BaseModel):
    """Shape returned by the LLM for a single question."""
    question_text: str
    competency: str
    difficulty: int
    expected_answer: str
    max_points: int = 10


class GenerateQuestionsRequest(BaseModel):
    num_questions_per_level: int = Field(default=3, ge=1, le=20)


class GenerateQuestionsResponse(BaseModel):
    assignment_id: str
    question_ids: list[str]
    total_generated: int


# --- Question CRUD (API 5) ---

class QuestionOut(BaseModel):
    id: str
    assignment_id: str
    question_text: str
    competency: str
    difficulty: int
    expected_answer: str
    max_points: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
