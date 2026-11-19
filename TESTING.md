# Testing Guide

This document describes the testing setup for the Cogitate monorepo, covering both the Python backend and the TypeScript/React frontend, along with the automated test report generator.

---

## Test Report Generator

**The runner is [`scripts/testing/run_tests.py`](scripts/testing/run_tests.py)** — one run is one folder under
`data/test-runs/<name>/` (`report.md`, `report.xml`, `events.jsonl`), which is what the `/testing-dashboard`
page starts, watches and cancels, and what `--group {unit,workflows,api,components}` partitions. Everything
below describes `generate_test_report.py`, the older single-file markdown report, which still exists and is
what `README.md` points at.

A script at [`scripts/testing/generate_test_report.py`](scripts/testing/generate_test_report.py) runs both backend (pytest) and frontend (vitest) suites and produces a timestamped markdown report with pass/fail counts, timing breakdowns, and lists of all failed tests.

### Usage

```bash
# From the project root:

# Default (light scan) — excludes @pytest.mark.slow and StreamingService.test.ts (~2 min)
python3 scripts/testing/generate_test_report.py

# Medium scan — excludes only @pytest.mark.slow tests (includes StreamingService)
python3 scripts/testing/generate_test_report.py --medium

# Full sweep — runs everything (~5-6 min)
python3 scripts/testing/generate_test_report.py --full-sweep

# Custom output path
python3 scripts/testing/generate_test_report.py --output my-report.md
```

### Output Location

Reports are written to `backend/reports/test-report-{date}.md` by default. For example:
- `backend/reports/test-report-{date}.md`

The `backend/reports/` directory is gitignored, so reports are never committed.
This location is inside the backend tree so the application can serve reports in the future.

### Report Contents

Each report includes:

| Section | Description |
|---------|-------------|
| **Build Status Dashboard** | At-a-glance ✅/⚠️/❌ status for pytest and vitest |
| **Backend — pytest** | Passed, failed, skipped, warnings counts + duration |
| **Frontend — vitest** | Test files, passed, failed counts + duration |
| **Failed Tests** | Full dotted paths of every failing test |
| **Timing Breakdown** | Duration per suite and % of total time |
| **Known Issues** | Failures classified by type — 🔌 connection errors (need backend running), ❌ code-level failures (actual bugs), ❓ unclassified |

### Light-Scan vs Full-Sweep Strategy

| Mode | Command | Typical Duration | What's Excluded |
|------|---------|:----------------:|-----------------|
| **Light scan** | _(default)_ | ~2 min | `@pytest.mark.slow`, `StreamingService.test.ts` |
| **Medium scan** | `--medium` | ~4 min | `@pytest.mark.slow` only |
| **Full sweep** | `--full-sweep` | ~5-6 min | Nothing |

**Recommended workflow:**
1. Run default (light scan) during active development for quick feedback
2. Run `--full-sweep` before committing to catch regressions

---

## Running Tests Directly

---

## Backend Tests (`backend/`)

### Test Runner

