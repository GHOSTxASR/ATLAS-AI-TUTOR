from __future__ import annotations

from typing import AsyncIterator
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db.repositories.profile_repo import ProfileRepository
from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk
from app.schemas.memory import MemoryCreate, MemoryUpdate
from app.services.memory_service import MemoryService


class MockExtractionLLM(BaseModelClient):
    """Mock LLM returning structured memory extraction and conversation summaries."""

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        content = messages[-1].content
        if "extraction" in messages[0].content or "JSON" in content:
            # Memory extraction response
            return ChatResponse(
                content='[{"category": "weakness", "subject": "Graph Theory", "content": "Confuses BFS and DFS traversal queues", "confidence": 0.85}, '
                        '{"category": "preference", "subject": "General", "content": "Prefers visual step-by-step trace", "confidence": 0.90}]'
            )
        else:
            # Summarization response
            return ChatResponse(
                content="Learner reviewed tree traversals and practiced binary search problems. Clarified queue mechanisms."
            )

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="Mock stream", done=True)

    async def close(self) -> None:
        pass

    def get_provider_name(self) -> str:
        return "mock"


@pytest.fixture
async def async_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_memory_service_crud_and_learner_context(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Learner Context User", profile_type="JEE")

    service = MemoryService(session=async_db_session)

    # 1. Create memories
    mem1 = await service.create_memory(
        profile_id=profile.id,
        data=MemoryCreate(category="strength", subject="Kinematics", content="Mastered 1D motion equations", confidence=0.9),
    )
    mem2 = await service.create_memory(
        profile_id=profile.id,
        data=MemoryCreate(category="weakness", subject="Optics", content="Struggles with lens formula signs", confidence=0.8),
    )
    mem3 = await service.create_memory(
        profile_id=profile.id,
        data=MemoryCreate(category="preference", content="Prefers real-life analogies", confidence=1.0),
    )

    assert mem1.embedding_id is not None
    assert mem2.embedding_id is not None
    assert mem3.embedding_id is not None

    # 2. Learner Profile Context formatting
    context_str = await service.get_learner_profile_context(profile.id)
    assert "<LEARNER_PROFILE>" in context_str
    assert "Mastered 1D motion equations" in context_str
    assert "Struggles with lens formula signs" in context_str
    assert "Prefers real-life analogies" in context_str

    # 3. Update memory
    updated = await service.update_memory(
        profile.id, mem2.id, MemoryUpdate(confidence=0.95, content="Solidifying lens formula signs")
    )
    assert updated.confidence == 0.95
    assert updated.content == "Solidifying lens formula signs"

    # 4. Delete memory
    await service.delete_memory(profile.id, mem1.id)
    remaining = await service.list_memories(profile.id)
    assert len(remaining) == 2


@pytest.mark.asyncio
async def test_memory_extraction_and_summarization(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    monkeypatch.setattr("app.services.memory_service.get_model_client", lambda s: MockExtractionLLM())

    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Extraction Learner", profile_type="GATE")

    service = MemoryService(session=async_db_session)

    messages = [
        ChatMessage(role="user", content="I keep confusing when to use BFS vs DFS in graph cycles."),
        ChatMessage(role="assistant", content="Let's trace both step by step with a queue and stack visualization."),
    ]

    # Run extraction
    extracted = await service.extract_memories_from_conversation(
        profile_id=profile.id, session_id="session-123", messages=messages
    )

    assert len(extracted) >= 2
    categories = {m.category for m in extracted}
    assert "weakness" in categories
    assert "preference" in categories

    # Run summarization
    summary = await service.summarize_conversation(
        profile_id=profile.id, session_id="session-123", messages=messages
    )
    assert "traversals" in summary
