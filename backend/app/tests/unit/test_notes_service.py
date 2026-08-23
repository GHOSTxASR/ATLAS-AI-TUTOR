from __future__ import annotations

from typing import AsyncIterator
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, Roadmap, RoadmapNode
from app.db.repositories.profile_repo import ProfileRepository
from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk
from app.schemas.notes import NoteCreate, NoteGenerateRequest, NoteUpdate
from app.services.notes_service import NotesService


class MockNoteLLM(BaseModelClient):
    """Mock LLM generating structured notes in markdown."""

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        content = messages[-1].content
        if "modality: 'cheat_sheet'" in content.lower():
            return ChatResponse(
                content="# Cheat Sheet: Binary Search\n\n| Case | Complexity |\n|---|---|\n| Best | O(1) |\n| Worst | O(log N) |"
            )
        elif "modality: 'revision_note'" in content.lower():
            return ChatResponse(
                content="# Revision Note: Binary Search\n\n## ⚡ Core Invariant\nArray must be monotonically ordered.\n\n## ⚠️ Pitfall\nAvoid integer overflow in mid calculation."
            )
        elif "modality: 'summary'" in content.lower():
            return ChatResponse(
                content="# Summary: Binary Search\n\n• Axiom: Halves search space.\n• Formula: T(N) = T(N/2) + 1.\n• Takeaway: Logarithmic time complexity."
            )
        else:
            return ChatResponse(
                content="# Lesson Note: Binary Search\n\n## 1. Executive Conceptual Foundation\nBinary search is a divide and conquer algorithm."
            )

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="Mock Note", done=True)

    async def close(self) -> None:
        pass

    def get_provider_name(self) -> str:
        return "mock_note_llm"


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
async def test_notes_generation_across_all_modalities(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    monkeypatch.setattr("app.services.notes_service.get_model_client", lambda s: MockNoteLLM())

    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Notes Scholar", profile_type="GATE")

    # Create Roadmap node to link note
    roadmap = Roadmap(profile_id=profile.id, title="Algorithms", mode="strict", is_active=True)
    async_db_session.add(roadmap)
    await async_db_session.flush()

    node = RoadmapNode(
        roadmap_id=roadmap.id,
        profile_id=profile.id,
        title="Binary Search",
        node_type="topic",
        status="in_progress",
    )
    async_db_session.add(node)
    await async_db_session.commit()

    service = NotesService(session=async_db_session)

    # 1. Test Lesson Note Generation
    n_lesson = await service.generate_note(
        profile.id,
        NoteGenerateRequest(topic_title="Binary Search", note_type="lesson_note", roadmap_node_id=node.id),
    )
    assert n_lesson.note_type == "lesson_note"
    assert "Lesson Note" in n_lesson.title
    assert "divide and conquer" in n_lesson.content.lower()

    # 2. Test Revision Note Generation
    n_rev = await service.generate_note(
        profile.id,
        NoteGenerateRequest(topic_title="Binary Search", note_type="revision_note", roadmap_node_id=node.id),
    )
    assert n_rev.note_type == "revision_note"
    assert "Revision Note" in n_rev.title
    assert "Core Invariant" in n_rev.content

    # 3. Test Cheat Sheet Generation
    n_cheat = await service.generate_note(
        profile.id,
        NoteGenerateRequest(topic_title="Binary Search", note_type="cheat_sheet", roadmap_node_id=node.id),
    )
    assert n_cheat.note_type == "cheat_sheet"
    assert "O(log N)" in n_cheat.content

    # 4. Test Summary Generation
    n_sum = await service.generate_note(
        profile.id,
        NoteGenerateRequest(topic_title="Binary Search", note_type="summary", roadmap_node_id=node.id),
    )
    assert n_sum.note_type == "summary"
    assert "Axiom" in n_sum.content

    # 5. List Notes with Filters
    all_notes = await service.list_notes(profile.id)
    assert len(all_notes) == 4

    rev_notes = await service.list_notes(profile.id, note_type="revision_note")
    assert len(rev_notes) == 1
    assert rev_notes[0].note_type == "revision_note"


@pytest.mark.asyncio
async def test_user_authored_note_crud(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Author Student", profile_type="JEE")

    service = NotesService(session=async_db_session)

    # 1. Create User Note
    user_note = await service.create_user_note(
        profile.id,
        NoteCreate(
            title="My Personal Calculus Notes",
            content="Integration by parts formula: uv - int(v du)",
            note_type="lesson_note",
            tags=["calculus", "math"],
        ),
    )
    assert user_note.source == "user_written"
    assert "calculus" in user_note.tags

    # 2. Get Note
    fetched = await service.get_note(profile.id, user_note.id)
    assert fetched.title == "My Personal Calculus Notes"

    # 3. Update Note
    updated = await service.update_note(
        profile.id,
        user_note.id,
        NoteUpdate(title="My Updated Calculus Notes", content="New calculus text"),
    )
    assert updated.title == "My Updated Calculus Notes"

    # 4. Delete Note
    deleted = await service.delete_note(profile.id, user_note.id)
    assert deleted is True

    remaining = await service.list_notes(profile.id)
    assert len(remaining) == 0
