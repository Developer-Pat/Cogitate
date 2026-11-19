"""C3 gate 2 — the migration chain builds the same schema as `create_all`.

One round trip on a throwaway database:

    empty -> upgrade head -> downgrade base -> upgrade head

and then the alembic-built schema is diffed against a `create_all`-built one:
table set, per-column type affinity/nullability/primary key, and index names.
The last step opens every model against the alembic-built database, so a table
that exists but cannot be queried by its ORM class still fails here.

Usage: python scripts/alembic_roundtrip.py
"""

import asyncio
import os
import sqlite3
import sys
import tempfile

from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import BASE_DIR
from app.core.database import Base

HERE = BASE_DIR / "backend"

# Tables alembic owns, plus SQLite's own bookkeeping for AUTOINCREMENT counters.
NOT_IN_BASELINE = {"alembic_version", "sqlite_sequence"}

AFFINITY = {"INTEGER": "INTEGER", "BOOLEAN": "INTEGER", "REAL": "REAL", "FLOAT": "REAL"}


def alembic_config(url: str) -> Config:
    cfg = Config(str(HERE / "alembic.ini"))
    cfg.set_main_option("script_location", str(HERE / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def tables(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def columns(conn: sqlite3.Connection, table: str) -> dict[str, tuple]:
    shape = {}
    for row in conn.execute(f"PRAGMA table_info({table})"):
        name, decl, not_null, pk = row[1], row[2].upper(), row[3], row[5]
        shape[name] = (AFFINITY.get(decl, decl), None if pk else not_null, pk)
    return shape


def index_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {
        row[1]
        for row in conn.execute(f"PRAGMA index_list({table})")
        if not row[1].startswith("sqlite_auto")
    }


async def build_create_all(path: str) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


async def assert_models_queryable(url: str) -> None:
    """Every model must be able to SELECT against the migrated schema."""
    engine = create_async_engine(url)
    failures: list[str] = []
    total = len(Base.metadata.sorted_tables)
    async with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            try:
                await conn.execute(select(table).limit(0))
            except Exception as exc:  # noqa: BLE001 — the message is the finding
                failures.append(f"{table.name}: {exc}")
    await engine.dispose()
    print(f"models queryable: {total - len(failures)}/{total}")
    if failures:
        print("NOT queryable:")
        for failure in failures:
            print("   ", failure)
        raise SystemExit(1)


def diff_schema(migrated: sqlite3.Connection, fresh: sqlite3.Connection) -> int:
    migrated_tables = tables(migrated) - NOT_IN_BASELINE
    fresh_tables = tables(fresh) - NOT_IN_BASELINE
    failures = 0

    if migrated_tables != fresh_tables:
        failures += 1
        print(f"table set differs — migrated only: {sorted(migrated_tables - fresh_tables)}")
        print(f"                     create_all only: {sorted(fresh_tables - migrated_tables)}")

    for name in sorted(migrated_tables & fresh_tables):
        migrated_cols, fresh_cols = columns(migrated, name), columns(fresh, name)
        for key in sorted(set(migrated_cols) | set(fresh_cols)):
            if migrated_cols.get(key) != fresh_cols.get(key):
                failures += 1
                print(
                    f"column {name}.{key}: migrated {migrated_cols.get(key)}"
                    f" create_all {fresh_cols.get(key)}"
                )

        migrated_idx, fresh_idx = index_names(migrated, name), index_names(fresh, name)
        if migrated_idx != fresh_idx:
            failures += 1
            print(f"indexes on {name} — migrated only: {sorted(migrated_idx - fresh_idx)}")
            print(f"                    create_all only: {sorted(fresh_idx - migrated_idx)}")
    return failures


def main() -> int:
    workdir = tempfile.mkdtemp()
    migrated_path = os.path.join(workdir, "migrated.db")
    fresh_path = os.path.join(workdir, "fresh.db")
    url = f"sqlite:///{migrated_path}"
    cfg = alembic_config(url)

    print("upgrade head ...")
    command.upgrade(cfg, "head")
    after_upgrade = tables(sqlite3.connect(migrated_path)) - NOT_IN_BASELINE
    print(f"   {len(after_upgrade)} tables")

    print("downgrade base ...")
    command.downgrade(cfg, "base")
    leftover = tables(sqlite3.connect(migrated_path)) - NOT_IN_BASELINE
    print(f"   {len(leftover)} tables left")
    if leftover:
        print("   FAIL: downgrade left tables behind:", sorted(leftover))
        return 1

    print("upgrade head again ...")
    command.upgrade(cfg, "head")
    second_upgrade = tables(sqlite3.connect(migrated_path)) - NOT_IN_BASELINE
    print(f"   {len(second_upgrade)} tables")

    asyncio.run(build_create_all(fresh_path))
    failures = diff_schema(sqlite3.connect(migrated_path), sqlite3.connect(fresh_path))

    asyncio.run(assert_models_queryable(f"sqlite+aiosqlite:///{migrated_path}"))

    if after_upgrade != second_upgrade:
        failures += 1
        print("FAIL: the two upgrades disagree")
    print("\nRESULT:", "SYMMETRIC" if failures == 0 else f"{failures} mismatch(es)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
