---
title: Team Tool Service
type: atlas-service
path: frontend/src/services/domain/TeamToolService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# Team Tool Service

**Path**: `frontend/src/services/domain/TeamToolService.ts`
**Type**: service

## Purpose

API client for team management and team-tool assignment. Teams are modeled as collections of `entity_type: 'agent'` (see `types/collections.ts`); this service manages the team CRUD, its member (agent) list, and the tools assigned to the team — either **directly** (`source_type: 'direct'`) or **via a toolbox** (`source_type: 'toolbox'`, expanded server-side into individual tool assignments). Also exposes a team-sync operation that pushes the team's assigned tools down to its member agents. Exported as a singleton (`teamToolService`).

## Exported API (exact signatures)

Multi-export file: `export class TeamToolService` + `export const teamToolService = new TeamToolService()` (singleton) + `export default teamToolService` (same instance).

```ts
export class TeamToolService {
  // private: teamsPath = '/api/v1/teams'; teamsCache: Collection[] | null; cacheTimestamp: number | null; CACHE_TTL = 120_000 (2 min)

  async listTeams(): Promise<Collection[]>                                    // GET /api/v1/teams, 2-min in-memory cache
  async getTeam(teamId: string): Promise<Team>                                // 3 parallel GETs merged into one Team
  async createTeam(teamData: CollectionCreate): Promise<Collection>           // POST, forces entity_type: 'agent'; invalidates cache
  async updateTeam(teamId: string, teamData: CollectionUpdate): Promise<Collection> // PUT; invalidates cache
  async deleteTeam(teamId: string): Promise<void>                             // DELETE; invalidates cache
  async addMemberToTeam(teamId: string, memberData: CollectionItemCreate): Promise<CollectionItem> // POST, forces entity_type: 'agent'
  async removeMemberFromTeam(teamId: string, memberId: string): Promise<void> // DELETE
  async getTeamMembers(teamId: string): Promise<CollectionItem[]>             // GET
  async getTeamTools(teamId: string): Promise<TeamTool[]>                     // GET, returns response.tools || []
  async assignToolToTeam(teamId: string, toolData: TeamToolCreate): Promise<TeamTool> // POST
  async updateTeamTool(teamId: string, toolId: string, updateData: TeamToolUpdate): Promise<TeamTool> // PUT
  async removeToolFromTeam(teamId: string, toolId: string, sourceType?: 'direct' | 'toolbox'): Promise<void> // DELETE, optional ?source_type=
  async assignToolboxToTeam(teamId: string, assignData: ToolboxAssignCreate): Promise<ToolboxAssignResponse> // POST
  async removeToolboxFromTeam(teamId: string, toolboxId: string): Promise<void> // DELETE
  async syncTeamTools(teamId: string, agentIds?: string[]): Promise<TeamSyncResponse> // POST
  clearCache(): void                                                          // public; clears the teams list cache
}
```

Supporting types (from `types/team_tools.ts`): `TeamTool` (`id`, `team_id`, `tool_id`, `source_type: 'direct' | 'toolbox'`, `source_id`, `priority`, `is_active`, `config`, `created_at`, `updated_at`, optional `tool?: ToolSummary`), `TeamToolCreate`, `TeamToolUpdate` (`priority?`, `is_active?`, `config?`), `TeamToolListResponse` (`{ tools, total }`), `ToolboxAssignCreate` (`toolbox_id`, `priority?`), `ToolboxAssignResponse` (`id`, `team_id`, `toolbox_id`, `tool_count`, `tools_added: Array<{tool_id, tool_name}>`, `created_at`), `TeamSyncRequest` (`agent_ids?`), `TeamSyncResponse` (`synced_agents`, `tools_assigned`, `tools_removed`, `conflicts_detected`, `conflicts: ConflictInfo[]`), `Team` (extends `Collection` with `members: CollectionItem[]` and `tools: TeamTool[]`).

## Endpoints

All under base path `/api/v1/teams`.

| Method | Path | Purpose | Service method |
|---|---|---|---|
| GET | `/api/v1/teams` | List all teams (2-min cache) | `listTeams` |
| POST | `/api/v1/teams` | Create team (payload forced to `entity_type: 'agent'`) | `createTeam` |
| GET | `/api/v1/teams/{teamId}` | Get team | `getTeam` (part of 3-way parallel fetch) |
| PUT | `/api/v1/teams/{teamId}` | Update team | `updateTeam` |
| DELETE | `/api/v1/teams/{teamId}` | Delete team | `deleteTeam` |
| GET | `/api/v1/teams/{teamId}/members` | List team members | `getTeamMembers` / `getTeam` (parallel) |
| POST | `/api/v1/teams/{teamId}/members` | Add member (payload forced to `entity_type: 'agent'`) | `addMemberToTeam` |
| DELETE | `/api/v1/teams/{teamId}/members/{memberId}` | Remove member | `removeMemberFromTeam` |
| GET | `/api/v1/teams/{teamId}/tools` | List tools assigned to team | `getTeamTools` / `getTeam` (parallel) |
| POST | `/api/v1/teams/{teamId}/tools` | Assign a tool directly to the team | `assignToolToTeam` |
| PUT | `/api/v1/teams/{teamId}/tools/{toolId}` | Update team-tool config (priority/active/config) | `updateTeamTool` |
| DELETE | `/api/v1/teams/{teamId}/tools/{toolId}?source_type=direct\|toolbox` | Remove a tool assignment (source_type disambiguates direct vs toolbox-sourced) | `removeToolFromTeam` |
| POST | `/api/v1/teams/{teamId}/toolboxes` | Assign a toolbox to the team (server expands to tool assignments) | `assignToolboxToTeam` |
| DELETE | `/api/v1/teams/{teamId}/toolboxes/{toolboxId}` | Remove a toolbox from the team | `removeToolboxFromTeam` |
| POST | `/api/v1/teams/{teamId}/sync` | Sync team tools down to member agents | `syncTeamTools` |

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `apiClient` (`../apiClient`) | service | HTTP client returning `{ data?, error? }`; every REST call in this service goes through it |
| `frontendLoggingService` (`../frontendLoggingService`) | service | `debug`/`info`/`error` logging for each operation, cache hits, and cache invalidation |
| `types/team_tools` | types | `TeamTool`, `TeamToolCreate`, `TeamToolUpdate`, `TeamToolListResponse`, `ToolboxAssignCreate`, `ToolboxAssignResponse`, `TeamSyncRequest`, `TeamSyncResponse`, `Team`, `TeamToolSourceType` |
| `types/collections` | types | `Collection`, `CollectionItem`, `CollectionCreate`, `CollectionUpdate`, `CollectionItemCreate` — teams are agent collections |

