#!/usr/bin/env python3
"""
Agent Provider Health Check — validate every agent's provider/model.

Recurring issue: agents can reference a deprecated or non-existent
provider/model (e.g. an agent pointing at `deepseek-chat` after a
deprecation, or a model id that never existed). This check surfaces
them BEFORE they fail at chat time.

Checks per agent:
1. Provider exists in the providers table (and is active)
2. Model resolves — present in provider_model_cache OR curated_models
   (the two sources of truth for what a provider actually offers)
3. Recent usage failures (usage_logs, last N days): consecutive
   failures + last error message

Severity:
- FAIL: provider missing/inactive OR model unresolvable (broken config)
- WARN: recent failures on an otherwise-valid config (operational)

Exit code: 1 if any FAIL is found (broken config). WARN (recent
operational failures) is reported but does not fail the gate.
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB = PROJECT_ROOT / "cogitate.db"
FAILURE_WINDOW_DAYS = 7


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open read-only connection (never create a ghost file)."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def _resolve_models(db: sqlite3.Connection) -> Dict[str, set]:
    """Build {provider_name: {model_id, ...}} from cache + curated."""
    resolved: Dict[str, set] = {}
    conn = db

    for provider_id, provider_name, model_id in conn.execute(
        """
        SELECT p.id, p.name, c.model_id
        FROM provider_model_cache c JOIN providers p ON p.id = c.provider_id
        """
    ).fetchall():
        resolved.setdefault(provider_name, set()).add(model_id)

    for provider_id, provider_name, model_id in conn.execute(
        """
        SELECT p.id, p.name, c.model_id
        FROM curated_models c JOIN providers p ON p.id = c.provider_id
        """
    ).fetchall():
        resolved.setdefault(provider_name, set()).add(model_id)

    return resolved


def _usage_failures(
    db: sqlite3.Connection, agent_id: int, window_days: int,
    dismissed_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Recent usage failures for an agent (success=0 within window).

    If dismissed_at is set (agent health_dismissed_at, naive-UTC string),
    failures at or before it are acknowledged and excluded — matching the
    service's health_for_agents (F6).
    """
    # usage_logs.created_at = server_default func.now() → SQLite
    # CURRENT_TIMESTAMP = UTC, stored as a NAIVE string. Use naive UTC with
    # the SPACE separator (matches SQLAlchemy's storage format; isoformat's
    # default 'T' would miscompare at the window-boundary day).
    cutoff = (
        datetime.now(timezone.utc).replace(tzinfo=None)
        - timedelta(days=window_days)
    ).isoformat(sep=' ')
    rows = db.execute(
        """
        SELECT success, error_message, created_at FROM usage_logs
        WHERE agent_id = ? AND created_at >= ?
        ORDER BY id DESC
        """,
        (agent_id, cutoff),
    ).fetchall()

    if dismissed_at:
        # Exclude acknowledged failures (at/before dismissal)
        rows = [r for r in rows if r[2] > dismissed_at]

    failures = [r for r in rows if r[0] == 0]
    consecutive = 0
    for r in rows:
        if r[0] == 0:
            consecutive += 1
        else:
            break  # most recent was success — chain broken

    return {
        "total": len(rows),
        "failures": len(failures),
        "consecutive_failures": consecutive,
        "last_error": failures[0][1] if failures else None,
        "last_failure_at": failures[0][2] if failures else None,
    }


def _count_agents(db_path: Path) -> int:
    """How many agents the scan actually LOOKED AT.

    Separate from ``check_agents`` because the report lists only the agents needing
    attention: an EMPTY report means "nothing to report", not "no agents exist".
    Both states used to print the same words — ``No agents found.`` — over a database
    holding two live agents, so a clean bill of health read as a blind spot. That is
    the one failure this project's checks exist to avoid, and the count is what tells
    the two apart.
    """
    db = _connect(db_path)
    try:
        return int(db.execute("SELECT COUNT(*) FROM agents").fetchone()[0])
    finally:
        db.close()


