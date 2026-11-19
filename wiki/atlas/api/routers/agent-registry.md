---
title: Agent Registry
type: atlas-api
path: wiki/atlas/api/routers/agent-registry.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/agent-registry, status/active]
---

# Agent Registry — API

## Purpose

Agent packages: create/version/execute/lineage/status + registry health. Delegation targets.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `POST` | `/api/v1/agent-registry/execute` | Execute Package By Name |
| `GET` | `/api/v1/agent-registry/packages` | List Packages |
| `POST` | `/api/v1/agent-registry/packages` | Create Package |
| `GET` | `/api/v1/agent-registry/packages/active` | List Active Packages |
| `POST` | `/api/v1/agent-registry/packages/archive-by-role` | Archive Packages By Role |
| `DELETE` | `/api/v1/agent-registry/packages/{package_id}` | Delete Package |
| `GET` | `/api/v1/agent-registry/packages/{package_id}` | Get Package |
| `PUT` | `/api/v1/agent-registry/packages/{package_id}` | Update Package |
| `POST` | `/api/v1/agent-registry/packages/{package_id}/execute` | Execute Package |
| `GET` | `/api/v1/agent-registry/packages/{package_id}/lineage` | Get Package Lineage |
| `PUT` | `/api/v1/agent-registry/packages/{package_id}/status` | Set Package Status |
| `POST` | `/api/v1/agent-registry/packages/{package_id}/versions` | Create Package Version |
| `GET` | `/api/v1/agent-registry/status` | Registry Status |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/api/routers/agents|Agents]]
- [[atlas/api/routers/agent-chat|Agent Chat]]


**Pattern**: white-pages registry (strict name → agent); see [[references/software-patterns|Software Patterns]].
