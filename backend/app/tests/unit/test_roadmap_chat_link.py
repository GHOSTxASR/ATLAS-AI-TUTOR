"""A roadmap topic has one chat thread, and studying it moves the topic on.

Threads carried no reference to the topic they were opened from, so every visit
to a node started another identical conversation, and nothing done in a chat
was ever reflected back onto the roadmap.
"""

from __future__ import annotations

import pytest


@pytest.fixture
async def db(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path / "link-data"))

    from app.config import get_settings
    from app.db import database
    from app.db.models import Base

    get_settings.cache_clear()
    settings = get_settings()
    settings.paths.sqlite_dir.mkdir(parents=True, exist_ok=True)
    database._configure(settings)
    async with database._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with database.async_session() as session:
        yield session


async def _profile(db):
    from app.db.repositories.profile_repo import ProfileRepository

    return await ProfileRepository(db).create(name="Learner", profile_type="GATE")


async def _node(db, profile_id: str, title: str):
    """A real roadmap node.

    Chat sessions carry a foreign key to roadmap_nodes, so a made-up id is
    rejected outright -- which is the constraint doing its job.
    """
    from app.db.models import Roadmap, RoadmapNode

    roadmap = Roadmap(profile_id=profile_id, title="Test Roadmap", mode="strict", version=1)
    db.add(roadmap)
    await db.flush()

    node = RoadmapNode(
        roadmap_id=roadmap.id,
        profile_id=profile_id,
        title=title,
        node_type="topic",
    )
    db.add(node)
    await db.flush()
    return node


async def test_topic_resolves_to_one_thread(db):
    from app.services.chat_service import ChatService

    profile = await _profile(db)
    service = ChatService(db)

    node = await _node(db, profile.id, "Graph Algorithms")
    first, created_first = await service.session_for_topic(
        profile.id, node.title, roadmap_node_id=node.id
    )
    second, created_second = await service.session_for_topic(
        profile.id, node.title, roadmap_node_id=node.id
    )

    assert created_first is True
    assert created_second is False
    assert first.id == second.id


async def test_renamed_thread_is_still_found_by_its_topic(db):
    """The node id is the key precisely so auto-naming cannot orphan a thread."""
    from app.schemas.chat import ChatSessionUpdate
    from app.services.chat_service import ChatService

    profile = await _profile(db)
    service = ChatService(db)

    node = await _node(db, profile.id, "Network Flow")
    original, _ = await service.session_for_topic(
        profile.id, node.title, roadmap_node_id=node.id
    )
    await service.update_session(
        profile.id, original.id, ChatSessionUpdate(title="Max-Flow Min-Cut, Explained")
    )

    found, created = await service.session_for_topic(
        profile.id, node.title, roadmap_node_id=node.id
    )
    assert created is False
    assert found.id == original.id


async def test_thread_predating_the_link_is_adopted(db):
    """Existing threads matched by title get the node id attached on first use."""
    from app.schemas.chat import ChatSessionCreate
    from app.services.chat_service import ChatService

    profile = await _profile(db)
    service = ChatService(db)

    node = await _node(db, profile.id, "Sorting Networks")
    legacy = await service.create_session(profile.id, ChatSessionCreate(title=node.title))
    assert legacy.roadmap_node_id is None

    found, created = await service.session_for_topic(
        profile.id, node.title, roadmap_node_id=node.id
    )
    assert created is False
    assert found.id == legacy.id
    assert found.roadmap_node_id == node.id


async def test_different_topics_get_different_threads(db):
    from app.services.chat_service import ChatService

    profile = await _profile(db)
    service = ChatService(db)

    node_a = await _node(db, profile.id, "Topic A")
    node_b = await _node(db, profile.id, "Topic B")
    a, _ = await service.session_for_topic(profile.id, node_a.title, roadmap_node_id=node_a.id)
    b, _ = await service.session_for_topic(profile.id, node_b.title, roadmap_node_id=node_b.id)
    assert a.id != b.id
