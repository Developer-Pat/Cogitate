"""The two-phase shutdown record (2026-09-12).

THE CONTRACT, settled with the user and APP-OWNED:

  - **A report is written on EVERY shutdown, clean or not.** That is what makes
    its absence meaningful. If we wrote one only when something went wrong,
    "no record" would be ambiguous — and ambiguity is the failure mode this
    whole arc keeps meeting.
  - **Two phases.** ``draining`` is written BEFORE the drain begins, and flipped
    to ``complete`` after it ends. A row still reading ``draining`` at the next
    boot is PROOF that the previous exit died mid-shutdown. One row saying "it
    was clean" could not tell a crash from a clean exit: a crash leaves the
    previous clean row in place, and the successor reads it happily.
  - **Nothing is abandoned silently.** What did not finish is NAMED.

The audience is the NEXT BOOT — a message across a process boundary, which is
why it is persisted rather than printed — and, through the next boot, the
operator and PSP Phase C.

Failure is degraded, never destructive: if the record cannot be written, that
is logged and shutdown continues. Nothing about shutdown may be able to break
shutdown. And if nothing can be written at all, the missing completion is
*still* the message.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select

from app.core.activity import snapshot
from app.core.database import AsyncSessionLocal
from app.infrastructure.database.models import ShutdownRecord

logger = logging.getLogger(__name__)

# The newest N records are kept; older ones are pruned on write. A pattern of
# unclean exits should be visible, which a single row cannot show.
SHUTDOWN_RECORD_KEEP = 20

# The record THIS process is currently living in. Set at boot (`mark_running`)
# and again when we begin draining.
#
# WHY IT MATTERS: `report_last_shutdown()` reads the NEWEST row, which is the
# right answer at BOOT (main.py calls it before `mark_running`, deliberately).
# But the same function called MID-SESSION returns this process's own `running`
# marker -- so the Dashboard card would announce "the last exit was unclean"
# about the application the user is currently looking at. It has to be excluded.
_CURRENT_RECORD_ID: Optional[int] = None


def _set_current_record(record_id: Optional[int]) -> None:
    """Remember the record this process owns."""
    global _CURRENT_RECORD_ID
    _CURRENT_RECORD_ID = record_id


def get_current_record_id() -> Optional[int]:
    """The record this process owns, if any."""
    return _CURRENT_RECORD_ID


# WHY THE REASON MUST BE PENDING RATHER THAN WRITTEN HERE:
#
# The shutdown button originally called `begin_shutdown_record()` directly to
# record its intent. That produced TWO defects, one of them serious:
#
#   1. the intent was LOST -- the app's real shutdown handler then wrote its own
#      record with the default reason, and THAT is the one that completes, so the
#      successor read "sigterm" and could not tell a button press from a reload;
#
#   2. it manufactured a PHANTOM CRASH -- the early `draining` row was never
#      completed, and a `draining` row means "died mid-shutdown". The button was
#      planting a false crash signal in the very system built to detect crashes.
#
# So the intent is held here and picked up by the ONE record that the real
# shutdown writes. One shutdown, one record, the right reason.
_PENDING_REASON: Optional[str] = None


def set_pending_reason(reason: Optional[str]) -> None:
    """Declare why this process is about to exit, for the record it will write."""
    global _PENDING_REASON
    _PENDING_REASON = reason


def get_pending_reason() -> Optional[str]:
    """The declared exit reason, if one was requested."""
    return _PENDING_REASON


# ── THE INJECTABLE SESSION ──────────────────────────────────────────────────
# This module talks to the database directly (it runs during shutdown, when
# FastAPI's dependency machinery is not available to ask), so it cannot use
# `dependency_overrides` — which is how conftest isolates every other path.
#
# That would have made the tests write shutdown_records into the PRODUCTION
# database: the identical isolation trap this session spent the morning on.
# So the factory is injectable, following `AgentDistributor`'s precedent
# ("injectable for tests; defaults to the app's session factory").
_session_factory = None


def set_session_factory(factory) -> None:
    """Override the session factory (tests). ``None`` restores the default."""
    global _session_factory
    _session_factory = factory


def _factory():
    """The app's session factory, unless a test has injected one."""
    if _session_factory is not None:
        return _session_factory()
    return AsyncSessionLocal()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def mark_running(reason: str = "boot") -> Optional[int]:
    """Liveness marker: this instance is UP and has not begun to shut down.

    THREE STATES, NOT TWO, and this is the one that was missing. The first
    draft had only ``draining`` and ``complete``, which cannot see a ``kill -9``
    at all: no shutdown code runs, so phase one never writes, the newest row is
    the PREVIOUS clean shutdown, and the successor reads "clean" — a crash
    wearing the last good exit's clothes.

        running   → up (written at boot)
        draining  → shutting down
        complete  → finished

    Now every way of dying is distinguishable, and the successor still claims
    nothing when there is nothing to read.

    Written AFTER ``report_last_shutdown()``, never before: the report must read
    the PREVIOUS instance's state, not the one we are about to write.
    """
    try:
        async with _factory() as db:
            row = ShutdownRecord(
                phase="running",
                started_at=_now(),
                in_flight_json="[]",
                reason=reason,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
        _set_current_record(row.id)
        return row.id
    except Exception as exc:
        logger.warning("⚠️ Could not write the startup record: %s", exc)
        return None


async def begin_shutdown_record(reason: Optional[str] = None) -> Optional[int]:
    """Phase one: declare the drain starting, naming what is in flight.

    MUST run before the drain, so that a crash *during* the drain leaves a
    half-written row behind as evidence. Returns the row id, or None if the
    record could not be written (shutdown continues either way).

    The reason resolves in this order: an explicit argument, then a PENDING
    reason (set by the lifecycle endpoints when a human asked for this exit),
    then "sigterm" as the honest default -- the signal we cannot distinguish
    from a reload. This is the ONE record a shutdown writes, which is why the
    intent is parked rather than pre-written (see `set_pending_reason`).
    """
    reason = reason or _PENDING_REASON or "sigterm"
    in_flight = snapshot()
    try:
        async with _factory() as db:
            row = ShutdownRecord(
                phase="draining",
                started_at=_now(),
                in_flight_json=json.dumps(in_flight),
                reason=reason,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
        # This process now owns the draining record, so a mid-drain reader
        # excludes it too (it is the exit in progress, not the last one).
        _set_current_record(row.id)
        logger.info(
            "🔻 Shutdown drain beginning (%s) — in flight: %s",
            reason, ", ".join(in_flight) if in_flight else "nothing",
        )
        return row.id
    except Exception as exc:
        # Degrade honestly: say it failed, keep going.
        logger.warning("⚠️ Could not write the shutdown record (draining): %s", exc)
        return None


async def complete_shutdown_record(
    record_id: Optional[int],
    completed: Optional[List[str]] = None,
    abandoned: Optional[List[str]] = None,
) -> None:
    """Phase two: flip the row to ``complete``, naming what finished and what did not.

    MUST run before ``close_db()`` — that is what the drain fix guarantees.
    """
    completed = completed or []
    abandoned = abandoned or []
    if record_id is None:
        # Phase one failed. Say so; do not pretend a record exists.
        logger.warning(
            "⚠️ Shutdown completing with no record to close (phase one failed) — "
            "completed: %s | abandoned: %s",
            ", ".join(completed) or "nothing",
            ", ".join(abandoned) or "nothing",
        )
        return
    try:
        async with _factory() as db:
            result = await db.execute(
                select(ShutdownRecord).where(ShutdownRecord.id == record_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                logger.warning("⚠️ Shutdown record %s vanished before completion", record_id)
                return
            row.phase = "complete"
            row.completed_at = _now()
            row.completed_json = json.dumps(completed)
            row.abandoned_json = json.dumps(abandoned)

            # Prune, keeping the newest N.
            keep = (
                await db.execute(
                    select(ShutdownRecord.id).order_by(ShutdownRecord.id.desc()).limit(SHUTDOWN_RECORD_KEEP)
                )
            ).scalars().all()
            if keep:
                await db.execute(
                    delete(ShutdownRecord).where(ShutdownRecord.id.notin_(keep))
                )
            await db.commit()

        if abandoned:
            logger.warning(
                "✅ Shutdown complete — abandoned (named): %s", ", ".join(abandoned)
            )
        else:
            logger.info("✅ Shutdown complete — nothing abandoned")
    except Exception as exc:
        logger.warning("⚠️ Could not complete the shutdown record: %s", exc)


async def report_last_shutdown(exclude_current: bool = False) -> Dict[str, Any]:
    """Read the PREVIOUS shutdown's record and say what it means. Called at boot.

    Three outcomes, and the third is the point of the whole design:

    ``clean``    — phase ``complete``. Report any abandoned items by name.
    ``unclean``  — phase ``draining``. The previous exit DIED MID-SHUTDOWN.
    ``none``     — no record at all. Say exactly that and claim nothing;
                   a first boot and a wiped store are indistinguishable here,
                   and inventing "clean" would be the lie this arc is about.

    ``exclude_current`` is for MID-SESSION readers — the Dashboard card, which
    asks "how did the LAST one end?" while this instance is very much alive. The
    newest row is then our own ``running`` marker, and reporting it would
    announce an unclean exit about the application the user is looking at. At
    boot the flag is unnecessary (main.py reports before marking) and defaults
    off, so the boot path is unchanged.
    """
    try:
        async with _factory() as db:
            stmt = select(ShutdownRecord).order_by(ShutdownRecord.id.desc()).limit(1)
            if exclude_current and _CURRENT_RECORD_ID is not None:
                stmt = (
                    select(ShutdownRecord)
                    .where(ShutdownRecord.id != _CURRENT_RECORD_ID)
                    .order_by(ShutdownRecord.id.desc())
                    .limit(1)
                )
            row = (await db.execute(stmt)).scalar_one_or_none()

        if row is None:
            logger.info(
                "🕳️  No shutdown record — no claim about the previous exit "
                "(first run, or the record store is missing)"
            )
            return {"state": "none", "record": None}

        record = {
            "id": row.id,
            "phase": row.phase,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "reason": row.reason,
            "in_flight": json.loads(row.in_flight_json or "[]"),
            "completed": json.loads(row.completed_json or "[]"),
            "abandoned": json.loads(row.abandoned_json or "[]"),
        }

        if row.phase == "running":
            # The process was up and never began to shut down: killed, crashed,
            # or the machine went down. NOTHING was recorded in flight (the
            # marker is written at boot), so there is no list to offer — say so
            # rather than implying the work was empty.
            logger.warning(
                "🚨 The previous instance DIED WITHOUT SHUTTING DOWN "
                "(record #%s, last seen up at %s). No clean exit was recorded.",
                row.id, record["started_at"],
            )
            _notify(
                "Last exit was not clean",
                "The previous instance was stopped without shutting down (killed, "
                "crashed, or the machine went down). Nothing was recorded in flight.",
                "warning",
            )
            return {"state": "unclean", "record": record, "how": "died-while-running"}

        if row.phase == "draining":
            abandoned = record["in_flight"]
            logger.warning(
                "🚨 The previous shutdown DID NOT COMPLETE (record #%s, started %s, "
                "reason %s). Was in flight: %s",
                row.id, record["started_at"], record["reason"],
                ", ".join(abandoned) if abandoned else "nothing recorded",
            )
            _notify(
                "Previous shutdown did not complete",
                f"The last exit died mid-shutdown ({record['reason'] or 'unknown reason'}). "
                + (f"Was in flight: {', '.join(abandoned)}." if abandoned else "Nothing was recorded in flight."),
                "warning",
            )
            return {"state": "unclean", "record": record, "how": "died-mid-shutdown"}

        abandoned = record["abandoned"]
        if abandoned:
            logger.warning(
                "✅ Previous shutdown completed, but abandoned (named): %s",
                ", ".join(abandoned),
            )
            _notify(
                "Last shutdown abandoned work",
                f"Completed cleanly but did not finish: {', '.join(abandoned)}.",
                "info",
            )
        else:
            logger.info("✅ Previous shutdown completed cleanly (record #%s)", row.id)
        return {"state": "clean", "record": record}

    except Exception as exc:
        logger.warning("⚠️ Could not read the last shutdown record: %s", exc)
        return {"state": "unknown", "record": None, "error": str(exc)}


def _notify(title: str, message: str, kind: str) -> None:
    """Surface it, never silently. The notify leg must not break the boot."""
    try:
        from app.domain.messaging.services import publish

        publish("notify:system-shutdown", {
            "kind": "system-shutdown",
            "title": title,
            "message": message,
            "type": kind,
        })
    except Exception as exc:  # the notify leg must never kill startup
        logger.warning("⚠️ Shutdown notify failed: %s", exc)