[pytest](https://docs.pytest.org/) with the `pytest-asyncio` plugin for async test support.

```bash
cd backend

# Run the full suite (excluding e2e)
uv run pytest --ignore=tests/e2e

# Run a specific test file
uv run pytest tests/unit/tools/test_execution_service.py -v

# Run a specific test class or method
uv run pytest tests/components/test_state_machine.py::TestStateMachine -v

# Run with verbose output and short tracebacks
uv run pytest --no-header -q --tb=short

# Run async tests that require the anyio backend
uv run pytest -k "anyio"
```

### Configuration

Test settings are in [`backend/pyproject.toml`](backend/pyproject.toml) under `[tool.pytest.ini_options]`:

- **`asyncio_mode = "auto"`** — async test functions are automatically detected and run
- **`testpaths`** — declared paths for discovery; note this list is outdated and doesn't include `tests/unit/` or `app/workflows/tests/`

### Directory Layout

The directories ARE the runner's groups (`scripts/testing/run_tests.py --group <name>`):

```
backend/tests/
├── unit/          # Fast, isolated — most of the suite
├── api/           # HTTP surface: routers, validation, error shapes
├── components/    # Component-level behaviour (vector stores, services)
├── workflows/     # LangGraph workflows, templates, compositions
├── integration/   # Real HTTP/DB round trips
├── e2e/           # End-to-end; needs the backend running, excluded by default
├── meta/          # Tests of the test harness itself (never collected by a group)
├── conftest.py    # Shared engine, test client, fixtures, the shared-db guard
└── ...
```

### Conftest Files

Two conftest files provide test infrastructure:

| File | Scope | Purpose |
|------|-------|---------|
| [`backend/tests/conftest.py`](backend/tests/conftest.py) | Global | Creates a temp-file-based async SQLite engine, provides `test_engine` (session-scoped), `test_session` (function-scoped), and `client` (HTTP test client) fixtures |
| [`backend/tests/workflows/conftest.py`](backend/tests/workflows/conftest.py) | Workflow tests only | Skips a test at collection time when a table it needs is absent from the sandbox — resolved through `Paths`, so the check reads the temporary copy, not the production file |

### Key Fixtures (from `backend/tests/conftest.py`)

```python
# Session-scoped engine — creates all ORM tables once per test run
@pytest_asyncio.fixture(scope="session")
async def test_engine(): ...

# Function-scoped session — rollback after each test
@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine) -> AsyncSession: ...

# HTTP test client with DB dependency overrides
@pytest_asyncio.fixture(scope="function")
async def client(test_engine) -> AsyncClient: ...
```

### Database Isolation

Tests use a **temporary file-based SQLite** database, never the production `cogitate.db`. The engine is
session-scoped (tables created once), and the autouse `auto_clean_tables` fixture truncates every
ORM-managed table after each test function, so one test cannot see another's rows — including rows written
through the raw `sqlite3` connections some tests open instead of the ORM session.

The file starts from one of **two origins**, and both are the same schema:

| origin | when | what fills it |
|---|---|---|
| a copy of a real database | this machine has `cogitate.db` | `sqlite3`'s backup API, read-only on the source |
| the models plus reference rows | a clean clone, no database | `Base.metadata.create_all`, then `backend/tests/fixtures/cogitate_fixtures.json` (12 tables: agents, tools, collections, curated models, macro sets …) |

Neither path is a lesser one, and the suite has to pass on the second: `scripts/testing/verify_flat_tree.sh`
runs the fast suite in a tree with no database and no `.env`. The fixture file is the thing that could drift
from the models — measured 2026-11-18, its 12 tables are all in the ORM and none of its columns is unknown
to them; regenerate it with `scripts/testing/export_test_fixtures.py` when a table changes.

### The workflow tests

They live at `backend/tests/workflows/`, beside the unit and component tests, and most of them reach the
database through raw `sqlite3` rather than the ORM. A module-level check in
[`backend/tests/workflows/conftest.py`](backend/tests/workflows/conftest.py) skips a test at collection time
when a table it needs is missing from the sandbox, so a missing table shows as a **skip**, never as
`no such table` mid-run.

### Tests Located Outside `tests/` — none

Every backend test is under `backend/tests/`, grouped by kind (`unit/`, `workflows/`, `components/`, `api/`,
`integration/`, `e2e/`). The workflow tests used to sit inside the application package, at
`backend/app/workflows/tests/`; that tree is gone, and a module that names it is describing a directory
that no longer exists.

---

## Frontend Tests (`frontend/`)

### Test Runner

[Vitest](https://vitest.dev/) with [jsdom](https://github.com/jsdom/jsdom) environment for DOM simulation.

```bash
cd frontend

# Run all tests once
npm run test

# Run with UI
npm run test:ui

# Run in watch mode
npm run test:watch

# Run with coverage
npm run test:coverage
```

### Configuration

Frontend test settings are in [`frontend/vitest.config.ts`](frontend/vitest.config.ts):

- **`globals: true`** — `describe`, `it`, `expect` available without imports
- **`environment: 'jsdom'`** — browser-like environment
- **`setupFiles`** — `./src/test/setup.ts` runs before each test file
- **Coverage** via `v8` provider, excludes `node_modules/`, test utilities, config, and dist

### Directory Layout

```
frontend/src/
├── __tests__/           # Test files
│   └── smoke.test.tsx   # Basic infrastructure smoke test
└── test/                # Test utilities and setup
    ├── setup.ts         # Vitest setup file (runs before tests)
    └── test-utils.tsx   # Shared test utilities
```

### Running TypeScript Checks

```bash
cd frontend
npx tsc -b              # TypeScript compilation check
```

---

## Root-Level Tests

The root [`pyproject.toml`](pyproject.toml) includes a minimal pytest configuration for smoke-level tests:

```bash
# From project root
uv run pytest                  # Runs tests collected from root
```

These primarily cover [`main.py`](main.py) and basic infrastructure checks.

---

## Static Analysis

| Tool | Command | Scope |
|------|---------|-------|
| **Ruff** | `uv run ruff check backend/` | Python linting (0 errors) |
| **Mypy** | `uv run mypy backend/app/` | Python type checking (0 errors) |
| **tsc** | `npx tsc -b` (from `frontend/`) | TypeScript compilation (0 errors) |
| **ESLint** | `npm run lint` (from `frontend/`) | TypeScript/JS linting |

---

## Common Commands Cheat Sheet

```bash
# === Backend ===

# Run everything except long-running e2e tests
uv run pytest --ignore=tests/e2e --ignore=tests/integration

# Run a specific area
uv run pytest tests/unit/tools/
uv run pytest tests/components/
uv run pytest tests/integration/

# Run with coverage
uv run pytest --cov=app --cov-report=term-missing

# Run and stop on first failure
uv run pytest -x --ignore=tests/e2e

# Lint and type-check
uv run ruff check backend/
uv run mypy backend/app/

# === Frontend ===

npm run test                    # Run once
npm run test:coverage           # Run with coverage
npx tsc -b                      # Type check
npm run lint                    # Lint

# === All-in-one smoke check ===

./cogitate.sh start             # Start services
curl http://localhost:8000/api/v1/health  # Verify backend
npm run build                   # Verify frontend builds
```

---

## Areas That Need Work

1. **`test_phase_2_gate.py` repeats three modules that now cover the same ground.** It holds session-numbered
   copies of the observability, agent-versioning and error-handling checks — as substring route matches and
   pass/fail counters — plus one `test_integration` the three modules do not have. The files it duplicates are
   `test_langfuse_observability.py`, `test_agent_versioning.py` and `test_error_handling.py`. Deleting the
   copies is a coverage call, so it is filed rather than taken.

Everything else that stood here has been settled: the three session-named modules are renamed after their
subject and can now fail (see the Testing Strategy above), the sandbox's two origins are described as the
design they are, and the sentence naming a `backend/app/workflows/tests/` tree is gone with the tree.

---

## Writing Tests

### Backend (pytest)

```python
"""Test my feature."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


class TestMyFeature:
    """Test my feature."""

    @pytest.mark.anyio
    async def test_something(self, test_session: AsyncSession):
        """Test something."""
        # test_session provides a clean DB session
        result = await my_function(test_session, arg=42)
        assert result is not None
```

### Frontend (Vitest)

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '../test/test-utils'

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent />)
    expect(screen.getByText('Hello')).toBeDefined()
  })
})
```
