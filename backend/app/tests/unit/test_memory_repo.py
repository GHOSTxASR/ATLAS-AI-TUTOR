from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db.repositories.memory_repo import MemoryRepository
from app.db.repositories.profile_repo import ProfileRepository


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
async def test_memory_repo_crud_and_filtering(async_db_session: AsyncSession):
    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Memory Learner", profile_type="JEE")

    memory_repo = MemoryRepository(async_db_session)

    # 1. Create memories
    m1 = await memory_repo.create(
        profile_id=profile.id,
        category="weakness",
        subject="Calculus",
        content="Struggles with integration by parts",
        confidence=0.8,
    )
    m2 = await memory_repo.create(
        profile_id=profile.id,
        category="strength",
        subject="Algebra",
        content="Excels at quadratic equations",
        confidence=0.95,
    )

    # 2. List all
    all_mem = await memory_repo.get_by_profile_id(profile.id)
    assert len(all_mem) == 2

    # 3. Filter by category
    weaknesses = await memory_repo.get_by_profile_id(profile.id, category="weakness")
    assert len(weaknesses) == 1
    assert weaknesses[0].id == m1.id

    # 4. Filter by min_confidence
    high_conf = await memory_repo.get_by_profile_id(profile.id, min_confidence=0.9)
    assert len(high_conf) == 1
    assert high_conf[0].id == m2.id

    # 5. Update confidence
    updated = await memory_repo.update_confidence(m1.id, 0.15)
    assert updated is not None
    assert round(updated.confidence, 2) == 0.95


@pytest.mark.asyncio
async def test_memory_decay_and_pruning(async_db_session: AsyncSession):
    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Decay Learner", profile_type="GATE")

    memory_repo = MemoryRepository(async_db_session)

    # High confidence record
    await memory_repo.create(
        profile_id=profile.id,
        category="fact",
        content="Targeting top IITs",
        confidence=0.9,
    )
    # Low confidence record nearing decay threshold
    low_rec = await memory_repo.create(
        profile_id=profile.id,
        category="weakness",
        content="Uncertain about floating point representation",
        confidence=0.2,
    )

    # Apply decay (factor 0.9, threshold 0.19) -> 0.2 * 0.9 = 0.18 < 0.19 -> pruned
    pruned = await memory_repo.decay_confidences(profile_id=profile.id, decay_factor=0.9, prune_threshold=0.19)
    assert len(pruned) == 1
    assert pruned[0] == low_rec.id

    remaining = await memory_repo.get_by_profile_id(profile.id)
    assert len(remaining) == 1
    assert round(remaining[0].confidence, 2) == 0.81
