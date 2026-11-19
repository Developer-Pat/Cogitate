"""Workflow-run retention — the WINDOWS, and the prune that honours them.

Runs accumulate, in three places at once: the run's identity ROW, the debug SNAPSHOTS inside
that row's metadata, and the checkpoint THREAD it owns. Measured on this install before any of
this existed: 176 rows carrying **4.85 MB** of snapshots per list request (~95 KB a row, 213 KB
on the heavier families), and 53 checkpoint threads with **nothing in the app ever deleting
one**. A 5-minute monitor is 288 runs a day, so the arithmetic is ~28 MB/day of snapshots and
~4.3 MB/day of threads — ~840 MB a month, for runs nobody will read.

THE WINDOWS ARE CONFIG, NOT CODE. `RetentionPolicy` declares the SHAPE and one default set; the
EFFECTIVE policy is resolved from the app's settings (`user_settings.settings["workflow_retention"]`),
so every window can be read, changed and PREVIEWED from the settings surface with no code edit
and no restart. `resolve_policy` is tolerant field by field: an absent, partial or malformed
section falls back to the defaults, because a settings blob written by an older build must never
break the maintenance path.

TWO CLOCKS, because the two things decay differently:

    snapshot_days    the debug snapshots inside the row   — days (the weight, and the value)
    run_days         the run's identity row AND its checkpoint thread — months, TOGETHER
plus `abandoned_hours`: a row still `started` that long ago is not running — it is `abandoned`,
a status the list can finally say out loud instead of forever claiming to run.

`enabled` gates the SCHEDULED prune, not a person: a fresh install prunes nothing on its own
(the same ruling that ships triggers deactivated), while an explicit "prune now" is a human act
and runs. Either way a prune is never silent — it returns a `RetentionReport` with the counts and
the bytes, and `dry_run` is the endpoint's default.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from pydantic import BaseModel, Field

from .execution_history import (
    delete_executions,
    list_prunable_executions,
    mark_abandoned_before,
    strip_node_snapshots_before,
)

logger = logging.getLogger(__name__)

#: Where the policy lives in the app's settings blob (`user_settings.settings`).
POLICY_SETTINGS_KEY = "workflow_retention"


class RetentionPolicy(BaseModel):
    """The windows, as DATA. One default set lives here; the effective one comes from settings.

    Every field is a window in the units it is naturally reasoned about in, and every one is
    optional to configure — a partial settings section resolves to these values field by field.
    """

    enabled: bool = Field(
        default=False,
        description="Prune automatically on the schedule. A fresh install prunes nothing until asked.",
    )
    snapshot_days: int = Field(default=7, ge=1, description="Keep a run's debug snapshots this long.")
    run_days: int = Field(
        default=90,
        ge=1,
        description=(
            "Keep a run's identity row this long — and its checkpoint thread WITH it: the two are "
            "paired on purpose, because a thread that outlives its row is an invisible orphan and a "
            "row that outlives its thread is a `/status` 404 the list still shows."
        ),
    )
    abandoned_hours: int = Field(
        default=24,
        ge=1,
        description="A row still `started` this long is not running — it is `abandoned`.",
    )
    schedule_hour: int = Field(
        default=3, ge=0, le=23, description="Hour (UTC) the scheduled prune runs at."
    )


#: THE DEFAULTS — declared once, surfaced through the API, overridable from settings.
DEFAULT_POLICY = RetentionPolicy()


class RetentionReport(BaseModel):
    """What a prune did (or would do). A maintenance run reports; it never surprises."""

    dry_run: bool
    enabled: bool
    policy: dict[str, Any]
    rows_pruned: int = 0
    threads_pruned: int = 0
    snapshots_stripped: int = 0
    snapshot_bytes_freed: int = 0
    abandoned_marked: int = 0
    abandoned_ids: list[str] = Field(default_factory=list)
    pruned_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    generated_at: str = ""

    def describe(self) -> str:
        """One line for the log — the shape a maintenance event should always have."""
        verb = "would prune" if self.dry_run else "pruned"
        extra = f" | errors: {'; '.join(self.errors)}" if self.errors else ""
        return (
            f"retention: {verb} {self.rows_pruned} row(s) + {self.threads_pruned} thread(s), "
            f"stripped {self.snapshots_stripped} snapshot blob(s) "
            f"({self.snapshot_bytes_freed / 1e6:.2f} MB), marked {self.abandoned_marked} abandoned"
            f" | dry_run={self.dry_run} enabled={self.enabled}{extra}"
        )


def resolve_policy(settings_blob: Optional[dict[str, Any]]) -> RetentionPolicy:
    """The EFFECTIVE policy: the settings section where it is valid, the defaults elsewhere.

    Field by field on purpose. A settings blob is written by whatever build was current at the
    time, so it can be missing, partial, or hold a stale type; none of those may break the
    maintenance path or silently change a window the operator did not set.
    """
    section = (settings_blob or {}).get(POLICY_SETTINGS_KEY)
    if not isinstance(section, dict):
        return DEFAULT_POLICY.model_copy()

    known = {k: v for k, v in section.items() if k in RetentionPolicy.model_fields}
    try:
        # `model_validate` on the known subset applies the defaults for whatever is absent, and
        # its constraints (ge/le) reject nonsense — a bad value falls back rather than loosening.
        return RetentionPolicy.model_validate(known)
    except Exception as e:
        logger.warning(f"workflow retention: settings section unusable ({e}); using the defaults")
        return DEFAULT_POLICY.model_copy()


def _cutoff(*, days: int = 0, hours: int = 0) -> str:
    """An isoformat cutoff in the writer's own shape, so string comparison is exact."""
    moment = datetime.now(UTC) - timedelta(days=days, hours=hours)
    return moment.isoformat().replace("+00:00", "Z")


