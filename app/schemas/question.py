from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DifficultyRange(BaseModel):
    min: int = 1
    max: int = 5


# --- AI generation ---

class RubricResponse(BaseModel):
    expected_key_concepts: list[str] = []
    grading_criteria: str = ""
    max_points: int = 10


class GeneratedQuestionAI(BaseModel):
    question_text: str
    competency: str
    difficulty: int
    expected_key_concepts: list[str] = []
    rubric: RubricResponse


class GenerateQuestionsRequest(BaseModel):
    title: str
    competencies: list[str]
    learning_objectives: list[str]
    difficulty_min: int = Field(ge=1, le=5)
    difficulty_max: int = Field(ge=1, le=5)
    num_questions_per_competency: int = 3
    programming_language: str = "Python"


class GenerateQuestionsResponse(BaseModel):
    assignment_id: str
    question_ids: list[str]
    total_generated: int


# --- Question CRUD ---

class QuestionOut(BaseModel):
    id: str
    assignment_id: str
    question_text: str
    competency: str
    difficulty: int
    source: str
    status: str
    question_type: str
    last_modified_by: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RubricOut(BaseModel):
    id: str
    question_id: str
    expected_key_concepts: list[str] | None = None
    grading_criteria: dict | str | None = None
    max_points: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QuestionWithRubricOut(BaseModel):
    id: str
    assignment_id: str
    question_text: str
    competency: str
    difficulty: int
    source: str
    status: str
    question_type: str
    last_modified_by: str | None = None
    created_at: datetime
    updated_at: datetime
    rubric: RubricOut | None = None

    model_config = {"from_attributes": True}


class UpdateQuestionRequest(BaseModel):
    question_text: Optional[str] = None
    competency: Optional[str] = None
    difficulty: Optional[int] = None
    modified_by: str


class ApproveQuestionRequest(BaseModel):
    approved_by: str


class SetQuestionTypeRequest(BaseModel):
    type: str = Field(pattern="^(required|adaptive)$")
