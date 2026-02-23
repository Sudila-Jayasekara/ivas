"""
Question Database Model

Simplified question model. Questions are generated from saved GradingCriteria
and stored here for use by the assessment system.
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
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


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
    expected_answer: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    max_points: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="draft"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("difficulty >= 1 AND difficulty <= 5", name="ck_difficulty"),
    )
