from __future__ import annotations

from datetime import UTC, datetime

# Guard against a stale timestamp inflating the study-time total (e.g. a quiz
# left open overnight). Roughly one long study session.
MAX_SESSION_MINUTES = 180.0


def elapsed_study_minutes(
    started_at: datetime | None,
    ended_at: datetime | None = None,
    *,
    cap_minutes: float = MAX_SESSION_MINUTES,
) -> float:
    """Minutes between two instants, clamped to a plausible study session.

    Analytics stores ``AnalyticsEvent.value`` as study minutes, so every
    emitter must produce a duration rather than a score or a count.
    """
    if started_at is None:
        return 0.0

    end = ended_at or datetime.now(UTC)
    # SQLite hands back naive datetimes; assume they are already UTC.
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)

    minutes = (end - started_at).total_seconds() / 60.0
    return round(max(0.0, min(minutes, cap_minutes)), 2)

