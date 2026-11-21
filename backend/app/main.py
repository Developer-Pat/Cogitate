"""
FastAPI application entry point.

Creates and configures the main FastAPI application instance
with middleware, routes, and lifecycle events.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import litellm
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.api.v1.router import router as api_v1_router
from app.core.config import Paths, get_settings
from app.core.shutdown_record import (
    begin_shutdown_record,
    complete_shutdown_record,
    mark_running,
    report_last_shutdown,
)
from app.core.database import (
    AsyncSession,
    close_db,
    init_db,
    init_documents_db,
)
from app.core.logging_config import setup_logging
from app.domain.tools.models import Tool as ToolModel

# Import workflow API routes (Phase 2)

# Import all models to ensure they are registered with Base.metadata
# This must happen before init_db() is called

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()


async def auto_sync_tools(db: AsyncSession) -> None:
    """
    Two-way sync: initialise the in-memory registry, then upsert each
    registry tool definition into the database.

    This makes the code-level tool class the single source of truth for
    schema definitions (``arguments_schema``, ``config_schema``, etc.)
    and fixes the long-standing bug where ``resolve_tools()`` queries the
    DB for schemas that were never written there by the registry.
    """
    from app.domain.tools.registry import ToolRegistry, init_default_registry

    # Step 1 — initialise in-memory registry with built-in tool handlers
    init_default_registry()
    logger.info("Initialised default registry with builtin tools")

    # Step 2 — upsert every registry tool into the DB so that
    #          resolve_tools() finds populated schema records.
    registry = ToolRegistry.get_instance()
    synced = 0

    for tool_def in registry.list_tools(builtin_only=True):
        result = await db.execute(
            select(ToolModel).where(ToolModel.slug == tool_def.slug)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update the DB record with the registry's authoritative schema
            existing.name = tool_def.name
            existing.description = tool_def.description
            existing.arguments_schema = tool_def.arguments_schema or {}
            existing.config_schema = tool_def.config_schema or {}
            existing.icon = tool_def.metadata.get("icon")
            existing.color = tool_def.metadata.get("color")
            existing.tags = tool_def.metadata.get("tags")
            existing.is_builtin = True
            existing.is_active = True
            existing.capability = tool_def.capability
            existing.access_tier = tool_def.metadata.get("access_tier")
        else:
            tool = ToolModel(
                name=tool_def.name,
                slug=tool_def.slug,
                description=tool_def.description,
                arguments_schema=tool_def.arguments_schema or {},
                config_schema=tool_def.config_schema or {},
                icon=tool_def.metadata.get("icon"),
                color=tool_def.metadata.get("color"),
                tags=tool_def.metadata.get("tags"),
                is_builtin=True,
                is_active=True,
                capability=tool_def.capability,
                access_tier=tool_def.metadata.get("access_tier"),
                provider="System",
                type="builtin",
                version="1.0.0",
            )
            db.add(tool)

        synced += 1
        # Flush per tool to avoid SQLAlchemy's insertmanyvalues
        # sentinel bug (JSON/UUID inserts in one batch trip it)
        await db.flush()
    # the session is autocommit=False — commit explicitly or the
    # sync is rolled back on context exit (the pre-existing bug:
    # the sync "ran" but never persisted)
    await db.commit()
    logger.info("Synced %d built-in tool definitions to database", synced)


async def verify_tool_invariants(db: AsyncSession) -> None:
    """
    Check that every registered tool has a complete DB record with a
    populated ``arguments_schema``.

    Logs a ``WARNING`` for each missing or empty-schema slug.
    Does **not** block startup — the goal is observability.
    """
    from app.domain.tools.registry import ToolRegistry

    registry = ToolRegistry.get_instance()
    all_slugs: set[str] = set(registry.get_all_slugs())

    missing = 0
    bad_schema = 0

    for slug in sorted(all_slugs):
        result = await db.execute(
            select(ToolModel).where(ToolModel.slug == slug)
        )
        tool = result.scalar_one_or_none()

        if tool is None:
            logger.warning(
                "⚠️ Tool '%s' has no DB record",
                slug,
            )
            missing += 1
        elif tool.arguments_schema is None:
            logger.warning(
                "⚠️ Tool '%s' has null/empty arguments_schema in database",
                slug,
            )
            bad_schema += 1

    if missing == 0 and bad_schema == 0:
        logger.info(
            "✅ All %d tool slugs have complete DB records with schemas",
            len(all_slugs),
        )
    else:
        logger.warning(
            "Tool invariant check: %d missing, %d with null schema (of %d total)",
            missing,
            bad_schema,
            len(all_slugs),
        )

# How long the app may spend draining a background task at shutdown.
# Deliberately INSIDE uvicorn's --timeout-graceful-shutdown (15s, see
# cogitate.sh): the transport is the outer bound, this is the inner one, and
# the app should finish first so it can say what it did rather than be cut off.
SHUTDOWN_DRAIN_SECONDS = 5


async def drain_task(task: "asyncio.Task[None]", timeout: float = SHUTDOWN_DRAIN_SECONDS) -> str:
    """Cancel a background task and WAIT for it, bounded. Returns what happened.

    THE BUG THIS FIXES (2026-09-12): ``task.cancel()`` only *requests*
    cancellation. Without awaiting, the coroutine can still be mid-iteration —
    mid-``shutil.move`` — when ``close_db()`` runs, so the application closes
    its own database underneath a live task. Found by reading the lifespan; a
    real corruption race, independent of PSP.

    The bound matters as much as the await: an unbounded wait is just a
    different hang. And note ``CancelledError`` is a ``BaseException``, so the
    ``except Exception`` this replaces could never have caught it.

    Returns one of: ``"stopped"``, ``"cancelled"``, ``"timeout"``, ``"error"``.
    """
    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=timeout)
        return "stopped"
    except asyncio.TimeoutError:
        return "timeout"
    except asyncio.CancelledError:
        # Either our own cancel() landing (the expected path) or OUR caller
        # being cancelled. Only swallow the first; never mask the second.
        if task.cancelled():
            return "cancelled"
        raise
    except Exception:
        logger.exception("Background task raised while draining")
        return "error"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting up Cogitate application...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    # THE SCHEMA FIRST. Everything below this line reads or writes tables, and a
    # fresh install has none: the seeds used to run before `init_db`, so a clean
    # clone died at startup with "no such table: system_flags" — invisible on any
    # machine that already had a database.
    await init_db()
    logger.info("✅ Main database initialized")

    # Seed external access flag in system_flags table
    from app.api.v1.agent_chat.middleware import seed_external_access_flag
    await seed_external_access_flag()

    # Seed the agent packages (Phase 1 — the canned blueprints; idempotent)
    from app.domain.agent_packages.seeds import seed_agent_packages
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as _seed_db:
        await seed_agent_packages(_seed_db)
        # Seed the A-Key Macros meta-topic + starter sets (2026-09-03,
        # the akeys roadmap Phase 3 — the A1-A5 action-key bank's
        # out-of-box source; idempotent, never overwrites user edits)
        from app.domain.macros.seeds import seed_akeys_macros
        await seed_akeys_macros(_seed_db)

        # THE PACKAGED SETUP PICKS (2026-11-21): `express_setup.json` is the authority and the
        # `setup_picks` table is its loaded copy, so a fresh install can offer "one model, one
        # key" without anyone running a command. Idempotent; never deletes a row a user added.
        from app.domain.providers.express_setup import load_packaged

        for _line in await load_packaged(_seed_db):
            logger.info("express setup — %s", _line)

    # Centralized LiteLLM retry defaults (applied once at startup).
    # These control LiteLLM's internal retry loop on transient failures
    # (rate limits, 5xx).  They are module-level globals that affect all
    # synchronous completion() calls.  For async retry logic, see
    # acompletion_with_retry in llm_utils.py.
    # NOTE: Do NOT pass "retry", "num_retries", or "retry_delay" in
    # per-request kwargs — LiteLLM forwards unknown kwargs to provider
    # APIs (e.g. Groq) which reject them.
    litellm.num_retries = 3
    litellm.retry_delay = 2
    logger.info("✅ Centralized LiteLLM retry settings applied (num_retries=%d, retry_delay=%d)", litellm.num_retries, litellm.retry_delay)

    # Initialize main database
    # (created above, before the seeds — see the note there)

    # THE SUCCESSOR'S FIRST QUESTION (2026-09-12): how did the last one end?
    # A report is written on EVERY shutdown, so its ABSENCE is meaningful too.
    # Runs here because the table must exist first; never fatal.
    try:
        await report_last_shutdown()
        # ...and only THEN mark ourselves up. Order matters: the report reads
        # the PREVIOUS instance's state, and marking first would overwrite it.
        await mark_running()
    except Exception as exc:  # a boot must not depend on the record
        logger.warning("⚠️ Shutdown-record check failed: %s", exc)

    # Initialize documents database
    await init_documents_db()
    logger.info("✅ Documents database initialized")


    # DISABLED: Database logging (using file-based logging instead)
    # setup_database_logging(AsyncSessionLocal, level=logging.INFO)
    # logger.info("Database logging enabled")

    # THE KIT-SLOT SYNC (2026-09-04, the agent-kits build P1): the
    # singular agents.kit_id -> the agent_kits JOIN (idempotent —
    # missing rows only). The join converges from the old slot at
    # every boot; never blocks the startup.
    try:
        from app.domain.agent_kits.service import AgentKitService

        async with AsyncSessionLocal() as session:
            await AgentKitService(session).sync_from_agent_slots()
            await session.commit()
    except Exception as exc:  # pragma: no cover - defensive boot guard
        logger.warning("AgentKitService boot sync failed: %s", exc)

    # Auto-sync registry tool definitions to database
    async with AsyncSessionLocal() as session:
        await auto_sync_tools(session)

    # Verify all registered tools have complete DB records
    async with AsyncSessionLocal() as session:
        await verify_tool_invariants(session)

    # THE SHIPPED AGENTS (Phase D, item 3): the news desk's first two reporters, seeded
    # once per install from `backend/templates/agents/`. Placed HERE, not beside the other
    # seeds: a kit is a tool-typed collection and its members are tool ROWS, which the
    # `auto_sync_tools` call above is what puts there. Idempotent, and it DEFERS (saying
    # why) on an install where nothing answers chat yet. Never blocks the boot.
    try:
        from app.domain.agents.shipped import seed_shipped_agents

        async with AsyncSessionLocal() as _shipped_db:
            for _outcome in await seed_shipped_agents(_shipped_db):
                logger.info("shipped agent — %s", _outcome.describe())
    except Exception as exc:  # pragma: no cover - defensive boot guard
        logger.warning("shipped-agent seed failed: %s", exc)


    # Initialize workflow trigger scheduler
    try:
        from app.workflows.triggers.scheduler import get_scheduler
        scheduler = get_scheduler()
        scheduler.start()
        scheduler.load_triggers_from_database()
        logger.info("✅ Workflow trigger scheduler initialized")
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize trigger scheduler: {e}")

    # WORKFLOW-RUN RETENTION (the WINDOWS are config — workflows/retention.py). Two things happen
    # at boot and only one of them can change anything:
    #
    #   1. THE RECONCILIATION: rows still `started` past the grace period are `abandoned`. Nothing
    #      can be running this early in a boot, a run whose process died must not claim to run
    #      forever, and these rows were exempt from every retention rule (no `completed_at`). It is
    #      a TRUTHFUL status update rather than a deletion, so it does not wait for `enabled`.
    #   2. THE SCHEDULED PRUNE: registered HOURLY and self-gating, so the hour it actually runs at
    #      comes from the policy each time — changing the setting needs no restart.
    try:
        from datetime import UTC as _UTC, datetime as _dt, timedelta as _td

        from app.workflows.execution_history import mark_abandoned_before
        from app.workflows.retention import load_settings_blob, resolve_policy, scheduled_prune

        _policy = resolve_policy(await load_settings_blob())
        _stale = mark_abandoned_before(
            (_dt.now(_UTC) - _td(hours=_policy.abandoned_hours))
            .isoformat()
            .replace("+00:00", "Z")
        )
        if _stale:
            logger.warning(
                "⚠️  %d run(s) were still marked 'started' past the %dh grace — now 'abandoned': %s",
                len(_stale), _policy.abandoned_hours, ", ".join(_stale[:5]),
            )
        scheduler.add_maintenance_job(
            "workflow-retention",
            "0 * * * *",
            scheduled_prune,
            "Workflow-run retention (the windows come from the settings)",
        )
    except Exception as e:
        logger.warning(f"⚠️ Failed to set up workflow-run retention: {e}")

    # THE PROVIDER CATALOG'S OWN REFRESH — the OPT-IN timer. The catalog is a TTL cache and NOTHING
    # else refreshes it: rows past `expires_at` are served as they are, and their prices are what the
    # usage page and a traced call's cost are computed from. The job is registered here and is INERT
    # until a user enables a schedule: with no schedule rows nothing is ever due, so the app ships
    # with no provider sync of its own. A user turns it on per provider, in that provider's panel.
    try:
        from app.domain.providers.scheduler import sync_due_providers

        scheduler.add_maintenance_job(
            "provider-catalog-sync",
            "0 * * * *",
            sync_due_providers,
            "Provider catalog refresh (only the schedules a user enabled)",
        )
    except Exception as e:
        logger.warning(f"⚠️ Failed to register the provider catalog sync: {e}")

    # THE AVAILABILITY BRIDGE'S POLL (the bridge's fourth and last seam) — the IDLE path over the
    # services THIS MACHINE hosts. Two things make it shippable unasked: the SCOPE is loopback only
    # (the ruling: the app may be running on somebody else's network, so it adds no packet of its
    # own), and it is what makes the bridge's other halves useful while nobody is looking — a change
    # is announced without a page visit, and the pre-turn REFUSAL gets the warm memo it reads
    # (`refusal.py`: a turn never pays a probe, so a cold cache refuses nothing).
    try:
        from app.domain.providers.availability import register_idle_poll

        register_idle_poll(scheduler)
    except Exception as e:
        logger.warning(f"⚠️ Failed to register the availability poll: {e}")

    # THE EXA-TIMER's boot-rebuild (the v2, 2026-08-28): the pending
    # timer-records → the scheduler's jobs — the restart-survival!
    try:
        from app.domain.external_agent.timer_service import ensure_pending_timers
        await ensure_pending_timers()
        logger.info("✅ Exa-timer scheduler restored (the pending timers)")
    except Exception as e:
        logger.warning(f"⚠️ Failed to restore the Exa-timers: {e}")

    # THE STARTUP SYSTEM-AUDIT (2026-08-20 → 2026-08-24): the user's
    # call — MOVE the sweep off the boot path: schedule it ~5
    # minutes AFTER startup (the relative DateTrigger one-shot),
    # so the startup process stays clean, uncluttered. The audit
    # runs the system-audit graph (the read-back-verified
    # ConsistencyAudit), the report files to the Exa desktop
    # inbox, and the NOTIFY LEG publishes notify:system-sweep on
    # the bus (the toaster + the user sees the outcome — never
    # silent).
    try:
        from app.workflows.api.workflow_router import get_workflow_config
        from app.workflows.graphs.system_audit_graph import create_system_audit_graph

        async def _system_sweep() -> None:
            try:
                graph = create_system_audit_graph().compile()
                result = await graph.ainvoke({}, get_workflow_config("startup-audit"))
                from app.workflows.distribution.distributors import AgentDistributor
                from app.workflows.distribution.models import WorkflowProduct
                from datetime import datetime, timezone
                product = WorkflowProduct(
                    product_type="system-check",
                    title="System Sweep",
                    body=result.get("report_text", "(no report)"),
                    source_template="system-audit",
                    created_at=datetime.now(timezone.utc).isoformat(),
                    meta={"recipient_agent": "exa"},
                )
                delivery = AgentDistributor().deliver(product)
                logger.info("✅ System sweep delivered: %s", delivery.detail)

                # THE NOTIFY LEG (2026-08-24): the user sees the
                # outcome — the bus carries notify:system-sweep,
                # the frontend toaster renders it. Never silent.
                try:
                    from app.domain.messaging.services import publish
                    findings = (result.get("audit_result") or {}).get("total_findings", "?")
                    publish("notify:system-sweep", {
                        "kind": "system-sweep",
                        "title": "System Sweep",
                        "message": f"Sweep complete: {findings} findings — the report is in the Exa inbox",
                        "type": "info" if findings in (0, "0", "?") else "warning",
                        "action": {"label": "View report", "link": delivery.path} if delivery.path else None,
                    })
                    logger.info("✅ System sweep notify published")
                except Exception as _ne:
                    logger.warning("⚠️ System sweep notify failed: %s", _ne)
            except Exception as e:  # the sweep must never fail the app
                logger.warning("⚠️ System sweep failed: %s", e)

        from app.workflows.triggers.scheduler import get_scheduler
        # THE DELAY IS CONFIGURABLE (2026-08-24): 60s for testing
        # (the user's call — no reason to wait 5 minutes while
        # developing), 300s when tuned for production.
        import os as _os
        _sweep_delay = int(_os.environ.get("SYSTEM_SWEEP_DELAY_SECONDS", "60"))
        # OPT-IN (2026-09-12): scheduling at boot means scheduling after
        # every --reload, i.e. after every file save. See the setting's
        # docstring in core/config.py. The mute heal below is NOT gated —
        # it is unrelated to the sweep and must still run.
        if settings.startup_sweep_enabled and settings.exa_background_processing_enabled:
            get_scheduler().schedule_once(
                job_id="system-sweep-after-startup",
                callback=_system_sweep,
                delay_seconds=_sweep_delay,
            )
            logger.info("✅ System sweep scheduled (one-shot, +%ss after startup)", _sweep_delay)
        elif settings.startup_sweep_enabled:
            # THE COUPLING (2026-09-12): the sweep's only consumer is Exa's
            # queue-clearing, which reads .exa-workspace/inbox/. With the
            # drain off, a sweep files a report into a folder nothing
            # empties — so it is not scheduled, and it says so rather than
            # quietly doing nothing.
            logger.info(
                "⏸️  Startup system sweep HELD: EXA_BACKGROUND_PROCESSING_ENABLED=false, "
                "so nothing would drain the report it files into the Exa inbox. "
                "Both must be on (see the Exa config page)."
            )
        else:
            logger.info(
                "⏸️  Startup system sweep DISABLED (STARTUP_SWEEP_ENABLED=false). "
                "Run it on demand: POST /api/v1/workflows/execute "
                '{"workflow_id": "system-audit"}'
            )
        # THE MUTE'S STARTUP HEAL (2026-08-29, the notifications-
        # upgrade): a scheduled mute whose end passed during downtime
        # restores at boot (the missed APScheduler job — the config's
        # mute_until is the record; the restore flips + announces).
        try:
            from app.domain.messaging.notifications import ensure_mute_restore
            await ensure_mute_restore()
        except Exception as e:
            logger.warning("⚠️ notifications restore heal failed: %s", e)
    except Exception as e:
        logger.warning(f"⚠️ Failed to schedule the startup system audit: {e}")

    # ── THE INBOX PROCESSOR (2026-08-25, the user's ask) ──────────
    # The recurring queue clearing: every N minutes (default 900s =
    # 15 min, INBOX_PROCESSOR_INTERVAL_SECONDS for testing) — run
    # the log sweep, MOVE the inbox's reports to system-reports/,
    # and toast the user ONLY when the findings need attention
    # (Exa's judgment rules — the queue-clearing skill). The toast
    # never fires for the clean/routine runs.
    async def _process_inbox_once() -> None:
        from app.core.config import Paths as _Paths
        from app.domain.messaging.services import publish
        import shutil
        inbox = _Paths.exa_workspace / "inbox"
        reports_dir = _Paths.exa_workspace / "system-reports"
        if not inbox.exists():
            return
        reports = sorted(inbox.glob("*.md"))
        if not reports:
            return
        reports_dir.mkdir(parents=True, exist_ok=True)
        # THE JUDGMENT (2026-08-25, the live-caught design fix): the
        # toast judges the REPORTS' CONTENT (what Exa reads — the
        # queue-clearing skill's rule), NOT a fresh sweep — the
        # sweep creates the reports; the processor clears the queue.
        # The attention rule: any '**warning**' bullet (the errors /
        # floods) → the user needs to know; clean reports → silent.
        moved = []
        attention_reports = []
        for r in reports:
            text = r.read_text(encoding="utf-8", errors="replace")
            shutil.move(str(r), str(reports_dir / r.name))
            moved.append(r.name)
            if "**warning**" in text:
                attention_reports.append(r.name)
        if attention_reports:
            try:
                publish("notify:exa-queue", {
                    "kind": "log-sweep",
                    "from": "exa",
                    "title": "Exa: queue cleared",
                    "message": f"Exa processed {len(moved)} report(s) — {len(attention_reports)} "
                              f"need attention (errors or floods). The report is in System reports.",
                    "type": "warning",
                })
                logger.info("✅ Inbox processor: %s report(s) moved, %s need attention — toast sent",
                            len(moved), len(attention_reports))
            except Exception as _ne:
                logger.warning("⚠️ Inbox processor notify failed: %s", _ne)
        else:
            logger.info("✅ Inbox processor: %s report(s) moved, clean — no toast", len(moved))

    async def _inbox_processor_loop() -> None:
        while True:
            try:
                await _process_inbox_once()
            except Exception as e:  # the processor must never die
                logger.warning("⚠️ Inbox processor failed: %s", e)
            await asyncio.sleep(_inbox_interval)

    _inbox_interval = int(_os.environ.get("INBOX_PROCESSOR_INTERVAL_SECONDS", "900"))
    if settings.exa_background_processing_enabled:
        _inbox_task = asyncio.create_task(_inbox_processor_loop())
        logger.info("✅ Inbox processor scheduled (recurring, every %ss)", _inbox_interval)
    else:
        # Never silent: the workspace is NOT being drained, and that has a
        # consequence the operator should see stated, not inferred.
        _inbox_task = None
        logger.info(
            "⏸️  Exa background processing DISABLED "
            "(EXA_BACKGROUND_PROCESSING_ENABLED=false) — the workspace is NOT "
            "drained; reports accumulate in .exa-workspace/inbox/"
        )

    yield

    # Shutdown
    logger.info("Shutting down Cogitate application...")

    # ── PHASE ONE of the shutdown record ─────────────────────────────────
    # BEFORE any draining, so that a crash DURING the drain leaves a
    # `draining` row behind as evidence. That stale row is the whole reason
    # for two phases: with a single "was clean" row, a crash would leave the
    # previous clean row in place and the successor would read it happily.
    # No explicit reason: resolves to a PENDING one when a human asked for this
    # exit (the shutdown button), else "sigterm" — the signal we cannot
    # distinguish from a reload. See `set_pending_reason`.
    _record_id = await begin_shutdown_record()
    _completed: list[str] = []
    _abandoned: list[str] = []

    # Drain the inbox processor BEFORE close_db() (absent when Exa background
    # is off). cancel() only requests; drain_task awaits it, bounded.
    if _inbox_task is not None:
        outcome = await drain_task(_inbox_task)
        if outcome in ("stopped", "cancelled"):
            _completed.append("inbox processor")
            logger.info("✅ Inbox processor drained (%s)", outcome)
        elif outcome == "timeout":
            _abandoned.append("inbox processor (still mid-iteration)")
            logger.warning(
                "⚠️ Inbox processor did not stop within %ss — it may still be "
                "mid-iteration (a partial move is possible)",
                SHUTDOWN_DRAIN_SECONDS,
            )
        else:
            _abandoned.append("inbox processor (raised while draining)")

    # Shutdown scheduler
    try:
        from app.workflows.triggers.scheduler import get_scheduler
        scheduler = get_scheduler()
        # wait=True is now SAFE — the transport bounds the whole shutdown
        # (uvicorn --timeout-graceful-shutdown 15s), so an unbounded wait is no
        # longer possible. It is an AsyncIOScheduler, so its jobs run in THIS
        # loop and wait=True genuinely awaits them. With wait=False a running
        # trigger job could still touch the DB after close_db() — the same
        # defect class as the cancelled task fixed just above.
        scheduler.shutdown(wait=True)
        _completed.append("workflow trigger scheduler")
        logger.info("✅ Workflow trigger scheduler shutdown complete")
    except Exception as e:
        _abandoned.append("workflow trigger scheduler (shutdown raised)")
        logger.warning(f"⚠️ Trigger scheduler shutdown error: {e}")

    # ── PHASE TWO — and it MUST precede close_db() ───────────────────────
    # The drain ordering above is what makes this safe: by here, every task
    # we waited on has actually finished. Nothing is abandoned silently —
    # what did not finish is named.
    await complete_shutdown_record(_record_id, _completed, _abandoned)

    await close_db()
    logger.info("Database connections closed")


def create_app() -> FastAPI:
    """
    Application factory.

    Creates and configures the FastAPI application instance.

    Returns:
        FastAPI: Configured application instance
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Multi-agent LLM orchestration platform",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # Mount static files for profile images
    profile_images_path = Path(settings.profile_images_dir)
    profile_images_path.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(profile_images_path)), name="static")

    # Mount the notification sounds (the wav-assets store) — the
    # curated seed is copied in ADDITIVELY (missing files only; user
    # uploads + replaced curated files are never touched — the
    # images' restore doctrine).
    sounds_path = Paths.from_settings(settings).notification_sounds_dir
    sounds_path.mkdir(parents=True, exist_ok=True)
    curated_sounds = Paths.from_settings(settings).curated_sounds_dir
    if curated_sounds.exists():
        for p in curated_sounds.glob("*.wav"):
            target = sounds_path / p.name
            if not target.exists():
                target.write_bytes(p.read_bytes())


    # Include routers
    app.include_router(api_v1_router)

    # Register external access toggle middleware (after routers)
    from app.api.v1.agent_chat.middleware import add_external_access_middleware
    add_external_access_middleware(app)

    # The access-evidence journal (2026-08-20): the rotating
    # access.log that verify-http-evidence reads — uvicorn's own
    # access log is stdout-bound; this file is the robust source.
    from app.core.access_evidence import add_access_evidence_middleware, rotate_access_file
    rotate_access_file(Paths.access_log)
    add_access_evidence_middleware(app, Paths.access_log)

    # Root endpoint
    @app.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        """Root endpoint with basic application info."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "running",
        }

    return app


# Create application instance
app = create_app()
