from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import QuizAttempt
from app.db.repositories.base import BaseRepository


class QuizRepository(BaseRepository[QuizAttempt]):
    def __init__(self, session: AsyncSession):
        super().__init__(model=QuizAttempt, session=session)

    async def create_attempt(
        self,
        profile_id: str,
        roadmap_node_id: str | None,
        mode: str,
        total_questions: int,
        questions_json: str,
        time_limit_seconds: int | None = None,
    ) -> QuizAttempt:
        """Create a new quiz session record."""
        return await self.create(
            profile_id=profile_id,
            roadmap_node_id=roadmap_node_id,
            mode=mode,
            total_questions=total_questions,
            questions_json=questions_json,
            time_limit_seconds=time_limit_seconds,
            started_at=datetime.now(timezone.utc),
        )

    async def get_attempt(self, attempt_id: str) -> QuizAttempt | None:
        """Fetch a quiz attempt by ID."""
        return await self.get_by_id(attempt_id)

    async def list_by_profile(
        self, profile_id: str, limit: int = 20
    ) -> Sequence[QuizAttempt]:
        """List past quiz attempts ordered by start date descending."""
        stmt = (
            select(QuizAttempt)
            .where(QuizAttempt.profile_id == profile_id)
            .order_by(QuizAttempt.started_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def save_results(
        self,
        attempt: QuizAttempt,
        score: float,
        correct_count: int,
        questions_json: str,
    ) -> QuizAttempt:
        """Record final score and completed status for a quiz attempt."""
        attempt.score = score
        attempt.correct_count = correct_count
        attempt.questions_json = questions_json
        attempt.completed_at = datetime.now(timezone.utc)
        self.session.add(attempt)
        await self.session.commit()
        await self.session.refresh(attempt)
        return attempt

    async def delete_by_profile_id(self, profile_id: str) -> None:
        """Delete all quiz attempts for a profile."""
        await self.session.execute(
            delete(QuizAttempt).where(QuizAttempt.profile_id == profile_id)
        )
        await self.session.commit()


# Backward compatibility alias
QuizRepo = QuizRepository
