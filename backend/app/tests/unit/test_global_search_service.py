from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import (
    Base,
    ChatMessage,
    ChatSession,
    Document,
    Note,
    Roadmap,
    RoadmapNode,
)
from app.db.repositories.graph_repo import GraphRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.schemas.search import GlobalSearchRequest
from app.services.global_search_service import GlobalSearchService


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
async def test_global_search_across_all_five_pillars(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Search Tester", profile_type="GATE")

    # 1. Chat Pillar
    session = ChatSession(profile_id=profile.id, title="Tree Algorithms Discussion")
    async_db_session.add(session)
    await async_db_session.flush()

    msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content="Binary trees have logarithmic height in balanced AVL trees.",
    )
    async_db_session.add(msg)

    # 2. Notes Pillar
    note = Note(
        profile_id=profile.id,
        title="Lesson Note: Binary Tree Traversals",
        content="Inorder, preorder, and postorder depth-first traversals on binary trees.",
        note_type="lesson_note",
        source="ai_generated",
    )
    async_db_session.add(note)

    # 3. Documents Pillar
    doc = Document(
        profile_id=profile.id,
        filename="binary_tree_structures.pdf",
        file_path=str(tmp_path / "binary_tree_structures.pdf"),
        content_hash="abc123hash",
        file_type="pdf",
        status="extracted",
    )
    async_db_session.add(doc)

    # 4. Roadmap Pillar
    roadmap = Roadmap(profile_id=profile.id, title="Data Structures", mode="strict", is_active=True)
    async_db_session.add(roadmap)
    await async_db_session.flush()

    node = RoadmapNode(
        roadmap_id=roadmap.id,
        profile_id=profile.id,
        title="Binary Search Trees",
        node_type="topic",
        status="in_progress",
    )
    async_db_session.add(node)
    await async_db_session.commit()

    # 5. Knowledge Graph Pillar
    graph_repo = GraphRepository(settings=get_settings())
    await graph_repo.add_node(
        profile_id=profile.id,
        label="Binary Heap",
        node_type="concept",
        description="Complete binary tree satisfying heap invariant property.",
        mastery_score=0.75,
    )

    # Execute Global Search
    service = GlobalSearchService(session=async_db_session)
    response = await service.global_search(
        profile_id=profile.id,
        request=GlobalSearchRequest(query="Binary", limit_per_category=5, include_semantic=False),
    )

    # Verify search found items across all 5 pillars
    assert response.total_results >= 5

    # 1. Chats
    assert len(response.chats) >= 1
    assert any("Binary" in c.snippet or "Binary" in c.title for c in response.chats)

    # 2. Notes
    assert len(response.notes) >= 1
    assert any("Binary" in n.title for n in response.notes)

    # 3. Documents
    assert len(response.documents) >= 1
    assert any("binary_tree" in d.title.lower() for d in response.documents)

    # 4. Graph
    assert len(response.graph) >= 1
    assert any("Binary Heap" in g.title for g in response.graph)

    # 5. Roadmap
    assert len(response.roadmap) >= 1
    assert any("Binary Search Trees" in r.title for r in response.roadmap)
