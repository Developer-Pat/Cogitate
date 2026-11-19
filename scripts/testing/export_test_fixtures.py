"""Export the reference rows the suite asserts on, as data the tree can carry.

The test sandbox used to start as a COPY of the operator's `cogitate.db`,
because the seeded rows (the workflow kinds catalog, the 36 workflow
templates, the demo compositions, the tool registry) exist nowhere in code.
That made the suite unrunnable on a clean clone — no database, no seed.

This script writes those rows to `backend/tests/fixtures/cogitate_fixtures.json`
so the sandbox can be built from `create_all` + this file instead. Regenerate it
when the reference set changes deliberately:

    python3 scripts/testing/export_test_fixtures.py

Which tables: only reference/fixture content the suite asserts on. Runtime
records (sessions, messages, traces, usage, approvals, execution history) are
deliberately excluded — a test that needs one must create it.
"""

import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.core.config import BASE_DIR, Paths  # noqa: E402  (after the path is on sys.path)
from app.infrastructure.database import Base  # noqa: E402 — registers every model

LIVE_DB = Path(str(Paths.shared_db))
OUT = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "cogitate_fixtures.json"

# Insert order matters: parents before children.
TABLES = (
    "workflow_kinds",
    "workflow_templates",
    "workflow_compositions",
    "tool_categories",
    "tools",
    "agents",
    "agent_tools",
    "workflow_triggers",
    "macro_sets",
    "collections",
    "collection_items",
    "curated_models",
)

INTEGER_LIKE = ("BOOLEAN", "INTEGER", "REAL", "FLOAT", "NUMERIC")

#: The install path is THIS machine's. Tool and template configs embed it
#: (`base_path`), so it is replaced with a placeholder: the fixtures must not
#: carry a home directory, and no test asserts it.
INSTALL_PLACEHOLDER = "<install>"


def portable(value):
    """A cell value with the machine's own paths made relative."""
    if isinstance(value, str):
        return value.replace(str(BASE_DIR), INSTALL_PLACEHOLDER)
    return value


def columns(conn: sqlite3.Connection, table: str) -> list[tuple[str, str]]:
    """The columns to carry: those the MODEL declares.

    The live database can hold retired columns (``collections.default_tool_permission``
    is one — nothing reads it any more). The models are the schema authority, so the
    fixture file follows them, and anything live-only is reported rather than exported.
    """
    declared = {column.name for column in Base.metadata.tables[table].columns}
    live = [(row[1], (row[2] or "").upper()) for row in conn.execute(f"PRAGMA table_info({table})")]
    live_only = [name for name, _ in live if name not in declared]
    if live_only:
        print(f"  {table}: live-only columns not carried: {sorted(live_only)}")
    missing = sorted(declared - {name for name, _ in live})
    if missing:
        print(f"  {table}: declared columns absent from the live database: {missing}")
    return [(name, decl) for name, decl in live if name in declared]


def main() -> int:
    if not LIVE_DB.exists():
        print(f"no live database at {LIVE_DB}")
        return 1

    conn = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    payload: dict[str, object] = {
        "note": (
            "Reference rows the test suite asserts on, exported from a working database. "
            "No runtime records, no credentials. Regenerate with "
            "scripts/testing/export_test_fixtures.py."
        ),
        "tables": {},
    }

    for table in TABLES:
        cols = columns(conn, table)
        rows = []
        for row in conn.execute(f"SELECT * FROM {table}"):
            record = {}
            for name, decl in cols:
                value = row[name]
                if isinstance(value, bytes):
                    continue  # never carry a blob into the tree
                record[name] = portable(value)
            rows.append(record)
        payload["tables"][table] = rows
        print(f"{table:24} {len(rows):4} rows")

    conn.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT} ({OUT.stat().st_size // 1024} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
