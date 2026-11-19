---
title: Testing & Tool Testing
type: atlas-devnote
category: testing
order: 1
confidence: medium
updated: 2026-08-05
tags: [type/dev-notes, domain/testing]
---

# Testing & Tool Testing

## How the project tests

- **Run the tests with the runner** — `python3 scripts/testing/run_tests.py
  --group <unit|all|ui|…>`, which is parallel by default. **Never** a bare
  `pytest` over the whole tree: that is serial, it does not exclude the
  quarantine, and it reports failures the runner never shows. Times and the
  full picture: [[dev-notes/testing/README|Testing (the test suite)]].
- **Backend**: pytest under `backend/tests/`.
  Run the system sweep (`scripts/core/sweep.py`, incl. mypy) after code
  changes — pytest misses errors in unimported modules.
- **Frontend**: vitest — `npx vitest run` + `npx tsc --noEmit`.
- **Atlas/wiki**: scripts/core/check_atlas_validation.py (wikilink
  + structure gate) — ALL PASS required.
- **Links**: scripts/core/check_dangling_links.py — every markdown link
  must resolve (relative to the file or the root; `--enforce` fails).
- **Verification habit**: user prefers automated test scripts over
  manual testing; new features get runnable tests that work
  standalone AND in the full sweep.

## Tool testing

- Tool handlers are testable via ToolRegistry.execute_tool with a
  fake agent context; unit tests live under backend/tests/.
- Old standalone dialog-test-runner scripts (D-scripts) were
  deleted — do not reference them.

## Per-domain test layout (backend/tests/)

- `unit/` — service-layer unit tests
- `api/` — endpoint tests (routers + schemas)
- `integration/` — cross-service integration
- `workflows/` — workflow/graph tests
- `components/` + `e2e/` — component + end-to-end
- Frontend: vitest (`frontend/src/**/__tests__/`) — 412 tests.

## Tool-testing recipe

1. Build a handler instance (e.g. `SummarizeLlmTool()`)
2. Prepare the args fixture (matching the arguments_schema)
3. `await handler.execute(config, **args)`
4. Assert the returned `ToolExecutionResult` (success/error +
   content)

Run: `unset CORS_ORIGINS; python -m pytest backend/tests/ -q` —
854 tests (7 skipped).

## Offline by design — the tests never hit the network (2026-08-12)

Every sweep is 100% offline; there is no internet dependency.

- **Backend HTTP tests** use `AsyncClient(transport=ASGITransport(app))`
  — in-process ASGI, no socket.
- **LLM/provider tests** are fully `unittest.mock`ed (AsyncMock /
  MagicMock / patch) — they import the real classes but never invoke
  them live.
- **ACP/external-agent tests** run against a FAKE subprocess speaking
  JSON-RPC 2.0 over stdio (echo/silent python scripts) — real
  `hermes` is never spawned.
- **DB tests** use an in-memory SQLite test engine, tables truncated
  per test (conftest `auto_clean_tables`).
- **Frontend tests** mock `fetch` in every test file (0 use real
  fetch); localStorage/WebSocket mocked too.

Consequence: the `ERROR|WARNING` noise in app.log during a test
window is the tests exercising FAILURE PATHS (mocked failures,
`v99.0`, `FNBot`, "boom") — expected noise, not real connections
(see known-issues.md triage). The only live-network things in the
dev flow are the RUNNING servers (runtime LLM/API calls), never the
test command.
