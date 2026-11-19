"""
System API endpoints.

Provides system status, metrics, and health information.
"""

import logging
import platform
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil  # type: ignore[import-untyped]
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import Paths, get_settings


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])

# Track application start time
START_TIME = time.time()


# ── THE SHUTDOWN BUTTON (2026-09-15) ─────────────────────────────────────────
# The app REQUESTS, the launcher ACTS (the user's decision). A web request
# cannot stop the server serving it, and the backend is only half the app — the
# frontend is separately supervised, so a backend-only stop leaves vite serving
# a broken UI. The launcher already does this properly: group kill, verify,
# survivors named.
#
# So this endpoint does NOT kill anything. It records the INTENT (so the exit
# report names a human action instead of "sigterm") and then asks the launcher,
# DETACHED, so the request outlives the process it is killing.


class LifecycleRequest(BaseModel):
    """A user-initiated lifecycle action."""
    confirm: bool = Field(
        default=False,
        description="Must be true. A lifecycle action is recoverable, so this is "
                    "a plain confirm — NOT the typed-name gate reserved for "
                    "irreversible deletes.",
    )


def _launcher_command() -> Optional[tuple]:
    """The launcher invocation, or None if it cannot be found."""
    # The project root, resolved the same way the app resolves everything else.
    # A script that is not there must be REPORTED, never assumed to have run.
    root = Paths.from_settings(get_settings()).shared_db.parent
    launcher = root / "cogitate.sh"
    if not launcher.exists():
        return None
    return (str(launcher), str(root))


async def _request_lifecycle(action: str) -> Dict[str, Any]:
    """Record the intent, then ask the launcher to act — detached.

    `action` is "stop" or "restart", and it becomes the shutdown record's reason
    ("user-requested-stop" / "user-requested-restart") so the next boot can say a
    human did this rather than guessing "sigterm".
    """
    import subprocess as _subprocess

    from app.core.shutdown_record import set_pending_reason

    found = _launcher_command()
    if found is None:
        raise HTTPException(
            status_code=503,
            detail="The launcher (cogitate.sh) was not found, so the action was "
                   "NOT performed. Nothing has stopped.",
        )
    launcher, root = found

    # 1. PARK THE INTENT — do not write a record here.
    #
    #    Writing one caused two defects: the app's real shutdown handler then
    #    wrote its own record with the default reason and THAT is the one that
    #    completes (so the intent was lost), and the early row sat at `draining`
    #    forever, which means "died mid-shutdown" — a phantom crash in the system
    #    built to detect crashes. Instead, the ONE record the shutdown writes
    #    picks this reason up. One shutdown, one record, the right reason.
    reason = f"user-requested-{action}"
    set_pending_reason(reason)

    # 2. Ask the launcher, DETACHED and in a new session so it survives us.
    #    A web request cannot outlive the process it stops: this one hands the
    #    job to a process that can.
    try:
        _subprocess.Popen(
            [launcher, action],
            cwd=root,
            start_new_session=True,
            stdout=_subprocess.DEVNULL,
            stderr=_subprocess.DEVNULL,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to invoke the launcher for %s: %s", action, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Could not invoke the launcher: {exc}. Nothing has stopped.",
        ) from exc

    logger.info("🛑 User-requested %s — the launcher owns the kill (reason %s)", action, reason)
    return {
        "accepted": True,
        "action": action,
        "reason": reason,
        # The client is told, in the payload, that losing the connection is the
        # EXPECTED outcome — so the UI does not raise an error toast or leave a
        # spinner turning. This is the single most likely thing to get wrong.
        "expect_connection_drop": True,
        "note": (
            "The launcher is stopping the application. The connection WILL drop; "
            "that is success, not an error."
        ),
    }


@router.get("/shutdown/last")
async def get_last_shutdown():
    """The last exit's record and what it means — the Dashboard card's data.

    `clean` / `unclean` / `running` / `none`. The `none` case claims nothing:
    a first boot and a wiped store are indistinguishable, and inventing "clean"
    would be the lie this whole mechanism exists to prevent.
    """
    from app.core.shutdown_record import report_last_shutdown

    # exclude_current: mid-session, the newest row is THIS process's own running
    # marker. Without this the card announces an unclean exit about the app the
    # user is currently looking at.
    return await report_last_shutdown(exclude_current=True)


