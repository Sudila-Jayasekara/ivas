"""
Voice Biometric API Routes

Provides endpoints for:
  - Voiceprint enrollment (register a student's voice)
  - Speaker verification (check if audio matches enrolled voiceprint)
  - Enrollment status checks
  - Session verification summary (audit trail)

These endpoints work alongside the voice assessment WebSocket which
performs continuous speaker verification during live assessments.
"""

import asyncio
import logging
from datetime import datetime, timezone
from functools import partial
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.voiceprint import Voiceprint, VoiceVerificationLog
from app.repositories.voiceprint_repository import VoiceprintRepository
from app.schemas.voice_biometric import (
    AddEnrollmentSampleRequest,
    AddEnrollmentSampleResponse,
    EnrollmentStatusResponse,
    EnrollVoiceprintRequest,
    EnrollVoiceprintResponse,
    ReEnrollRequest,
    SessionVerificationSummary,
    VerifyVoiceRequest,
    VerifyVoiceResponse,
)
from app.services.voice_biometric_service import (
    MIN_ENROLLMENT_SAMPLES,
    VERIFICATION_THRESHOLD,
    average_embeddings,
    compute_embedding_from_audio,
    verify_speaker,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice-biometrics", tags=["voice-biometrics"])


# ── Enrollment ────────────────────────────────────────────────────────


@router.post("/enroll", response_model=EnrollVoiceprintResponse)
async def enroll_voiceprint(
    req: EnrollVoiceprintRequest,
    db: AsyncSession = Depends(get_db),
):
    """Enroll a student's voiceprint from one or more audio samples.

    Requires at least 3 samples for a reliable voiceprint.
    If a voiceprint already exists, it is deactivated and replaced.
    """
    repo = VoiceprintRepository(db)
    loop = asyncio.get_running_loop()

    # Compute embeddings for all samples (CPU-bound → thread pool)
    embeddings: list[list[float]] = []
    for i, sample in enumerate(req.audio_samples):
        try:
            emb = await loop.run_in_executor(
                None, partial(compute_embedding_from_audio, sample)
            )
            embeddings.append(emb)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Sample {i + 1}: {e}",
            )

    sample_count = len(embeddings)
    status = "enrolled" if sample_count >= MIN_ENROLLMENT_SAMPLES else "needs_more_samples"

    # Average into a single voiceprint
    voiceprint_vector = average_embeddings(embeddings)

    # Deactivate any existing voiceprint
    await repo.deactivate_all_for_student(req.student_id)

    # Create new voiceprint
    vp = Voiceprint(
        id=str(uuid4()),
        student_id=req.student_id,
        embedding=voiceprint_vector,
        sample_count=sample_count,
        is_active=status == "enrolled",
    )
    await repo.create(vp)
    await db.commit()

    message = (
        f"Voiceprint enrolled with {sample_count} samples."
        if status == "enrolled"
        else f"Only {sample_count} sample(s) provided. Need at least {MIN_ENROLLMENT_SAMPLES} for reliable enrollment."
    )

    return EnrollVoiceprintResponse(
        student_id=req.student_id,
        voiceprint_id=vp.id,
        sample_count=sample_count,
        status=status,
        message=message,
    )


