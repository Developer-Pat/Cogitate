"""The verification store — the honesty loop's persistence (Phase 6).

The verified-facts channel + the track record, in a dedicated
sidecar DB (verification_store.db — the pipeline_traces pattern:
WAL-mode, schema-on-connect, locator-resolved, TTL-pruned).

Two tables:
- verified_facts: facts written ONLY after a check — {claim,
  verified_by, verified_when, source, detail}
- track_record: per-agent operation outcomes — {agent, operation,
  claimed, verified, outcome, at}

The loop's power: it doesn't make the agent honest, it makes the
SYSTEM verify — these tables are that verification's memory.
"""

from __future__ import annotations

import json
import logging
import os as _os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import Paths

logger = logging.getLogger(__name__)

DB_NAME = "verification_store.db"
FACT_TTL_DAYS = 90
TRACK_TTL_DAYS = 365

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS verified_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim TEXT NOT NULL,
    verified_by TEXT NOT NULL,
    verified_when TEXT NOT NULL,
    source TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS track_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,
    operation TEXT NOT NULL,
    claimed TEXT NOT NULL,
    verified TEXT NOT NULL,
    outcome TEXT NOT NULL,
    at TEXT NOT NULL
);
"""

_PRAGMAS = "PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;"


def _db_path() -> str:
    """THE DATA DIRECTORY, RESOLVED — never `Paths.data_dir`.

    That class attribute is a dataclass FIELD DEFAULT (a fixed BASE_DIR/data), so
    it ignores settings: a test running the verification store wrote its rows into
    the operator's own `data/verification_store.db` while every redirected path
    moved into the sandbox. `Paths.from_settings` re-roots EVERY declared path
    from one database location — that is the resolver this module wants.
    """
    from app.core.config import get_settings

    return str(Paths.from_settings(get_settings()).data_dir / DB_NAME)


def _get_conn() -> sqlite3.Connection:
    db = _db_path()
    _os.makedirs(_os.path.dirname(db), exist_ok=True)
    conn = sqlite3.connect(db, timeout=5)
    conn.row_factory = sqlite3.Row
    for pragma in _PRAGMAS.strip().split(";"):
        if pragma.strip():
            conn.execute(pragma.strip())
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Verified facts ─────────────────────────────────────────────────────────

def record_verified_fact(
    claim: str,
    verified_by: str,
    source: str,
    detail: Optional[Dict[str, Any]] = None,
) -> int:
    """Persist a fact ONLY after verification (the channel's contract).

    The caller has already checked: the claim matches the system's
    actual state. This row is the verified truth.
    """
    conn = _get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO verified_facts (claim, verified_by, verified_when, source, detail, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (claim, verified_by, _now(), source, json.dumps(detail) if detail else None, _now()),
        )
        conn.execute("DELETE FROM verified_facts WHERE created_at < datetime('now', ?)",
                     (f"-{FACT_TTL_DAYS} days",))
        conn.commit()
        return int(cur.lastrowid or 0)
    except Exception as e:  # noqa: BLE001
        logger.warning("verification-store: fact record failed: %s", e)
        return 0
    finally:
        conn.close()


def list_verified_facts(limit: int = 50) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT claim, verified_by, verified_when, source, detail FROM verified_facts "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("detail"):
                try:
                    d["detail"] = json.loads(d["detail"])
                except (TypeError, json.JSONDecodeError):
                    pass
            out.append(d)
        return out
    finally:
        conn.close()


# ── Track record ───────────────────────────────────────────────────────────

def record_operation(
    agent: str,
    operation: str,
    claimed: str,
    verified: str,
    outcome: str,
) -> int:
    """Persist an operation outcome — the claimed vs verified vs outcome."""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO track_record (agent, operation, claimed, verified, outcome, at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (agent, operation, claimed, verified, outcome, _now()),
        )
        conn.execute("DELETE FROM track_record WHERE at < datetime('now', ?)",
                     (f"-{TRACK_TTL_DAYS} days",))
        conn.commit()
        return int(cur.lastrowid or 0)
    except Exception as e:  # noqa: BLE001
        logger.warning("verification-store: track record failed: %s", e)
        return 0
    finally:
        conn.close()


def list_track_record(agent: str | None = None, limit: int = 100) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        if agent:
            rows = conn.execute(
                "SELECT agent, operation, claimed, verified, outcome, at FROM track_record "
                "WHERE agent = ? ORDER BY id DESC LIMIT ?",
                (agent, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT agent, operation, claimed, verified, outcome, at FROM track_record "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def reliability(agent: str) -> Dict[str, Any]:
    """The agent's track record summarized — the raw material for
    reliability routing (research, but the data is cheap)."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT outcome FROM track_record WHERE agent = ?", (agent,)
        ).fetchall()
    finally:
        conn.close()
    total = len(rows)
    verified = sum(1 for r in rows if r["outcome"] == "verified")
    return {
        "agent": agent,
        "operations": total,
        "verified": verified,
        "mismatched": total - verified,
        "accuracy": round(verified / total, 3) if total else None,
    }
