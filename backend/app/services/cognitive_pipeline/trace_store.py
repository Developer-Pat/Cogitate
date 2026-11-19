"""
Trace store for cognitive pipeline execution traces.

Persists per-request pipeline traces to a dedicated ``pipeline_traces.db``
(SQLite, separate from ``cogitate.db`` and per-agent ``cognitive_memory.db``)
to avoid contention with the shared database.

TTL-based automatic cleanup runs on each write: traces older than 30 days
are pruned.  The cleanup check is cheap (one ``DELETE`` per call) and runs
in the same transaction as the insert.
"""

import sqlite3
import json
import os as _os
import logging
from dataclasses import asdict
from typing import Optional

from app.services.cognitive_pipeline.models import CognitiveResult

logger = logging.getLogger(__name__)

# Default TTL: 30 days
TRACE_TTL_DAYS = 30

# ── Schema ──────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cognitive_traces (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL,
    message_id  INTEGER,
    trace_json  TEXT NOT NULL,
    metrics_json TEXT,
    memory_delta_json TEXT,
    error       TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

_PRAGMAS = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
"""

_TTL_CLEANUP_SQL = "DELETE FROM cognitive_traces WHERE created_at < datetime('now', ?)"

_INSERT_SQL = """
INSERT INTO cognitive_traces
    (session_id, message_id, trace_json, metrics_json, memory_delta_json, error)
