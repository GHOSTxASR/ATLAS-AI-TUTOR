from __future__ import annotations

import logging

from app.config import get_settings
from app.db.database import async_session
from app.db.repositories.chat_repo import ChatMessageRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)


async def extract_session_memory_and_summary(profile_id: str, session_id: str) -> None:
    """Background task to extract learner memories and generate a conversation summary after chat turns."""
    settings = get_settings()

    async with async_session() as db:
        try:
            msg_repo = ChatMessageRepository(db)
            messages = await msg_repo.get_by_session_id(session_id)
            if not messages or len(messages) < 2:
                return

            memory_service = MemoryService(session=db, settings=settings)
            # 1. Extract new memories (strengths, weaknesses, preferences)
            await memory_service.extract_memories_from_conversation(
                profile_id=profile_id,
                session_id=session_id,
                messages=messages,
            )

            # 2. Generate and index conversation summary
            await memory_service.summarize_conversation(
                profile_id=profile_id,
                session_id=session_id,
                messages=messages,
            )
        except Exception as e:
            logger.warning(f"Background memory extraction/summarization error for session {session_id}: {e}")


async def run_memory_decay_task() -> None:
    """Scheduled maintenance job to decay old unreinforced memories."""
    settings = get_settings()
    async with async_session() as db:
        try:
            profile_repo = ProfileRepository(db)
            profiles = await profile_repo.get_all()
            memory_service = MemoryService(session=db, settings=settings)

            total_pruned = 0
            for p in profiles:
                pruned = await memory_service.decay_old_records(profile_id=p.id)
                total_pruned += pruned

            logger.info(f"Memory decay task completed. Pruned {total_pruned} weak memories.")
        except Exception as e:
            logger.warning(f"Memory decay maintenance task failed: {e}")


# Backward compatibility
run_memory_extraction_task = run_memory_decay_task
