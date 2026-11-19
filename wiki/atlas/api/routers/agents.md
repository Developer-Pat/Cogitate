---
title: Agents
type: atlas-api
path: wiki/atlas/api/routers/agents.md
category: api-atlas
order: 2
confidence: medium
updated: 2026-08-16
tags: [type/api, domain/agents, status/active]
---

# Agents — API

> Routers: `backend/app/api/v1/agents/` — 3 modules
> (router, templates_router, provisioning_router).
> Status: **ACTIVE** — core facility (agent CRUD, templates,
> provisioning). NOTE: `/agents/ab-tests/*` in the old skeleton
> actually belongs to `/api/v1/ab-tests/*` (separate router) —
> see [[atlas/api/routers/ab-tests|A/B Tests]].

## Purpose

Agent lifecycle management: **CRUD** (list/create/get/update/
delete), **export/import** (JSON round-trip for sharing agents),
**duplicate**, **templates** (save agents as reusable templates,
apply to new agents), **system templates** (built-in starter
configs), **provisioning** (create a full agent with memory DBs +
registration), **health dismissal** (acknowledge provider-health
warnings), and **cards** (compact agent summaries for selectors).

Backing services (`backend/app/domain/agents/`): agents CRUD
service, template service, provisioning service, health service.

## Endpoints

### Agent CRUD (`router.py` — `/api/v1/agents`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/agents` | List agents (with health state) — **FULL LIST by default** (the 2026-08-17 pagination-trap fix: bounded registries return everything; the UI opts into `page`/`page_size`) |
| `POST` | `/agents` | Create agent |
| `GET` | `/agents/stats` | Aggregate stats |
| `GET` | `/agents/duplicates` | Find duplicate agents |
| `GET` | `/agents/{agent_id}` | Get agent |
| `PUT` | `/agents/{agent_id}` | Update agent (profile, model, provider) |
| `DELETE` | `/agents/{agent_id}?hard=false` | **The recoverable delete (DEACTIVATE)** — soft-deletes the row (deleted_at + archived_path), archives the workspace (agents/.archived/<key>-<ts>/, never hard-deleted), removes relational rows (tool links/grants/collections/chat sessions), KEEPS execution history; returns the result report (bom + archived_path). Built-ins → 403. 2026-08-16 |
| `DELETE` | `/agents/{agent_id}?hard=true` | **The PERMANENT scrub (2026-08-19)** — IRREVERSIBLE: the row + every reference (tool links, grants, collections, sessions, messages, usage logs, versions, runtime configs) + the workspace (archived or live) + the cognitive-memory file, all removed. The caller gates it (the keyed tier + explicit confirmation). Nothing restores it |
| `POST` | `/agents/{agent_id}/duplicate` | Clone an agent |
| `GET` | `/agents/{agent_id}/card` | Agent card — the A2A discovery doc + the **ARM resource card** block (`arm`: depth, competence, spec, capability — Phase F: the selection surface Exa reads when composing orchestrations; the user sees the persona, ARM sees the card) |
| `GET` | `/agents/{agent_id}/export` | Export as JSON |
| `POST` | `/agents/import` | Import agent JSON |
| `POST` | `/agents/{agent_id}/image` | Upload avatar image (deduped by pixel fingerprint — re-uploading the same image reuses the existing file, 2026-08-11) |
| `GET` | `/agents/deleted` | Soft-deleted agents + their archive paths — the restore view's data (recovery is DB-discoverable). Registered BEFORE /{agent_id} (path-param order). 2026-08-16 |
| `POST` | `/agents/{agent_id}/restore` | Restore a soft-deleted agent: the archived workspace moves back, delete markers clear, the row is live again — ADDITIVE, explicit (never automatic). 400 if not soft-deleted |
| `GET` | `/agents/by-name/{name}` | Resolve a unique name to an agent — the white pages (strict; 404 if missing) |
| `POST` | `/agents/select` | The yellow pages — filter + rank the pool by criteria; returns ARM cards with `matched_on` |
| `POST` | `/agents/route` | Route a message to an addressed agent (the recipient channel) |
| `POST` | `/agents/{agent_id}/set-default` | Mark an agent as the default for a provider/model |
| `GET` | `/agents/{agent_id}/versions` | Agent version history |
| `PATCH` | `/agents/{agent_id}/versions/{version}/status` | Update a version's status |

