---
title: Triggers
type: atlas-api
path: wiki/atlas/api/routers/triggers.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/triggers, status/active]
---

# Triggers — API

## Purpose

Workflow triggers: schedules + webhook endpoints, activate/deactivate.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/triggers` | List Triggers |
| `POST` | `/api/v1/triggers` | Create Trigger |
| `GET` | `/api/v1/triggers/schedules/list` | List Schedules |
| `GET` | `/api/v1/triggers/webhooks/endpoints` | List Webhook Endpoints |
| `DELETE` | `/api/v1/triggers/{trigger_id}` | Delete Trigger |
| `GET` | `/api/v1/triggers/{trigger_id}` | Get Trigger |
| `PUT` | `/api/v1/triggers/{trigger_id}` | Update Trigger |
| `POST` | `/api/v1/triggers/{trigger_id}/activate` | Activate Trigger |
| `POST` | `/api/v1/triggers/{trigger_id}/deactivate` | Deactivate Trigger |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/api/routers/workflows|Workflows]]
- [[atlas/api/routers/webhooks|Webhooks]]