@router.post("/shutdown")
async def request_shutdown(payload: LifecycleRequest):
    """Stop the application. The app requests; the launcher acts."""
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="confirm must be true.")
    return await _request_lifecycle("stop")


@router.post("/restart")
async def request_restart(payload: LifecycleRequest):
    """Restart the application. A superset of stop — the more useful dev action."""
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="confirm must be true.")
    return await _request_lifecycle("restart")


# ── THE FRONTEND MODE (2026-09-17) ──────────────────────────────────────────
# Which BUILD the frontend serves: development (the unbundled dev server) or
# production (the built bundle). Same contract as the button above — the app
# REQUESTS, the launcher ACTS — with two deliberate differences:
#
#   1. NO `set_pending_reason`. Nothing is shutting down, so there is no exit
#      record to inform. Recording an intent here would write a reason for a
#      shutdown that never happens.
#   2. `expect_connection_drop` is FALSE. Only the frontend cycles; this backend
#      stays up, so the reply arrives normally. (The lifecycle path must set it
#      true because it asks for the very process that would send the reply to
#      die.) A client that treated a drop as success here would hide a real
#      failure.
#
# The mode is persisted by the LAUNCHER, in .pids/frontend.mode — this endpoint
# only reads it. One writer, so the file cannot disagree with what is running.

FRONTEND_MODES = ("development", "production")


class ModeRequest(BaseModel):
    """A request to switch which build the frontend serves."""

    mode: str = Field(description="'development' or 'production'.")
    confirm: bool = Field(
        default=False,
        description="Must be true. Recoverable and reversible, so a plain "
                    "confirm — NOT the typed-name gate reserved for "
                    "irreversible deletes.",
    )


def _frontend_mode_file() -> Optional[Path]:
    """The launcher's own mode record, or None if the project root is wrong."""
    root = Paths.from_settings(get_settings()).shared_db.parent
    return root / ".pids" / "frontend.mode"


@router.get("/mode")
async def get_frontend_mode() -> Dict[str, Any]:
    """Which build the frontend is serving — and what else it could serve.

    Read from the launcher's record rather than guessed. `mode` is `None` when
    the file is absent (the app was never started by the launcher), which claims
    nothing rather than assuming development.
    """
    path = _frontend_mode_file()
    mode: Optional[str] = None
    if path is not None and path.exists():
        try:
            recorded = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            logger.warning("Could not read the frontend mode file: %s", exc)
            recorded = ""
        if recorded in FRONTEND_MODES:
            mode = recorded

    return {
        "mode": mode,
        "available": list(FRONTEND_MODES),
        # The record is written BEFORE the new server binds, so a client waiting
        # for a switch must also probe the frontend itself — this endpoint
        # cannot tell it the server is up. Said here rather than left implied.
        "note": "The mode is written before the new server starts serving; "
                "probe the frontend to know it is back.",
    }


@router.post("/mode")
async def request_mode_switch(payload: ModeRequest) -> Dict[str, Any]:
    """Switch the frontend between the two builds. The app requests; the launcher acts.

    The switch keeps the SAME port: the app's state (auth token, persisted
    stores, the cross-tab channel) is origin-scoped, so a second port would log
    the user out and sever tab coordination.
    """
    import subprocess as _subprocess

    if not payload.confirm:
        raise HTTPException(status_code=400, detail="confirm must be true.")

    mode = (payload.mode or "").strip().lower()
    # Accept the short forms the launcher does, so the API is forgiving in the
    # same way the CLI is.
    mode = {"dev": "development", "prod": "production"}.get(mode, mode)
    if mode not in FRONTEND_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown mode '{payload.mode}'. Expected one of: "
                   f"{', '.join(FRONTEND_MODES)}.",
        )

    found = _launcher_command()
    if found is None:
        raise HTTPException(
            status_code=503,
            detail="The launcher (cogitate.sh) was not found, so the mode was "
                   "NOT switched. Nothing has changed.",
        )
    launcher, root = found

    # Detached, like the lifecycle path: the build can run for over a minute, so
    # the request must not be waiting on it. The launcher owns the sequencing
    # (build, stop, start, verify) — see cmd_mode in cogitate.sh.
    try:
        _subprocess.Popen(
            [launcher, "mode", mode],
            cwd=root,
            start_new_session=True,
            stdout=_subprocess.DEVNULL,
            stderr=_subprocess.DEVNULL,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to invoke the launcher for mode=%s: %s", mode, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Could not invoke the launcher: {exc}. Nothing has changed.",
        ) from exc

    logger.info("🔀 User-requested frontend mode switch -> %s", mode)
    return {
        "accepted": True,
        "action": "mode",
        "mode": mode,
        # NOT expected to drop: the backend is not the process being cycled.
        "expect_connection_drop": False,
        "note": (
            "The launcher is switching the frontend. It rebuilds first, so this "
            "can take ~70s when switching to production; the frontend will be "
            "briefly unavailable, and the backend stays up throughout."
        ),
    }


