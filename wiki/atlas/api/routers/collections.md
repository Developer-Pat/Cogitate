---
title: Collections
type: atlas-api
path: wiki/atlas/api/routers/collections.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/collections, status/active]
---

# Collections — API

## Purpose

User collections (groups of agents/tools/workflows).

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/collections` | List Collections |
| `POST` | `/api/v1/collections` | Create Collection |
| `GET` | `/api/v1/collections/contains/{entity_type}/{entity_id}` | Find Collections Containing Entity |
| `DELETE` | `/api/v1/collections/{collection_id}` | Delete Collection |
| `GET` | `/api/v1/collections/{collection_id}` | Get Collection |
| `PUT` | `/api/v1/collections/{collection_id}` | Update Collection |
| `GET` | `/api/v1/collections/{collection_id}/items` | Get Collection Items |
| `POST` | `/api/v1/collections/{collection_id}/items` | Add Item To Collection |
| `DELETE` | `/api/v1/collections/{collection_id}/items/{item_id}` | Remove Item From Collection |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/ui/components/features/collections/Collections Index|Collections UI]]
