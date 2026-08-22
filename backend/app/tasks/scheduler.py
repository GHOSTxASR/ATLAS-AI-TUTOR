from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.tasks.embedding_task import process_embedding_queue
from app.tasks.memory_extraction_task import run_memory_decay_task

logger = logging.getLogger(__name__)

# Memories decay slowly; running this more often would prune reinforcement
# before the learner has had a chance to revisit a topic.
MEMORY_DECAY_INTERVAL_HOURS = 24

_SCHEDULER_RUNNING = False
_BACKGROUND_TASK: asyncio.Task | None = None
_APSCHEDULER_INSTANCE: Any = None


async def _polling_loop(interval_seconds: float = 5.0) -> None:
    """Fallback asyncio polling loop when APScheduler is not available."""
    global _SCHEDULER_RUNNING
    decay_every = max(1, int(MEMORY_DECAY_INTERVAL_HOURS * 3600 / interval_seconds))
    ticks = 0

    while _SCHEDULER_RUNNING:
        try:
            await process_embedding_queue(batch_size=100)
        except Exception as e:
            logger.error(f"Error in embedding queue worker: {e}", exc_info=True)

        ticks += 1
        if ticks % decay_every == 0:
            try:
                await run_memory_decay_task()
            except Exception as e:
                logger.error(f"Error in memory decay worker: {e}", exc_info=True)

        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            break


def start_scheduler() -> None:
    """Start background scheduler / worker loop."""
    global _SCHEDULER_RUNNING, _BACKGROUND_TASK, _APSCHEDULER_INSTANCE
    if _SCHEDULER_RUNNING:
        return

    _SCHEDULER_RUNNING = True

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        _APSCHEDULER_INSTANCE = AsyncIOScheduler()
        _APSCHEDULER_INSTANCE.add_job(
            process_embedding_queue,
            "interval",
            seconds=5,
            id="process_embedding_queue",
            replace_existing=True,
        )
        # Memory decay was fully implemented but never registered, so weak or
        # stale learner memories accumulated forever and were never pruned.
        _APSCHEDULER_INSTANCE.add_job(
            run_memory_decay_task,
            "interval",
            hours=MEMORY_DECAY_INTERVAL_HOURS,
            id="run_memory_decay",
            replace_existing=True,
        )
        _APSCHEDULER_INSTANCE.start()
        logger.info("APScheduler started with embedding queue and memory decay jobs.")
    except Exception as e:
        logger.info(f"Using asyncio background loop for tasks ({e}).")
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        _BACKGROUND_TASK = loop.create_task(_polling_loop(interval_seconds=5.0))


def shutdown_scheduler() -> None:
    """Gracefully stop background scheduler."""
    global _SCHEDULER_RUNNING, _BACKGROUND_TASK, _APSCHEDULER_INSTANCE
    _SCHEDULER_RUNNING = False

    if _APSCHEDULER_INSTANCE is not None:
        try:
            _APSCHEDULER_INSTANCE.shutdown(wait=False)
        except Exception as e:
            logger.warning(f"Error shutting down APScheduler: {e}")
        _APSCHEDULER_INSTANCE = None

    if _BACKGROUND_TASK is not None and not _BACKGROUND_TASK.done():
        _BACKGROUND_TASK.cancel()
        _BACKGROUND_TASK = None
