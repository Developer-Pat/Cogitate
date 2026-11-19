---
title: Messages — API surface
type: atlas-api
path: backend/app/api/v1/messaging/router.py
category: api-atlas
confidence: medium
updated: 2026-08-25
tags: [type/api, domain/messages, status/active]
---

# Messages — the API surface

## Current (frontend-local)

The message queue is FRONTEND-LOCAL (the `messageStore`, persisted
in the browser). The backend surface that feeds it:

- **The bus**: `notify:<kind>` topics (the sweeps, the Exa queue
  clearing, the system events). The payload: kind / title /
  message / type (info|success|warning|error) / action /
  `from` (e.g. "exa" — the source discriminator).
- **The publish**: `app/domain/messaging/services.py` (the
  `publish` helper) — used by the system sweep + the inbox
  processor (the Exa queue clearing).

## The phase-2 contract (the backend queue — planned, not built)

The durable upgrade — the endpoints the frontend's store would
swap to:

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/messages` | the queue (filter/sort/paginate) |
| POST | `/api/v1/messages/read` | mark messages read |
| DELETE | `/api/v1/messages` | bulk delete |
| POST | `/api/v1/messages/clear` | clear the queue |

The store API (add / markAllRead / deleteMessages / clearAll)
mirrors the contract — the swap is the source only.
