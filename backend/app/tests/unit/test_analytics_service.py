from __future__ import annotations

from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, MemoryRecord, Roadmap, RoadmapNode
from app.db.repositories.profile_repo import ProfileRepository
from app.schemas.analytics import AnalyticsEventCreate
from app.services.analytics_service import AnalyticsService


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
async def test_analytics_service_overview_and_mastery(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "learningos-data"))
    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Analytics Learner", profile_type="JEE")

    # 1. Create Roadmap with mixed node mastery and statuses
    roadmap = Roadmap(profile_id=profile.id, title="Physics Roadmap", mode="strict", is_active=True)
    async_db_session.add(roadmap)
    await async_db_session.flush()

    # Topic 1: Completed, High mastery (0.9)
    async_db_session.add(
        RoadmapNode(
            roadmap_id=roadmap.id,
            profile_id=profile.id,
            title="Kinematics 1D",
            node_type="topic",
            status="completed",
            mastery_score=0.9,
            time_spent_minutes=45,
            completed_at=datetime.now(timezone.utc),
        )
    )
    # Topic 2: In Progress, Moderate mastery (0.6)
    async_db_session.add(
        RoadmapNode(
            roadmap_id=roadmap.id,
            profile_id=profile.id,
            title="Newton's Laws",
            node_type="topic",
            status="in_progress",
            mastery_score=0.6,
            time_spent_minutes=30,
        )
    )
    # Topic 3: Not Started, Zero mastery
    async_db_session.add(
        RoadmapNode(
            roadmap_id=roadmap.id,
            profile_id=profile.id,
            title="Work and Energy",
            node_type="topic",
            status="not_started",
            mastery_score=0.0,
            time_spent_minutes=0,
        )
    )
    await async_db_session.commit()

    service = AnalyticsService(session=async_db_session)

    # 2. Test Overview
    overview = await service.get_overview(profile.id)
    assert overview.total_topics == 3
    assert overview.completed_topics == 1
    assert overview.in_progress_topics == 1
    assert overview.not_started_topics == 1
    assert overview.completion_percentage == 33.3
    assert overview.average_mastery == 0.5
    assert overview.total_study_minutes >= 75

    # 3. Test Mastery Distribution
    mastery = await service.get_mastery_distribution(profile.id)
    assert mastery.mastered_count == 1      # Kinematics 1D (0.9)
    assert mastery.proficient_count == 1    # Newton's Laws (0.6)
    assert mastery.unstarted_count == 1     # Work and Energy (0.0)
    assert mastery.needs_practice_count == 0


@pytest.mark.asyncio
async def test_analytics_service_events_heatmap_and_weaknesses(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "learningos-data"))
    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Heatmap Learner", profile_type="GATE")

    service = AnalyticsService(session=async_db_session)

    # 1. Log study events
    ev1 = await service.log_event(
        profile.id,
        AnalyticsEventCreate(event_type="time_logged", value=30, metadata_json='{"subject": "Algorithms"}'),
    )
    assert ev1.id is not None

    # 2. Add a memory weakness
    async_db_session.add(
        MemoryRecord(
            profile_id=profile.id,
            category="weakness",
            subject="Algorithms",
            content="Confuses dynamic programming memoization with tabulation",
            confidence=0.8,
            is_active=True,
        )
    )
    await async_db_session.commit()

    # 3. Test Heatmap
    heatmap = await service.get_heatmap(profile.id, days=7)
    assert len(heatmap) == 7
    total_mins = sum(h.minutes for h in heatmap)
    assert total_mins >= 30

    # 4. Test Weaknesses
    weaknesses = await service.get_weaknesses(profile.id)
    assert len(weaknesses) >= 1
    assert "memoization" in (weaknesses[0].title + " " + weaknesses[0].reason)
