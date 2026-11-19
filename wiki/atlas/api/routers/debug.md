---
title: Debug
type: atlas-api
path: wiki/atlas/api/routers/debug.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/debug, status/active]
---

# Debug — API

## Purpose

Debug actions (list/cancel/clear) + error tracking (list/resolve/delete). Dev tooling.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/debug/actions` | List Debug Actions |
| `DELETE` | `/api/v1/debug/actions/history` | Clear Actions History |
| `GET` | `/api/v1/debug/actions/running` | Get Running Actions |
| `POST` | `/api/v1/debug/actions/{action_id}/cancel` | Cancel Debug Action |
| `GET` | `/api/v1/debug/errors` | List Errors |
| `DELETE` | `/api/v1/debug/errors/resolved` | Delete Resolved Errors |
| `DELETE` | `/api/v1/debug/errors/{error_id}` | Delete Error |
| `GET` | `/api/v1/debug/errors/{error_id}` | Get Error |
| `POST` | `/api/v1/debug/errors/{error_id}/resolve` | Resolve Error |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/ui/pages/Debugging|Debugging page]]