def check_agents(db_path: Path, include_healthy: bool = False) -> List[Dict[str, Any]]:
    """Run the health scan. Returns report entries."""
    db = _connect(db_path)
    resolved = _resolve_models(db)

    agents = db.execute(
        """
        SELECT id, name, provider, model, is_active, is_builtin
        FROM agents ORDER BY id
        """
    ).fetchall()

    reports: List[Dict[str, Any]] = []

    for agent_id, name, provider, model, is_active, is_builtin in agents:
        entry: Dict[str, Any] = {
            "id": agent_id,
            "name": name,
            "provider": provider,
            "model": model,
            "is_active": bool(is_active),
            "is_builtin": bool(is_builtin),
            "status": "ok",
            "issues": [],
            "usage": {},
        }

        # 1. Provider exists?
        prov = db.execute(
            "SELECT id, is_active FROM providers WHERE name = ?", (provider,)
        ).fetchone()
        if prov is None:
            entry["status"] = "fail"
            entry["issues"].append(f"provider '{provider}' does not exist")
        elif not prov[1]:
            entry["status"] = "fail"
            entry["issues"].append(f"provider '{provider}' is inactive")
        else:
            # 2. Model resolves?
            model_set = resolved.get(provider, set())
            if model not in model_set:
                entry["status"] = "fail"
                entry["issues"].append(
                    f"model '{model}' not found for provider '{provider}' "
                    "(not in model cache or curated list)"
                )

        # 3. Usage failures (only meaningful if config is valid).
        #    Honor health dismissal (F6) so a dismissed warning doesn't
        #    fail the sweep gate.
        dismissed = db.execute(
            "SELECT health_dismissed_at FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()
        entry["usage"] = _usage_failures(
            db, agent_id, FAILURE_WINDOW_DAYS,
            dismissed_at=dismissed[0] if dismissed else None,
        )
        if entry["status"] == "ok" and entry["usage"]["failures"] > 0:
            entry["status"] = "warn"
            entry["issues"].append(
                f"{entry['usage']['failures']} failure(s) in last "
                f"{FAILURE_WINDOW_DAYS}d (consecutive: "
                f"{entry['usage']['consecutive_failures']})"
            )

        if entry["status"] != "ok" or include_healthy:
            reports.append(entry)

    db.close()
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent provider health scan")
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB, help="Path to cogitate.db"
    )
    parser.add_argument(
        "--include-healthy", action="store_true",
        help="Include healthy agents in the report",
    )
    args = parser.parse_args()

    reports = check_agents(args.db, include_healthy=args.include_healthy)
    checked = _count_agents(args.db)

    print("AGENT PROVIDER HEALTH SCAN")
    print("==========================")
    if not reports:
        print(f"  Nothing to report — {checked} agent(s) checked, all healthy.")
        return 0

    fails = [r for r in reports if r["status"] == "fail"]
    warns = [r for r in reports if r["status"] == "warn"]
    ok = [r for r in reports if r["status"] == "ok"]

    for r in reports:
        flag = {"fail": "❌", "warn": "⚠️", "ok": "✅"}[r["status"]]
        print(f"  {flag} [{r['status']:4s}] #{r['id']} {r['name']} "
              f"({r['provider']}/{r['model']})")
        for issue in r["issues"]:
            print(f"       - {issue}")
        u = r["usage"]
        if r["status"] != "ok" and u.get("last_error"):
            print(f"       - last error: {u['last_error'][:120]}")

    print()
    print(f"  RESULT: {len(fails)} fail, {len(warns)} warn, {len(ok)} ok "
          f"(of {checked} checked)")

    # Gate semantics: any FAIL → non-zero exit (WARN is reported, not gated), which
    # is what the module docstring says. The comment here claimed "fail or warn"
    # long after the code stopped doing that.
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
