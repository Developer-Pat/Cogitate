---
title: Tools
type: atlas-api
path: wiki/atlas/api/routers/tools.md
category: api-atlas
order: 4
confidence: medium
updated: 2026-09-15
tags: [type/api, domain/tools, status/active]
---

# Tools — API

> Router: `backend/app/api/v1/tools/router.py`.
> Status: **ACTIVE** — the tool registry, agent-tool assignment,
> and tool execution backbone (agents call tools through this).

## Purpose

Tool management: **capabilities** (the canonical vocabulary —
`web-search`, `file-read`, `db-query`... the ARM selection axis,
Phase A of the tooling canonical upgrade), **categories**
(hierarchical tool taxonomy for display), **tool CRUD** (the tool
registry — builtin + custom tools), **agent-tool assignment**
(which tools each agent can use), **execution** (run a tool by
id), and **usage logging** (per-tool usage stats).

The `capability` field on every tool is the canonical slug
declared in code (`app/domain/tools/capabilities.py` — the frozen
vocabulary) and mirrored into the `tools` table by the boot sync.
Tools with the same capability are interchangeable providers of
that capability.

The vocabulary is **frozen in the sense that a slug never changes
once set** — a tool's capability is its ARM identity. Adding a slug
is permitted and has precedent: `ui-navigate` ("move the user's
view") was added rather than borrowing `doc-lookup`, because an app
page is not a document and the mislabel would make ARM select
navigation for documentation work. An addition changes no existing
tool's identity.

Backing services: tool registry (builtin tool classes),
tool permission service, tool execution service, usage logger.

## Endpoints

### Categories

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/tools/categories` | Create category |
| `GET` | `/tools/categories` | List categories |
| `GET` | `/tools/categories/tree` | Category tree |
| `GET` | `/tools/categories/{category_id}` | Get category |
| `GET` | `/tools/categories/slug/{slug}` | Get by slug |
| `PUT` | `/tools/categories/{category_id}` | Update |
| `DELETE` | `/tools/categories/{category_id}` | Delete |

### Tools

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/tools/search` | Search tools |
| `GET` | `/tools/{tool_id}` | Get tool |
| `GET` | `/tools/slug/{slug}` | Get by slug |
| `PUT` | `/tools/{tool_id}` | Update |
| `DELETE` | `/tools/{tool_id}` | Delete |

### Agent-tool assignment

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/tools/agents/{agent_id}/tools` | List agent's tools |
| `POST` | `/tools/agents/{agent_id}/tools` | Enable tool for agent |
| `GET` | `/tools/agents/{agent_id}/tools/{tool_id}` | Get agent tool binding |
| `PUT` | `/tools/agents/{agent_id}/tools/{tool_id}` | Update binding (permissions) |
| `DELETE` | `/tools/agents/{agent_id}/tools/{tool_id}` | Remove from agent |
| `POST` | `/tools/agents/{agent_id}/tools/{tool_id}/disable` | Disable for agent |

### Execution + usage

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/tools/execute` | Execute a tool (agent runtime calls this) |
| `POST` | `/tools/usage/logs` | Log tool usage |
| `GET` | `/tools/usage/logs` | Usage logs |
| `GET` | `/tools/usage/stats` | Usage stats |

## Auth

All endpoints require an authenticated session. Tool execution
checks the agent's tool permissions before running.

## Status

**ACTIVE** — the tool registry + execution are core to agent
functionality (agents use tools via this API).

## Related

- [[atlas/ui/components/Tools/Tools Index|Tools UI]]
- [[atlas/ui/services/domain/ToolService|ToolService]]
- [[dev-notes/tools/tools-architecture|Tools Architecture (dev-notes)]]
- [[atlas/api/routers/agent-registry|Agent Registry]] — agent-tool bindings
