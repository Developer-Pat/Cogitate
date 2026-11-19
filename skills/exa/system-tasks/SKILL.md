---
name: system-tasks
description: "The system-tasks umbrella (2026-08-27): run the test suite, interpret the report, report the digest, and clean up the working copy. Expandable to the system sweeps + the maintenance tasks (ghosts, zombies, logs). The tests live in the RUNNER (scripts/testing/run_tests.py — the group-first harness); the system checks live in the SWEEP (scripts/core/sweep.py)."
version: 1.0.0
author: Cogitate Team
tags: [cogitate, system, tests, sweeps, maintenance, exa]
---

# System Tasks (tests, sweeps, maintenance)

The umbrella skill for the system-level operations. THE TESTS AND THE
SWEEPS ARE DIFFERENT TOOLS WITH DIFFERENT PURPOSES:
- **The runner** (`scripts/testing/run_tests.py`) — the TEST suite:
  code + UI health, the functional groups, the parallel/sequential
  modes, the timing metrics.
- **The sweep** (`scripts/core/sweep.py`) — the SYSTEM checks: logs,
  ghost files, zombie processes, the stale-db checks, maintenance.
  (The sweep's integration is a later expansion — the tests first.)

## The runner (the tests)

```
python3 scripts/testing/run_tests.py --group <name> [--parallel|--sequential]
        [--output PATH] [--timeout N] [--require-backend] [--include-quarantine]
```

The groups (the functional partitions):
- unit / workflows / api / components / integration / e2e / all / ui
- `ui` = the frontend's vitest (the other groups run pytest)
- The quarantine (the parked problem-children) is EXCLUDED from every
  group by default — it runs only with `--include-quarantine`.

The defaults: group=unit, parallel, and the run lands in its OWN FOLDER —
`data/test-runs/<ts>/`, resolved from the app's path locator. Run from the
project root; the runner prints `RUN_DIR: <path>` when it finishes.

## The report interpretation

The report's header: the group, the files, the backend-status stamp
("backend: healthy" / "backend: DOWN — the backend-marked tests will
skip"). The body: the pytest/vitest output + the durations table +
the summary (passed/failed/skipped) + the ELAPSED + the EXIT.

The semantic markers:
- `backend` — the connection-class tests (skip when the backend's down)
- `quarantine` — the parked problem-children (excluded by default)

The failure classes (the report's evidence):
- CONNECTION — the backend/network-dependent (the backend stamp says)
- CODE — the real assertions/import errors
- ORDERING — the flaky order/state (the known issue)

## The Exa flow (run -> read -> report)

1. RUN: `python3 scripts/testing/run_tests.py --group <g>`, from the project
   root. The run lands in `data/test-runs/<ts>/` and the runner prints
   `RUN_DIR: <path>`.
2. READ: the run — `<RUN_DIR>/report.md` for the failures, the timings and
   the classification; `<RUN_DIR>/report.xml` when you need per-test detail.
3. REPORT: the digest to the user — what ran, what failed (by class),
   the slowest items, the EXIT. The digest's bounded: the failures +
   the classification + the timings + the delta vs the previous run.
4. NO CLEANUP: the run IS the evidence. There is no working copy to move or
   delete, and runs are NEVER Exa's to delete.

## The timer (the EXA-TIMER, 2026-08-28 — the quiescence fix)

When you start a LONG process (the tests ~3 min, the sweeps 5-10+,
research), DON'T sit idle waiting — set a timer, finish your turn,
and pick up when it fires:
- The tool: `set_timer(duration_seconds, context)` — call it in
  your run (e.g. "run the suite, then set a 3-minute timer").
- The flow: launch the process → set the timer with a context
  describing what to check (the results-path, the digest-ask) →
  finish the turn cleanly.
- The pickup: when the timer fires, the panel surfaces a
  CONFIRMABLE message ("⏰ the timer fired — the context") — the
  user sends it or discards it (the 08-13 doctrine: NO auto-fire).
  The confirm carries the context + the instruction to read the
  results, report the digest, and clean up the working copy.
- The API (the debug/operator): POST /api/v1/external-agent/timer
  {duration_seconds, context}; GET /timers; DELETE /timer/{id}.
- The v2 (DONE 2026-08-28): the DB-persisted records (the
  agent_timers table) — the pending timers survive the backend
  restarts (the boot-rebuild restores them; the expired fire
  immediately).

## The provider-maintenance (the model lifecycle — the 2026-08-27
Ox-removal lesson)

When a model/agent's availability is in question, or the task is
removing a dead provider entry:
1. CHECK the catalog FIRST (the OpenRouter API — the model-list; a
   404/absent = gone). The app's /providers/health says the PROVIDER's
   alive — it does NOT say a specific model's serving.
2. AUDIT the references (the curated-pricing, the quick-switch
   options, the workflow defaults — the grep for the model-id).
3. CLEAR the dead references (the pricing, the UI options) — but
   KEEP the defensive DETECTION code (the "model-id in m" family-
   checks + their comments carry the history; they never fire now).
4. SWAP the live defaults (a workflow's default_model must point at
   a WORKING model — the flash-brain family).
5. The HARNESS-BRAIN DOCTRINE: the agent harness wants the FAST-CHAT
   brains (deepseek-v4-flash etc.) — a heavy-thinking LLM driving
   the harness times out from too much thinking (the ox-alpha
   finding). The reasoning models belong to the deep-work, not the
   harness.
6. The removal itself is the OPERATOR's gate (the destructive
   doctrine) — the task's the audit + the execution AFTER the go.

## The rules

- The failing-tests rule: when fixing, run ONLY the failing tests
  (the targeted file/class/test) — never the full suite while
  chasing.
- Long suites (the all-group) need the user's prior OK.
- The hard copy is the evidence; the pipes lie.
- The backend-dependent tests need a healthy backend (the runner's
  pre-flight stamps it; --require-backend fails the run early).
- NEVER modify the test files' markers without checking the heredoc
  strings — the marker-inserts must land after `import pytest`,
  never inside the embedded fake-server scripts (the 2026-08-27
  lesson: the corruption caused a fake "ACP-hang").

## The sweep (the system checks)

THE SWEEP AND THE RUNNER ARE DIFFERENT TOOLS:
- The runner = the TEST suite (the code + UI health).
- The sweep = the SYSTEM checks (scripts/core/sweep.py): the logs,
  the ghosts, the zombies, the maintenance. It GATES the system.

```
python3 scripts/core/sweep.py                # full (all checks, combined report)
python3 scripts/core/sweep.py backend        # backend checks only
python3 scripts/core/sweep.py frontend       # frontend checks only
python3 scripts/core/sweep.py backend --parallel
python3 scripts/core/sweep.py full --roll-baseline
```

The backend's 12 checks: mypy, imports, deprecation warnings,
pytest (the fast gate), the router-decorators, the path-arithmetic,
the stale-cogitate-db, the ghost-db scan, the stale /tmp temp-db
scan (the tests' session-engine leftovers), the zombie test-process
scan (the reparented leak class), the atlas validation, the
agent-health. The frontend's 4: tsc, eslint, vitest, the build.

The interpretation:
- The reports land in scripts/core/sweep-reports/ (the
  sweep-backend-*.md / sweep-frontend-*.md patterns) — the
  auto-reports pruned beyond the newest N; the baselines kept.
- The classes: GHOSTS (the zero-size repo dbs + the stale /tmp
  temp-dbs), ZOMBIES (the reparented test processes — the leak
  class: kill -9 <pid>), MAINTENANCE (the baselines, the pruning).
- The sweep REPORTS — the destructive actions are the operator's
  call (it never auto-deletes).

The Exa-flow for the sweeps: the SAME loop as the tests — run the
sweep (its reports land in `data/sweep/`; add `--output <path>` only
if you need a working copy), read the findings, report the digest
(the failures + the classes + the fix-suggestions). Reports are never
Exa's to delete.
