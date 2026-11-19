---
title: Tools Architecture
type: atlas-devnote
category: tools
order: 1
confidence: medium
updated: 2026-09-10
tags: [type/dev-notes, domain/tools]
---

# Tools Architecture

## Overview

Tools give agents capabilities (web search, file ops, DB queries,
macros, etc.). Backend: backend/app/domain/tools/.

## Core model (pattern)

- **ToolDefinition** (registry.py) — schema for a tool: slug, name,
  description, argument JSON-schema (llm_schema.py), handler.
- **ToolRegistry** — singleton registry: register/unregister/get,
  list_tools, execute_tool, plus a `decorator` for registration.
  BuiltinToolRegistrar registers the built-in handlers.
- **ToolExecutionService** (execution_service.py) — the execution
  path: resolve config → validate args → execute → wrap result
  (ToolExecutionResult: to_llm_message / to_user_message /
  to_summary_message).
- **ToolCategoryService / ToolRegistryService** — CRUD for tool
  metadata + categories (DB-backed).
- **AgentToolService** — per-agent tool enablement
  (enable/disable/remove/config).
- **ToolPermissionService** — access control: per-tool permissions,
  collection-scoped permission (default_tool_permission),
  check_permission, get_accessible_tools.
- **TeamToolService** (team_tools.py) — team-scoped tool bindings.

## Built-in handlers

`builtin/` holds the tool IMPLEMENTATIONS (one module per tool family):
agent_manager, agent_select, agent_state (`update-sources` /
`update-state`), agent_beat (`update-beat`), assignment (`open-assignment` /
`add-note` / `read-assignment` / `close-assignment` — the per-assignment notebook),
consult, datetime,
delegation_logging, doc_index, doc_reader, doc_vector_store,
code_vector_store, document_manager, duckduckgo, file_info,
file_manager, jina_reader, macro_manager, provider_manager, publish,
run_post, run_python, send_notification, sequential_thinking,
set_timer, skill_reader, sqlite_query, state_dumper,
system_diagnostics, wikipedia, workflow_manager.

Several tools are registered INLINE in `registry.py` rather than as a
builtin module: `calculator`; the Exa-program tools (2026-08-18/19) —
`set-trigger-schedule`, `verify-trigger-config`, `verify-backend-health`,
`restart-backend` (keyed), `search-knowledge` (the RAG lookup),
`graph-query` (the topology), `delete-agent` (keyed — deactivate or
permanent scrub), `restore-agent` (keyed — the undo),
`list-archived-agents` (gras — the soft-deleted roster),
`audit-consistency` (gras — the system consistency audit),
`repair-consistency` (the repair counterpart),
`verify-http-evidence` (gras — the access-journal evidence for a claim);
`consult` (the external-agent second-opinion channel — its handler
module is `builtin/consult_handler.py`); and `open-page` (gras — a
destination in this app, resolved against the GENERATED page map; see
[[dev-notes/tools/tool-registration|Tool Registration]] for the generator,
the artifact and the sync gate).

(The 2026-08-19 list named several modules that do not exist in
`builtin/` and have no registered slug — `line_editor`, `clipboard`,
`tavily`, `summarize_llm`, `todo`, `log_reader`, `text_tools`,
`sqlite_manager` — all dropped here. The self-state tools
`update-state`, `update-sources`, `update-beat` were missing; they are
the surface the agents subsystem's own docs describe.)

## Agent wiring — the tooling paradigm (2026-08-19)

**THE PARADIGM COMPLETION**: the manual agent_tools grid
was the unfinished half of the tooling rewrite. The canonical rule
(the study's "keyed tools need grants; read tools just work") is
now the runtime:

- **GRAS tools** (read-only tier) are the default surface — the
  registry is the surface, no assignment row needed; an agent_tools
  row with `is_enabled=0` EXCLUDES one. **"To EVERY agent by default"
  no longer holds**: the KITS layer (below) overrides the default.
- **Keyed tools** (write/admin: restart-backend, the write family)
  need the enabled link AND the grant (`agent_tool_grants`, the
  fix-mode mechanism) — enforced at execution.
- **DB-only external tools** (create_tool, never in the registry)
  are listed only when explicitly enabled — no regression for
  custom tools.
- The chat context builder uses the SAME selection
  (get_enabled_tools_for_agent) — the LLM surface and the
  enforcement cannot diverge.
- **agent_tools** is now the exception list (exclusions) + the
  keyed-entry gate — not the primary access control.
- The tier is DECLARED on the tool (access_tier: gras|keyed) or
  derived from the capability; the registry definition is the
  tier surface (the DB row can lag).
- **THE KITS LAYER overrides the default** (2026-08-24, the
  ownership correction; 2026-09-04, the union build) — the layer
  this 2026-08-19 text predates and never named. An agent OWNS its
  kits: the `agent_kits` JOIN rows (many-to-many) ∪ the singular
  `agents.kit_id` slot (the back-compat read). The surface = the
  UNION of all owned kits' granted tools
  (`tool_collection_permissions`), deduped — see
  `execution_service.py::_toolkit_slugs_for_agent`. Owns NO kit →
  the default GRAS surface; owns kits → the kits ARE the surface
  (a deliberately tool-less kit = no tools).

Tool cache: _get_cached_tools/_set_cached_tools + invalidate on
changes (AgentService).