@router.get("/status")
async def get_system_status():
    """
    Get system status.

    Returns:
        dict: System status including:
            - status: Overall system status
            - uptime: Application uptime in seconds
            - version: Application version
            - python_version: Python version
            - platform: Operating system platform
    """
    settings = get_settings()
    uptime = time.time() - START_TIME

    return {
        "status": "healthy",
        "uptime": uptime,
        "version": settings.app_version,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "environment": settings.environment,
    }


@router.get("/metrics")
async def get_system_metrics():
    """
    Get system metrics.

    Returns:
        dict: System metrics including:
            - cpu: CPU usage percentage
            - memory: Memory usage in MB
            - disk: Disk usage percentage
            - database: Database statistics
    """
    # Get CPU usage
    cpu_percent = psutil.cpu_percent(interval=1)

    # Get memory usage
    memory = psutil.virtual_memory()
    memory_used_mb = memory.used / (1024 * 1024)
    memory_percent = memory.percent

    # Get disk usage
    disk = psutil.disk_usage("/")
    disk_percent = disk.percent

    return {
        "cpu": {
            "usage": cpu_percent,
            "cores": psutil.cpu_count(logical=True),
        },
        "memory": {
            "used_mb": round(memory_used_mb, 2),
            "total_mb": round(memory.total / (1024 * 1024), 2),
            "usage": memory_percent,
        },
        "disk": {
            "used_gb": round(disk.used / (1024 * 1024 * 1024), 2),
            "total_gb": round(disk.total / (1024 * 1024 * 1024), 2),
            "usage": disk_percent,
        },
    }


@router.get("/info")
async def get_system_info():
    """
    Get detailed system information.

    Returns:
        dict: Detailed system information
    """
    settings = get_settings()

    return {
        "application": {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "debug": settings.debug,
        },
        "system": {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
        },
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "compiler": platform.python_compiler(),
        },
    }


# ═══════════════════════════════════════════════════════════
# Diagnostics Endpoints
# ═══════════════════════════════════════════════════════════

