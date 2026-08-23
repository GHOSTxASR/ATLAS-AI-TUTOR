from __future__ import annotations

from typing import AsyncIterator
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db.repositories.chat_repo import ChatSessionRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk
from app.exceptions import AtlasError
from app.schemas.chat import TutorChatRequest
from app.services.tutor_orchestrator import TutorOrchestrator


class MockTutorLLM(BaseModelClient):
    """Mock LLM capturing mode-specific prompts and returning simulated tutor responses."""

    def __init__(self):
        self.last_system_prompt: str = ""

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        for msg in messages:
            if msg.role == "system":
                self.last_system_prompt = msg.content
        return ChatResponse(content="Tutor mode response completed.")

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="Tutor stream", done=False)
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        pass

    def get_provider_name(self) -> str:
        return "mock_tutor_llm"


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
async def test_tutor_mode_prompt_construction(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    from app.config import get_settings
    get_settings.cache_clear()

    orchestrator = TutorOrchestrator(session=async_db_session)

    # 1. Teaching Mode
    p_teach = orchestrator.build_system_prompt(
        mode="teaching",
        profile_name="Alex",
        profile_type="GATE",
        topic_context="Dynamic Programming",
    )
    assert "TEACHING (Deep Conceptual Learning)" in p_teach
    assert "Socratic check-for-understanding" in p_teach
    assert "Dynamic Programming" in p_teach

    # 2. Revision Mode
    p_rev = orchestrator.build_system_prompt(
        mode="revision",
        profile_name="Alex",
        profile_type="GATE",
        topic_context="Dynamic Programming",
    )
    assert "REVISION (High-Yield Rapid Review)" in p_rev
    assert "Highlight core definitions, critical equations" in p_rev

    # 3. Summary Mode
    p_sum = orchestrator.build_system_prompt(
        mode="summary",
        profile_name="Alex",
        profile_type="GATE",
        topic_context="Dynamic Programming",
    )
    assert "SUMMARY (Executive TL;DR Synthesis)" in p_sum
    assert "3-5 structured bullet points" in p_sum

    # 4. General Knowledge Mode
    p_gen = orchestrator.build_system_prompt(
        mode="general_knowledge",
        profile_name="Alex",
        profile_type="GATE",
        topic_context="Quantum Computing",
    )
    assert "GENERAL KNOWLEDGE (Interdisciplinary Curiosity)" in p_gen
    assert "beyond strict syllabus boundaries" in p_gen


@pytest.mark.asyncio
async def test_tutor_orchestrator_chat_turn(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    mock_llm = MockTutorLLM()
    monkeypatch.setattr("app.services.tutor_orchestrator.get_model_client", lambda s: mock_llm)

    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Tutor Student", profile_type="JEE")

    orchestrator = TutorOrchestrator(session=async_db_session)

    # Test Revision mode chat turn
    req = TutorChatRequest(
        content="Summarize the Doppler effect equations.",
        mode="revision",
    )
    resp = await orchestrator.handle_chat_turn(profile.id, req)

    assert resp.mode == "revision"
    assert resp.session_id is not None
    assert resp.content == "Tutor mode response completed."
    assert "REVISION (High-Yield Rapid Review)" in mock_llm.last_system_prompt


@pytest.mark.asyncio
async def test_tutor_chat_rejects_session_from_another_profile(async_db_session: AsyncSession):
    profile_repo = ProfileRepository(async_db_session)
    owner = await profile_repo.create(name="Session Owner", profile_type="GATE")
    other_profile = await profile_repo.create(name="Other Learner", profile_type="GATE")
    session = await ChatSessionRepository(async_db_session).create(
        profile_id=owner.id,
        title="Private session",
    )

    orchestrator = TutorOrchestrator(session=async_db_session)

    with pytest.raises(AtlasError) as error:
        await orchestrator.handle_chat_turn(
            other_profile.id,
            TutorChatRequest(session_id=session.id, content="Attempted cross-profile access"),
        )

    assert error.value.status_code == 404
