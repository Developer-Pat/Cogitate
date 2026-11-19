---
title: Router Architecture
type: atlas-devnote
category: api
order: 1
confidence: high
updated: 2026-08-07
tags: [type/dev-notes, domain/api]
---

# Router Architecture

## Current shape

- API v1 routers under backend/app/api/v1/ — grouped by domain
  (agents/, chat/, providers/, macros/, sessions/, teams/, tools/,
  wiki/...).
- Each router is an APIRouter with a prefix + tags, registered in
  backend/app/api/v1/router.py (47 include_router calls) which is
  mounted in main.py under /api/v1.
- The aggregator (router.py) is the single registration point —
  new domains add an import + include_router there.

## Registration order matters

- **Literal-before-parameterized**: literal routes (e.g.
  /managed/keys) must be registered BEFORE parameterized routes
  (/managed/{provider_id}) or they get shadowed.
- **Specific-before-generic**: `/workflows/templates/*` (specific)
  is included before `/workflows/*` (generic) — see the comments in
  router.py. The generic workflow router must be last.
- Commented ordering hints in router.py (e.g. agent_lists_router
  before agents_router) document the intentional order.

## Dependency injection (DI)

- Routers use `Depends()` for services + DB:
  - Service dependencies via `get_*_service` factories (e.g.
    `get_agent_service` — 17 uses in agents/router.py)
  - DB sessions via `get_db` (AsyncSessionLocal per request)
- The pattern: router → Depends(service factory) → service owns
  business logic + DB access.

## Streaming (SSE) vs JSON patterns

- **SSE**: chat/stream (StreamingResponse, text/event-stream),
  logs/stream, agent-chat WS — streaming endpoints return
  StreamingResponse and emit SSE-formatted chunks.
- **JSON**: standard endpoints return response models (Pydantic
  schemas) directly.
- WebSockets (agent-chat /ws) are the live-channel variant.

## Verification note

Written from current router.py + agents/router.py + chat/router.py
(2026-08-07). The old ROUTER_ARCHITECTURE_ANALYSIS is superseded.
