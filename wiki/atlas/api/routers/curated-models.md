---
title: Curated Models
type: atlas-api
path: wiki/atlas/api/routers/curated-models.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/curated-models, status/active]
---

# Curated Models — API

## Purpose

Human-curated model list per provider (verified flag, category, free). DB is source of truth; config seed is fallback.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/curated-models` | List Curated Models |
| `POST` | `/api/v1/curated-models` | Create Curated Model |
| `DELETE` | `/api/v1/curated-models/{curated_id}` | Delete Curated Model |
| `GET` | `/api/v1/curated-models/{curated_id}` | Get Curated Model |
| `PUT` | `/api/v1/curated-models/{curated_id}` | Update Curated Model |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/api/routers/providers|Providers]]
- [[atlas/ui/components/features/providers/CuratedModelsManager|CuratedModelsManager]]
