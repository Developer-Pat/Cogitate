---
title: Tool Management
category: tools
subtopic: Overview
order: 1
confidence: high
created: 2026-07-27
updated: 2026-09-10
tags: [domain/help]
---

# Tool Management

Tools extend what agents can do — connecting them to external
services, data sources, and system capabilities. The Tool Management
page shows the tool registry: every tool known to the system, with
its inputs, outputs, and status.

## What the registry shows

The table lists each tool with:

- **Name** — the tool's identifier (e.g. `doc_reader`,
  `sqlite_manager`).
- **Description** — what the tool does.
- **Capability** — the category of thing the tool can do
  (`web-search`, `file-read`, `db-query`...). Tools with the same
  capability are interchangeable choices for the same job (e.g.
  several search providers all provide `web-search`).
- **Access** — the tool's registry tier. **Keyed** tools change or
  manage things (writing files, managing agents, database writes) and
  need an explicit grant before an agent can use them. **GRAS** tools
  ("safe to execute without grants" — read-only) work as soon as
  they're enabled. The same idea as the fix-mode grant on the Agent
  page.
- **Type / Status** — builtin tools ship with the system; custom tools
  can be added.
- **Selection** — checkboxes let you act on multiple tools at once.

## Actions

- **Delete** — removes a custom tool from the registry (builtin tools
  are protected).
- **Duplicate** — currently a placeholder (not yet implemented).
- **Toolkits** — a toolkit is a named set of tools. Toolkits are how
  tools actually reach an agent: attach a toolkit to an agent and its
  tools become part of that agent's surface. Manage them on the
  **Toolkits** page (Utilities → Toolkits).

## How tools reach agents

Merely existing in the registry isn't enough. An agent's tool surface
is built from what it **owns**: attach **toolkits** to the agent (Agent
Profiles → Collections → Toolkits) and the surface becomes the union of
those toolkits' tools. An agent that owns no toolkit keeps the default
surface configured per-agent on the Tools tab. Keyed tools still need
their explicit grant before the runtime will actually call them.

## Related

- [Agent Profiles](/wiki/help/agent-profiles) — enabling tools per agent
