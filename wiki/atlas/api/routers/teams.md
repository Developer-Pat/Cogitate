---
title: Teams
type: atlas-api
path: wiki/atlas/api/routers/teams.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/teams, status/active]
---

# Teams — API

## Purpose

Teams of agents (collectives): CRUD, members, tool assignment,
tool sync. The toolbox-assignment layer was removed (the tooling
canonical upgrade) — tools attach to AGENTS via the single
`agent_tools` gate; teams/collections are organizational.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/teams` | List Teams |
| `POST` | `/api/v1/teams` | Create Team |
| `DELETE` | `/api/v1/teams/{team_id}` | Delete Team |
| `GET` | `/api/v1/teams/{team_id}` | Get Team |
| `PUT` | `/api/v1/teams/{team_id}` | Update Team |
| `GET` | `/api/v1/teams/{team_id}/members` | Get Team Members |
| `POST` | `/api/v1/teams/{team_id}/members` | Add Member To Team |
| `DELETE` | `/api/v1/teams/{team_id}/members/{member_id}` | Remove Member From Team |
| `POST` | `/api/v1/teams/{team_id}/sync` | Sync Team Tools |
| `GET` | `/api/v1/teams/{team_id}/tools` | Get Team Tools |
| `POST` | `/api/v1/teams/{team_id}/tools` | Assign Tool To Team |
| `DELETE` | `/api/v1/teams/{team_id}/tools/{tool_id}` | Remove Tool From Team |
| `PUT` | `/api/v1/teams/{team_id}/tools/{tool_id}` | Update Team Tool |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/api/routers/agents|Agents]]
- [[atlas/ui/pages/TeamsManagement|Teams page]]
