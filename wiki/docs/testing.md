---
title: Testing Guide
type: atlas-docs
path: wiki/docs/testing.md
confidence: medium
updated: 2026-08-05
tags: [type/docs, domain/docs]
---

# Testing Guide

## Running Tests

All commands are run from the `backend/` directory.

### Full Suite (ask permission first — takes ~5m)

```bash
uv run pytest -v
```

### Fast Suite (excludes slow LLM tests — ~45s)

```bash
uv run pytest -x -m "not slow and not integration" --ignore=tests/e2e --tb=short -q
```

### Full Backend Sweep (all checks including mypy, imports — ~5m)

```bash
cd .. && python3 scripts/core/sweep.py backend
```

---

## Running Specific Areas

### Cognitive Pipeline (109 unit tests — ~13s)

Runs all pipeline tests including vector store, skills, provisioning, and memory export:

```bash
uv run pytest tests/unit/cognitive_pipeline/ -v
```

### New Feature Tests (22 tests — ~4s)

Run independently without the full pipeline suite:

```bash
uv run pytest tests/unit/cognitive_pipeline/test_vector_store.py -v
uv run pytest tests/unit/cognitive_pipeline/test_skill_aware_cb.py -v
uv run pytest tests/unit/cognitive_pipeline/test_provisioning.py -v
uv run pytest tests/unit/cognitive_pipeline/test_memory_export.py -v
uv run pytest tests/unit/cognitive_pipeline/test_memory_persistence.py -v
```

Or all together:

```bash
uv run pytest tests/unit/cognitive_pipeline/test_vector_store.py tests/unit/cognitive_pipeline/test_skill_aware_cb.py tests/unit/cognitive_pipeline/test_provisioning.py tests/unit/cognitive_pipeline/test_memory_export.py tests/unit/cognitive_pipeline/test_memory_persistence.py -v
```

### API Endpoint Tests (17 tests — ~20s)

```bash
uv run pytest tests/api/v1/ -v
```

### Integration Tests (~60s)

```bash
uv run pytest tests/integration/ -v
```

### Individual Test File

```bash
uv run pytest tests/unit/cognitive_pipeline/test_executor.py -v
```

### Single Test

```bash
uv run pytest tests/unit/cognitive_pipeline/test_executor.py::TestExecutorRegistry::test_default_registry_has_default -v
```

### E2E Tests (1 slow test — live LLM)

```bash
uv run pytest tests/e2e/ -v --slow
```

### Workflow Tests

```bash
uv run pytest tests/workflows/ -v
```

### Frontend Tests

```bash
cd frontend
npx vitest run          # Run all
npx vitest --watch      # Watch mode
```

---

## Test Markers

Tests are tagged with markers that control what runs by default:

| Marker | Meaning | Included in Fast Suite? |
|--------|---------|------------------------|
| (none) | Pure unit, no external deps | ✅ Yes |
| `integration` | Requires database | ❌ No |
| `slow` | Live LLM calls | ❌ No |
| `performance` | Timing-sensitive | ❌ No |

```bash
uv run pytest -m integration          # Integration only
uv run pytest -m "not slow"           # Everything except slow
uv run pytest -m slow                 # Slow (live LLM) only
uv run pytest -m ""                   # ALL tests including slow
```

---

## Test Organization

```
backend/tests/
├── unit/                         # Pure unit tests
│   ├── cognitive_pipeline/       # Pipeline strategies (vector store, skills, memory)
│   └── tools/                    # Tool handlers
├── components/                   # Component-level tests (doc reader, etc.)
├── api/
│   └── v1/                       # Versioned API endpoint tests
├── integration/
│   └── chat/                     # Chat integration tests (real DB)
├── workflows/                    # LangGraph workflow tests
└── e2e/                          # End-to-end tests
```


---

## Configuration

Pytest is configured in `backend/pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "integration",
    "performance",
    "slow",      # Live LLM calls — excluded from fast runs
]
asyncio_mode = "auto"
testpaths = ["tests"]
```

Shared fixtures live in `backend/tests/conftest.py` and provide:
- **Test database** — isolated SQLite database per session
- **Test client** — HTTPX `AsyncClient` with the app mounted
- **DB override** — dependency injection for test isolation
- **Auto-cleanup** — database reset between tests

### Memory Persistence Standalone Script

An alternative standalone verification script lives at the project root:

```bash
python3 scripts/verify_memory_persistence.py
```

This runs the same checks outside pytest — useful for ad-hoc verification
or CI debugging without the full suite.
