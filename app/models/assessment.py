"""
Assessment Database Models

Defines the SQLAlchemy ORM models for the assessment module, representing how
assessment sessions, questions asked during a session, and student responses
are stored in the PostgreSQL database. These models are used by Repositories
to read and write data.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    student_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    assignment_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    trigger_reason: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    code_context: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    question_id: Mapped[str] = mapped_column(String, nullable=False)