VALUES (?, ?, ?, ?, ?, ?)
"""

# ── Helpers ─────────────────────────────────────────────────────────────────

def _db_path() -> str:
    """Return the absolute path to ``pipeline_traces.db``."""
    from app.core.config import Paths, get_settings
    return str(Paths.from_settings(get_settings()).data_dir / "pipeline_traces.db")


def _get_conn() -> sqlite3.Connection:
    """Get a WAL-mode connection, creating the schema if needed."""
    db = _db_path()
    _os.makedirs(_os.path.dirname(db), exist_ok=True)
    conn = sqlite3.connect(db, timeout=5)
    conn.row_factory = sqlite3.Row
    for pragma in _PRAGMAS.strip().split(";"):
        if pragma.strip():
            conn.execute(pragma.strip())
    conn.execute(_SCHEMA_SQL)
    conn.commit()
    return conn


def save_trace(
    result: CognitiveResult,
    session_id: int,
    message_id: Optional[int] = None,
) -> None:
    """Persist a pipeline trace to ``pipeline_traces.db``.

    Parameters
    ----------
    result:
        The completed pipeline result with trace data.
    session_id:
        The session this trace belongs to.
    message_id:
        Optional message ID for correlation.
    """
    try:
        conn = _get_conn()
        conn.execute(
            _INSERT_SQL,
            (
                session_id,
                message_id,
                json.dumps(result.trace.to_dict()),
                json.dumps(asdict(result.metrics)) if result.metrics else None,
                json.dumps(asdict(result.memory_delta)) if result.memory_delta else None,
                result.error,
            ),
        )
        # TTL cleanup — runs in same transaction
        deleted = conn.execute(_TTL_CLEANUP_SQL, (f"-{TRACE_TTL_DAYS} days",)).rowcount
        conn.commit()
        if deleted:
            logger.info(
                "Pipeline trace cleanup: deleted %d trace(s) older than %d days",
                deleted, TRACE_TTL_DAYS,
            )
    except Exception:
        logger.exception("Failed to persist pipeline trace")


def cleanup_old_traces(days: int = TRACE_TTL_DAYS) -> int:
    """Explicit cleanup — delete traces older than *days*.  Returns count."""
    try:
        conn = _get_conn()
        deleted = conn.execute(_TTL_CLEANUP_SQL, (f"-{days} days",)).rowcount
        conn.commit()
        if deleted:
            logger.info("Explicit trace cleanup: deleted %d trace(s) older than %d days", deleted, days)
        conn.close()
        return deleted
    except Exception:
        logger.exception("Trace cleanup failed")
        return 0


# ── Read side ─────────────────────────────────────────────────────────────────
# These back the agent-chat trace endpoints (get_session_trace, list_traces,
# get_metrics, trace-stream). Previously those queried a main-DB
# `cognitive_traces` table that nothing ever wrote — the Debugging UI's
# trace view was effectively empty. The TraceStore (pipeline_traces.db) is
# the live writer, so the reads point here (DB cleanup Phase 1, 1A).

def get_session_trace(session_id: int) -> Optional[dict]:
    """Most recent trace for a session, or None."""
    try:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT id, session_id, message_id, trace_json, metrics_json, "
                "memory_delta_json, error, created_at FROM cognitive_traces "
                "WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except Exception:
        logger.exception("Failed to read session trace")
        return None


def list_traces(limit: int = 50) -> list[dict]:
    """Most recent traces across all sessions, newest first."""
    try:
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT id, session_id, message_id, trace_json, metrics_json, "
                "memory_delta_json, error, created_at FROM cognitive_traces "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:
        logger.exception("Failed to list traces")
        return []


def get_traces_since(last_id: int, limit: int = 10) -> list[dict]:
    """Traces with id > last_id, ascending (for SSE polling)."""
    try:
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT id, session_id, message_id, trace_json, metrics_json, "
                "memory_delta_json, error, created_at FROM cognitive_traces "
                "WHERE id > ? ORDER BY id ASC LIMIT ?",
                (last_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:
        logger.exception("Failed to poll traces")
        return []


def trace_metrics() -> dict:
    """Aggregate metrics across all traces (count, duration, tokens, errors)."""
    try:
        conn = _get_conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM cognitive_traces").fetchone()[0]
            errors = conn.execute(
                "SELECT COUNT(*) FROM cognitive_traces WHERE error IS NOT NULL"
            ).fetchone()[0]
            metrics = {
                "total_runs": total,
                "error_count": errors,
                "avg_duration_ms": 0.0,
                "max_duration_ms": 0.0,
                "total_tokens": 0,
                "avg_tokens_per_run": 0.0,
                "total_llm_calls": 0,
                "total_tool_calls": 0,
                "total_cache_hits": 0,
                "avg_input_tokens": 0.0,
                "avg_output_tokens": 0.0,
            }
            total_input_tokens = 0
            total_output_tokens = 0
            for row in conn.execute(
                "SELECT metrics_json, trace_json FROM cognitive_traces "
                "WHERE metrics_json IS NOT NULL"
            ):
                try:
                    m = json.loads(row[0])
                    t = json.loads(row[1]) if row[1] else {}
                except (TypeError, ValueError):
                    continue
                dur = m.get("total_duration_ms", 0) or 0
                metrics["avg_duration_ms"] += dur
                metrics["max_duration_ms"] = max(metrics["max_duration_ms"], dur)
                tokens = m.get("total_tokens", 0) or 0
                metrics["total_tokens"] += tokens
                metrics["total_llm_calls"] += m.get("llm_calls", 0) or 0
                metrics["total_tool_calls"] += m.get("tool_calls", 0) or 0
                metrics["total_cache_hits"] += m.get("cache_hits", 0) or 0
                # Per-component input/output tokens from trace_json
                for comp in ("context_builder", "executor", "memory_manager", "response_formatter"):
                    comp_data = t.get(comp, {}) if isinstance(t, dict) else {}
                    total_input_tokens += comp_data.get("input_tokens", 0) or 0
                    total_output_tokens += comp_data.get("output_tokens", 0) or 0
            if total:
                metrics["avg_duration_ms"] = round(metrics["avg_duration_ms"] / total, 2)
                metrics["avg_tokens_per_run"] = round(metrics["total_tokens"] / total, 2)
                metrics["avg_input_tokens"] = round(total_input_tokens / total, 2)
                metrics["avg_output_tokens"] = round(total_output_tokens / total, 2)
            return metrics
        finally:
            conn.close()
    except Exception:
        logger.exception("Failed to compute trace metrics")
        return {
            "total_runs": 0, "error_count": 0, "avg_duration_ms": 0.0,
            "max_duration_ms": 0.0, "total_tokens": 0, "avg_tokens_per_run": 0.0,
            "total_llm_calls": 0, "total_tool_calls": 0, "total_cache_hits": 0,
            "avg_input_tokens": 0.0, "avg_output_tokens": 0.0,
        }
