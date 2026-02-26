"""
Grading Criteria API Schemas

Pydantic models for grading-criteria generation, retrieval, and editing.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# --- AI generation request/response ---

class GenerateGradingCriteriaRequest(BaseModel):
    assignment_text: str = Field(..., min_length=1)
    replace_existing: bool = Field(default=False, description="If true, deletes all existing criteria before generating. If false, appends new criteria (skipping duplicates).")


class GradingCriteriaAI(BaseModel):
    """Shape returned by the LLM for a single criterion row."""
    competency: str
    difficulty_level: int = Field(ge=1, le=5)
    level_label: str
    level_description: str
    marking_criteria: str
    max_points: int


class GenerateGradingCriteriaResponse(BaseModel):
    assignment_id: str
    criteria_ids: list[str]
    total_generated: int


# --- CRUD ---

class GradingCriteriaOut(BaseModel):
    id: str
    assignment_id: str
    competency: str
    difficulty_level: int
    level_label: str
    level_description: str
    marking_criteria: str
    max_points: int
    programming_language: str
    learning_objectives: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UpdateGradingCriteriaRequest(BaseModel):
    competency: Optional[str] = None
    difficulty_level: Optional[int] = Field(None, ge=1, le=5)
    level_label: Optional[str] = None
    level_description: Optional[str] = None
    marking_criteria: Optional[str] = None
    max_points: Optional[int] = None
    programming_language: Optional[str] = None
    learning_objectives: Optional[list[str]] = None
