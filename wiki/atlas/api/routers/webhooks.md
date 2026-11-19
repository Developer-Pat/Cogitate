---
title: Webhooks
type: atlas-api
path: wiki/atlas/api/routers/webhooks.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/webhooks, status/active]
---

# Webhooks — API

## Purpose

Webhook receive (external events) + endpoint listing + test.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/webhooks/endpoints` | List Webhook Endpoints |
| `POST` | `/api/v1/webhooks/test/{trigger_id}` | Test Webhook Trigger |
| `POST` | `/api/v1/webhooks/{endpoint_path}` | Receive Webhook |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/api/routers/workflows|Workflows]]
- [[atlas/api/routers/triggers|Triggers]]
