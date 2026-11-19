---
title: Collections, Teams & Toolkits
type: atlas-devnote
category: frontend
order: 3
confidence: draft
updated: 2026-09-04
tags: [type/dev-notes, domain/frontend]
---

# Collections, Teams & Toolkits

Organizational grouping, three framings: collections (membership
items), teams (agent groups + team tools), and TOOLKITS (the
tool-typed collections an agent OWNS).

## The framings (2026-09-04, the agent-kits build)

- **Collections** — `user_key` scoping (default "default");
  entity_type distinguishes agents/tools/etc. Membership via
  `collection_items` (entity_id/entity_type/entity_name).
- **Teams** — collections of entity_type='agent'; team-tool
  assignments via `team_tools`. A team's UI still speaks
  "toolboxes" (its own framing — not renamed in the _35 build).
- **TOOLKITS** — a kit = a collection of entity_type='tool'. An
  agent OWNS N kits (plural, many-to-many, sharable) via the
  `agent_kits` JOIN (agent_id + kit_id; the agent-kits build P1).
  Ownership is NOT membership ("the agent owns the
  kit, the kit should not own the agent").
  - The singular `agents.kit_id` slot is SEMANTICALLY RETIRED
    (kept as the display-primary/back-compat read — create_all
    cannot drop columns). The boot sync
    (AgentKitService.sync_from_agent_slots) converges the slot
    into the join at every startup; mid-run adoptions write the
    slot + the union policy reads both.
  - THE SURFACE (the union policy, P2): an agent's
    tool surface = the UNION of all owned kits' granted tools
    (tool_collection_permissions), deduped. ANY kit suppresses
    the GRAS default + the agent_tools links; no kits = the
    default surface; all-empty kits = no tools (the shallow bot).
  - The kits: Search Kit (7 read/search tools) + Workspace Kit
    (the write/state surface: file-manager, update-sources,
    update-state, file-info, datetime — the P3 seed,
    scripts/seed_workspace_kit.py). Bob owns both.
  - The kit's VISIBLE tool list = its collection_items (the
    toolkit page's "items"); its EXECUTION surface = the
    tool_collection_permissions rows (the policy reads
    permissions, not items).

## FE ↔ BE flow

- The toolkit UI: `/toolkits` + `/toolkits/:collectionId` (the
  Toolboxes → Toolkits rename, P4 96810168; the legacy
  `/toolboxes` + `/tool-collections` paths redirect).
  `ToolCollectionsManagement` shows each kit + its owning agents
  (via GET /collections/{id}/agent-owners); an agent profile's
  Collections tab shows its OWNED toolkits + attach/detach
  (GET/POST /agents/{id}/kits + DELETE /agents/{id}/kits/{kit_id}).
- Collections/teams membership still flows through
  `/api/v1/collections` + `/teams`.
- Kits' tools: `AddToolsToToolboxModal` (the file name predates
  the rename) adds tools as collection_items; the permissions
  (the execution surface) are managed through the tool-permission
  API.

## The uuid convention (learned in the _35 build)

tools.id is STORED as uuid4().hex (no dashes — the seeded
records) while the ORM's Uuid(as_uuid=False) type reads it back
dashed. tool_collection_permissions.tool_id (String(36)) must
reference the STORED hex form or the FK fails. Collections use
str(uuid4()) (dashed). Only the tools side is hex.
