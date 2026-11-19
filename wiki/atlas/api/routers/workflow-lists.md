---
title: Workflow Lists
type: atlas-api
path: wiki/atlas/api/routers/workflow-lists.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/workflow-lists, status/active]
---

# Workflow Lists — API

## Purpose

Curated workflow collections (add/remove workflows).

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/workflow-lists` | List Workflow Lists |
| `POST` | `/api/v1/workflow-lists` | Create Workflow List |
| `GET` | `/api/v1/workflow-lists/search` | Search Workflow Lists |
| `DELETE` | `/api/v1/workflow-lists/{list_id}` | Delete Workflow List |
| `GET` | `/api/v1/workflow-lists/{list_id}` | Get Workflow List |
| `PUT` | `/api/v1/workflow-lists/{list_id}` | Update Workflow List |
| `GET` | `/api/v1/workflow-lists/{list_id}/workflows` | Get Workflows In List |
| `DELETE` | `/api/v1/workflow-lists/{list_id}/workflows/{workflow_id}` | Remove Workflow From List |
| `POST` | `/api/v1/workflow-lists/{list_id}/workflows/{workflow_id}` | Add Workflow To List |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/api/routers/workflows|Workflows]]
