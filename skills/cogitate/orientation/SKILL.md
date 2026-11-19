---
name: cogitate-orientation
description: "First skill to load when working on the Cogitate codebase — the map: where things live, how to find truth, and how to verify. Use before any diagnostic or modification work."
version: 1.0.0
author: Cogitate Team
license: MIT
metadata:
  cogitate:
    tags: [orientation, onboarding, cogitate, map]
    related_skills: [cogitate-analyze-logs, restart-cogitate]
---

# Cogitate Orientation

You are working on the **Cogitate** codebase (pre-launch, pre-push —
nothing has shipped; work is BUILT + committed). This skill is the map.

## The layout

- `backend/app/` — FastAPI application
  - `api/v1/` — thin HTTP routers (one per domain; `router.py` registers them)
  - `domain/<name>/` — business logic (services.py + schemas.py per domain)
  - `services/cognitive_pipeline/` — the chat pipeline (conduit, registry, memory_manager, executor)
  - `infrastructure/database/` — SQLAlchemy models, migrations (alembic)
- `frontend/src/` — React app
  - `pages/` — one page per route
  - `components/features/agentInteraction/` — the chat UI
  - `stores/` — zustand stores (cognitiveHubStore = sessions/agents)
  - `services/` — API client layer
- `wiki/` — the KNOWLEDGE BASE (markdown, rendered in-app)
  - `atlas/` — the source of truth: `ui/pages/` (page docs), `api/routers/` (API docs), `ui/services/` (frontend services)
  - `dev-notes/` — hard-won lessons (known-issues.md, modal-dialogs.md, agents/, assets/)
  - `help/` — user-facing help pages (matched by frontmatter `category`)
- `assets/agent-images/` — canonical curated agent images (git-tracked)
- `data/` — runtime data (gitignored): `profile_images/`, `monitor/` (workflow products, toasts)
- `scripts/core/` — dev tooling (seed scripts, validators, sweep)
- `todo/master.md` — the todo list (markdown; local only, `todo/` is gitignored)
- `local/` — session files + roadmaps + proposals (UNTRACKED — never commit)

## How to find truth

1. **The wiki atlas is the source of truth** for UI/API structure: `wiki/atlas/api/routers/` documents every backend router; `wiki/atlas/ui/pages/` documents every page; `wiki/atlas/ui/services/` documents frontend services.
2. **Dev notes hold the lessons**: `wiki/dev-notes/known-issues.md` (warning-log triage + known gotchas), `wiki/dev-notes/agents/consulting-agent.md` (this consultant's design), `wiki/dev-notes/frontend/modal-dialogs.md` (modal gotchas).
3. **The code is authoritative**: when wiki and code disagree, the code wins — verify before trusting.

## How to verify (ALWAYS)

- Backend health: `curl -s localhost:8000/api/v1/health`
- Frontend: `curl -s -o /dev/null -w "%{http_code}" localhost:5173/dashboard` (expect 200)
- The atlas validator: `python3 scripts/core/check_atlas_validation.py` (expect ALL PASS)
- The sweep: `python3 scripts/core/sweep.py backend` (expect 9/9)
- Tests: `unset CORS_ORIGINS; python -m pytest backend/tests/ -q --tb=no`
- A consultant that reports must CHECK ITS OWN CLAIMS — tail the logs, hit the API, run the query. Report what you actually see.

## Context for diagnostics

- Logs: `backend/logs/app.log` (rotating; app.log.1, .2, .3)
- Traces: `data/pipeline_traces.db` (SQLite — cognitive pipeline traces per message)
- Sessions/agents: the `cogitate.db` SQLite DB (main app DB)
- Active UI session: exposed via the UI state bridge (active_session_id / active_agent_id)
- The agent chat API: `POST /api/v1/agent-chat/message` (session_id + message → agent's real pipeline answer)