### Health (`router.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/agents/{agent_id}/health/dismiss` | Acknowledge health warnings (until next failure) |
| `DELETE` | `/agents/{agent_id}/health/dismiss` | Undismiss |

### System templates (`router.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/agents/system-templates` | List built-in starters |
| `GET` | `/agents/system-templates/{template_id}` | Get one |
| `POST` | `/agents/system-templates/apply` | Create agent from template |

### Templates (`templates_router.py` — `/api/v1/agents/templates`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/agents/templates` | List templates |
| `POST` | `/agents/templates` | Create template |
| `GET` | `/agents/templates/{template_id}` | Get template |
| `PUT` | `/agents/templates/{template_id}` | Update template |
| `DELETE` | `/agents/templates/{template_id}` | Delete template |
| `POST` | `/agents/templates/{template_id}/apply` | Apply to a new agent |
| `POST` | `/agents/templates/from-agent/{agent_id}` | Save existing agent as template |

### Provisioning (`provisioning_router.py` — `/api/v1/agents/{name}`)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/agents/{name}/provision` | Full provision (agent + memory DBs + registration) |
| `GET` | `/agents/{name}/status` | Provisioning status |
| `DELETE` | `/agents/{name}/archive` | Archive agent |

## Auth

All endpoints require an authenticated session. Image upload
accepts multipart; export/import are JSON.

## Status

**ACTIVE** — core. Agent CRUD/templates/provisioning power the
Agents section (Profiles, Templates pages) and the agent registry
(drives chat/agent-chat delegation).

## Related

- [[atlas/api/routers/agent-registry|Agent Registry]] — registry (delegation targets)
- [[atlas/api/routers/agent-chat|Agent Chat]] — agent-to-agent chat
- [[atlas/api/routers/chat|Chat]] — user chat
- [[atlas/ui/components/AgentProfiles/Agent Profiles Index|Agent Profiles UI]]
- [[atlas/api/routers/ab-tests|A/B Tests]] — the ab-tests endpoints
  (NOT under /agents)
- [[dev-notes/agents/agent-lifecycle|Agent Lifecycle (dev-notes)]]

## Repository seam (agent-lifecycle Phase A–D)

Agent storage goes through `AgentRepository` (backend/app/domain/
agents/repository.py) — the ABC contract: create_agent,
delete_agent, resolve_agent, agent_workspace, select_agents,
list_deleted, restore_agent. `agents.workspace_key` holds the
stable folder key; the folder is found by column, never a
filesystem scan. The factory (`get_agent_repository`) returns the
disk implementation today; the industrial fork swaps in a DB
implementation (the fork boundary).

**The lifecycle contract (Phase B–D):**
- **Create** scaffolds the workspace: `agents/<workspace_key>/`
  with a DERIVED agent.json (regenerable from the row —
  `_derived: true`) + skills/; the row is the source of truth.
- **Delete** = the recoverable delete: BOM gather (tool links,
  grants, collections, chat sessions) → workspace ARCHIVED (moved
  to agents/.archived/, never hard-deleted) → row SOFT-deleted
  (deleted_at + archived_path — history KEPT) → the result report.
- **Pool exclusion**: soft-deleted agents are excluded from the
  LIVE pool everywhere (list ×2, resolve_agent, select_agents
  filter deleted_at IS NULL).
- **Restore** = ADDITIVE: the shelved workspace moves back, the
  markers clear, the row is live again. Explicit, never automatic.
- **Depth** is derived (workspace_key present = deep), never a
  flag — the UI shows the 'deep' badge.

## The adopt-package (2026-08-24, the agent-package Phase 2)

POST /api/v1/agents/{agent_id}/adopt-package with
{"package_id": "..."} — copy the package's kit_id + skills +
llm_spec into the agent's OWN fields + set the package_id
(provenance). The agent owns its copies; the package never owns
the agent. Returns the updated AgentResponse.