@router.post("/enroll/sample", response_model=AddEnrollmentSampleResponse)
async def add_enrollment_sample(
    req: AddEnrollmentSampleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Add a single audio sample to an existing (or new) enrollment.

    Useful for incremental enrollment — client records one sample at a time.
    """
    repo = VoiceprintRepository(db)
    loop = asyncio.get_running_loop()

    # Compute embedding
    try:
        new_emb = await loop.run_in_executor(
            None, partial(compute_embedding_from_audio, req.audio_sample)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Find existing voiceprint (active OR inactive — during enrollment it's inactive)
    existing = await repo.find_any_by_student(req.student_id)

    if existing:
        # Re-average: reconstruct old embeddings approximation + new sample
        # Since we store the averaged embedding, we use weighted average
        old_count = existing.sample_count
        old_emb = existing.embedding
        new_count = old_count + 1

        # Weighted average: (old_avg * old_count + new) / new_count
        import numpy as np

        old_arr = np.array(old_emb, dtype=np.float32) * old_count
        new_arr = np.array(new_emb, dtype=np.float32)
        combined = (old_arr + new_arr) / new_count
        norm = np.linalg.norm(combined)
        if norm > 0:
            combined = combined / norm

        await repo.update_embedding(existing.id, combined.tolist(), new_count)

        if new_count >= MIN_ENROLLMENT_SAMPLES and not existing.is_active:
            from sqlalchemy import update as sql_update
            from app.models.voiceprint import Voiceprint as VP

            await db.execute(
                sql_update(VP).where(VP.id == existing.id).values(is_active=True)
            )

        await db.commit()

        status = "enrolled" if new_count >= MIN_ENROLLMENT_SAMPLES else "needs_more_samples"
        return AddEnrollmentSampleResponse(
            student_id=req.student_id,
            voiceprint_id=existing.id,
            sample_count=new_count,
            status=status,
            message=f"Sample added ({new_count} total)."
            if status == "enrolled"
            else f"Sample added ({new_count}/{MIN_ENROLLMENT_SAMPLES} needed).",
        )

    # Truly no voiceprint at all — create new one
    vp = Voiceprint(
        id=str(uuid4()),
        student_id=req.student_id,
        embedding=new_emb,
        sample_count=1,
        is_active=False,  # Not enough samples yet
    )
    await repo.create(vp)
    await db.commit()

    return AddEnrollmentSampleResponse(
        student_id=req.student_id,
        voiceprint_id=vp.id,
        sample_count=1,
        status="needs_more_samples",
        message=f"Enrollment started (1/{MIN_ENROLLMENT_SAMPLES} samples).",
    )


# ── Verification ──────────────────────────────────────────────────────


@router.post("/verify", response_model=VerifyVoiceResponse)
async def verify_voice(
    req: VerifyVoiceRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify that an audio clip matches the enrolled voiceprint for a student."""
    repo = VoiceprintRepository(db)
    loop = asyncio.get_running_loop()

    # Load voiceprint
    vp = await repo.find_active_by_student(req.student_id)
    if not vp:
        raise HTTPException(
            status_code=404,
            detail=f"No enrolled voiceprint for student {req.student_id}. "
            "Please complete voice enrollment first.",
        )

    # Compute live embedding
    try:
        live_emb = await loop.run_in_executor(
            None, partial(compute_embedding_from_audio, req.audio_data)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Compare
    passed, score = verify_speaker(live_emb, vp.embedding)

    # Count consecutive failures for this session
    consecutive_failures = await repo.count_consecutive_failures(req.session_id)
    if not passed:
        consecutive_failures += 1

    # Log verification attempt
    log = VoiceVerificationLog(
        id=str(uuid4()),
        session_id=req.session_id,
        student_id=req.student_id,
        similarity_score=score,
        threshold=VERIFICATION_THRESHOLD,
        passed=passed,
        consecutive_failures=consecutive_failures if not passed else 0,
    )
    await repo.create_verification_log(log)
    await db.commit()

    message = "Voice verified — identity confirmed." if passed else (
        "Voice does not match enrolled voiceprint. "
        f"Similarity: {score:.2f} (threshold: {VERIFICATION_THRESHOLD:.2f})."
    )

    return VerifyVoiceResponse(
        student_id=req.student_id,
        passed=passed,
        similarity_score=round(score, 4),
        threshold=VERIFICATION_THRESHOLD,
        message=message,
    )


# ── Status & Summary ─────────────────────────────────────────────────


@router.get("/enrollment-status/{student_id}", response_model=EnrollmentStatusResponse)
async def enrollment_status(
    student_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Check whether a student has an active voiceprint enrollment."""
    repo = VoiceprintRepository(db)
    vp = await repo.find_active_by_student(student_id)

    return EnrollmentStatusResponse(
        student_id=student_id,
        is_enrolled=vp is not None,
        sample_count=vp.sample_count if vp else 0,
        created_at=vp.created_at if vp else None,
        updated_at=vp.updated_at if vp else None,
    )


@router.get("/session-summary/{session_id}", response_model=SessionVerificationSummary)
async def session_verification_summary(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the verification audit trail for an assessment session."""
    repo = VoiceprintRepository(db)
    logs = await repo.get_session_verification_logs(session_id)

    total = len(logs)
    passed_count = sum(1 for l in logs if l.passed)
    failed_count = total - passed_count
    avg_sim = (sum(l.similarity_score for l in logs) / total) if total > 0 else 0.0

    # Session is flagged if there are 3+ consecutive failures anywhere in the logs
    is_flagged = any(l.consecutive_failures >= 3 for l in logs)

    checks = [
        {
            "checked_at": l.checked_at.isoformat(),
            "similarity_score": round(l.similarity_score, 4),
            "passed": l.passed,
            "consecutive_failures": l.consecutive_failures,
        }
        for l in logs
    ]

    return SessionVerificationSummary(
        session_id=session_id,
        total_checks=total,
        passed_checks=passed_count,
        failed_checks=failed_count,
        average_similarity=round(avg_sim, 4),
        is_flagged=is_flagged,
        checks=checks,
    )


# ── Re-enrollment ────────────────────────────────────────────────────


@router.post("/re-enroll", response_model=EnrollVoiceprintResponse)
async def re_enroll_voiceprint(
    req: ReEnrollRequest,
    db: AsyncSession = Depends(get_db),
):
    """Deactivate existing voiceprint and re-enroll with new samples."""
    # Reuse the enroll endpoint logic (it already deactivates old ones)
    enroll_req = EnrollVoiceprintRequest(
        student_id=req.student_id,
        audio_samples=req.audio_samples,
    )
    return await enroll_voiceprint(enroll_req, db)
