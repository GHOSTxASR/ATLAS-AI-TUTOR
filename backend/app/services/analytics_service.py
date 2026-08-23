from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.models import (
    AnalyticsEvent,
    ChatSession,
    Document,
    Note,
    QuizAttempt,
)
from app.db.repositories.analytics_repo import AnalyticsRepository
from app.db.repositories.memory_repo import MemoryRepository
from app.db.repositories.notes_repo import NotesRepository
from app.db.repositories.profile_repo import ProfileRepository
from app.db.repositories.quiz_repo import QuizRepository
from app.db.repositories.roadmap_repo import RoadmapRepository
from app.exceptions import AtlasError
from app.schemas.analytics import (
    ActivityHeatmapItem,
    AnalyticsEventCreate,
    AnalyticsOverviewResponse,
    ChapterProgressItem,
    LearningVelocityPoint,
    MasteryDistributionResponse,
    MasteryTierTopic,
    StudyTimeBreakdown,
    WeaknessConcept,
)

logger = logging.getLogger(__name__)

# Mastery tiers, kept in step with the labels rendered on the analytics page.
MASTERED_THRESHOLD = 0.85
PROFICIENT_THRESHOLD = 0.60


class AnalyticsService:
    """Service providing learning progress metrics, mastery tracking, and full study analytics."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.repo = AnalyticsRepository(session)
        self.roadmap_repo = RoadmapRepository(session)
        self.memory_repo = MemoryRepository(session)
        self.profile_repo = ProfileRepository(session)
        self.notes_repo = NotesRepository(session)
        self.quiz_repo = QuizRepository(session)

    async def _require_profile(self, profile_id: str) -> None:
        profile = await self.profile_repo.get_by_id(profile_id)
        if not profile:
            raise AtlasError(status_code=404, code="NOT_FOUND", message="Profile not found")

    async def log_event(self, profile_id: str, data: AnalyticsEventCreate) -> AnalyticsEvent:
        """Record an analytics interaction event."""
        await self._require_profile(profile_id)
        return await self.repo.log_event(
            profile_id=profile_id,
            event_type=data.event_type,
            entity_type=data.entity_type,
            entity_id=data.entity_id,
            value=data.value,
            metadata_json=data.metadata_json,
        )

    async def get_overview(self, profile_id: str) -> AnalyticsOverviewResponse:
        """Calculate high-level study metrics, topic completion, mastery, chapter progress, and time breakdown."""
        await self._require_profile(profile_id)

        # 1. Roadmap topic stats & Chapter progress
        active_roadmap = await self.roadmap_repo.get_active_roadmap(profile_id)
        total_topics = 0
        completed_topics = 0
        in_progress_topics = 0
        not_started_topics = 0
        mastery_sum = 0.0
        total_node_minutes = 0
        chapter_progress_map: dict[str, dict[str, Any]] = {}

        if active_roadmap and active_roadmap.nodes:
            topic_nodes = [n for n in active_roadmap.nodes if n.node_type in ("topic", "bridge", "concept")]
            total_topics = len(topic_nodes) or len(active_roadmap.nodes)

            # Node ID to Title map for chapter grouping
            parent_map = {n.id: n.title for n in active_roadmap.nodes if n.node_type in ("unit", "chapter", "module")}

            for n in active_roadmap.nodes:
                total_node_minutes += n.time_spent_minutes
                if n.node_type in ("topic", "bridge", "concept"):
                    if n.status == "completed":
                        completed_topics += 1
                    elif n.status == "in_progress":
                        in_progress_topics += 1
                    else:
                        not_started_topics += 1

                    mastery_sum += n.mastery_score

                    # Group by parent chapter or default to curriculum title
                    chapter_name = parent_map.get(n.parent_id or "", active_roadmap.title)
                    if chapter_name not in chapter_progress_map:
                        chapter_progress_map[chapter_name] = {
                            "total": 0,
                            "completed": 0,
                            "mastery_sum": 0.0,
                        }
                    chapter_progress_map[chapter_name]["total"] += 1
                    if n.status == "completed":
                        chapter_progress_map[chapter_name]["completed"] += 1
                    chapter_progress_map[chapter_name]["mastery_sum"] += n.mastery_score

        completion_pct = round((completed_topics / total_topics * 100.0), 1) if total_topics > 0 else 0.0
        avg_mastery = round((mastery_sum / total_topics), 2) if total_topics > 0 else 0.0

        chapter_items = [
            ChapterProgressItem(
                chapter_title=cname,
                total_topics=cdata["total"],
                completed_topics=cdata["completed"],
                completion_percentage=round((cdata["completed"] / cdata["total"] * 100.0), 1) if cdata["total"] > 0 else 0.0,
                average_mastery=round((cdata["mastery_sum"] / cdata["total"]), 2) if cdata["total"] > 0 else 0.0,
            )
            for cname, cdata in chapter_progress_map.items()
        ]

        # 2. Detailed Study Time Breakdown
        chat_time_res = await self.session.execute(
            select(func.coalesce(func.sum(AnalyticsEvent.value), 0.0))
            .where(AnalyticsEvent.profile_id == profile_id)
            .where(AnalyticsEvent.event_type.in_(("chat_turn", "session_active")))
        )
        chat_mins = int(chat_time_res.scalar() or 0)

        quiz_time_res = await self.session.execute(
            select(func.coalesce(func.sum(AnalyticsEvent.value), 0.0))
            .where(AnalyticsEvent.profile_id == profile_id)
            .where(AnalyticsEvent.event_type.in_(("quiz_taken", "assessment_completed")))
        )
        quiz_mins = int(quiz_time_res.scalar() or 0)

        notes_time_res = await self.session.execute(
            select(func.coalesce(func.sum(AnalyticsEvent.value), 0.0))
            .where(AnalyticsEvent.profile_id == profile_id)
            .where(AnalyticsEvent.event_type.in_(("note_generated", "note_read")))
        )
        notes_mins = int(notes_time_res.scalar() or 0)

        time_logged_res = await self.session.execute(
            select(func.coalesce(func.sum(AnalyticsEvent.value), 0.0))
            .where(AnalyticsEvent.profile_id == profile_id)
            .where(AnalyticsEvent.event_type.in_(("time_logged", "topic_completed", "quiz_taken", "chat_turn", "note_generated", "note_read")))
        )
        logged_time_mins = int(time_logged_res.scalar() or 0)

        total_study_minutes = max(total_node_minutes, total_node_minutes + chat_mins + quiz_mins + notes_mins, logged_time_mins)
        breakdown = StudyTimeBreakdown(
            roadmap_minutes=total_node_minutes,
            chat_minutes=chat_mins,
            quiz_minutes=quiz_mins,
            notes_minutes=notes_mins,
            total_minutes=total_study_minutes,
        )

        # 3. Learning streak
        streak = await self.repo.compute_streak_days(profile_id)

        # 4. Total chat sessions
        sess_count_res = await self.session.execute(
            select(func.count(ChatSession.id)).where(ChatSession.profile_id == profile_id)
        )
        total_sessions = int(sess_count_res.scalar() or 0)

        # 5. Total documents
        doc_count_res = await self.session.execute(
            select(func.count(Document.id)).where(Document.profile_id == profile_id)
        )
        total_documents = int(doc_count_res.scalar() or 0)

        # 6. Total notes
        notes_count_res = await self.session.execute(
            select(func.count(Note.id)).where(Note.profile_id == profile_id)
        )
        total_notes = int(notes_count_res.scalar() or 0)

        # 7. Total quizzes and average score
        quiz_stats_res = await self.session.execute(
            select(
                func.count(QuizAttempt.id),
                func.coalesce(func.avg(QuizAttempt.score), 0.0),
            ).where(QuizAttempt.profile_id == profile_id)
        )
        total_quizzes, avg_quiz_score = quiz_stats_res.one()

        return AnalyticsOverviewResponse(
            completion_percentage=completion_pct,
            total_topics=total_topics,
            completed_topics=completed_topics,
            in_progress_topics=in_progress_topics,
            not_started_topics=not_started_topics,
            average_mastery=avg_mastery,
            total_study_minutes=total_study_minutes,
            active_streak_days=streak,
            total_sessions=total_sessions,
            total_documents=total_documents,
            total_notes=total_notes,
            total_quizzes_taken=int(total_quizzes or 0),
            average_quiz_score=round(float(avg_quiz_score or 0.0), 2),
            study_time_breakdown=breakdown,
            chapter_progress=chapter_items,
        )

    async def get_heatmap(self, profile_id: str, days: int = 30) -> list[ActivityHeatmapItem]:
        """Aggregate daily active minutes and interaction density for calendar heatmaps."""
        await self._require_profile(profile_id)
        raw_events = await self.repo.get_daily_activity(profile_id=profile_id, days=days)

        event_map = {r["date"]: r for r in raw_events}
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

        result: list[ActivityHeatmapItem] = []
        cur = start_date
        while cur <= end_date:
            cur_str = cur.isoformat()
            data = event_map.get(cur_str, {"minutes": 0, "events_count": 0})
            result.append(
                ActivityHeatmapItem(
                    date=cur_str,
                    minutes=int(data["minutes"]),
                    events_count=int(data["events_count"]),
                )
            )
            cur += timedelta(days=1)

        return result

    async def get_mastery_distribution(self, profile_id: str) -> MasteryDistributionResponse:
        """Categorize topics across 4 mastery tiers (Mastered, Proficient, Needs Practice, Unstarted)."""
        await self._require_profile(profile_id)
        active_roadmap = await self.roadmap_repo.get_active_roadmap(profile_id)

        response = MasteryDistributionResponse()
        if not active_roadmap or not active_roadmap.nodes:
            return response

        for n in active_roadmap.nodes:
            if n.node_type not in ("topic", "bridge", "concept"):
                continue

            tier_item = MasteryTierTopic(
                id=n.id,
                title=n.title,
                mastery_score=n.mastery_score,
                status=n.status,
            )

            # Thresholds must match the tier labels the UI prints
            # ("Mastered >85%", "Proficient 60-85%"). They were 0.8/0.5, so a
            # topic at 81% was reported as Mastered on a card claiming >85%.
            score = n.mastery_score
            if score >= MASTERED_THRESHOLD:
                response.mastered_count += 1
                response.mastered_topics.append(tier_item)
            elif score >= PROFICIENT_THRESHOLD:
                response.proficient_count += 1
                response.proficient_topics.append(tier_item)
            elif score > 0.0 or n.status == "in_progress":
                response.needs_practice_count += 1
                response.needs_practice_topics.append(tier_item)
            else:
                response.unstarted_count += 1
                response.unstarted_topics.append(tier_item)

        return response

    async def get_learning_velocity(
        self, profile_id: str, days: int = 14
    ) -> list[LearningVelocityPoint]:
        """Compute rolling daily topic completion count and study minutes."""
        await self._require_profile(profile_id)
        raw_velocity = await self.repo.get_daily_velocity(profile_id=profile_id, days=days)

        v_map = {r["date"]: r for r in raw_velocity}
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

        points: list[LearningVelocityPoint] = []
        cur = start_date
        while cur <= end_date:
            cur_str = cur.isoformat()
            entry = v_map.get(cur_str, {"topics_completed": 0, "study_minutes": 0})
            points.append(
                LearningVelocityPoint(
                    date=cur_str,
                    topics_completed=int(entry["topics_completed"]),
                    study_minutes=int(entry["study_minutes"]),
                )
            )
            cur += timedelta(days=1)

        return points

    async def get_weaknesses(self, profile_id: str) -> list[WeaknessConcept]:
        """Aggregate diagnosed learning weaknesses from roadmap node scores and memory records."""
        await self._require_profile(profile_id)
        weaknesses: list[WeaknessConcept] = []

        # 1. Low mastery roadmap nodes
        active_roadmap = await self.roadmap_repo.get_active_roadmap(profile_id)
        if active_roadmap and active_roadmap.nodes:
            for n in active_roadmap.nodes:
                if n.node_type in ("topic", "bridge") and n.status == "in_progress" and n.mastery_score < 0.5:
                    weaknesses.append(
                        WeaknessConcept(
                            id=n.id,
                            title=n.title,
                            subject=active_roadmap.title,
                            source="roadmap_node",
                            mastery_score=n.mastery_score,
                            reason=f"Current mastery is {int(n.mastery_score*100)}%. Requires targeted practice.",
                        )
                    )

        # 2. Diagnosed weakness records in Memory
        mem_records = await self.memory_repo.get_by_profile_id(profile_id, category="weakness")
        for m in mem_records:
            weaknesses.append(
                WeaknessConcept(
                    id=m.id,
                    title=m.subject,
                    subject=m.subject,
                    source="memory_record",
                    mastery_score=None,
                    reason=m.content,
                )
            )

        return weaknesses
