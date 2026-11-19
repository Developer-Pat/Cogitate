---
title: Team Detail
type: atlas-page
path: frontend/src/pages/TeamDetail.tsx
confidence: high
updated: 2026-07-31
tags: [type/page, domain/atlas-ui]
---
# Team Detail

**Component**: `frontend/src/pages/TeamDetail.tsx`
**Route**: `/teams/:teamId` (lazy-loaded; title "Team Detail", `requiresAuth: true`, icon `user-friends`, breadcrumb "Team Detail")
**Last Updated**: 2026-07-31

## Purpose

TeamDetail is the drill-down page for a single agent team. It renders the team's header (icon, name, description, member/tool counts, created/updated dates) and exposes two tabbed views — **Members** (which agents belong to the team) and **Tools & Toolboxes** (which tools are assigned, directly or via toolboxes). From here the user can edit or delete the team, add/remove agent members, assign tools and toolboxes with priorities, remove tool assignments, and trigger a "sync" that propagates the team's tool set to its member agents. The page is the detail counterpart of the `/teams` list page ([[TeamsManagement]]).

## Key Features

- **Team header** — icon, name, description, member count, tool count, and created/updated timestamps; "Back to Teams" navigation.
- **Members tab** — table of member agents (name + added date) with per-row Remove; empty state with "Add Members" CTA.
- **Add Member modal** — loads all agents, filters out ones already in the team, search-as-you-type filter, single-select dropdown, then adds via the page's `handleAddMember`.
- **Tools & Toolboxes tab** — tools grouped into "Direct Tools" vs "Tools from Toolboxes", each row showing tool name/description, priority badge, Active/Inactive status, and Remove.
- **Add Tools modal** — multi-select (with Select All) of active tools not already assigned, shared priority input; assigns each selected tool.
- **Add Toolboxes modal** — multi-select of tool-type collections (toolboxes) not already assigned, shared priority input.
- **Edit team** — opens `EditCollectionModal` (name, description, color, icon; entity type read-only in practice); saves via PUT.
- **Delete team** — confirmation via `DeleteConfirmationModal`, then navigates back to `/teams`.
- **Sync Tools** — POSTs a team sync (propagates team tools to member agents); disabled with spinner while running; logs detected conflicts to the console (toast wiring commented out).

## Components Used

| Component | Path | Purpose |
|---|---|---|
| `TeamMembersTab` | `frontend/src/components/Teams/TeamMembersTab.tsx` | Members tab: lists `team.members`, Remove action, embedded Add-Member modal (loads agents via `AgentService.getAgents()`). |
| `TeamToolsTab` | `frontend/src/components/Teams/TeamToolsTab.tsx` | Tools tab: groups `team.tools` by `source_type` (`direct` vs `toolbox`), renders per-group `ToolsTable`, Add Tools/Toolboxes buttons. |
| `ToolsTable` (internal to TeamToolsTab) | `frontend/src/components/Teams/TeamToolsTab.tsx` | Table of tool assignments: name/description, priority badge, Active/Inactive badge, Remove button. |
| `AddToolsModal` | `frontend/src/components/Teams/AddToolsModal.tsx` | Multi-select assigner; loads candidates via `ToolService.listTools({ is_active: true })`, excludes tools already on the team, calls `onAssign(toolId, priority)` per selection. |
| `AddToolboxesModal` | `frontend/src/components/Teams/AddToolboxesModal.tsx` | Multi-select assigner; loads candidates via `collectionsService.listCollections({ entity_type: 'tool' })`, excludes toolboxes already assigned (by `source_id`), calls `onAssign(toolboxId, priority)`. |
| `EditCollectionModal` | `frontend/src/components/features/collections/EditCollectionModal.tsx` | Edit dialog (name/description/color/icon); pure UI — submits via `onSave(id, updates)` prop, no API calls of its own. |
| `DeleteConfirmationModal` | `frontend/src/components/features/collections/DeleteConfirmationModal.tsx` | Delete confirmation dialog; pure UI — confirms via `onConfirm(id)` prop, no API calls of its own. |

## Hooks Used

| Hook | Path | Purpose |
|---|---|---|
| `useParams` | `react-router-dom` | Reads `teamId` from the `/teams/:teamId` route segment. |
| `useNavigate` | `react-router-dom` | Navigates back to `/teams` after delete and from Back/error-state buttons. |
| `useState` | `react` | Local state: `team`, `isLoading`, `error`, `activeTab`, `editingTeam`, `deletingTeam`, modal flags, `isSyncing`. |
| `useEffect` | `react` | Runs `loadTeam()` on mount / whenever `loadTeam` identity changes. |
| `useCallback` | `react` | Memoizes `loadTeam` (depends on `teamId`) so the effect doesn't refire spuriously. |
| `useNotificationStore` | `frontend/src/stores/notificationStore.ts` | Zustand selector for `addNotification` — surfaces error toasts on failed member adds. |

## Data Flow

