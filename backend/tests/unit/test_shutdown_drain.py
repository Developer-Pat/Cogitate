"""The drain returns only once the task has stopped, reporting a cancel or a timeout honestly.

THE BUG THESE PIN. In the lifespan's shutdown, `_inbox_task.cancel()` was
called and never awaited, then `close_db()` ran — so the application could close
its own database underneath a task that was still iterating (still inside a
`shutil.move`). `cancel()` only *requests* cancellation.

The property that matters is not "we asked it to stop". It is: **when
`drain_task` returns, the task has actually finished its cleanup — or we have
said out loud that we could not wait.** Two of the three tests below fail
against a bare `cancel()`.
"""
import asyncio

import pytest

from app.main import drain_task


@pytest.mark.anyio
async def test_the_task_has_really_finished_before_we_return():
    """The bug in one assertion, and the reason the fix exists.

    The worker's `finally` stands in for the work that must not be cut off —
    the DB write, the `shutil.move`. A bare `cancel()` returns while this is
    still pending; `drain_task` must not.
    """
    finished_cleanup = []

    async def worker() -> None:
        try:
            while True:
                await asyncio.sleep(0.01)
        finally:
            # whatever must complete before close_db() runs
            await asyncio.sleep(0.05)
            finished_cleanup.append(True)

    task = asyncio.create_task(worker())
    await asyncio.sleep(0.02)  # let it get going

    outcome = await drain_task(task)

    assert outcome in ("stopped", "cancelled")
    assert task.done(), "drain_task returned with the task still running"
    assert finished_cleanup == [True], (
        "drain_task returned BEFORE the task's cleanup ran — this is exactly "
        "the close_db()-under-a-live-task race"
    )


@pytest.mark.anyio
async def test_an_ordinary_cancel_is_reported_as_cancelled_not_an_error():
    """The expected path, named. `CancelledError` is a BaseException, so the
    `except Exception` this replaced could never have caught it — it would have
    surfaced as an unhandled error at shutdown."""

    async def worker() -> None:
        while True:
            await asyncio.sleep(0.01)

    task = asyncio.create_task(worker())
    await asyncio.sleep(0.02)

    assert await drain_task(task) == "cancelled"


@pytest.mark.anyio
async def test_a_task_slower_than_the_bound_is_reported_as_timeout():
    """The bound is the point. An unbounded wait is just a different hang, and
    uvicorn (--timeout-graceful-shutdown 15s) is only the outer backstop — the
    app must finish first so it can SAY what it did instead of being cut off."""

    async def slow_cleanup() -> None:
        try:
            while True:
                await asyncio.sleep(0.01)
        finally:
            await asyncio.sleep(0.30)  # finite, but far longer than the bound

    task = asyncio.create_task(slow_cleanup())
    await asyncio.sleep(0.02)

    assert await drain_task(task, timeout=0.05) == "timeout"
