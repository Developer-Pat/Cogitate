---
title: Backend Architecture
type: atlas-entity
path: wiki/entities/backend-architecture.md
confidence: medium
updated: 2026-08-05
tags: [type/entity, domain/entities]
---

# Backend Architecture

## Overview

FastAPI application, layered: API (routers) → domain (services) →
infrastructure (DB/LLM). Python >=3.12, SQLAlchemy 2.0 async,
Pydantic v2, Alembic migrations, uvicorn.

## Directory layout (current)

```
backend/
├── app/
│   ├── main.py               # create_app + lifespan (init_db, sync)
│   ├── api/v1/               # API layer — per-domain routers
│   │   ├── router.py         # aggregates all v1 routers
│   │   ├── agents/ agent_chat/ analytics/ chat/ collections/
│   │   ├── dashboard/ database/ debug/ diagnostics/ health/ logs/
│   │   ├── macros/ providers/ rag/ sessions/ settings/ system/
│   │   ├── teams/ tools/ tool_permissions/ wiki/ workflow_lists/
│   │   ├── curated_models_router.py  versions_router.py ...
│   ├── domain/               # business logic, per-domain services
│   │   ├── agents/ chat/ collections/ databases/ documents/ logs/
│   │   ├── macros/ providers/ rag/ sessions/ settings/ title/ tools/
│   │   ├── workflows/ workflow_lists/ agent_lists/ agent_registry/
│   ├── infrastructure/       # database models + llm integrations
│   ├── services/             # cross-cutting services
│   │   ├── cognitive_pipeline/   # pipeline traces
│   │   ├── agent_list_service.py  workflow_list_service.py
│   ├── core/                 # config, database, dependencies
├── alembic/                  # migrations (one baseline, 0001)
├── tests/  scripts/  logs/
```

## Lifecycle

`main.py` lifespan: `init_db()` (create_all — the same schema the alembic
baseline builds, see [[dev-notes/configuration/alembic-migrations]]),
auto-sync tools, verify tool invariants. Shutdown closes DB.

## API layer

- `router.py` aggregates domain routers under /api/v1.
- **Route-order matters**: literal routes (e.g. /providers/keys,
  /providers/managed/*) register BEFORE parameterized routes
  (/providers/{id}) or they get shadowed.
- Streaming (SSE) endpoints: chat router (`generate_stream`),
  cognitive_sse.py.

## Domain layer

Service pattern: `class XService(db: AsyncSession)` with async
methods; router instantiates per-request. Examples: AgentService,
ProviderConfigService, DefaultProviderService, AgentMacroService,
ToolRegistryService, RagIngestService, TitleService.

## Infrastructure

- SQLAlchemy models: backend/app/infrastructure/database/models.py
- DBs: main cogitate.db, documents cogitate_docs_en.db, pipeline
  traces pipeline_traces.db, per-agent cognitive_memory.db,
  vector DBs (system_docs/system_code).

## Dependency injection conventions

- **DB session**: `get_db()` (backend/app/core/dependencies.py) —
  yields an `AsyncSession` per request (FastAPI `Depends`).
- **Service factories**: each domain exposes `get_<domain>_service()`
  (e.g. `get_agent_service(db=Depends(get_db))`) — routers depend
  on the factory, never construct services inline.
- **Pattern**: router → `Depends(get_x_service)` → service owns
  business logic + DB access. Tests inject the same factories with
  fakes.

## Middleware + auth model

- **CORS** middleware (configurable `CORS_ORIGINS` in .env).
- **External-access toggle** middleware (agent_chat/middleware.py):
  checks `system_flags.external_access_enabled` per request → 403
  when disabled (request-cached).
- **No user accounts** — single-operator local-first system; API
  keys live in `.env` (EnvKeyStore), the API reports key presence
  only.

## Full API surface

- Routers: `backend/app/api/v1/` (grouped by domain, registered in
  router.py) + workflow routers under `backend/app/workflows/api/`.
- Endpoint inventory: see [[atlas/api/API Atlas|API Atlas]] (35
  router pages).
