---
title: Alembic Migrations
type: atlas-devnote
category: configuration
order: 4
confidence: high
updated: 2026-11-17
tags: [type/dev-notes, domain/configuration]
---

# Alembic Migrations

## One baseline, generated from the models

The chain is a **single revision**: `backend/alembic/versions/0001_baseline.py`. It was
generated from `Base.metadata` by autogenerate against an empty database, so
`alembic upgrade head` and `init_db`'s `create_all` build the **same** schema by
construction — 53 tables, the same columns, the same indexes.

That equality is the point. The previous chain could not be replayed: its first three
revisions contained no DDL and the fourth `ALTER`ed a table nothing had created, while
nine tables existed only as migration DDL and never in the models. Neither mechanism
could build a fresh database on its own.

The models are therefore the single source of truth, and this revision is not edited
by hand:

- **A schema change is a new revision on top of `0001`** — never an edit to it.
  (While the tree is still unpublished the baseline itself may be regenerated from
  the models, which is cheaper than a delta that means nothing yet; the moment the
  chain leaves the machine, that stops.)
- `create_all` still runs at startup (`init_db`), so a fresh install works either way;
  alembic exists for the changes `create_all` cannot make (drops, type changes,
  backfills).

## The pieces that must stay in step

| piece | what it does |
|---|---|
| `app/infrastructure/database/models.py` | declares the tables |
| `app/infrastructure/database/__init__.py` | the **registration point** — every model module is imported here, which is what puts the table on `Base.metadata` |
| `alembic/env.py` | imports that same package, so autogenerate's `target_metadata` is the real schema |
| `backend/scripts/schema_parity_check.py` | proves `create_all` still matches the live database |
| `backend/scripts/alembic_roundtrip.py` | proves `upgrade head → downgrade base → upgrade head` is symmetric and equal to `create_all` |

**A new model must be imported in `__init__.py`** (the import block *and* `__all__`). A
model whose module is never imported is invisible: `create_all` will not create its
table, autogenerate will not see it, and a foreign key pointing at it fails at
metadata-sort time with `NoReferencedTableError` — which is how `tools` was found
missing from the registration point.

## Commands

```bash
cd backend
alembic current                    # the revision the database is stamped at
alembic upgrade head               # apply pending revisions
alembic downgrade base             # drop everything the baseline creates
alembic revision --autogenerate -m "what changed" --rev-id 0002
alembic stamp --purge head         # re-stamp a database whose recorded revision is gone
```

Revision ids continue the numeric series (`0002`, `0003`, …) — pass `--rev-id` because
autogenerate defaults to a random hash. Never the hash style.

**The URL is the app's, not the ini's.** `env.py` sets `sqlalchemy.url` from
`settings.database_url` — `DATABASE_URL` when it is set, otherwise `<project root>/cogitate.db`
— stripping the async driver (`+aiosqlite`) for alembic's synchronous engine. `alembic.ini`
deliberately carries no URL of its own: a `DATABASE_URL` override must migrate the database the
app will open, not a second file at a hardcoded path.

## Existing databases

Every database that predates the baseline is **stamped**, not migrated:
`alembic stamp --purge head` writes `0001` into `alembic_version` without running any
DDL, because the tables are already there. `--purge` matters when the recorded revision
names a deleted file — without it alembic refuses to resolve the current version.

## Verifying the schema path

```bash
cd backend
../.venv/bin/python scripts/schema_parity_check.py    # create_all == live database
../.venv/bin/python scripts/alembic_roundtrip.py      # chain is symmetric == create_all
```

Both must print `PARITY` / `SYMMETRIC`. Run them after any model change and after any
new revision.

## Pitfalls

- **Autogenerate refuses an empty database** ("Target database is not up to date"). Stamp
  the throwaway database at head first, or generate against a copy of a migrated one.
- **Do not point autogenerate at the live database** to generate a whole-schema revision:
  it produces a diff and will propose dropping the runtime tables
  (`_sqlite_manager_audit_log`, `alembic_version`).
- **SQLite cannot alter most things**; use `op.batch_alter_table` for column changes, and
  table-rebuild patterns for renames.
- **A migration is a record of what it did** — never import live app code into one, or the
  file silently changes meaning later.
