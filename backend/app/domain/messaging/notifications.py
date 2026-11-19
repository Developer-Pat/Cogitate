"""THE NOTIFICATION SERVICE (2026-08-30, the F2 extraction of the
architecture-fit review): the scheduled-mute's lifecycle — the
APScheduler restore job, the expiry flip + the announcement, the
startup heal. The API layer (notifications_router) calls here; the
scheduling is domain logic, not endpoint concerns.
"""

from __future__ import annotations

import time

from app.domain.messaging.notifications_config import (
    get_notifications_config,
    save_notifications_config,
)

# The scheduled-mute's restore job id (one per mute — replaced).
_RESTORE_JOB_ID = "notifications-restore"


def schedule_mute_restore(mute_until: float) -> None:
    """The mute's end: the APScheduler one-shot that restores the
    notifications (the flip + the announcement). Rejects a past end."""
    from datetime import datetime, timedelta, timezone

    from app.domain.external_agent.timer_service import get_scheduler

    if mute_until <= time.time():
        raise ValueError("mute_until must be in the future")
    scheduler = get_scheduler()
    delta = max(1.0, mute_until - time.time())
    scheduler.add_job(
        restore_notifications,
        trigger="date",
        run_date=datetime.now(timezone.utc) + timedelta(seconds=delta),
        id=_RESTORE_JOB_ID,
        replace_existing=True,
    )


def cancel_mute_restore() -> None:
    """Remove the pending restore job (the restore-now path)."""
    from app.domain.external_agent.timer_service import get_scheduler

    scheduler = get_scheduler()
    try:
        scheduler.remove_job(_RESTORE_JOB_ID)
    except Exception:
        pass  # no pending job — fine


async def restore_notifications() -> None:
    """THE MUTE'S EXPIRY: flip suppressed back + announce. No-ops
    when the config is already restored (a manual restore-now or a
    newer mute won the race). Also the startup heal's target."""
    from app.domain.messaging.services import publish

    from app.infrastructure.database import get_db_session

    async for db in get_db_session():
        cfg = await get_notifications_config(db)
        if cfg.get("suppressed") is not True:
            return  # already restored (manual or a newer mute)
        await save_notifications_config(db, {"suppressed": False}, clear={"mute_until"})
        break
    publish(
        "notify:system",
        {
            "title": "Notifications back on",
            "message": "Muted notifications are enabled again.",
            "type": "info",
            "from": "system",
            "kind": "notifications-restored",
        },
    )


async def ensure_mute_restore() -> None:
    """THE STARTUP HEAL (main.py's lifespan): a mute whose end passed
    during downtime restores at boot (the job may have been missed)."""
    from app.infrastructure.database import get_db_session

    async for db in get_db_session():
        cfg = await get_notifications_config(db)
        if (
            cfg.get("suppressed") is True
            and cfg.get("mute_until")
            and cfg["mute_until"] < time.time()
        ):
            await restore_notifications()
        break
