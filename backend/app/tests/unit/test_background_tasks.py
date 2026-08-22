"""Detached background work must survive until it completes.

`asyncio.create_task` results were discarded. The event loop keeps only a weak
reference, so an unreferenced task may be collected mid-flight, and nothing
drained outstanding work at shutdown or reported its exceptions.
"""

from __future__ import annotations

import asyncio
import gc

from app.tasks import background


async def test_spawned_task_survives_garbage_collection():
    finished: list[int] = []

    async def job(n: int) -> None:
        for _ in range(5):
            await asyncio.sleep(0)
        finished.append(n)

    for i in range(50):
        background.spawn(job(i), name=f"job-{i}")
        gc.collect()

    await background.drain(timeout=5.0)
    assert sorted(finished) == list(range(50))


async def test_drain_waits_for_outstanding_work():
    finished: list[str] = []

    async def slow() -> None:
        await asyncio.sleep(0.05)
        finished.append("done")

    background.spawn(slow(), name="slow")
    assert background.pending_count() == 1

    await background.drain(timeout=5.0)
    assert finished == ["done"]
    assert background.pending_count() == 0


async def test_failing_task_is_logged_and_does_not_escape(caplog):
    async def boom() -> None:
        raise RuntimeError("background failure")

    with caplog.at_level("WARNING"):
        background.spawn(boom(), name="boom")
        await background.drain(timeout=5.0)

    assert any("background failure" in record.getMessage() for record in caplog.records)
    assert background.pending_count() == 0


async def test_drain_cancels_tasks_that_overrun():
    async def forever() -> None:
        await asyncio.sleep(60)

    background.spawn(forever(), name="forever")
    await background.drain(timeout=0.05)
    assert background.pending_count() == 0
