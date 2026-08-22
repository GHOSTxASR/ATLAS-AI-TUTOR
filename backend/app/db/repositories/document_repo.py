from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document
from app.db.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=Document, session=session)

    async def get_by_profile_id(self, profile_id: str) -> Sequence[Document]:
        result = await self.session.execute(
            select(Document)
            .where(Document.profile_id == profile_id)
            .order_by(Document.created_at.desc())
        )
        return result.scalars().all()

    list_by_profile = get_by_profile_id

    async def get_by_statuses(self, statuses: Sequence[str]) -> Sequence[Document]:
        """Documents currently in any of the given processing states."""
        result = await self.session.execute(
            select(Document)
            .where(Document.status.in_(list(statuses)))
            .order_by(Document.created_at.asc())
        )
        return result.scalars().all()

    async def get_by_hash(self, profile_id: str, content_hash: str) -> Document | None:
        result = await self.session.execute(
            select(Document)
            .where(Document.profile_id == profile_id)
            .where(Document.content_hash == content_hash)
        )
        return result.scalars().first()
