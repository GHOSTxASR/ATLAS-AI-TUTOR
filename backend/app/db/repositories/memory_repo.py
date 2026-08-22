from __future__ import annotations

from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryRecord
from app.db.repositories.base import BaseRepository


class MemoryRepository(BaseRepository[MemoryRecord]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=MemoryRecord, session=session)

    async def get_by_profile_id(
        self,
        profile_id: str,
        category: str | None = None,
        min_confidence: float = 0.0,
        is_active: bool | None = True,
    ) -> Sequence[MemoryRecord]:
        """Fetch memory records for a profile with optional filters."""
        stmt = select(MemoryRecord).where(MemoryRecord.profile_id == profile_id)
        if category:
            stmt = stmt.where(MemoryRecord.category == category)
        if min_confidence > 0.0:
            stmt = stmt.where(MemoryRecord.confidence >= min_confidence)
        if is_active is not None:
            stmt = stmt.where(MemoryRecord.is_active == is_active)

        stmt = stmt.order_by(MemoryRecord.confidence.desc(), MemoryRecord.created_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_subject(self, profile_id: str, subject: str) -> Sequence[MemoryRecord]:
        """Fetch memories matching a specific subject or topic."""
        result = await self.session.execute(
            select(MemoryRecord)
            .where(MemoryRecord.profile_id == profile_id)
            .where(MemoryRecord.subject.ilike(f"%{subject}%"))
            .where(MemoryRecord.is_active.is_(True))
        )
        return result.scalars().all()

    async def update_confidence(self, memory_id: str, delta: float) -> MemoryRecord | None:
        """Reinforce (+delta) or penalize (-delta) memory confidence, bounded to [0.0, 1.0]."""
        record = await self.get_by_id(memory_id)
        if not record:
            return None
        new_conf = min(1.0, max(0.0, record.confidence + delta))
        record.confidence = new_conf
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def decay_confidences(
        self,
        profile_id: str | None = None,
        decay_factor: float = 0.95,
        prune_threshold: float = 0.2,
    ) -> list[str]:
        """Apply memory decay factor and prune records that fall below prune_threshold. Returns pruned IDs."""
        stmt = select(MemoryRecord).where(MemoryRecord.is_active.is_(True))
        if profile_id:
            stmt = stmt.where(MemoryRecord.profile_id == profile_id)

        result = await self.session.execute(stmt)
        records = result.scalars().all()

        pruned_ids: list[str] = []
        for r in records:
            new_conf = r.confidence * decay_factor
            if new_conf < prune_threshold:
                pruned_ids.append(r.id)
                await self.session.delete(r)
            else:
                r.confidence = new_conf
                self.session.add(r)

        await self.session.commit()
        return pruned_ids

    async def delete_by_profile_id(self, profile_id: str) -> None:
        """Delete all memory records for a profile."""
        await self.session.execute(
            delete(MemoryRecord).where(MemoryRecord.profile_id == profile_id)
        )
        await self.session.commit()


# Backward compatibility alias
MemoryRepo = MemoryRepository
