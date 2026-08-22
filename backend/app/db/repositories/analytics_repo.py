from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnalyticsEvent
from app.db.repositories.base import BaseRepository


# Event types that represent time actually spent studying. The heatmap and the
# study-time breakdown must agree on this set: the heatmap previously omitted
# note activity, so it under-reported the same days the breakdown counted.
STUDY_EVENT_TYPES = (
    "topic_completed",
    "topic_started",
    "quiz_taken",
    "assessment_completed",
    "chat_turn",
    "session_active",
    "note_generated",
    "note_read",
)


class AnalyticsRepository(BaseRepository[AnalyticsEvent]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=AnalyticsEvent, session=session)

    async def log_event(
        self,
        profile_id: str,
        event_type: str,
        entity_type: str = "roadmap_node",
        entity_id: str | None = None,
        value: float | None = None,
        metadata_json: str | None = None,
        occurred_at: datetime | None = None,
    ) -> AnalyticsEvent:
        """Record a study or progress analytics event."""
        return await self.create(
            profile_id=profile_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            value=value,
            metadata_json=metadata_json,
            occurred_at=occurred_at or datetime.now(timezone.utc),
        )

    async def get_events_by_profile(
        self,
        profile_id: str,
        event_type: str | None = None,
        since: datetime | None = None,
    ) -> Sequence[AnalyticsEvent]:
        """Fetch analytics events with optional type and date filters."""
        stmt = select(AnalyticsEvent).where(AnalyticsEvent.profile_id == profile_id)
        if event_type:
            stmt = stmt.where(AnalyticsEvent.event_type == event_type)
        if since:
            stmt = stmt.where(AnalyticsEvent.occurred_at >= since)

        stmt = stmt.order_by(AnalyticsEvent.occurred_at.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_daily_activity(
        self, profile_id: str, days: int = 30
    ) -> list[dict[str, Any]]:
        """Aggregate daily study minutes and interaction event counts."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        events = await self.get_events_by_profile(profile_id=profile_id, since=cutoff)

        daily_map: dict[str, dict[str, int]] = {}
        # Pre-fill all dates in range
        today = date.today()
        for i in range(days):
            d_str = (today - timedelta(days=days - 1 - i)).isoformat()
            daily_map[d_str] = {"minutes": 0, "events_count": 0}

        for ev in events:
            d_str = ev.occurred_at.strftime("%Y-%m-%d")
            if d_str not in daily_map:
                daily_map[d_str] = {"minutes": 0, "events_count": 0}

            daily_map[d_str]["events_count"] += 1
            if ev.event_type == "time_logged" and ev.value:
                daily_map[d_str]["minutes"] += int(ev.value)
            elif ev.event_type in STUDY_EVENT_TYPES:
                # Default 5 study minutes activity per interaction if no explicit duration was logged
                daily_map[d_str]["minutes"] += int(ev.value or 5)

        return [{"date": d, "minutes": val["minutes"], "events_count": val["events_count"]} for d, val in sorted(daily_map.items())]

    get_activity_by_day = get_daily_activity

    async def get_daily_velocity(
        self, profile_id: str, days: int = 14
    ) -> list[dict[str, Any]]:
        """Compute rolling daily topic completion count and study minutes."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        events = await self.get_events_by_profile(profile_id=profile_id, since=cutoff)

        v_map: dict[str, dict[str, int]] = {}
        today = date.today()
        for i in range(days):
            d_str = (today - timedelta(days=days - 1 - i)).isoformat()
            v_map[d_str] = {"topics_completed": 0, "study_minutes": 0}

        for ev in events:
            d_str = ev.occurred_at.strftime("%Y-%m-%d")
            if d_str not in v_map:
                v_map[d_str] = {"topics_completed": 0, "study_minutes": 0}

            if ev.event_type == "topic_completed":
                v_map[d_str]["topics_completed"] += 1
                v_map[d_str]["study_minutes"] += int(ev.value or 15)
            elif ev.event_type == "time_logged":
                v_map[d_str]["study_minutes"] += int(ev.value or 0)
            elif ev.event_type in ("quiz_taken", "chat_turn", "note_generated"):
                v_map[d_str]["study_minutes"] += int(ev.value or 5)

        return [
            {
                "date": d,
                "topics_completed": val["topics_completed"],
                "study_minutes": val["study_minutes"],
            }
            for d, val in sorted(v_map.items())
        ]

    async def compute_streak_days(self, profile_id: str) -> int:
        """Compute the current consecutive daily learning streak."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=60)
        events = await self.get_events_by_profile(profile_id=profile_id, since=cutoff)
        if not events:
            return 0

        active_dates = {ev.occurred_at.date() for ev in events}
        today = date.today()
        yesterday = today - timedelta(days=1)

        # Check if active today or yesterday to continue streak
        current = today if today in active_dates else yesterday
        if current not in active_dates:
            return 0

        streak = 0
        check_date = current
        while check_date in active_dates:
            streak += 1
            check_date -= timedelta(days=1)

        return streak

    async def delete_by_profile_id(self, profile_id: str) -> None:
        """Delete all analytics events for a profile."""
        await self.session.execute(
            delete(AnalyticsEvent).where(AnalyticsEvent.profile_id == profile_id)
        )
        await self.session.commit()


# Backward compatibility alias
AnalyticsRepo = AnalyticsRepository
