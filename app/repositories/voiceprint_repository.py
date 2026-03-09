"""
Voiceprint Repository

Data access layer for voice biometric models. Provides CRUD operations for
voiceprint enrollment records and verification audit logs.
"""

from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.voiceprint import Voiceprint, VoiceVerificationLog


class VoiceprintRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Voiceprint CRUD ───────────────────────────────────────────────

    async def create(self, voiceprint: Voiceprint) -> Voiceprint:
        self.session.add(voiceprint)
        await self.session.flush()
        await self.session.refresh(voiceprint)
        return voiceprint

    async def find_active_by_student(self, student_id: str) -> Optional[Voiceprint]:
        result = await self.session.execute(
            select(Voiceprint).where(
                Voiceprint.student_id == student_id,
                Voiceprint.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def find_any_by_student(self, student_id: str) -> Optional[Voiceprint]:
        """Find any voiceprint for a student (active or inactive)."""
        result = await self.session.execute(
            select(Voiceprint).where(
                Voiceprint.student_id == student_id,
            )
        )
        return result.scalar_one_or_none()

    async def deactivate_all_for_student(self, student_id: str) -> int:
        """Deactivate all existing voiceprints for a student (before re-enrollment)."""
        result = await self.session.execute(
            update(Voiceprint)
            .where(Voiceprint.student_id == student_id)
            .values(is_active=False)
        )
        await self.session.flush()
        return result.rowcount

    async def update_embedding(
        self, voiceprint_id: str, embedding: list[float], sample_count: int
    ) -> None:
        await self.session.execute(
            update(Voiceprint)
            .where(Voiceprint.id == voiceprint_id)
            .values(embedding=embedding, sample_count=sample_count)
        )
        await self.session.flush()

    # ── Verification log ──────────────────────────────────────────────

    async def create_verification_log(self, log: VoiceVerificationLog) -> VoiceVerificationLog:
        self.session.add(log)
        await self.session.flush()
        return log

    async def get_session_verification_logs(
        self, session_id: str
    ) -> list[VoiceVerificationLog]:
        result = await self.session.execute(
            select(VoiceVerificationLog)
            .where(VoiceVerificationLog.session_id == session_id)
            .order_by(VoiceVerificationLog.checked_at.asc())
        )
        return list(result.scalars().all())

    async def count_consecutive_failures(self, session_id: str) -> int:
        """Count how many consecutive verification failures from the end of the session."""
        result = await self.session.execute(
            select(VoiceVerificationLog)
            .where(VoiceVerificationLog.session_id == session_id)
            .order_by(VoiceVerificationLog.checked_at.desc())
        )
        logs = list(result.scalars().all())
        count = 0
        for log in logs:
            if not log.passed:
                count += 1
            else:
                break
        return count
