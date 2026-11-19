---
title: Agent Lists
type: atlas-api
path: wiki/atlas/api/routers/agent-lists.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/agent-lists, status/active]
---

# Agent Lists — API

## Purpose

Curated agent groups for delegation targets and collections.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/agent-lists` | List Agent Lists |
| `POST` | `/api/v1/agent-lists` | Create Agent List |
| `DELETE` | `/api/v1/agent-lists/{list_id}` | Delete Agent List |
| `GET` | `/api/v1/agent-lists/{list_id}` | Get Agent List |
| `PUT` | `/api/v1/agent-lists/{list_id}` | Update Agent List |
| `GET` | `/api/v1/agent-lists/{list_id}/agents` | Get Agents In List |
| `DELETE` | `/api/v1/agent-lists/{list_id}/agents/{agent_id}` | Remove Agent From List |
| `POST` | `/api/v1/agent-lists/{list_id}/agents/{agent_id}` | Add Agent To List |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/api/routers/agents|Agents]]
- [[atlas/api/routers/teams|Teams]]
