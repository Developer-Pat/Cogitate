---
title: Macros
type: atlas-api
path: wiki/atlas/api/routers/macros.md
category: api-atlas
order: 3
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/macros, status/active]
---

# Macros — API

> Routers: `backend/app/api/v1/macros/` — 3 modules
> (router, export_router, backup_router).
> Status: **ACTIVE** — macro sets + meta-topics power the chat
> macro keyboard + meta-topic switching.

## Purpose

Macro-set and meta-topic management: **macro sets** (grouped
prompt macros), **meta-topics** (named prompt contexts with
multiple macro sets), **search**, **export/import** (JSON, for
sharing), **templates**, and **backup/restore**.

## Endpoints

### Macro sets + meta-topics (`router.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/topics/list` | List topics |
| `GET` | `/meta-topics` | List meta-topics |
| `GET` | `/meta-topics/{meta_topic_id}` | Get one |
| `POST` | `/meta-topics` | Create |
| `PUT` | `/meta-topics/{meta_topic_id}` | Update |
| `DELETE` | `/meta-topics/{meta_topic_id}` | Delete |
| `POST` | `/meta-topics/{meta_topic_id}/load` | Load into chat context |
| `POST` | `/meta-topics/{meta_topic_id}/save` | Save to file |
| `GET` | `/saves` | List saved meta-topics |
| `POST` | `/meta-topics/load/{folder}` | Load from file |
| `GET` | `/search` | Search macro sets |
| `GET` | `/{macro_set_id}` | Get macro set |
| `PUT` | `/{macro_set_id}` | Update macro set |
| `DELETE` | `/{macro_set_id}` | Delete macro set |

### Export/import (`export_router.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/macro-sets/{macro_set_id}` | Export a set |
| `GET` | `/meta-topics/{meta_topic_id}` | Export a meta-topic |
| `GET` | `/all` | Export everything |
| `POST` | `/import` | Import JSON |
| `POST` | `/macro-sets/import` | Import single set |
| `POST` | `/meta-topics/import` | Import meta-topic |
| `GET` | `/templates` | List templates |
| `GET` | `/templates/{filename}` | Get template |

### Backup (`backup_router.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/restore` | Restore from backup |

## Auth

All endpoints require an authenticated session.

## Status

**ACTIVE** — the MacroKeyboard + meta-topic switching in chat use
these endpoints.

## Related

- [[dev-notes/macros/macro-architecture|Macro Architecture (dev-notes)]]
