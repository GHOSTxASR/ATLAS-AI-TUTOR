from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, Roadmap, RoadmapEdge, RoadmapNode
from app.db.repositories.graph_repo import GraphRepository
from app.db.repositories.memory_repo import MemoryRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.services.unified_context_service import UnifiedContextService


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
async def test_unified_context_combination(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "learningos-data"))
    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Unified Learner", profile_type="GATE")

    # 1. Populate Memory Pillar
    memory_repo = MemoryRepository(async_db_session)
    await memory_repo.create(
        profile_id=profile.id,
        category="weakness",
        subject="Recursion",
        content="Struggles with stack overflow base cases in tree traversal",
        confidence=0.9,
    )
    await memory_repo.create(
        profile_id=profile.id,
        category="strength",
        subject="Asymptotic Analysis",
        content="Strong mastery of Big-O complexity proofs",
        confidence=0.95,
    )
    await memory_repo.create(
        profile_id=profile.id,
        category="profile",
        subject="learning_style",
        content="Visual learner who prefers diagrams and step-by-step assembly lines",
        confidence=1.0,
    )

    # 2. Populate Roadmap & Syllabus Pillar
    roadmap = Roadmap(profile_id=profile.id, title="GATE Algorithms Syllabus", mode="strict", is_active=True)
    async_db_session.add(roadmap)
    await async_db_session.flush()

    node1 = RoadmapNode(
        roadmap_id=roadmap.id,
        profile_id=profile.id,
        title="Recursion Trees",
        node_type="topic",
        status="in_progress",
        mastery_score=0.45,
    )
    node2 = RoadmapNode(
        roadmap_id=roadmap.id,
        profile_id=profile.id,
        title="Divide and Conquer",
        node_type="topic",
        status="not_started",
        mastery_score=0.0,
    )
    async_db_session.add_all([node1, node2])
    await async_db_session.flush()

    async_db_session.add(
        RoadmapEdge(
            roadmap_id=roadmap.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            edge_type="sequential",
        )
    )
    await async_db_session.commit()

    # 3. Populate Knowledge Graph Pillar
    graph_repo = GraphRepository(settings=get_settings())
    n_rec = await graph_repo.add_node(
        profile_id=profile.id,
        label="Recursion",
        node_type="concept",
        description="Self-referential mathematical formulations",
        mastery_score=0.5,
    )
    n_master = await graph_repo.add_node(
        profile_id=profile.id,
        label="Master Theorem",
        node_type="concept",
        description="Closed form solution for recurrence relations",
        mastery_score=0.8,
    )
    await graph_repo.add_edge(
        profile_id=profile.id,
        source=n_rec["id"],
        target=n_master["id"],
        edge_type="prerequisite_of",
    )

    # 4. Build Unified Context
    service = UnifiedContextService(session=async_db_session)
    unified_ctx = await service.build_unified_context(
        profile_id=profile.id,
        query="How do I analyze the time complexity of recursion trees?",
        mode="teaching",
        roadmap_node_id=node1.id,
    )

    # 5. Verify Unified Context Integrity
    # Memory checks
    assert len(unified_ctx.memory.weaknesses) >= 1
    assert "Recursion" in unified_ctx.memory.weaknesses[0]
    assert len(unified_ctx.memory.strengths) >= 1
    assert "Visual learner" in (unified_ctx.memory.learning_style or "")

    # Roadmap checks
    assert unified_ctx.roadmap.active_topic == "Recursion Trees"
    assert "Divide and Conquer" in unified_ctx.roadmap.next_topics

    # Knowledge Graph checks
    assert unified_ctx.graph.matched_concept == "Recursion"
    assert "Self-referential" in (unified_ctx.graph.concept_description or "")
    assert "Master Theorem" in unified_ctx.graph.prerequisite_concepts

    # Syllabus checks
    assert unified_ctx.syllabus.syllabus_title == "GATE Algorithms Syllabus"
    assert unified_ctx.syllabus.current_chapter == "Recursion Trees"

    # Full prompt verification
    prompt = unified_ctx.system_prompt
    assert "### 1. LEARNER MEMORY PROFILE:" in prompt
    assert "### 2. CURRICULUM & ROADMAP PROGRESSION:" in prompt
    assert "### 3. KNOWLEDGE GRAPH SEMANTIC MAP:" in prompt
    assert "### 4. SYLLABUS SCOPE:" in prompt
    assert "### 5. RETRIEVED DOCUMENT KNOWLEDGE (RAG):" in prompt
    assert unified_ctx.total_tokens > 50
