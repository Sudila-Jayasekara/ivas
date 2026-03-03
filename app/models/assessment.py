"""
Assessment Database Models

Defines the SQLAlchemy ORM models for the assessment module, representing how
assessment sessions, questions asked during a session, and student responses
are stored in the PostgreSQL database. These models are used by Repositories
to read and write data.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    student_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    assignment_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    trigger_reason: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    code_context: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Computed on session completion ---
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    competency_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

class AssessmentQuestionInstance(Base):
    __tablename__ = "assessment_question_instances"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("assessment_sessions.id"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("questions.id"),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    competency: Mapped[str] = mapped_column(String, nullable=False, default="")
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)

    # --- Socratic follow-up fields ---
    follow_up_depth: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    parent_instance_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("assessment_question_instances.id"),
        nullable=True,
    )
    follow_up_question_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class StudentResponse(Base):
    __tablename__ = "student_responses"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    question_instance_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("assessment_question_instances.id"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("assessment_sessions.id"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_type: Mapped[str | None] = mapped_column(String, nullable=True)
    transcript_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    response_time_seconds: Mapped[int] = mapped_column(Integer, default=0)

    # --- Evaluation fields (populated by LLM after submission) ---
    evaluation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_misconceptions: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # --- LLM layer outputs ---
    input_classification: Mapped[str | None] = mapped_column(String, nullable=True)      # evaluate | teach_and_skip | warn_and_reask | conversational | exchange_limit
    score_justification: Mapped[str | None] = mapped_column(Text, nullable=True)          # LLM explanation of why this score was given
    deep_analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)              # Background deep analysis results

    # --- Voice intent (from voice service LLM classification) ---
    voice_intent: Mapped[str | None] = mapped_column(String, nullable=True)               # answer_attempt | clarification_request | repeat_request | topic_question | proceed_request | off_topic


class ResponseCompetencyLink(Base):
    __tablename__ = "response_competency_links"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    response_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("student_responses.id"),
        nullable=False,
        index=True,
    )
    competency: Mapped[str] = mapped_column(String, nullable=False, index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    question_id: Mapped[str] = mapped_column(String, nullable=False)
