from __future__ import annotations

import logging
import re
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessage, ChatSession
from app.db.repositories.chat_repo import ChatMessageRepository, ChatSessionRepository
from app.exceptions import AtlasError
from app.schemas.chat import ChatMessageCreate, ChatSessionCreate, ChatSessionUpdate

logger = logging.getLogger(__name__)

#: Titles the app assigns itself, e.g. "Chat (Teaching)". Auto-naming only
#: replaces one of these -- anything else is a name the user chose, and
#: overwriting it would undo their edit on the next message.
_DEFAULT_TITLE = re.compile(r"^(chat|new session)\s*(\(.*\))?$", re.IGNORECASE)

_TITLE_MAX_CHARS = 48


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
        """Create a thread, reusing the one for a roadmap topic if it exists.

        Creating from a topic twice should land in the same conversation; the
        duplicates only existed because nothing recorded which topic a thread
        belonged to.
        """
        if data.roadmap_node_id:
            existing = await self.session_repo.get_by_roadmap_node(
                profile_id, data.roadmap_node_id
            )
            if existing is not None:
                return existing

        title = data.title if data.title and data.title.strip() else "New Chat"
        return await self.session_repo.create(
            profile_id=profile_id, title=title, roadmap_node_id=data.roadmap_node_id
        )

    async def update_session(self, profile_id: str, session_id: str, data: ChatSessionUpdate) -> ChatSession:
        chat_session = await self.get_session(profile_id, session_id)
        return await self.session_repo.update(chat_session, title=data.title)

    def _is_default_title(self, title: str) -> bool:
        return bool(_DEFAULT_TITLE.match((title or "").strip()))

    @staticmethod
    def _clean_title(raw: str) -> str:
        """Reduce a model reply to a usable title.

        Models like to answer with quotes, a trailing period, a "Title:" prefix
        or a whole sentence; none of those belong in a sidebar.
        """
        title = (raw or "").strip().splitlines()[0] if (raw or "").strip() else ""
        title = re.sub(r"^\s*(title|chat title)\s*[:\-]\s*", "", title, flags=re.IGNORECASE)
        title = title.strip().strip("\"'“”‘’").strip()
        title = title.rstrip(".")
        if len(title) > _TITLE_MAX_CHARS:
            title = title[:_TITLE_MAX_CHARS].rsplit(" ", 1)[0].rstrip(",;:") + "…"
        return title.strip()

    async def session_for_topic(
        self, profile_id: str, topic: str, roadmap_node_id: str | None = None
    ) -> tuple[ChatSession, bool]:
        """Return the thread for a topic, creating one only if none exists.

        Launching the tutor from a roadmap topic used to drop the learner on
        /chat with the topic typed into the box and no thread attached, so every
        visit started another one and the sidebar filled with identical rows.

        Keyed on the roadmap node when there is one, because that survives the
        thread being renamed -- by hand or by auto-naming. Title matching stays
        as the fallback for topics that are not roadmap nodes, and for threads
        created before the link existed.

        Returns the thread and whether it was created.
        """
        topic = (topic or "").strip()
        if not topic and not roadmap_node_id:
            raise AtlasError(
                status_code=422, code="VALIDATION_ERROR", message="A topic is required."
            )

        if roadmap_node_id:
            linked = await self.session_repo.get_by_roadmap_node(profile_id, roadmap_node_id)
            if linked is not None:
                return linked, False

        existing = await self.session_repo.get_by_profile_id(profile_id)
        wanted = topic.casefold()
        if wanted:
            # Newest first, so resuming picks up the most recent thread.
            for chat_session in existing:
                if (chat_session.title or "").strip().casefold() == wanted:
                    # Adopt it, so the next lookup goes by id rather than title.
                    if roadmap_node_id and not chat_session.roadmap_node_id:
                        chat_session = await self.session_repo.update(
                            chat_session, roadmap_node_id=roadmap_node_id
                        )
                    return chat_session, False

        created = await self.session_repo.create(
            profile_id=profile_id,
            title=topic or "New Chat",
            roadmap_node_id=roadmap_node_id,
        )
        return created, True

    async def autotitle_session(self, profile_id: str, session_id: str) -> ChatSession:
        """Name a session after what it is actually about.

        Every session was called "Chat (Teaching)", so the sidebar was a column
        of identical rows. Deliberately a separate call rather than part of the
        chat turn: titling is worth a second of latency on a list item, not on
        the reply the user is waiting to read.
        """
        chat_session = await self.get_session(profile_id, session_id)
        if not self._is_default_title(chat_session.title):
            return chat_session  # Renamed by hand; leave it alone.

        messages = await self.message_repo.get_by_session_id(session_id)
        first_user = next((m for m in messages if m.role == "user"), None)
        if not first_user or not (first_user.content or "").strip():
            return chat_session

        from app.config import get_settings
        from app.models.abstraction import ChatMessage as LLMMessage
        from app.models.provider_factory import get_model_client

        client = get_model_client(get_settings())
        try:
            response = await client.chat_complete(
                messages=[
                    LLMMessage(
                        role="system",
                        content=(
                            "Write a short title for a study conversation that opens with the "
                            "message below. Three to six words, no quotes, no trailing period, "
                            "no prefix such as 'Title:'. Name the subject matter, not the act of "
                            "asking. Reply with the title alone."
                        ),
                    ),
                    LLMMessage(role="user", content=(first_user.content or "")[:600]),
                ],
                temperature=0.2,
                max_tokens=400,
            )
            title = self._clean_title(response.content)
        except Exception as e:
            # A title is a nicety; never turn its failure into a failed request.
            logger.warning("Could not auto-title session %s: %s", session_id, e)
            return chat_session

        if not title:
            return chat_session
        return await self.session_repo.update(chat_session, title=title)

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
