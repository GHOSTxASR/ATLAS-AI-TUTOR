"""Tracking for detached background coroutines.

``asyncio.create_task`` results must be kept referenced: the event loop only
holds a weak reference, so an unreferenced task may be garbage collected before
it finishes (documented in the asyncio docs). Tracking them also gives shutdown
a chance to drain work in flight - previously a restart during memory
extraction simply lost it - and surfaces exceptions instead of letting them
disappear into an un-retrieved task result.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Coroutine

logger = logging.getLogger(__name__)

_pending: set[asyncio.Task[Any]] = set()


def spawn(coro: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task[Any]:
    """Run `coro` detached, keeping a strong reference until it completes."""
    task = asyncio.create_task(coro, name=name)
    _pending.add(task)

    def _done(finished: asyncio.Task[Any]) -> None:
        _pending.discard(finished)
        if finished.cancelled():
            return
        error = finished.exception()
        if error is not None:
            logger.warning("Background task %r failed: %s", name, error, exc_info=error)

    task.add_done_callback(_done)
    return task


def pending_count() -> int:
    """Number of detached tasks still running."""
    return len(_pending)


async def drain(timeout: float = 10.0) -> int:
    """Wait for outstanding tasks, cancelling any that overrun `timeout`."""
    if not _pending:
        return 0

    outstanding = list(_pending)
    logger.info("Waiting for %d background task(s) to finish...", len(outstanding))
    done, still_running = await asyncio.wait(outstanding, timeout=timeout)

    for task in still_running:
        task.cancel()
    if still_running:
        await asyncio.gather(*still_running, return_exceptions=True)
        logger.warning("Cancelled %d background task(s) that overran shutdown.", len(still_running))

    # Done-callbacks are scheduled with `loop.call_soon`, so they have not run
    # yet: `asyncio.wait` returning is not enough. Yield until they flush, or a
    # task's exception would go unlogged and `_pending` would look non-empty.
    while _pending:
        await asyncio.sleep(0)

    return len(done)
