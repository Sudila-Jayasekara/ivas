"""
Voice Biometric Database Models

Stores speaker voiceprints (embeddings) for biometric student verification
and logs every verification attempt for audit purposes. A voiceprint is
a 256-dimensional vector derived from the student's voice using a
GE2E (Generalized End-to-End) speaker encoder.

Enrollment: student provides voice samples → averaged into one embedding.
Verification: live audio compared against stored embedding via cosine similarity.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Voiceprint(Base):
    """Stores a student's enrolled voice embedding (256-dim float vector)."""

    __tablename__ = "voiceprints"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    student_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)

    # 256-dimensional GE2E embedding stored as a JSON array of floats
    embedding: Mapped[list] = mapped_column(JSONB, nullable=False)

    # How many audio samples were averaged to build this voiceprint
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Only one active voiceprint per student; allows re-enrollment
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class VoiceVerificationLog(Base):
    """Audit log for every speaker verification attempt during an assessment."""

    __tablename__ = "voice_verification_logs"

    id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # Cosine similarity score between live audio and stored voiceprint (0.0–1.0)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Threshold used for this check
    threshold: Mapped[float] = mapped_column(Float, nullable=False)

    # Whether the check passed
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # How many consecutive failures have occurred in this session at this point
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
