---
title: Paths and Path Resolution
type: devnote
path: wiki/dev-notes/architecture/Paths and Path Resolution.md
confidence: high
updated: 2026-08-17
tags: [type/dev-notes, domain/architecture]
---

# Paths and Path Resolution

How the application resolves its important paths — the discipline
that prevents the phantom-DB bug class (hand-computed paths opening
a wrong or empty file).

## The rule

**Never compute an app path by hand.** Modules import the locator;
they do not re-derive paths from `__file__` arithmetic, `cwd`, or
`BASE_DIR / "name"` recomputation.

## The backend locator — `Paths` (core/config.py)

`Paths.from_settings(settings)` resolves the canonical paths:

- `root` — the project root (BASE_DIR)
- `shared_db` — the shared cogitate.db, derived from
  `settings.database_url` (honors DATABASE_URL overrides; the
  industrial-fork seam — Postgres is an env change, not a code
  change)
- `data_dir`, `monitor_dir` — runtime data + the product/report
  delivery dir
- `rag_index_path`, `code_vector_path`, `rag_status_file` — the
  RAG index + the ingest-status file (the 2026-08-19 conversion:
  the RAG surface was the last hand-computed path class; now the
  locator owns it)
- `exa_home` — the external agent's Cogitate-local home
  (cogitate/.hermes — HERMES_HOME; Phase 1 of the Exa program)
- `exa_workspace` — the Exa DESK (cogitate/.exa-workspace — the
  inbox/reports/drafts/scratch; 2026-08-20, the home/workspace
  split)
- `access_log` — the access-evidence journal (backend/logs/
  access.log — the verify-http-evidence tool's source; the
  middleware's rotating file, 2026-08-20)
- `agents_dir` — the agent workspaces
- `trash_dir` + `trash_dir_for(domain)` — the recoverable-delete
  staging area, and ONE SHELF PER DOMAIN inside it (agents,
  test-runs, reports, dbs, misc). The ROOT is the locator's; the
  shelf NAMES belong to the trash domain registry
  (`app/domain/trash/registry.py`), so the locator deliberately
  carries no second copy of that vocabulary — and `trash_dir_for`
  enforces that a shelf name is a single clean path segment, so a
  misspelling is refused instead of planting a directory nothing
  renders.
- `logs_dir` — backend logs

Every module that opens the shared DB imports `Paths` — the
workflow services, routers, nodes, graphs, the list service, and
the tools that touch cogitate.db.

## The frontend locator — `API_BASE_URL` (services/apiClient.ts)

The single exported constant for the backend base URL
(`import.meta.env.VITE_API_URL || 'http://localhost:8000'`).
Services and fetch sites import it instead of repeating the env
fallback or hardcoding `http://localhost:8000`.

## What the discipline caught (2026-08-17)

- `workflow_router.py` + `template_router.py`: `parent×5` resolved
  to `<install-root>.db` (one directory too high) — a phantom empty DB one
  level above the root (0 bytes). Queries silently returned
  nothing.
- `skills_router.py`: `Path.cwd() / "cogitate.db"` — cwd-dependent
  (broke under the sweep's `backend/` cwd).
- `provisioning_router.py`: a hardcoded absolute cogitate.db path
  wrote "TestAgent" into production during test runs (the
  resurrection bug).
- Frontend: 5 raw `fetch('http://localhost:8000/...')` sites that
  bypassed the env config.

## The health check

`GET /health/comprehensive` reports each canonical path's
resolution (`shared_db`, `data_dir`, `monitor_dir`, `agents_dir`,
`logs_dir`, `exa_home`) — a missing shared DB (phantom class) surfaces as
"degraded" instead of silent wrong behavior.