1. **Mount load** — `useEffect` calls `loadTeam()`, which calls `teamToolService.getTeam(teamId)`. That service method fires **three parallel GETs** (`/api/v1/teams/{id}`, `/api/v1/teams/{id}/members`, `/api/v1/teams/{id}/tools`) via `Promise.all` and merges them into a single `Team` object (`{...collection, members, tools}`). `isLoading` gates a full-screen spinner; a failed load sets `error` and renders a "Team Not Found" state with a Back to Teams button.
2. **Members tab** — renders `team.members` (each `CollectionItem` carries `entity_id`/`entity_name`/`added_at`). Opening Add Member triggers `AgentService.getAgents()` (cached; backed by `ProfileService` → `GET /api/v1/agents`); agents already in `team.members[].entity_id` are filtered out and the rest are searchable. Adding calls `addMemberToTeam` (POST) then reloads the team. Removing calls `removeMemberFromTeam` (DELETE) then reloads.
3. **Tools tab** — `team.tools` (each `TeamTool` carries `tool_id`, `source_type`, `source_id`, `priority`, `is_active`, and an embedded `tool` summary) is split client-side by `source_type` into direct vs toolbox groups. Remove calls `removeToolFromTeam` (DELETE with optional `?source_type=`).
4. **Assignment flows** — Add Tools loads active tools (`ToolService.listTools({is_active: true})` → `GET /api/v1/tools?is_active=true`), Add Toolboxes loads tool-type collections (`collectionsService.listCollections({entity_type: 'tool'})` → `GET /api/v1/collections?entity_type=tool`); each modal excludes already-assigned items and assigns them one-by-one (POST `/tools` or POST `/toolboxes`), reloading the team after each batch.
5. **Edit / Delete** — Edit submits `CollectionUpdate` via `teamToolService.updateTeam` (PUT) and reloads; Delete confirms via `teamToolService.deleteTeam` (DELETE) then `navigate('/teams')`.
6. **Sync** — `handleSyncTools` POSTs `{agent_ids: undefined}` to the sync endpoint, logs any returned `conflicts`, and reloads the team; `isSyncing` disables the button during the request.
7. **Mutating writes always reload** — every successful mutation (`loadTeam()` re-fetch) keeps the page consistent with the backend; `TeamToolService` invalidates its 2-minute list cache on create/update/delete so the `/teams` list reflects changes.

## State Management

| Store / Service | Path | Usage |
|---|---|---|
| `notificationStore` (`useNotificationStore`) | `frontend/src/stores/notificationStore.ts` | Zustand store (in-memory, no persistence) for toast notifications; page reads the `addNotification` selector to push error toasts when adding a member fails. `TeamMembersTab` also uses it for load/add failures. |
| `teamToolService` (singleton `TeamToolService`) | `frontend/src/services/domain/TeamToolService.ts` | All team reads/writes; caches the team **list** for 2 min (`CACHE_TTL`), invalidates on create/update/delete; `getTeam` is a 3-way `Promise.all` merge (no caching). |
| `agentService` (fresh instance per use) | `frontend/src/services/domain/AgentService.ts` | Used by `TeamMembersTab`; `getAgents()` caches agent list and is backed by `ProfileService` (backend agent profiles). |
| `toolService` (fresh instance per use) | `frontend/src/services/domain/ToolService.ts` | Used by `AddToolsModal`; `listTools({is_active: true})` bypasses its cache (filtered query) and hits the backend. |
| `collectionsService` (singleton) | `frontend/src/services/domain/CollectionsService.ts` | Used by `AddToolboxesModal`; `listCollections({entity_type: 'tool'})` bypasses its cache (filtered query). |

## API Endpoints Called

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/teams/{teamId}` | Fetch team base record (name, description, icon, color, timestamps) — part of `getTeam`'s parallel load. |
| GET | `/api/v1/teams/{teamId}/members` | Fetch team member (agent) items — part of `getTeam`'s parallel load. |
| GET | `/api/v1/teams/{teamId}/tools` | Fetch team tool assignments (`TeamToolListResponse`) — part of `getTeam`'s parallel load. |
| PUT | `/api/v1/teams/{teamId}` | Update team (name/description/color/icon) from Edit modal. |
| DELETE | `/api/v1/teams/{teamId}` | Delete the team, then navigate to `/teams`. |
| POST | `/api/v1/teams/{teamId}/members` | Add an agent member (`{entity_id, entity_type: 'agent', entity_name}`). |
| DELETE | `/api/v1/teams/{teamId}/members/{memberId}` | Remove a member by member item id. |
| POST | `/api/v1/teams/{teamId}/tools` | Assign a tool directly (`{tool_id, source_type: 'direct', priority, is_active, config}`). |
| DELETE | `/api/v1/teams/{teamId}/tools/{toolId}?source_type=` | Remove a tool assignment (query param when removing toolbox-sourced tools). |
| POST | `/api/v1/teams/{teamId}/toolboxes` | Assign a toolbox (`{toolbox_id, priority}`); backend fans out its tools. |
| DELETE | `/api/v1/teams/{teamId}/toolboxes/{toolboxId}` | Remove a toolbox assignment (defined on the service; not wired to page UI). |
| POST | `/api/v1/teams/{teamId}/sync` | Sync team tools to member agents; returns `synced_agents`, counts, and `conflicts`. |
| GET | `/api/v1/agents` | (via `TeamMembersTab` → `AgentService.getAgents()` → `ProfileService`) — agent list for the Add Member modal. |
| GET | `/api/v1/tools?is_active=true` | (via `AddToolsModal` → `ToolService.listTools`) — candidate tools for assignment. |
| GET | `/api/v1/collections?entity_type=tool` | (via `AddToolboxesModal` → `CollectionsService.listCollections`) — candidate toolboxes for assignment. |

## Related Pages

- [[TeamsManagement]] — team list page at `/teams`; entry point into this page.
- [[ToolManagement]] — global tool registry browsed by the Add Tools modal.
- [[CollectionDetail]] — same collection-edit modal family; collections detail page.
- [[ToolCollectionDetail]] — toolbox detail page (toolboxes assignable to teams here).
- [[AgentProfiles]] — agent profiles that back the Add Member agent picker.