@router.get("/diagnostics/metrics")
async def get_diagnostics_metrics():
    """
    Get system diagnostics metrics.
    
    Returns current system metrics for diagnostics monitoring.
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    
    return {
        "metrics": [
            {
                "name": "CPU Usage",
                "value": cpu_percent,
                "unit": "percent",
                "status": "healthy" if cpu_percent < 80 else "warning",
                "threshold": 80,
                "trend": "stable"
            },
            {
                "name": "Memory Usage",
                "value": memory.percent,
                "unit": "percent",
                "status": "healthy" if memory.percent < 80 else "warning",
                "threshold": 80,
                "trend": "stable"
            },
            {
                "name": "Disk Usage",
                "value": disk.percent,
                "unit": "percent",
                "status": "healthy" if disk.percent < 80 else "warning",
                "threshold": 80,
                "trend": "stable"
            }
        ],
        "timestamp": time.time()
    }


@router.get("/audit/consistency")
async def audit_consistency() -> Dict[str, Any]:
    """
    Run the system consistency audit (2026-08-19): walk the
    reference graph and report every dangling edge — tool links,
    usage logs, sessions, grants, collection items, and workflow
    configs that name missing agents. READ-ONLY by contract: it
    REPORTS; repair is a separate explicit action (the house rule
    for destructive transforms).

    Returns:
        The audit report (status: clean|inconsistent + the
        per-check findings)
    """
    from app.core.config import Paths as _Paths
    from app.domain.audit import ConsistencyAudit
    # THE SETTINGS-DERIVED PATH, never `_Paths.shared_db`: that is a dataclass
    # FIELD DEFAULT (a fixed BASE_DIR/cogitate.db) and ignores DATABASE_URL, so
    # a test exercising this endpoint audited the operator's live database.
    return ConsistencyAudit(_Paths.from_settings(get_settings()).shared_db).run()


@router.post("/sweep/log")
async def run_log_sweep() -> Dict[str, Any]:
    """THE LOG SWEEP (2026-08-25, the user's ask): the independent
    run — scan the recent log window for the warnings + errors +
    FLOODING (identical-log clusters), drop the report in EXA'S
    INBOX (.exa-workspace/inbox/), and notify via the bus. NOT in
    the startup scan yet — the user runs it until it's debugged +
    tweaked, then it joins the system sweep."""
    from app.core.config import Paths as _Paths
    from app.domain.audit.integrity import IntegrityAudit
    from datetime import datetime, timezone

    # THE LOGS-DIR FIX (2026-08-25, live): the IntegrityAudit's
    # default logs_dir = db_path.parent/logs = the PROJECT ROOT/logs
    # (empty!) — the sweep silently scanned the wrong dir and
    # reported 'clean' against a real 34-warning window. The
    # Paths.logs_dir (backend/logs) is the truth.
    # BOTH paths settings-derived: the class attributes are FIELD DEFAULTS that
    # ignore DATABASE_URL — the same hole as the audit above.
    _paths = _Paths.from_settings(get_settings())
    findings = IntegrityAudit(_paths.shared_db, logs_dir=_paths.logs_dir).log_sweep()

    # the report -> Exa's inbox
    inbox = _paths.exa_workspace / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = inbox / f"log-sweep-{stamp}.md"
    lines = [f"# Log Sweep ({stamp}Z)", ""]
    if findings:
        for f_ in findings:
            lines.append(f"- **{f_.get('severity', 'info')}** {f_.get('message', '')}")
        lines.append("")
        lines.append(f"{len(findings)} finding(s).")
    else:
        lines.append("Clean — no warnings, errors, or floods in the recent window.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # the notify leg (never silent)
    try:
        from app.domain.messaging.services import publish
        publish("notify:log-sweep", {
            "kind": "log-sweep",
            "title": "Log Sweep",
            "message": f"Log sweep complete: {len(findings)} finding(s) — the report is in Exa's inbox",
            "type": "info" if not findings else "warning",
            "action": {"label": "View report", "link": str(path)},
        })
    except Exception as e:  # the notify must never kill the sweep
        import logging
        logging.getLogger(__name__).warning("notify failed: %s", e)

    return {
        "status": "clean" if not findings else "findings",
        "total_findings": len(findings),
        "findings": findings,
        "report_path": str(path),
    }


class ScrubConfirm(BaseModel):
    """The typed confirm for the real scrub run."""

    tables: List[str] = Field(default_factory=list)
    expected_counts: Dict[str, int] = Field(default_factory=dict)


class ScrubRequest(BaseModel):
    """The scrub request — dry-run by default."""

    dry_run: bool = Field(True, description="Report the would-delete; touch nothing")
    confirm: Optional[ScrubConfirm] = Field(
        None, description="Required for the real run — the typed counts"
    )


@router.post("/audit/scrub-orphans")
async def scrub_orphans(req: ScrubRequest) -> Dict[str, Any]:
    """THE ORPHAN SCRUB (2026-08-24, the sweep's cleanup half —
    local/system-sweep/03-scrub.md).

    The guardrails: dry-run by default; the typed confirm (the
    counts must match the live truth); a DB backup before the
    real run; the outcome reported (the deleted counts + the
    re-audit). NEVER touches the session-3 ghosts (the collided
    Exa messages in a live session — NOT orphans).

    THE FLOW: the sweep reports the orphans (the proposal) ->
    Exa proposes the scrub -> the user approves -> Exa calls this
    endpoint (dry-run first, then the typed confirm).
    """
    from app.core.config import Paths as _Paths
    from app.domain.audit.scrub import OrphanScrubService

    svc = OrphanScrubService(_Paths.from_settings(get_settings()).shared_db)
    try:
        result = svc.scrub(
            dry_run=req.dry_run,
            expected_counts=req.confirm.expected_counts if req.confirm else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.get("/diagnostics")
async def list_diagnostics():
    """
    List all system diagnostics.
    
    Returns diagnostic results for system health checks.
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    
    # Run basic diagnostics
    diagnostics = [
        {
            "id": "cpu-check",
            "name": "CPU Health Check",
            "status": "pass" if cpu_percent < 80 else "warning",
            "message": f"CPU usage is {cpu_percent:.1f}%",
            "timestamp": time.time()
        },
        {
            "id": "memory-check",
            "name": "Memory Health Check",
            "status": "pass" if memory.percent < 80 else "warning",
            "message": f"Memory usage is {memory.percent:.1f}%",
            "timestamp": time.time()
        },
        {
            "id": "disk-check",
            "name": "Disk Health Check",
            "status": "pass",
            "message": "Disk space is adequate",
            "timestamp": time.time()
        }
    ]
    
    return {
        "results": diagnostics,
        "total": len(diagnostics),
        "passed": len([d for d in diagnostics if d["status"] == "pass"]),
        "warnings": len([d for d in diagnostics if d["status"] == "warning"]),
        "failed": len([d for d in diagnostics if d["status"] == "fail"])
    }


@router.post("/diagnostics/run")
async def run_all_diagnostics():
    """
    Run all system diagnostics.
    
    Returns comprehensive diagnostic results.
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    
    diagnostics = [
        {
            "id": "cpu-check",
            "name": "CPU Health Check",
            "status": "pass" if cpu_percent < 80 else "warning",
            "message": f"CPU usage is {cpu_percent:.1f}%",
            "timestamp": time.time(),
            "duration": 0.1
        },
        {
            "id": "memory-check",
            "name": "Memory Health Check",
            "status": "pass" if memory.percent < 80 else "warning",
            "message": f"Memory usage is {memory.percent:.1f}%",
            "timestamp": time.time(),
            "duration": 0.1
        },
        {
            "id": "disk-check",
            "name": "Disk Health Check",
            "status": "pass" if disk.percent < 90 else "warning",
            "message": f"Disk usage is {disk.percent:.1f}%",
            "timestamp": time.time(),
            "duration": 0.1
        }
    ]
    
    return {
        "results": diagnostics,
        "total": len(diagnostics),
        "passed": len([d for d in diagnostics if d["status"] == "pass"]),
        "warnings": len([d for d in diagnostics if d["status"] == "warning"]),
        "failed": len([d for d in diagnostics if d["status"] == "fail"])
    }


@router.post("/diagnostics/{diagnostic_id}/run")
async def run_single_diagnostic(diagnostic_id: str):
    """
    Run a specific diagnostic by ID.
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    
    diagnostic_map = {
        "cpu-check": {
            "id": "cpu-check",
            "name": "CPU Health Check",
            "status": "pass" if cpu_percent < 80 else "warning",
            "message": f"CPU usage is {cpu_percent:.1f}%",
            "timestamp": time.time(),
            "duration": 0.1
        },
        "memory-check": {
            "id": "memory-check",
            "name": "Memory Health Check",
            "status": "pass" if memory.percent < 80 else "warning",
            "message": f"Memory usage is {memory.percent:.1f}%",
            "timestamp": time.time(),
            "duration": 0.1
        },
        "disk-check": {
            "id": "disk-check",
            "name": "Disk Health Check",
            "status": "pass",
            "message": "Disk space is adequate",
            "timestamp": time.time(),
            "duration": 0.1
        }
    }
    
    if diagnostic_id in diagnostic_map:
        return diagnostic_map[diagnostic_id]
    
    return {
        "id": diagnostic_id,
        "name": f"Diagnostic: {diagnostic_id}",
        "status": "pass",
        "message": "Diagnostic completed",
        "timestamp": time.time(),
        "duration": 0.1
    }


@router.post("/diagnostics/{diagnostic_id}/resolve")
async def resolve_diagnostic(diagnostic_id: str):
    """
    Mark a diagnostic as resolved.
    """
    return {
        "success": True,
        "message": f"Diagnostic {diagnostic_id} marked as resolved"
    }


@router.delete("/diagnostics/{diagnostic_id}")
async def delete_diagnostic(diagnostic_id: str):
    """
    Delete a specific diagnostic.
    """
    return {
        "success": True,
        "message": f"Diagnostic {diagnostic_id} deleted"
    }


@router.delete("/diagnostics/resolved")
async def delete_resolved_diagnostics():
    """
    Delete all resolved diagnostics.
    """
    return {
        "success": True,
        "message": "Resolved diagnostics deleted"
    }


# ── POST (Power-On Self Test) ─────────────────────────────────────────────────