# ── the prune ────────────────────────────────────────────────────────────────────────────


def prune_runs(policy: RetentionPolicy, *, dry_run: bool = True) -> RetentionReport:
    """Apply the policy. Never raises — a maintenance run that dies stops the housekeeping.

    ORDER MATTERS, and it is chosen rather than inherited: the ROWS go before their THREADS. A
    thread left without a row is invisible (an orphan journal entry nothing reads), while a row
    left without a thread is a lie the UI shows (`/status` 404s for a run the list still lists —
    measured on two rows before this existed).
    """
    report = RetentionReport(
        dry_run=dry_run,
        enabled=policy.enabled,
        policy=policy.model_dump(),
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )

    # 1. THE SNAPSHOTS — the weight, on the shortest clock. The rows stay; only the blobs go.
    try:
        stripped, freed = strip_node_snapshots_before(
            _cutoff(days=policy.snapshot_days), apply=not dry_run
        )
        report.snapshots_stripped = stripped
        report.snapshot_bytes_freed = freed
    except Exception as e:  # pragma: no cover — the primitive already catches; belt and braces
        report.errors.append(f"snapshots: {e}")

    # 2. THE ABANDONED — a TRUTHFUL status, not a deletion, so it does not wait for `enabled`.
    try:
        abandoned_ids = mark_abandoned_before(
            _cutoff(hours=policy.abandoned_hours), apply=not dry_run
        )
        report.abandoned_marked = len(abandoned_ids)
        report.abandoned_ids = abandoned_ids
    except Exception as e:  # pragma: no cover
        report.errors.append(f"abandoned: {e}")

    # 3. THE ROWS (and then their threads), on the long clock.
    try:
        prunable = list_prunable_executions(_cutoff(days=policy.run_days))
        ids = [r["id"] for r in prunable]
        report.rows_pruned = len(ids)
        report.pruned_ids = ids
        if not dry_run and ids:
            report.rows_pruned = delete_executions(ids)
            report.threads_pruned = _delete_threads(ids, report)
        elif dry_run:
            report.threads_pruned = len(ids)
    except Exception as e:
        report.errors.append(f"rows: {e}")

    logger.info(report.describe())
    return report


def _delete_threads(ids: list[str], report: RetentionReport) -> int:
    """Delete the checkpoint threads that belong to the pruned rows.

    The thread is the run's journal and it lives in a DIFFERENT store (`checkpoints.db`) with no
    foreign key to the history table — which is exactly why nothing joined them before, and why
    the app accumulated 53 threads it could never reclaim. The saver takes its own lock, so the
    call is safe from the maintenance thread.
    """
    from .checkpointing.config import CheckpointerManager

    deleted = 0
    try:
        saver = CheckpointerManager.get_checkpointer()
    except Exception as e:
        report.errors.append(f"checkpointer unavailable: {e}")
        return 0

    for thread_id in ids:
        try:
            saver.delete_thread(thread_id)
            deleted += 1
        except Exception as e:
            report.errors.append(f"thread {thread_id}: {e}")
    return deleted


def prune_with_settings(
    *, dry_run: bool = True, settings_blob: Optional[dict[str, Any]] = None
) -> RetentionReport:
    """Resolve the policy from settings and apply it — the one entry point every caller uses."""
    return prune_runs(resolve_policy(settings_blob), dry_run=dry_run)


# ── the settings read/write (the surface's backing store) ────────────────────────────────


async def load_settings_blob() -> dict[str, Any]:
    """The app settings blob, or `{}`. Async: every caller is in or near the app's loop."""
    from app.domain.settings.services import DEFAULT_USER_KEY, get_or_create_user_settings

    try:
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            settings = await get_or_create_user_settings(db, DEFAULT_USER_KEY)
            return dict(getattr(settings, "settings", None) or {})
    except Exception as e:
        logger.warning(f"workflow retention: could not read the settings blob ({e})")
        return {}


async def save_policy(policy: RetentionPolicy) -> dict[str, Any]:
    """Write the policy into the app settings blob (MERGE — the blob holds other sections too)."""
    from app.domain.settings.services import DEFAULT_USER_KEY, update_user_settings

    from app.core.database import AsyncSessionLocal

    blob = await load_settings_blob()
    blob[POLICY_SETTINGS_KEY] = policy.model_dump()
    async with AsyncSessionLocal() as db:
        await update_user_settings(db, blob, DEFAULT_USER_KEY)
    return blob


# ── the scheduled entry ──────────────────────────────────────────────────────────────────


def scheduled_prune() -> None:
    """The scheduler's entry point (sync, because APScheduler's API is).

    Reads the policy, and prunes only when it is ENABLED — the automation waits for the operator,
    while an explicit run from the surface never does. Imports the checkpointer lazily so a
    maintenance job cannot pull the graph machinery into startup.
    """
    try:
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:  # pragma: no cover — a scheduler thread with no loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        blob = loop.run_until_complete(load_settings_blob())
        policy = resolve_policy(blob)
        if not policy.enabled:
            logger.info("workflow retention: skipped (not enabled) — nothing was pruned")
            return
        # The job wakes HOURLY and gates itself, so the hour it prunes at is read from the policy
        # every time — changing `schedule_hour` takes effect without a restart.
        if datetime.now(UTC).hour != policy.schedule_hour:
            return
        prune_runs(policy, dry_run=False)
    except Exception as e:
        # A maintenance job must never take anything else down with it.
        logger.warning(f"workflow retention: the scheduled prune failed | {e}")
