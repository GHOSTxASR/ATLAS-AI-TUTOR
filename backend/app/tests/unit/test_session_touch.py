"""A completed chat turn must bump its session to the top of the sidebar.

`BaseRepository.update()` with no changed fields emits no SQL, so SQLAlchemy's
`onupdate` never fired: `updated_at` stayed frozen at creation time and the
session list (ordered by `updated_at DESC`) never reflected recent use.
"""

from __future__ import annotations

import asyncio

import pytest


@pytest.fixture
async def db(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "touch-data"))

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


async def test_touch_advances_updated_at(db):
    from app.db.repositories.chat_repo import ChatSessionRepository
    from app.db.repositories.profile_repo import ProfileRepository

    profile = await ProfileRepository(db).create(name="Touch", profile_type="JEE")
    repo = ChatSessionRepository(db)
    chat = await repo.create(profile_id=profile.id, title="s")
    before = chat.updated_at

    await asyncio.sleep(0.02)
    await repo.touch(chat)

    refreshed = await repo.get_by_id(chat.id)
    assert refreshed.updated_at > before


async def test_touched_session_sorts_to_the_top(db):
    from app.db.repositories.chat_repo import ChatSessionRepository
    from app.db.repositories.profile_repo import ProfileRepository

    profile = await ProfileRepository(db).create(name="Touch", profile_type="JEE")
    repo = ChatSessionRepository(db)

    first = await repo.create(profile_id=profile.id, title="first")
    await asyncio.sleep(0.02)
    await repo.create(profile_id=profile.id, title="second")

    listed = await repo.get_by_profile_id(profile.id)
    assert [s.title for s in listed] == ["second", "first"]

    # Using the older session must move it back to the top.
    await asyncio.sleep(0.02)
    await repo.touch(first)

    listed = await repo.get_by_profile_id(profile.id)
    assert [s.title for s in listed] == ["first", "second"]
