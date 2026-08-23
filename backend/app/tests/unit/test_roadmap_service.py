from __future__ import annotations

from typing import AsyncIterator
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db.repositories.profile_repo import ProfileRepository
from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk
from app.schemas.roadmap import RoadmapCreate, RoadmapNodeUpdate
from app.services.roadmap_service import RoadmapService


class MockRoadmapLLM(BaseModelClient):
    """Mock LLM for adaptive and hybrid roadmap generation."""

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        content = messages[-1].content
        if "bridge" in content:
            # Hybrid bridge response
            return ChatResponse(
                content='[{"title": "Basic Calculus Concepts", "description": "Limits and fundamentals", "prerequisite_for_topic": "1D Motion"}]'
            )
        else:
            # Adaptive DAG response
            return ChatResponse(
                content='{\n'
                        '  "ordered_nodes": [\n'
                        '    {"temp_id": "t1", "title": "Foundations of Mechanics", "description": "Basics", "node_type": "topic"},\n'
                        '    {"temp_id": "t2", "title": "1D Motion", "description": "Kinematics", "node_type": "topic"},\n'
                        '    {"temp_id": "t3", "title": "Newton\'s Laws", "description": "Dynamics", "node_type": "topic"}\n'
                        '  ],\n'
                        '  "dependencies": [\n'
                        '    {"from_temp_id": "t1", "to_temp_id": "t2", "edge_type": "prerequisite"},\n'
                        '    {"from_temp_id": "t2", "to_temp_id": "t3", "edge_type": "prerequisite"}\n'
                        '  ]\n'
                        '}'
            )

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        pass

    def get_provider_name(self) -> str:
        return "mock_roadmap_llm"


@pytest.fixture
async def async_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await engine.dispose()


SAMPLE_SYLLABUS = (
    "# Physics Mechanics\n"
    "## Kinematics\n"
    "### 1D Motion\n"
    "- Velocity and acceleration\n"
    "### 2D Motion\n"
    "- Projectiles\n"
    "## Dynamics\n"
    "### Newton's Laws\n"
    "- Inertia and force\n"
)


@pytest.mark.asyncio
async def test_roadmap_strict_mode(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Strict Learner", profile_type="JEE")

    service = RoadmapService(session=async_db_session)

    # 1. Generate Strict Mode Roadmap
    req = RoadmapCreate(syllabus_text=SAMPLE_SYLLABUS, mode="strict", title="Physics Strict Roadmap")
    roadmap = await service.generate_roadmap(profile.id, req)

    assert roadmap.mode == "strict"
    assert roadmap.version == 1
    assert roadmap.is_active is True
    assert len(roadmap.nodes) >= 6  # 1 Subject + 2 Chapters + 3 Topics
    assert len(roadmap.edges) >= 2  # Sequential edges between topics

    # Verify first topic unlocked, subsequent topic locked
    topic_nodes = [n for n in roadmap.nodes if n.node_type == "topic"]
    assert topic_nodes[0].unlocked is True
    assert topic_nodes[1].unlocked is False


@pytest.mark.asyncio
async def test_roadmap_adaptive_mode(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    monkeypatch.setattr("app.services.roadmap_service.get_model_client", lambda s: MockRoadmapLLM())

    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Adaptive Learner", profile_type="GATE")

    service = RoadmapService(session=async_db_session)

    # Generate Adaptive Mode Roadmap
    req = RoadmapCreate(syllabus_text=SAMPLE_SYLLABUS, mode="adaptive", title="Adaptive CS Roadmap")
    roadmap = await service.generate_roadmap(profile.id, req)

    assert roadmap.mode == "adaptive"
    assert len(roadmap.nodes) == 3
    assert all(n.ai_generated for n in roadmap.nodes)
    assert len(roadmap.edges) == 2


@pytest.mark.asyncio
async def test_roadmap_hybrid_mode(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    monkeypatch.setattr("app.services.roadmap_service.get_model_client", lambda s: MockRoadmapLLM())

    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Hybrid Learner", profile_type="JEE")

    service = RoadmapService(session=async_db_session)

    # Generate Hybrid Mode Roadmap
    req = RoadmapCreate(syllabus_text=SAMPLE_SYLLABUS, mode="hybrid", title="Hybrid Mechanics Roadmap")
    roadmap = await service.generate_roadmap(profile.id, req)

    assert roadmap.mode == "hybrid"
    bridge_nodes = [n for n in roadmap.nodes if n.node_type == "bridge"]
    assert len(bridge_nodes) >= 1
    assert "Basic Calculus Concepts" in bridge_nodes[0].title


@pytest.mark.asyncio
async def test_node_status_unlocks_and_progress(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "atlas-data"))
    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Progress Learner", profile_type="JEE")

    service = RoadmapService(session=async_db_session)
    req = RoadmapCreate(syllabus_text=SAMPLE_SYLLABUS, mode="strict")
    roadmap = await service.generate_roadmap(profile.id, req)

    node1 = next(n for n in roadmap.nodes if n.title == "1D Motion")
    node2 = next(n for n in roadmap.nodes if n.title == "2D Motion")

    # 1. Update Node 1 to completed
    await service.update_node_status(
        profile.id, roadmap.id, node1.id, RoadmapNodeUpdate(status="completed", mastery_score=0.9)
    )

    # 2. Re-fetch roadmap and check Node 2 unlock state & progress
    updated_roadmap = await service.get_active_roadmap(profile.id)
    updated_topic2 = next(n for n in updated_roadmap.nodes if n.id == node2.id)
    assert updated_topic2.unlocked is True
    assert updated_roadmap.progress.completed_nodes == 1
    assert updated_roadmap.progress.completion_percentage > 0.0
