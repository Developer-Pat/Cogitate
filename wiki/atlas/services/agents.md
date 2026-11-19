---
title: Services — Agents
type: atlas-api
path: wiki/atlas/services/agents.md
category: api-atlas
order: 3
confidence: medium
updated: 2026-08-16
tags: [type/api, domain/services, status/active]
---

# Agents Services

The agents domain owns agent lifecycle: CRUD, health, templates,
provisioning, and the agent registry (delegation packages).

## Services

| Service | Responsibility |
|---------|---------------|
| `AgentService` | Agent CRUD + business logic (provider/model resolution, health from usage_logs); the LIVE pool excludes soft-deleted agents (deleted_at IS NULL) |
| `AgentRepository` (ABC) + `DiskAgentRepository` | **The repository seam** (backend/app/domain/agents/repository.py) — the 5-op + 2 lifecycle contract: create_agent, delete_agent, resolve_agent, agent_workspace, select_agents, list_deleted, restore_agent. The fork boundary: the industrial version swaps in a DB implementation behind the same contract. 2026-08-16 |
| `workspace.py` | The workspace scaffold: make_workspace_key (stable, slugged, unique), agent_json (DERIVED from the row — never a second truth), scaffold() (folder + agent.json + skills/). 2026-08-16 |
| `AgentExportService` | Export/import agents as JSON (the folder lookup goes through the seam's agent_workspace — the column, not a scan) |
| `AgentRegistryService` | DB-backed agent packages (version/lineage/status) |
| `Nucleus` | Package execution harness (registry packages) |
| `AgentTemplateService` (in services.py) | Template CRUD + apply |
| Provisioning service (in services.py) | Full agent provision (memory DBs + registration) |

## Dependencies (mermaid)

```mermaid
flowchart LR
    API[Agent API routers] --> Repo[AgentRepository (the seam)]
    Repo --> Svc[AgentService]
    Repo --> WS[workspace.py scaffold]
    API --> Tpl[AgentTemplateService]
    API --> Prov[Provisioning]
    API --> Reg[AgentRegistryService]
    Svc --> PConfig[ProviderConfigService]
    Svc --> Cache[ProviderModelCacheService]
    Svc --> Usage[UsageTracker]
    Reg --> Nucleus[Nucleus Harness]
    Prov --> Svc
    Prov --> Memory[Memory DBs]
```

## Cross-service calls

- **Agents → Providers**: model resolution (`ProviderConfigService`),
  model existence (`ProviderModelCacheService`), health
  (`UsageTracker` failures)
- **Agents → Tools**: agent-tool permissions (via tools API)
- **Registry → Nucleus**: package execution harness

## Status

**ACTIVE** — core.

## Related

- [[atlas/api/routers/agents|Agents API]]
- [[atlas/api/routers/agent-registry|Agent Registry API]]
- [[dev-notes/agents/agent-lifecycle|Agent Lifecycle]]


**Pattern**: the ABC → Registry → Factory house style — AgentRepository (ABC) + DiskAgentRepository + the factory; see [[references/software-patterns|Software Patterns]].
