import enum
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# ---------- enums ----------

class QuestionSource(str, enum.Enum):
    ai_generated = "ai_generated"
    instructor_created = "instructor_created"


class QuestionStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    archived = "archived"


class QuestionType(str, enum.Enum):
    required = "required"
    adaptive = "adaptive"


# ---------- Question ----------

class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    assignment_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    competency: Mapped[str] = mapped_column(String, nullable=False, index=True)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[QuestionSource] = mapped_column(
        Enum(QuestionSource, name="question_source"), nullable=False
    )
    status: Mapped[QuestionStatus] = mapped_column(
        Enum(QuestionStatus, name="question_status"),
        nullable=False,
        server_default="draft",
    )
    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type"), nullable=False
    )
    last_modified_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    rubric: Mapped["Rubric | None"] = relationship(
        back_populates="question", uselist=False, lazy="selectin"
    )
    edit_history: Mapped[list["QuestionEditHistory"]] = relationship(
        back_populates="question", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("difficulty >= 1 AND difficulty <= 5", name="ck_difficulty"),
    )


# ---------- Rubric ----------

class Rubric(Base):
    __tablename__ = "rubrics"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    question_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), ForeignKey("questions.id"), nullable=False, index=True
    )
    expected_key_concepts: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    grading_criteria: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    max_points: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    question: Mapped["Question"] = relationship(back_populates="rubric")


# ---------- QuestionEditHistory ----------

class QuestionEditHistory(Base):
    __tablename__ = "question_edit_histories"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    question_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), ForeignKey("questions.id"), nullable=False, index=True
    )
    edited_by: Mapped[str] = mapped_column(String, nullable=False)
    changes_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    question: Mapped["Question"] = relationship(back_populates="edit_history")
