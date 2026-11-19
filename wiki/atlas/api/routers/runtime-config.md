---
title: Runtime Config
type: atlas-api
path: wiki/atlas/api/routers/runtime-config.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/runtime-config, status/active]
---

# Runtime Config — API

## Purpose

Per-session runtime configuration (model overrides, behavior toggles).

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `DELETE` | `/api/v1/runtime-config/session/{session_id}` | Delete Session Config |
| `GET` | `/api/v1/runtime-config/session/{session_id}` | Get Session Config |
| `POST` | `/api/v1/runtime-config/session/{session_id}` | Create Or Update Session Config |
| `PUT` | `/api/v1/runtime-config/session/{session_id}` | Update Session Config |
| `POST` | `/api/v1/runtime-config/session/{session_id}/reset` | Reset Session Config |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/api/routers/sessions|Sessions]]
