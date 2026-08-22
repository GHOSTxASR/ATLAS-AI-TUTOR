from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Profile
from app.db.repositories.base import BaseRepository


class ProfileRepository(BaseRepository[Profile]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=Profile, session=session)
