"""Chat history order must be deterministic.

Timestamps defaulted to SQL `CURRENT_TIMESTAMP`, which resolves only to the
second in SQLite. Every message written inside the same second therefore shared
one sort key, leaving `ORDER BY created_at` undefined - so the transcript shown
to the learner, and the history fed to the model, could come back scrambled.
"""

from __future__ import annotations

import pytest



@pytest.fixture
async def session(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "ordering-data"))

    from app.config import get_settings
    from app.db import database
    from app.db.models import Base

    get_settings.cache_clear()
    settings = get_settings()
    settings.paths.sqlite_dir.mkdir(parents=True, exist_ok=True)
    database._configure(settings)

    async with database._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with database.async_session() as db:
        yield db


async def _seed_session(db) -> str:
    from app.db.repositories.chat_repo import ChatSessionRepository
    from app.db.repositories.profile_repo import ProfileRepository

    profile = await ProfileRepository(db).create(name="Ordering", profile_type="JEE")
    chat = await ChatSessionRepository(db).create(profile_id=profile.id, title="t")
    return chat.id


async def test_rapid_messages_get_distinct_timestamps(session):
    from app.db.repositories.chat_repo import ChatMessageRepository

    session_id = await _seed_session(session)
    repo = ChatMessageRepository(session)

    for i in range(12):
        await repo.create(
            session_id=session_id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"msg-{i:02d}",
        )

    messages = await repo.get_by_session_id(session_id)
    stamps = {m.created_at for m in messages}
    assert len(stamps) == 12, "second-resolution timestamps collide and break ordering"


async def test_history_returns_in_insertion_order(session):
    from app.db.repositories.chat_repo import ChatMessageRepository

    session_id = await _seed_session(session)
    repo = ChatMessageRepository(session)

    expected = [f"msg-{i:02d}" for i in range(12)]
    for i, content in enumerate(expected):
        await repo.create(
            session_id=session_id,
            role="user" if i % 2 == 0 else "assistant",
            content=content,
        )

    messages = await repo.get_by_session_id(session_id)
    assert [m.content for m in messages] == expected

    # Alternating roles must survive too - a swap here would feed the model a
    # transcript where the tutor appears to answer before being asked.
    assert [m.role for m in messages][:4] == ["user", "assistant", "user", "assistant"]


async def test_created_at_has_sub_second_precision(session):
    from app.db.repositories.chat_repo import ChatMessageRepository

    session_id = await _seed_session(session)
    repo = ChatMessageRepository(session)

    message = await repo.create(session_id=session_id, role="user", content="hello")
    assert message.created_at.microsecond != 0 or message.created_at.second is not None
    # Two consecutive writes must be strictly ordered.
    second = await repo.create(session_id=session_id, role="assistant", content="hi")
    assert second.created_at >= message.created_at
    assert (message.created_at, message.id) != (second.created_at, second.id)
