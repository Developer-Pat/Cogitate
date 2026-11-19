"""C3 gate 1 — the models can build the database the app runs on.

Builds a database from `Base.metadata.create_all` into a temp file and diffs it
against the live `cogitate.db`.

WHAT FAILS, and what is only reported — the distinction is the point:

- **FAIL: content the models cannot produce.** A live table, a live index, or a
  live column that no model declares. That is the C3 defect: a fresh install
  would be missing something the application uses.
- **FAIL: a shared column whose storage class differs** (JSON against TEXT).
  Two spellings of one affinity are not a difference; a different affinity is.
- **REPORT ONLY: the models being AHEAD of the live database.** The live
  databases are grandfathered — `create_all` never adds an index or a
  constraint to an existing table — so a stricter NOT NULL, an extra index or a
  uniqueness the live table lacks is a MIGRATION waiting to happen, not a defect.
  They are printed as notes so the backlog is visible.

Deliberate differences with a reason live in `ACCEPTED`.

Usage: python scripts/schema_parity_check.py [--verbose]
"""

import asyncio
import os
import sqlite3
import sys
import tempfile

from sqlalchemy.ext.asyncio import create_async_engine

import app.main  # noqa: F401 — the real startup import path
from app.core.config import BASE_DIR
from app.core.database import Base

LIVE_DB = str(BASE_DIR / "cogitate.db")

REPAIRED = [
    "workflow_compositions",
    "workflow_kinds",
    "workflow_templates",
    "workflow_approvals",
    "workflow_execution_history",
    "agent_versions",
    "system_manager_config",
    "system_manager_config_records",
    "prompt_templates",
]

# Present in a live database for reasons that are not the models.
RUNTIME_TABLES = {"alembic_version", "_sqlite_manager_audit_log", "sqlite_sequence"}

# Deliberate differences, with the reason. A difference not listed here fails.
ACCEPTED: dict[tuple[str, str], str] = {
    ("collections", "default_tool_permission"): (
        "retired column: nothing reads or writes it. The live database keeps it; "
        "the model does not, and a fresh install never gets it."
    ),
    ("meta_topics", "topic_mappings"): (
        "live is JSON-typed, the model is Text. Every writer JSON-serializes into it "
        "(`macros/services.py`), so a JSON column would double-encode."
    ),
}


def affinity(declaration: str) -> str:
    """SQLite storage class, not the declared spelling.

    `UUID` is TEXT here, `VARCHAR(36)` is TEXT, `BOOLEAN` is INTEGER. A column
    whose type name differs inside one affinity is not drift; a JSON column
    against a TEXT one is, and stays visible.
    """
    declared = declaration.upper()
    if any(token in declared for token in ("CHAR", "CLOB", "TEXT", "UUID")):
        return "TEXT"
    if any(token in declared for token in ("INT", "BOOL")):
        return "INTEGER"
    if any(token in declared for token in ("REAL", "FLOA", "DOUB")):
        return "REAL"
    return declared


async def build_fresh(path: str) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


def tables(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def columns(conn: sqlite3.Connection, table: str) -> dict[str, tuple]:
    """(affinity, not_null, primary_key) per column."""
    shape = {}
    for row in conn.execute(f"PRAGMA table_info({table})"):
        name, decl, not_null, pk = row[1], row[2], row[3], row[5]
        shape[name] = (affinity(decl), None if pk else not_null, pk)
    return shape


def indexed_columns(conn: sqlite3.Connection, table: str) -> set[tuple[str, ...]]:
    """Which COLUMNS are indexed — not what the index is called.

    Index names are cosmetic: the live databases carry the older `idx_*` family
    while the models declare `ix_*`. Comparing the columns catches the
    difference that matters (a lookup nothing indexes) and ignores that one.
    """
    shape = set()
    for row in conn.execute(f"PRAGMA index_list({table})"):
        name = row[1]
        if name.startswith("sqlite_auto"):
            continue
        shape.add(tuple(info[2] for info in conn.execute(f"PRAGMA index_info('{name}')")))
    return shape


def unique_columns(conn: sqlite3.Connection, table: str) -> set[tuple[str, ...]]:
    return {
        tuple(info[2] for info in conn.execute(f"PRAGMA index_info('{row[1]}')"))
        for row in conn.execute(f"PRAGMA index_list({table})")
        if row[2] and not row[1].startswith("sqlite_auto")
    }


def main() -> int:
    verbose = "--verbose" in sys.argv
    path = os.path.join(tempfile.mkdtemp(), "fresh.db")
    asyncio.run(build_fresh(path))

    fresh = sqlite3.connect(path)
    live = sqlite3.connect(LIVE_DB)
    fresh_tables, live_tables = tables(fresh), tables(live)
    runtime = live_tables & RUNTIME_TABLES

    print(f"create_all builds: {len(fresh_tables)} tables")
    print(f"live database:     {len(live_tables)} tables ({len(runtime)} runtime: {sorted(runtime)})")

    failures = 0
    notes = 0
    accepted = 0

    missing_tables = live_tables - fresh_tables - RUNTIME_TABLES
    if missing_tables:
        failures += 1
        print(f"\n== FAIL live tables no model declares: {sorted(missing_tables)}")
    extra_tables = fresh_tables - live_tables
    if extra_tables:
        notes += 1
        print(f"\n== note models declare tables the live database lacks: {sorted(extra_tables)}")

    for table in sorted((live_tables | fresh_tables) - RUNTIME_TABLES):
        fresh_cols, live_cols = columns(fresh, table), columns(live, table)

        for name in sorted(set(live_cols) - set(fresh_cols)):
            reason = ACCEPTED.get((table, name))
            if reason:
                accepted += 1
                print(f"\n== accepted {table}.{name}: {reason}")
            else:
                failures += 1
                print(f"\n== FAIL {table}.{name}: live column, no model declares it")

        for name in sorted(set(fresh_cols) & set(live_cols)):
            live_shape, model_shape = live_cols[name], fresh_cols[name]
            reason = ACCEPTED.get((table, name))
            if live_shape == model_shape:
                continue
            if reason:
                accepted += 1
                print(f"\n== accepted {table}.{name}: {reason}")
            elif live_shape[0] != model_shape[0]:
                failures += 1
                print(f"\n== FAIL {table}.{name}: storage class live {live_shape[0]} model {model_shape[0]}")
            else:
                notes += 1
                if verbose:
                    stricter = "stricter" if model_shape[1] in (0, None) and live_shape[1] == 1 else "looser"
                    print(f"\n== note {table}.{name}: nullability live {live_shape[1]} model {model_shape[1]} ({stricter} model)")

        fresh_idx, live_idx = indexed_columns(fresh, table), indexed_columns(live, table)
        for shape in sorted(live_idx - fresh_idx):
            failures += 1
            print(f"\n== FAIL {table}: live index on {shape}, no model declares it")
        for shape in sorted(fresh_idx - live_idx):
            notes += 1
            if verbose:
                print(f"\n== note {table}: model indexes {shape}, the live database does not")

        for shape in sorted(unique_columns(fresh, table) - unique_columns(live, table)):
            notes += 1
            if verbose:
                print(f"\n== note {table}: model declares UNIQUE on {shape}, the live database does not")

    print(f"\naccepted: {accepted}   reported (model ahead of live): {notes}")
    print("RESULT:", "PARITY" if failures == 0 else f"{failures} defect(s)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
