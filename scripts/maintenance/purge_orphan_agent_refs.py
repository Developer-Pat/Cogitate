#!/usr/bin/env python3
"""Find — and, on request, clear — rows that name an agent that no longer exists.

WHY THIS EXISTS. The purge inventory (`app/domain/agents/purge.py`) fixed the
LIFECYCLE: from now on a hard delete clears every reference it claims. It cannot
fix the rows already on disk from the deletes that ran BEFORE it — the measured
residue is `usage_logs` naming agent 1, `tool_usage_logs` naming 15/24/25/31/33,
`agent_lists` carrying `[15…24]` and `[30…35]`, and the shared KV store's
`agent_45:` / `agent_48:` keys. This script is that one-off.

WHAT IT REFUSES TO GUESS. A value that is not an integer is NOT treated as a
stray: `agent_tool_grants` holds rows for the EXTERNAL agent under the id
`external`, which has no row in `agents` and is perfectly legitimate. Deleting
"anything not in agents" would take Exa's grants with it.

DRY RUN BY DEFAULT. Nothing is removed without `--apply`, and the reading half
never writes. The write half is deliberately per-row (`DELETE … WHERE col = ?`)
rather than reaching for the lifecycle's purge: these rows belong to agents that
are already gone, so there is no agent to scrub.

Usage:
    python3 scripts/maintenance/purge_orphan_agent_refs.py            # report
    python3 scripts/maintenance/purge_orphan_agent_refs.py --apply    # remove
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.core.config import Paths, get_settings  # noqa: E402
from app.domain.agents.purge import REFERENCE_COLUMNS  # noqa: E402

#: Values that name something which is NOT a row in `agents`, and are legitimate.
NON_AGENT_IDS = {"external"}


def _live_ids(con: sqlite3.Connection) -> set[int]:
    return {int(r[0]) for r in con.execute("SELECT id FROM agents")}


def _reference_columns(con: sqlite3.Connection) -> list[tuple[str, str]]:
    """Every (table, column) that NAMES an agent, read from the schema."""
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    )]
    found: list[tuple[str, str]] = []
    for table in tables:
        if table.startswith("sqlite_"):
            continue
        for row in con.execute(f'PRAGMA table_info("{table}")'):
            if row[1] in REFERENCE_COLUMNS:
                found.append((table, row[1]))
    return sorted(found)


def _values(con: sqlite3.Connection, table: str, column: str) -> list[tuple[str, object]]:
    """(row id, referencing value) pairs — a JSON array column yields one pair per
    element, so the report names WHAT is wrong rather than the row that holds it.
    """
    rows = list(con.execute(f'SELECT rowid, "{column}" FROM "{table}"'))
    out: list[tuple[str, object]] = []
    for rowid, value in rows:
        if value is None:
            continue
        if column == "agent_ids":
            import json

            try:
                for item in json.loads(value):
                    out.append((str(rowid), item))
            except (TypeError, ValueError):
                continue
        else:
            out.append((str(rowid), value))
    return out


def scan(con: sqlite3.Connection) -> dict[tuple[str, str], list[object]]:
    """{(table, column): [stray values]} — read-only."""
    live = _live_ids(con)
    strays: dict[tuple[str, str], list[object]] = {}
    for table, column in _reference_columns(con):
        for _rowid, value in _values(con, table, column):
            text = str(value)
            if text in NON_AGENT_IDS:
                continue
            try:
                numeric = int(text)
            except ValueError:
                continue          # not an agent id at all — never guess
            if numeric not in live:
                strays.setdefault((table, column), []).append(value)
    return strays


def shared_memory_keys(agent_ids: set[int]) -> list[str]:
    """The keys in the shared KV store that name an agent that is GONE."""
    path = Paths.from_settings(get_settings()).data_dir / "cognitive_memory.db"
    if not path.exists():
        return []
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        keys = [r[0] for r in con.execute("SELECT key FROM cognitive_memory")]
    finally:
        con.close()
    out: list[str] = []
    for key in keys:
        if not key.startswith("agent_"):
            continue
        head = key.split(":", 1)[0]
        try:
            if int(head.removeprefix("agent_")) not in agent_ids:
                out.append(key)
        except ValueError:
            continue
    return out


def apply(con: sqlite3.Connection, strays: dict[tuple[str, str], list[object]]) -> int:
    """Remove the strays. Returns how many rows/keys went."""
    import json

    gone = 0
    for (table, column), values in strays.items():
        for value in values:
            if column == "agent_ids":
                for rowid, current in con.execute(
                    f'SELECT rowid, "{column}" FROM "{table}"'
                ):
                    try:
                        items = json.loads(current)
                    except (TypeError, ValueError):
                        continue
                    if value in items:
                        con.execute(
                            f'UPDATE "{table}" SET "{column}" = ? WHERE rowid = ?',
                            (json.dumps([i for i in items if i != value]), rowid),
                        )
                        gone += 1
            else:
                gone += con.execute(
                    f'DELETE FROM "{table}" WHERE "{column}" = ?', (value,)
                ).rowcount
    return gone


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="remove the strays (default: report them only)")
    args = parser.parse_args()

    db = Path(Paths.from_settings(get_settings()).shared_db)
    print(f"database: {db}")
    con = sqlite3.connect(str(db))
    try:
        live = _live_ids(con)
        print(f"live agents: {sorted(live)}")
        strays = scan(con)
        total = sum(len(v) for v in strays.values())
        print(f"\nreferences naming a GONE agent: {total}")
        for (table, column), values in sorted(strays.items()):
            distinct = sorted({str(v) for v in values})
            live_kept = sorted({str(v) for v in values if str(v) in {str(i) for i in live}})
            print(f"  {table}.{column}: {len(values)} reference(s) over {len(distinct)} value(s) "
                  f"{distinct}{'' if not live_kept else f' (live ids kept: {live_kept})'}")

        missing_keys = shared_memory_keys(live)
        print(f"shared KV keys for a GONE agent: {len(missing_keys)}")
        for key in missing_keys:
            print(f"  {key}")

        if not args.apply:
            print("\nDRY RUN — nothing was removed. Re-run with --apply.")
            return 0

        gone = apply(con, strays)
        con.commit()
        if missing_keys:
            mem = Paths.from_settings(get_settings()).data_dir / "cognitive_memory.db"
            mem_con = sqlite3.connect(str(mem))
            try:
                mem_con.executemany(
                    "DELETE FROM cognitive_memory WHERE key = ?",
                    [(k,) for k in missing_keys],
                )
                mem_con.commit()
            finally:
                mem_con.close()
        print(f"\nremoved: {gone} row value(s), {len(missing_keys)} memory key(s)")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
