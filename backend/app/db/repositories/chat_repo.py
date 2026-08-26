from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessage, ChatSession, _utcnow
from app.db.repositories.base import BaseRepository


class ChatSessionRepository(BaseRepository[ChatSession]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=ChatSession, session=session)

    async def touch(self, chat_session: ChatSession) -> ChatSession:
        """Mark a session as just used so it sorts to the top of the list.

        ``update()`` with no changed fields emits no SQL at all, so SQLAlchemy's
        ``onupdate`` never fired and ``updated_at`` stayed frozen at creation
        time - meaning recently-used chats never moved up the sidebar.
        """
        return await self.update(chat_session, updated_at=_utcnow())

    async def get_by_profile_id(self, profile_id: str) -> Sequence[ChatSession]:
        result = await self.session.execute(
            select(ChatSession)
            .where(ChatSession.profile_id == profile_id)
            .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        )
        return result.scalars().all()

    async def get_by_roadmap_node(
        self, profile_id: str, roadmap_node_id: str
    ) -> ChatSession | None:
        """The most recently used thread for a roadmap topic, if one exists.

        Most recent rather than first: if several were created before threads
        were linked to topics, the one the learner actually came back to is the
        useful one to reopen.
        """
        result = await self.session.execute(
            select(ChatSession)
            .where(
                ChatSession.profile_id == profile_id,
                ChatSession.roadmap_node_id == roadmap_node_id,
            )
            .order_by(ChatSession.updated_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def search(self, profile_id: str, query: str) -> Sequence[ChatSession]:
        # Basic LIKE search on the title
        # In a later milestone, FTS5 will be used for full-text search.
        result = await self.session.execute(
            select(ChatSession)
            .where(ChatSession.profile_id == profile_id)
            .where(ChatSession.title.ilike(f"%{query}%"))
            .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        )
        return result.scalars().all()


class ChatMessageRepository(BaseRepository[ChatMessage]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=ChatMessage, session=session)

    async def get_by_session_id(self, session_id: str) -> Sequence[ChatMessage]:
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            # id is a deterministic tiebreaker for rows sharing a timestamp,
            # so history order can never depend on the query plan.
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
        return result.scalars().all()
