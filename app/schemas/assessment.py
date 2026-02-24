"""
Assessment API Schemas

Defines Pydantic models (schemas) for the assessment module. These schemas are
used by the FastAPI routes to validate incoming HTTP request bodies and serialize
outgoing HTTP response data for assessment sessions and student interactions.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class QuestionWithContext(BaseModel):
    question_id: str
    question_instance_id: str
    question_text: str
    competency: str
    difficulty: int
    code_context: str = ""
    hint: str = ""


# --- Trigger ---

class TriggerAssessmentRequest(BaseModel):
    student_id: str
    assignment_id: str
    code_context: str = ""


class TriggerAssessmentResponse(BaseModel):
    session_id: str
    first_question: QuestionWithContext | None = None
    total_questions: int = 0
    status: str


# --- Submit response ---

class SubmitResponseRequest(BaseModel):
    question_instance_id: str
    response_text: str
    response_type: str = ""


class SubmitResponseResponse(BaseModel):
    response_id: str
    next_question: QuestionWithContext | None = None
    is_complete: bool
    message: str = ""
    evaluation_score: float | None = None
    feedback_text: str | None = None
    detected_misconceptions: list[str] | None = None
    final_score: float | None = None
    max_score: float | None = None
    competency_summary: list[dict] | None = None


# --- Session details ---

class QuestionInstanceOut(BaseModel):
    id: str
    session_id: str
    question_id: str
    sequence_number: int
    asked_at: datetime
    competency: str
    difficulty: int
    model_config = {"from_attributes": True}


class StudentResponseOut(BaseModel):
    id: str
    question_instance_id: str
    session_id: str
    student_id: str
    response_text: str
    response_type: str | None = None
    submitted_at: datetime
    response_time_seconds: int
    evaluation_score: float | None = None
    feedback_text: str | None = None
    detected_misconceptions: list[str] | None = None
    model_config = {"from_attributes": True}


class SessionOut(BaseModel):
    id: str
    student_id: str
    assignment_id: str
    status: str
    trigger_reason: str
    started_at: datetime
    completed_at: datetime | None = None
    code_context: str | None = None
    final_score: float | None = None
    max_score: float | None = None
    competency_summary: list[dict] | None = None
    model_config = {"from_attributes": True}


class SessionDetailsOut(BaseModel):
    session: SessionOut
    questions_asked: list[QuestionInstanceOut]
    responses: list[StudentResponseOut]
    total_questions: int
    answered_questions: int


# --- Student sessions ---

class StudentSessionSummary(BaseModel):
    session_id: str
    assignment_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    questions_asked: int
    responses_given: int


# --- Instructor assessments ---

class InstructorAssessmentSummary(BaseModel):
    session_id: str
    student_id: str
    assignment_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    questions_asked: int
    responses_given: int


# --- Transcript ---

class ExchangeOut(BaseModel):
    question_text: str
    competency: str
    difficulty: int
    student_answer: str = ""
    asked_at: datetime
    answered_at: datetime | None = None
    response_time_seconds: int = 0
    evaluation_score: float | None = None
    feedback_text: str | None = None
    detected_misconceptions: list[str] | None = None


class AssessmentTranscriptOut(BaseModel):
    session_id: str
    student_id: str
    assignment_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    code_context: str = ""
    exchanges: list[ExchangeOut]
    final_score: float | None = None
    max_score: float | None = None
    competency_summary: list[dict] | None = None
