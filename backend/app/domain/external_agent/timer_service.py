"""The external agent's one-shot timers (the EXA-TIMER, 2026-08-28).

The v1: the APScheduler's one-shot + the bus-event at the expiry.
The v2 (2026-08-28): the DB-RECORDS (the agent_timers table) so the
pending timers survive the backend restarts — the scheduler's
rebuilt from the records on boot.

The pickup doctrine (the 08-13 incident): NO auto-fire — the event
surfaces as a CONFIRMABLE message; the user confirms or the next-ask
carries the context.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)

# The global scheduler instance (the workflow-triggers' pattern)
_scheduler_instance: Optional[Any] = None


def get_scheduler() -> Any:
    """Get or create the shared AsyncIOScheduler."""
    global _scheduler_instance
    if _scheduler_instance is None:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

        _scheduler_instance = AsyncIOScheduler()
        _scheduler_instance.start()
        logger.info("timer_service: the scheduler started")
    return _scheduler_instance


async def _load_pending() -> list[dict[str, Any]]:
    """Read the pending timer-records (the boot-rebuild + the list)."""
    from app.core.database import get_db_session
    from app.infrastructure.database.models import AgentTimer
    from sqlalchemy import select

    async for session in get_db_session():
        result = await session.execute(
            select(AgentTimer).where(AgentTimer.status == "pending")
        )
        records = result.scalars().all()
        return [
            {
                "timer_id": r.timer_id,
                "context": r.context,
                "fires_at": r.fires_at,
                "duration_seconds": r.duration_seconds,
            }
            for r in records
        ]
    return []


async def _reload_scheduler() -> None:
    """Rebuild the scheduler's jobs from the pending records (the boot-rebuild)."""
    from apscheduler.triggers.date import DateTrigger  # type: ignore[import-untyped]
    from datetime import datetime, timedelta, timezone

    scheduler = get_scheduler()
    for record in await _load_pending():
        # the run_date's a DATETIME (the DateTrigger rejects the float —
        # the v1's lesson!); the already-expired fire immediately
        remaining = max(0, record["fires_at"] - time.time())
        scheduler.add_job(
            _fire,
            trigger=DateTrigger(
                run_date=datetime.now(timezone.utc) + timedelta(seconds=remaining)
            ),
            args=[record["timer_id"]],
            id=record["timer_id"],
            replace_existing=True,
        )
        logger.info("timer_service: restored %s (%ss left)", record["timer_id"], int(remaining))


async def ensure_pending_timers() -> None:
    """THE BOOT-REBUILD (the v2's restart-survival): rebuild the
    scheduler's jobs from the pending records. The startup-hook
    (main.py) calls this; the expired ones fire immediately."""
    global _scheduler_instance
    if _scheduler_instance is None:
        await _reload_scheduler()


async def set_timer(duration_seconds: int, context: str) -> dict[str, Any]:
    """Set a one-shot timer: the DB-record + the scheduler-job. The
    expiry publishes the timer:{id}:fired event (the confirmable
    pickup — NO auto-fire)."""
    from datetime import datetime, timedelta, timezone
    from app.core.database import get_db_session
    from app.infrastructure.database.models import AgentTimer

    timer_id = f"timer-{uuid.uuid4().hex[:12]}"
    fires_at = time.time() + duration_seconds

    # the DB-record
    async for session in get_db_session():
        session.add(
            AgentTimer(
                timer_id=timer_id,
                context=context,
                fires_at=fires_at,
                duration_seconds=duration_seconds,
                status="pending",
                created_at=time.time(),
            )
        )
        await session.commit()
        break

    # the scheduler-job
    scheduler = get_scheduler()
    scheduler.add_job(
        _fire,
        trigger="date",
        run_date=datetime.now(timezone.utc) + timedelta(seconds=duration_seconds),
        args=[timer_id],
        id=timer_id,
        replace_existing=True,
    )
    logger.info("timer_service: set %s in %ss (%s)", timer_id, duration_seconds, context[:80])
    return {
        "timer_id": timer_id,
        "fires_at": fires_at,
        "duration_seconds": duration_seconds,
    }


async def _fire(timer_id: str) -> None:
    """The expiry: mark the record fired + publish the bus-event."""
    from app.core.database import get_db_session
    from app.infrastructure.database.models import AgentTimer
    from sqlalchemy import select

    # mark the record fired + capture the context (the DB's the source!)
    context = ""
    try:
        async for session in get_db_session():
            result = await session.execute(
                select(AgentTimer).where(AgentTimer.timer_id == timer_id)
            )
            record = result.scalars().first()
            if record is not None:
                context = record.context or ""
                record.status = "fired"
                await session.commit()
            break
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("timer_service: %s mark-fired failed: %s", timer_id, exc)

    try:
        from app.domain.messaging.services import publish

        publish(f"timer:{timer_id}:fired", {"timer_id": timer_id, "context": context})
        logger.info("timer_service: %s fired (%s)", timer_id, context[:80])
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("timer_service: %s fire-publish failed: %s", timer_id, exc)


async def list_timers() -> list[dict[str, Any]]:
    """The in-flight timers (the pending records — the debug/panel)."""
    records = await _load_pending()
    now = time.time()
    return [
        {
            "timer_id": r["timer_id"],
            "context": r["context"],
            "fires_at": r["fires_at"],
            "seconds_left": max(0, int(r["fires_at"] - now)),
        }
        for r in records
    ]


async def cancel_timer(timer_id: str) -> bool:
    """Cancel a pending timer (the operator's path)."""
    from app.core.database import get_db_session
    from app.infrastructure.database.models import AgentTimer
    from sqlalchemy import select

    scheduler = get_scheduler()
    try:
        scheduler.remove_job(timer_id)
    except Exception:
        pass

    cancelled = False
    async for session in get_db_session():
        result = await session.execute(
            select(AgentTimer).where(AgentTimer.timer_id == timer_id, AgentTimer.status == "pending")
        )
        record = result.scalars().first()
        if record is not None:
            record.status = "cancelled"
            await session.commit()
            cancelled = True
        break
    if cancelled:
        logger.info("timer_service: cancelled %s", timer_id)
    return cancelled
