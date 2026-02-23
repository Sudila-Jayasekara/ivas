"""
Grading Criteria Database Model

Defines the SQLAlchemy ORM model for AI-extracted grading criteria.
When a lecturer provides assignment text, the AI extracts competencies,
difficulty levels, marking criteria, programming language, and learning
objectives — all stored as GradingCriteria rows.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GradingCriteria(Base):
    __tablename__ = "grading_criteria"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    assignment_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    competency: Mapped[str] = mapped_column(String, nullable=False)
    difficulty_level: Mapped[int] = mapped_column(Integer, nullable=False)
    level_label: Mapped[str] = mapped_column(String, nullable=False)
    level_description: Mapped[str] = mapped_column(Text, nullable=False)
    marking_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    max_points: Mapped[int] = mapped_column(Integer, nullable=False)
    programming_language: Mapped[str] = mapped_column(String, nullable=False)
    learning_objectives: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "difficulty_level >= 1 AND difficulty_level <= 5",
            name="ck_gc_difficulty_level",
        ),
    )
