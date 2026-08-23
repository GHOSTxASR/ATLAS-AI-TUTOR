from __future__ import annotations

from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessage, ChatSession
from app.db.repositories.chat_repo import ChatMessageRepository, ChatSessionRepository
from app.exceptions import AtlasError
from app.schemas.chat import ChatMessageCreate, ChatSessionCreate, ChatSessionUpdate


class ChatService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.session_repo = ChatSessionRepository(session)
        self.message_repo = ChatMessageRepository(session)

    async def get_all_sessions(self, profile_id: str, query: str | None = None) -> Sequence[ChatSession]:
        if query:
            return await self.session_repo.search(profile_id, query)
        return await self.session_repo.get_by_profile_id(profile_id)

    async def get_session(self, profile_id: str, session_id: str) -> ChatSession:
        chat_session = await self.session_repo.get_by_id(session_id)
        if not chat_session or chat_session.profile_id != profile_id:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Chat session not found")
        return chat_session

    async def create_session(self, profile_id: str, data: ChatSessionCreate) -> ChatSession:
        title = data.title if data.title and data.title.strip() else "New Chat"
        return await self.session_repo.create(profile_id=profile_id, title=title)

    async def update_session(self, profile_id: str, session_id: str, data: ChatSessionUpdate) -> ChatSession:
        chat_session = await self.get_session(profile_id, session_id)
        return await self.session_repo.update(chat_session, title=data.title)

    async def delete_session(self, profile_id: str, session_id: str) -> None:
        chat_session = await self.get_session(profile_id, session_id)
        messages = await self.message_repo.get_by_session_id(chat_session.id)
        for msg in messages:
            await self.message_repo.delete(msg.id)
        await self.session_repo.delete(chat_session.id)

    async def get_messages(self, profile_id: str, session_id: str) -> Sequence[ChatMessage]:
        # Validate session ownership first
        await self.get_session(profile_id, session_id)
        return await self.message_repo.get_by_session_id(session_id)

    async def add_message(self, profile_id: str, session_id: str, data: ChatMessageCreate) -> ChatMessage:
        chat_session = await self.get_session(profile_id, session_id)

        message = await self.message_repo.create(
            session_id=chat_session.id,
            role=data.role,
            content=data.content
        )

        # Touch the session's updated_at timestamp to bubble it to the top of the list
        await self.session_repo.update(chat_session)

        return message
