---
name: cogitate-analyze-logs
description: "Diagnose Cogitate problems from logs — the timestamp-clustering triage method: distinguish REAL signals from test noise, find the actual bug. Use when anything 'seems wrong' with the running app."
version: 1.0.0
author: Cogitate Team
license: MIT
metadata:
  cogitate:
    tags: [diagnostics, logs, triage, debugging]
    related_skills: [cogitate-orientation, restart-cogitate]
---

# Cogitate Log Analysis

The triage method for `backend/logs/app.log` (and the error/warning
surfaces). Codified from real incidents — see
`wiki/dev-notes/known-issues.md` for the full story.

## The core rule: cluster by timestamp

Warnings/errors cluster in two kinds of windows:

1. **Startup / reload windows** (when uvicorn boots, when `--reload`
   restarts, when you restart servers) → warnings here are REAL
   signals. Investigate. (The macro-manager duplicate-registration bug
   was found exactly this way — 11× at every startup.)
2. **Test-run windows** (pytest sweeps, usually several minutes of
   dense output with test names in nearby lines) → warnings here are
   EXPECTED NOISE. The test suite intentionally exercises failure
   paths. Do not chase them.

How to tell: check the timestamps. If a warning cluster sits inside a
pytest window (look for `wf-test-*`, `v99.0`, `boom`, `FNBot`,
"Intentional failure", `unittest/mock.py` frames), it is test noise.
If it sits at a startup/reload moment, it is a real signal.

## Known noise markers (test pollution — do NOT chase)

- `wf-test-*`, `v99.0`, `boom` — mocked workflow tests
- `FNBot` — a mock agent
- `monitor-market-5min failed: boom` — mocked scheduler test
- `assert api_key is not None` / `commit failed, rolling back` — the
  providers keyless-Ollama path (fixed; see known-issues)
- Deliver-node warnings writing to `data/monitor/` — test isolation
  was fixed by monkeypatching `_products_dir`; if they reappear,
  check test isolation, not the app

## Real-signal patterns to hunt

- **Repeated at EVERY startup** → a registration/init bug (e.g. the
  macro-manager "already registered, overwriting" — a tool registered
  TWICE in `init_default_registry()`; the worse schema won)
- **500s from a specific endpoint** → route-order bugs (static routes
  must be declared BEFORE dynamic), session commit failures
- **"Failed to load templates"** → plain-string tags in DB (tolerant
  parsing now; check seed data)
- **WebSocket disconnects** → often the Vite proxy (`ws: true` needed
  for WS upgrade passthrough) or stale frontend modules

## The diagnostic loop

1. `tail -n 200 backend/logs/app.log` — see what's recent
2. Cluster by timestamp: startup/reload vs test-window
3. For real signals: grep the pattern, find the source module,
   read the code path
4. VERIFY your hypothesis: hit the endpoint (`curl`), check the DB,
   re-read the code — never report an unverified claim
5. Report: what you observed (with evidence), what it means, what to
   check next

## Verification tools

- `curl -s localhost:8000/api/v1/health` — backend alive
- `curl -s localhost:8000/api/v1/agent-chat/...` — API surface
- `python3 scripts/core/check_atlas_validation.py` — atlas health
- Read `wiki/dev-notes/known-issues.md` — the accumulated triage knowledge
