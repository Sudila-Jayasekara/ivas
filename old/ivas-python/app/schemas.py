from pydantic import BaseModel
from typing import Optional


class DifficultyRange(BaseModel):
    min: int = 1
    max: int = 5


class GenerateQuestionsRequest(BaseModel):
    assignment_id: str
    title: str
    competencies: list[str]
    difficulty_range: DifficultyRange
    learning_objectives: list[str]
    num_questions_per_competency: int = 3
    programming_language: str = "Python"


class RubricResponse(BaseModel):
    expected_key_concepts: list[str]
    grading_criteria: str
    max_points: int


class GeneratedQuestion(BaseModel):
    question_text: str
    competency: str
    difficulty: int
    expected_key_concepts: list[str]
    rubric: RubricResponse


class GenerateQuestionsResponse(BaseModel):
    assignment_id: str
    questions: list[GeneratedQuestion]
    total_generated: int


class HealthResponse(BaseModel):
    status: str
    service: str
    ollama_available: bool
