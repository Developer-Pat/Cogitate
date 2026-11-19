---
title: Compositions
type: atlas-api
path: wiki/atlas/api/routers/compositions.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/compositions, status/active]
---

# Compositions — API

## Purpose

Workflow compositions (combine workflows), execute/CRUD.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/compositions` | List Compositions |
| `POST` | `/api/v1/compositions` | Create Composition |
| `DELETE` | `/api/v1/compositions/{composition_id}` | Delete Composition |
| `GET` | `/api/v1/compositions/{composition_id}` | Get Composition |
| `PUT` | `/api/v1/compositions/{composition_id}` | Update Composition |
| `POST` | `/api/v1/compositions/{composition_id}/execute` | Execute Composition |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/api/routers/workflows|Workflows]]
