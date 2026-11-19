---
title: Agent Lifecycle & Provisioning
type: atlas-devnote
category: agents
order: 1
confidence: high
updated: 2026-09-10
tags: [type/dev-notes, domain/agents]
---

# Agent Lifecycle & Provisioning

## Overview

Agents are the core actors of the system. Each agent has a provider +
model pairing, a capability profile, enabled tools, health state —
and, since the lifecycle upgrade (2026-08-16), an ON-DISK identity:
a stable-keyed workspace folder with a derived agent.json. The
storage layer goes through the **repository seam** (`AgentRepository`
ABC + `DiskAgentRepository`, backend/app/domain/agents/repository.py)
— the contract the industrial fork implements in a real DB.

## The repository seam (the fork boundary)

All lifecycle operations route through the seam. The contract:

| Operation | What it does |
|-----------|-------------|
| `create_agent(data)` | Row first, then the workspace scaffold; folder-write failure rolls back the row (no half-created agents) |
| `delete_agent(id)` | BOM gather → archive the workspace → soft-delete the row → the result report (the DEACTIVATE tier — recoverable) |
| `hard_delete_agent(id)` | The IRREVERSIBLE scrub (2026-08-19): every reference (tool links, grants, collections, sessions, messages, usage logs, versions, runtime configs) + the workspace (archived or live) + the memory file → the row itself. Gated by the caller (the keyed tier + explicit confirmation) |
| `resolve_agent(name)` | The white pages — strict; soft-deleted agents never resolve |
| `agent_workspace(id)` | The folder path BY COLUMN (workspace_key) — no filesystem scan |
| `select_agents(criteria)` | The yellow pages — the ARM cards; excludes deleted |
| `list_deleted()` | Soft-deleted agents + their archive paths (recovery is DB-discoverable) |
| `restore_agent(id)` | The archived workspace moves back, markers clear — ADDITIVE, explicit |

The factory (`get_agent_repository`) returns the disk implementation
today. The industrial fork writes `DbAgentRepository` and flips the
factory — routers, lifecycle flows, and the ARM tools stay.

## Create — the scaffold

Creating an agent builds its on-disk identity (`workspace.py`):

1. **The row** is the source of truth (the name ban + profile
   validation preserved).
2. **workspace_key** — a stable, unique slug from the name
   (`agents/<key>/`). NOT the raw name: folder-safe + rename-proof
   (renames never move files).
3. **The face** (2026-09-10) — a plain create with no
   `profile_image_url` gets one from `pick_agent_face()`
   (`assets/agent-images/`, preferring an unused face); the template
   apply has its own allocation. A face must never block a create.
4. **The scaffold** — `agents/<key>/` writes a DERIVED agent.json
   (a snapshot of the row, `_derived: true` — regenerable, never a
   second truth), a FRESH `state.json`
   (`{"facts": {}, "sources": []}` — the instance starts empty), a
   `persona.md` written from the row's system prompt, and a `skills/`
   SEEDED from the shared library with the row's named skills (an
   existing file is never overwritten). See
   [[dev-notes/agents/agent-identity|Agent Identity]].
5. **Rollback** — row first, then the folder; a folder-write
   failure removes the row.

## Delete — the recoverable delete

Deleting is complete + disclosed + recoverable:

1. **BOM gather** — tool links, grants, collections, chat sessions.
2. **Move to the trash** — `agents/<workspace_key>/` moves to
   `trash/agents/<key>-<ts>/`, the AGENTS SHELF of the trash (never
   hard-deleted). The shelf is a surface: the trash page and the API
   both read it, so a deleted agent is FINDABLE rather than merely
   recoverable by whoever still remembers its row.
3. **Soft-delete** — `deleted_at` + `archived_path` on the row;
   execution history KEEPS its reference, and the row is what makes
   the shelf entry RESTORABLE (a folder with no row is residue).
4. **The report** — the DELETE response returns what was removed +
   where recovery lives.
5. **Pool exclusion** — soft-deleted agents leave the live pool
   (list, resolve, select all filter `deleted_at IS NULL`).

Built-in agents (is_builtin) stay protected (403).

## Restore — additive recovery

`POST /agents/{id}/restore` moves the archived workspace back and
clears the markers — the agent is live again. Explicit, never
automatic (the destructive-UX rule: deletion stays possible,
recovery is a deliberate action).

## The PERMANENT delete (2026-08-19) — the scrub

`DELETE /agents/{id}?hard=true` — the IRREVERSIBLE tier: the row
+ EVERY reference (tool links, grants, collections, sessions,
messages, usage logs, versions, runtime configs) + the workspace
(archived or live) + the memory file — all removed. The caller
gates it (the keyed tier + the UI's typed-name confirmation).
Nothing restores it — it is the one truly irreversible operation.
The BOM report shows exactly what was scrubbed. (The repository's
`hard_delete_agent`; `DELETE /agents/{id}` without the flag stays
the recoverable deactivate.)

**The UI's archived section** (2026-08-19): the sidebar shows
"Archived profiles (N)" always (the count is visible, not hidden
— the user's "agents the user can't see" concern). Each row:
Restore (recoverable) + Delete permanently (typed-name confirm).
The paths display FOLDER NAMES (the archiveFolderName helper —
legacy rows carried raw ../../.. forms).

## Rename (2026-08-19) — a supported feature

The architecture always decoupled name from workspace_key
("renames never move files"). The update path now enforces the
NAME BAN (a duplicate → clean 400, the create pattern) + syncs
the workspace agent.json's name. The folder + workspace_key stay
stable — chat history, memory, and skills keep their home.
Verified live: the DB name + agent.json both update; the folder
never moves.

## Reset memory (2026-08-19) — the deep agent restarts fresh

`POST /agents/{id}/reset-memory` (repository `reset_agent_memory`):
the cognitive-memory table clears + the chat sessions/messages
go — the agent SURVIVES (row, workspace, skills, identity stay).
The watch-it-learn demo restarts fresh. Destructive-ish (memory
is lost) but NOT deletion — the UI's Reset Memory button (edit
view) confirms explicitly.

## Depth — derived, not declared

An agent is **deep** when it has a `workspace_key` (the folder
exists). The UI shows the "deep" badge; the delete dialog shows
the full footprint. No flag — depth falls out of the workspace.

## Per-agent cognitive memory

Deep agents get their own memory DB, keyed by the WORKSPACE KEY
(not the raw name): `agents/<workspace_key>/cognitive_memory.db`.
The pipeline creates it when the agent folder exists; `repository.py`
resolves it as `Paths.agents_dir / agent.workspace_key /
"cognitive_memory.db"`. The export service reads it on agent export
(`export_service.py` — exports memory entries with the agent
archive).

## Frontend form state flow

`ProfileService.saveFormState` persists the agent-profile form
across sessions — form state is saved on change and restored on
load, so edits survive navigation/reloads. Agent creation/update
flows through the agents API + `agentProfilesStore` (zustand).

## Migration note

The workspace_key column (0070) was backfilled for existing deep
agents (researcher, system-manager); agents without a folder have
NULL until the scaffold creates it. The soft-delete columns (0071)
were added without a backfill — existing rows are live.
