---
tags: [type/dev-notes]
---

# Sweeps (the system checks)

The sweeps' documentation (2026-08-27 — the retool).

## The purpose — DIFFERENT from the tests

| Area | Tool | Purpose |
|---|---|---|
| The tests | `scripts/testing/run_tests.py` | Code + UI health (the runner) |
| The sweeps | `scripts/core/sweep.py` | The SYSTEM checks: logs, ghosts, zombies, maintenance |

The sweep is NOT the tests' home — it gates the SYSTEM: the
processes, the databases, the paths, the warnings, the maintenance.

## The commands

```
python3 scripts/core/sweep.py                # full (all checks, combined report)
python3 scripts/core/sweep.py backend        # backend checks only (separate report)
python3 scripts/core/sweep.py frontend       # frontend checks only (separate report)
python3 scripts/core/sweep.py backend --parallel
python3 scripts/core/sweep.py full --roll-baseline
```

## The checks (2026-08-27 inventory)

The BACKEND (12):
- mypy, the import check, the deprecation warnings
- pytest (the fast gate) / pytest-all (the slow, with --include-slow)
- the router-decorator check, the path-arithmetic check
- the stale-cogitate-db check, the ghost-database scan
- **the stale /tmp temp-db scan** (2026-08-27 — the tests' session-
  engine leftovers: the timeout-kills bypass the teardown + the
  xdist workers accumulate; age-based (>1h), REPORT-ONLY)
- **the zombie test-process scan** (2026-08-27 — the leak class:
  the reparented (ppid 1) pytest/run_tests/fake-acp/HERMES-ACP
  processes — the agent-family joined after the 08-27 zombie-agent
  (the old Exa connection's process survived the restart and
  contended with the live agent); the 08-26 PID 531696 held 4 fds
  on the db; REPORT-ONLY)
- the atlas validation, the agent-health scan

The FRONTEND (5): tsc, eslint, vitest, the build, **the dev-servers'
health check** (2026-08-27 — the backend's health + the vite's root;
the vite's IPv6-only default refused the panel's IPv4 ws-connections
(the offline bug) — the launch: `npx vite --host 0.0.0.0 --port 5173`;
REPORT-ONLY).

## The interpretation

The reports land in `data/sweep/` (the locator's sweep dir) — the
`sweep-backend-*.md` + `sweep-frontend-*.md` patterns — the
auto-generated reports are pruned beyond the newest N; the human
docs + the baseline are never pruned. Each check returns a
returncode + the output; the sweep's exit = the worst check's.

The sweep's own reports live apart from the test runs on purpose: a run is a
person's work (`data/test-runs/`, one folder per run), the sweep's output is
the chain machine's health record. Nothing test-related is written to `local/`.

## The classes

- GHOSTS: the zero/near-zero .db files in the repo (the ghost-db
  scan) + the stale /tmp temp-dbs (the age-based scan)
- ZOMBIES: the reparented test-family processes (the leak class)
- MAINTENANCE: the baselines, the pruning, the agent-health

## The rules

- The checks REPORT; the destructive actions are the operator's
  call (the sweep never auto-deletes).
- The sweep and the runner are SEPARATE tools — the pytest inside
  the sweep stays the fast gate; the full suite is the RUNNER's
  job (the parallel groups).
