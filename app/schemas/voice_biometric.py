"""
Voice Biometric API Schemas

Pydantic models for enrollment, verification, and status check endpoints.
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ── Enrollment ────────────────────────────────────────────────────────

class EnrollVoiceprintRequest(BaseModel):
    """Start or add to a voiceprint enrollment.

    audio_samples: list of base64-encoded WAV audio clips (minimum 3).
    Each sample should be 3–10 seconds of the student speaking naturally.
    """

    student_id: str
    audio_samples: list[str] = Field(
        ...,
        min_length=1,
        description="Base64-encoded WAV audio samples",
    )


class EnrollVoiceprintResponse(BaseModel):
    student_id: str
    voiceprint_id: str
    sample_count: int
    status: str  # "enrolled" | "needs_more_samples"
    message: str


# ── Single sample add (incremental enrollment) ───────────────────────

class AddEnrollmentSampleRequest(BaseModel):
    student_id: str
    audio_sample: str = Field(..., description="Base64-encoded WAV audio")


class AddEnrollmentSampleResponse(BaseModel):
    student_id: str
    voiceprint_id: str
    sample_count: int
    status: str
    message: str


# ── Verification ──────────────────────────────────────────────────────

class VerifyVoiceRequest(BaseModel):
    """One-shot speaker verification against the enrolled voiceprint."""

    student_id: str
    session_id: str
    audio_data: str = Field(..., description="Base64-encoded WAV audio to verify")


class VerifyVoiceResponse(BaseModel):
    student_id: str
    passed: bool
    similarity_score: float
    threshold: float
    message: str


# ── Enrollment status ─────────────────────────────────────────────────

class EnrollmentStatusResponse(BaseModel):
    student_id: str
    is_enrolled: bool
    sample_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ── Session verification summary ──────────────────────────────────────

class SessionVerificationSummary(BaseModel):
    session_id: str
    total_checks: int
    passed_checks: int
    failed_checks: int
    average_similarity: float
    is_flagged: bool
    checks: list[dict] = []


# ── Re-enrollment ────────────────────────────────────────────────────

class ReEnrollRequest(BaseModel):
    """Deactivate current voiceprint and start fresh enrollment."""

    student_id: str
    audio_samples: list[str] = Field(
        ...,
        min_length=1,
        description="Base64-encoded WAV audio samples for re-enrollment",
    )
