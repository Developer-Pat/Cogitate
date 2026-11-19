---
title: Agent Packages API
type: atlas-api
path: backend/app/api/v1/agent_packages/router.py
confidence: high
updated: 2026-08-25
tags: [type/api, domain/agent-packages]
---

# Agent Packages API — /api/v1/agent-packages

The agent package = the BLUEPRINT (the toolkit ref + the
recommended skillset + the advisory llm_spec). The agent OWNS its
copies; the package records the provenance (the ownership rule,
2026-08-24).

## The endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | /api/v1/agent-packages | Create a package |
| GET | /api/v1/agent-packages | List the packages |
| GET | /api/v1/agent-packages/{id} | Get one package |
| PUT | /api/v1/agent-packages/{id} | Update a package |
| POST | /api/v1/agent-packages/{id}/provision | Provision an agent FROM the package |
| DELETE | /api/v1/agent-packages/{id} | Delete a package |

## The adopt (the agents' side)

POST /api/v1/agents/{agent_id}/adopt-package with
{"package_id": "..."} — copies the package's kit_id + skills +
llm_spec into the agent's OWN fields + sets package_id (the
provenance). See the agents API doc.

## The package schema

```
name: str (the package name)
description: str | null
kit_id: str | null (the toolkit ref — a tool-typed collection)
skills: list[str] (the recommended skillset)
llm_spec: {kind, thinking, location, min_context} | null (the
          advisory LLM contract — the Luminosity Scale's future
          home!)
```
