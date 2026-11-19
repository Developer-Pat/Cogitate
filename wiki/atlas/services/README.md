---
title: Services Map
type: atlas-api
path: wiki/atlas/services
category: api-atlas
order: 1
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/services, status/active]
---

# Services Map — the application's service-oriented architecture

The backend is organized as **domain services** under
`backend/app/domain/<area>/`. Each service owns a slice of
business logic and is called by the API routers (thin) and by
other services. This map shows the services, their responsibilities,
and how they call each other.

## Service families

- [[atlas/services/providers|Providers]] — LLM provider config,
  completion, model discovery/cache, usage, keys
- [[atlas/services/agents|Agents]] — agent CRUD, templates,
  provisioning, registry
- [[atlas/services/tools|Tools]] — tool registry, execution,
  permissions, builtin tool handlers
- [[atlas/services/workflows|Workflows]] — execution, routing,
  triggers, approvals, compositions, versioning, ab-testing
- [[atlas/services/cognitive|Cognitive]] — profiles, memory,
  vectors
- [[atlas/services/platform|Platform]] — sessions, chat, logs,
  macros, collections, settings, analytics, rag, runtime-config

## The calling pattern

```
API routers (thin) → domain services (business logic)
                     → other domain services (cross-cutting)
                     → infrastructure (DB, vector stores, .env)
```

- **Providers** is the most-depended-on family (completion +
  usage power chat, agents, tools)
- **Agents** depends on providers (model resolution) + tools
  (permissions)
- **Workflows** orchestrates agents + tools + providers
- **Tools** execution depends on providers (LLM calls) + agents
  (permissions)

## Status

**ACTIVE** — the service layer is the app's backbone.