## Usage Example

```ts
import { teamToolService } from '../services/domain/TeamToolService'

// List teams (cached 2 minutes; cache invalidated on create/update/delete)
const teams = await teamToolService.listTeams()

// Load a team with members + tools (three parallel GETs merged)
const team = await teamToolService.getTeam('team-123')

// Assign a tool directly, and assign a whole toolbox
await teamToolService.assignToolToTeam('team-123', { tool_id: 'tool-1', source_type: 'direct', priority: 1 })
await teamToolService.assignToolboxToTeam('team-123', { toolbox_id: 'tb-1' })

// Remove a toolbox-sourced assignment (pass source_type so the server disambiguates)
await teamToolService.removeToolFromTeam('team-123', 'tool-1', 'toolbox')

// Push team tools down to specific member agents (omit agentIds for all members)
const result = await teamToolService.syncTeamTools('team-123', ['agent-1', 'agent-2'])
console.log(result.synced_agents, result.conflicts_detected)
```

## Data Flow / Notes

- **Direct tools vs toolboxes**: every assignment carries `source_type: 'direct' | 'toolbox'` (and `source_id` = toolbox id when toolbox-sourced). `assignToolboxToTeam` returns `tools_added` — the server expands the toolbox into per-tool assignments. The UI (`TeamToolsTab`) groups tools by source type; removals pass `source_type` as a query param so the server removes the right assignment.
- **Team = agent collection**: `createTeam` and `addMemberToTeam` hard-code `entity_type: 'agent'` into the payload; teams reuse the generic collections backend (`Collection`/`CollectionItem`).
- **Caching**: only the team *list* is cached (`CACHE_TTL` = 2 min). `createTeam`/`updateTeam`/`deleteTeam` invalidate; `clearCache()` exposes manual invalidation. `getTeam` never caches — it fires `GET /teams/{id}`, `GET /teams/{id}/members`, and `GET /teams/{id}/tools` in parallel via `Promise.all` and merges them into `{ ...team, members, tools }` (member/tool errors abort the whole call).
- **Error handling pattern**: every method checks `response.error`; on error it logs via `frontendLoggingService.error(...)` and throws `new Error(response.error.message)`; unexpected exceptions are logged and rethrown.
- **`useCache` hardcoded**: `listTeams` declares `const useCache = true;` — a vestigial toggle, always on.

## Related (components/hooks/services consuming it)

- `frontend/src/pages/TeamDetail.tsx` — primary consumer; calls `getTeam`, `updateTeam`, `deleteTeam`, `addMemberToTeam`, `removeMemberFromTeam`, `assignToolToTeam`, `assignToolboxToTeam`, `removeToolFromTeam`, `syncTeamTools`. Owns the tab state and wires callbacks into the Teams components below.
- `frontend/src/pages/AgentProfiles.tsx` — calls `teamToolService.listTeams()` to populate the team-filter dropdown (line 70).
- `frontend/src/components/Teams/TeamToolsTab.tsx` — **does not import the service**; purely presentational, receives `team`, `onAddTools`, `onAddToolboxes`, `onRemoveTool` props from `TeamDetail` and groups `team.tools` by `source_type`.
- `frontend/src/components/Teams/TeamMembersTab.tsx`, `AddToolsModal.tsx`, `AddToolboxesModal.tsx` — likewise fed by `TeamDetail` callbacks; no direct service import (verified by grep).
- Related wiki pages: `wiki/atlas/ui/pages/TeamDetail.md`, `wiki/atlas/ui/pages/AgentProfiles.md`, `wiki/atlas/ui/components/Teams/AddToolsModal.md`, `wiki/atlas/ui/components/Teams/AddToolboxesModal.md`.

## Deprecation / Obsolete Notes

- **Not deprecated.** No `@deprecated`, "legacy", "unused", or "no longer used" markers anywhere in the source. Actively consumed by `TeamDetail.tsx` (9 methods) and `AgentProfiles.tsx` (`listTeams`).
- **Methods with no current UI consumer** (still part of the exported API, possibly used by future flows): `createTeam`, `getTeamMembers`, `getTeamTools`, `updateTeamTool`, `clearCache`. Note `getTeam` fetches members/tools directly via `apiClient` rather than reusing `getTeamMembers`/`getTeamTools`.
- Minor code smell (not deprecation): the hardcoded `const useCache = true;` in `listTeams`.
- The old `docs/atlas/` entry (`docs/atlas/services/domain/Team-tool-service.md`) is stale — this wiki page supersedes it.
