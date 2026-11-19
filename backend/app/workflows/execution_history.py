"""
Workflow Execution History — identity records for workflow runs.

Gives every workflow execution a first-class identity record
(workflow_execution_history table), complementing the anonymous
checkpoint journal. Written on workflow start, updated on
complete/fail. Carries template_id, agent link (metadata JSON),
input/output, timestamps, and elapsed time.

Phase A of the workflow-execution-identity proposal
(local/proposals/workflow-execution-identity.md).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, UTC
from typing import Any, Optional

logger = logging.getLogger(__name__)

from app.core.config import Paths, get_settings
DB_PATH = Paths.from_settings(get_settings()).shared_db


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_json(value: Any) -> Optional[str]:
    """Serialize a value to JSON, sanitizing non-serializable objects.

    Workflow outputs frequently contain LangChain message objects
    (HumanMessage etc.). We stringify anything unknown rather than
    failing the write — execution identity must never break.
    """
    if value is None:
        return None
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return json.dumps({"unserializable": True, "preview": str(value)[:200]})


def record_execution_start(
    *,
    execution_id: str,
    template_id: str,
    composition_id: Optional[str] = None,
    parent_execution_id: Optional[str] = None,
    input_data: Optional[dict[str, Any]] = None,
    agent_id: Optional[str] = None,
    extra_metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Insert a workflow_execution_history row for a run that is starting.

    Low-frequency write (once per workflow run) — negligible
    contention. Failure is logged, never raised: execution identity
    must not break workflow execution itself.
    """
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    metadata: dict[str, Any] = dict(extra_metadata or {})
    if agent_id:
        metadata["agent_id"] = agent_id

    try:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO workflow_execution_history (
                    id, composition_id, template_id, parent_execution_id,
                    status, current_step, total_steps, input_data,
                    output_data, error_message, started_at, completed_at,
                    elapsed_seconds, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    execution_id,
                    composition_id,
                    template_id,
                    parent_execution_id,
                    "started",
                    0,
                    None,
                    _safe_json(input_data) if input_data is not None else "{}",
                    None,
                    None,
                    now,
                    None,
                    None,
                    json.dumps(metadata) if metadata is not None else "{}",
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to record workflow start | id={execution_id} | {e}")


def record_execution_complete(
    execution_id: str,
    *,
    status: str,
    output_data: Optional[dict[str, Any]] = None,
    error_message: Optional[str] = None,
    current_step: Optional[int] = None,
    total_steps: Optional[int] = None,
    trace_level: Optional[str] = None,
    node_snapshots: Optional[list[dict]] = None,
    degraded: bool = False,
) -> None:
    """Update an execution record with the final outcome.

    `status` is the run's EXECUTION outcome and `degraded` is the second axis (the 2026-10-07
    ruling): a run whose step failed and was ABSORBED is `completed` AND `degraded`, so a
    surface can say "it finished, with something wrong inside it" without re-deriving that from
    `error_message` — or, worse, from the state's `execution_result.error`, which is overloaded
    with per-item errors from the batch families.
    """
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    # Elapsed: read started_at, compute delta
    elapsed: Optional[float] = None
    try:
        conn0 = _connect()
        try:
            row = conn0.execute(
                "SELECT started_at FROM workflow_execution_history WHERE id = ?",
                (execution_id,),
            ).fetchone()
        finally:
            conn0.close()
        if row and row["started_at"]:
            try:
                started = datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
                ended = datetime.fromisoformat(now.replace("Z", "+00:00"))
                elapsed = (ended - started).total_seconds()
            except ValueError:
                elapsed = None
    except Exception:
        elapsed = None

    # MERGE, never replace: the metadata column already carries the
    # agent_id (set by record_execution_start) and anything extra —
    # overwriting it would silently drop that identity (the ab-test
    # join reads json_extract(metadata, '$.agent_id')).
    try:
        conn = _connect()
        try:
            existing_row = conn.execute(
                "SELECT metadata FROM workflow_execution_history WHERE id = ?",
                (execution_id,),
            ).fetchone()
            existing_metadata: dict[str, Any] = {}
            if existing_row and existing_row["metadata"]:
                try:
                    existing_metadata = json.loads(existing_row["metadata"])
                except (TypeError, ValueError):
                    existing_metadata = {}
            existing_metadata["trace_level"] = trace_level
            existing_metadata["node_snapshots"] = node_snapshots or []
            # THE SECOND AXIS — always written, so a reader never has to INFER "not degraded"
            # from an absent key. Rows recorded before this flag existed have no `degraded`
            # key at all; `_with_degraded` reads those as not degraded.
            existing_metadata["degraded"] = bool(degraded)
            merged_metadata = _safe_json(existing_metadata)

            conn.execute(
                """
                UPDATE workflow_execution_history SET
                    status = ?,
                    output_data = ?,
                    error_message = ?,
                    current_step = ?,
                    total_steps = ?,
                    completed_at = ?,
                    elapsed_seconds = ?,
                    metadata = ?
                WHERE id = ?
                """,
                (
                    status,
                    _safe_json(output_data),
                    error_message,
                    current_step,
                    total_steps,
                    now,
                    elapsed,
                    merged_metadata,
                    execution_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to record workflow completion | id={execution_id} | {e}")


def get_execution(execution_id: str) -> Optional[dict[str, Any]]:
    """Fetch one execution record (for tests / verification)."""
    try:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM workflow_execution_history WHERE id = ?",
                (execution_id,),
            ).fetchone()
        finally:
            conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.warning(f"Failed to read execution | id={execution_id} | {e}")
        return None




def _with_degraded(row: dict[str, Any]) -> dict[str, Any]:
    """The `degraded` flag lifted out of the metadata JSON, for a reader.

    The flag lives in the `metadata` column (no migration: it is a run ANNOTATION, which is what
    that column is for), so every reader of the list would otherwise have to parse JSON to see
    it. Absence reads as NOT degraded — the rows recorded before the flag existed were not
    degraded runs, and a metadata blob that will not parse must never take the list down.
    """
    degraded = False
    raw = row.get("metadata")
    if raw:
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(parsed, dict):
                degraded = bool(parsed.get("degraded"))
        except (TypeError, ValueError):
            degraded = False
    row["degraded"] = degraded
    return row


def list_executions(
    template_id: Optional[str] = None,
    trigger_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List execution records, newest first.

    Filters: template_id and/or trigger_id (trigger_id matches
    input_data JSON containing {"trigger_id": ...} — the scheduler
    records it on triggered runs, which distinguishes direct vs
    triggered executions).
    """
    try:
        conn = _connect()
        try:
            # THE DEBUG SNAPSHOTS ARE NOT SHIPPED (measured: the newest 50 rows carried
            # 4.85 MB and `node_snapshots` was 100% of it, ~95 KB a row). The row keeps them
            # in the database — the maintenance path and a detail read look there — while the
            # LIST stays in kilobytes. `json_valid` guards a hand-edited blob: a malformed
            # metadata column must never take the list endpoint down.
            sql = (
                "SELECT id, composition_id, template_id, parent_execution_id, status, "
                "current_step, total_steps, input_data, output_data, error_message, started_at, "
                "completed_at, elapsed_seconds, "
                "CASE WHEN json_valid(metadata) "
                "     THEN json_remove(metadata, '$.node_snapshots') "
                "     ELSE metadata END AS metadata "
                "FROM workflow_execution_history"
            )
            clauses: list[str] = []
            params: list[Any] = []
            if template_id:
                clauses.append("template_id = ?")
                params.append(template_id)
            if trigger_id:
                clauses.append("input_data LIKE ?")
                params.append(f"%{trigger_id}%")
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            sql += " ORDER BY started_at DESC LIMIT ?"
            params.append(int(limit))
            rows = conn.execute(sql, params).fetchall()
            return [_with_degraded(dict(r)) for r in rows]
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to list executions | {e}")
        return []
def delete_execution(execution_id: str) -> bool:
    """Delete an execution record. Returns True if a row was deleted."""
    try:
        conn = _connect()
        try:
            cur = conn.execute(
                "DELETE FROM workflow_execution_history WHERE id = ?",
                (execution_id,),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to delete execution | id={execution_id} | {e}")
        return False


# ── RETENTION PRIMITIVES (the WINDOWS are config: `workflows/retention.py`) ─────────────
#
# Table-level operations only — the policy, the ordering and the report live in
# `workflows/retention.py`. They sit here because this module owns the table: its connection,
# its JSON column, and its isoformat timestamps (string comparison against a cutoff in the same
# shape is exact).
#
# THE OLD `prune_executions` IS GONE, replaced by these: it deleted rows where
# `completed_at IS NOT NULL` — which left the checkpoint threads behind (nothing ever deleted
# one) and made the 9 stuck `started` rows immortal by construction.


def strip_node_snapshots_before(cutoff_iso: str, *, apply: bool = True) -> tuple[int, int]:
    """Rows whose debug snapshots have aged out, and the snapshot BYTES they hold.

    With `apply=True` the snapshots are removed and the same measurement is returned, so a
    PREVIEW and the act report the same numbers — a preview that measures something else than
    the prune is worse than no preview. The ROW stays; only the blob goes.
    """
    where = (
        "started_at < ? AND json_valid(metadata) "
        "AND json_extract(metadata, '$.node_snapshots') IS NOT NULL"
    )
    try:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT id, LENGTH(json_extract(metadata, '$.node_snapshots')) AS n "
                f"FROM workflow_execution_history WHERE {where}",
                (cutoff_iso,),
            ).fetchall()
            if not rows:
                return 0, 0
            ids = [r["id"] for r in rows]
            snapshot_bytes = sum(r["n"] or 0 for r in rows)
            if apply:
                conn.executemany(
                    "UPDATE workflow_execution_history "
                    "SET metadata = json_remove(metadata, '$.node_snapshots') WHERE id = ?",
                    [(i,) for i in ids],
                )
                conn.commit()
            return len(ids), snapshot_bytes
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to strip node snapshots | {e}")
        return 0, 0


def list_prunable_executions(cutoff_iso: str) -> list[dict[str, Any]]:
    """Rows past their keep-window: `id`, `status` and `ended_at`, newest first.

    `COALESCE(completed_at, started_at)` — a row that never completed still AGES. Requiring a
    `completed_at` is what made the stuck runs permanent, so the cutoff never skips them.
    """
    try:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT id, status, COALESCE(completed_at, started_at) AS ended_at "
                "FROM workflow_execution_history "
                "WHERE COALESCE(completed_at, started_at) < ? "
                "ORDER BY ended_at DESC",
                (cutoff_iso,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to list prunable executions | {e}")
        return []


def delete_executions(ids: list[str]) -> int:
    """Delete the named rows; returns how many went."""
    if not ids:
        return 0
    try:
        conn = _connect()
        try:
            cur = conn.executemany(
                "DELETE FROM workflow_execution_history WHERE id = ?", [(i,) for i in ids]
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to delete executions | {e}")
        return 0


def mark_abandoned_before(cutoff_iso: str, *, apply: bool = True) -> list[str]:
    """The `started` rows older than the cutoff — they are NOT running; return their ids.

    With `apply=True` they become `abandoned`. Nothing in this app could tell an executing run
    from one whose process died, and these rows were exempt from every retention rule (no
    `completed_at`). Marking is a TRUTHFUL status update rather than a deletion, so it does not
    wait for retention to be enabled. `completed_at` stays NULL: the run's end is unknown, and
    inventing a timestamp would be the same lie the status exists to fix.
    """
    try:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT id FROM workflow_execution_history "
                "WHERE status = 'started' AND started_at < ?",
                (cutoff_iso,),
            ).fetchall()
            ids = [r["id"] for r in rows]
            if not ids:
                return []
            if apply:
                conn.executemany(
                    "UPDATE workflow_execution_history SET status = 'abandoned' WHERE id = ?",
                    [(i,) for i in ids],
                )
                conn.commit()
            return ids
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to mark abandoned runs | {e}")
        return []


def retention_stats() -> dict[str, Any]:
    """What the store holds right now — the numbers a preview and a settings surface show."""
    empty: dict[str, Any] = {
        "rows": 0, "metadata_bytes": 0, "snapshot_bytes": 0,
        "oldest": None, "newest": None, "by_status": {},
    }
    try:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS rows, "
                "COALESCE(SUM(LENGTH(metadata)), 0) AS metadata_bytes, "
                "COALESCE(SUM(CASE WHEN json_valid(metadata) THEN "
                "  LENGTH(COALESCE(json_extract(metadata, '$.node_snapshots'), '')) "
                "  ELSE 0 END), 0) AS snapshot_bytes, "
                "MIN(started_at) AS oldest, MAX(started_at) AS newest "
                "FROM workflow_execution_history"
            ).fetchone()
            stats = dict(row)
            stats["by_status"] = {
                r["status"]: r["n"]
                for r in conn.execute(
                    "SELECT status, COUNT(*) AS n FROM workflow_execution_history GROUP BY status"
                )
            }
            return stats
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to read retention stats | {e}")
        return empty
