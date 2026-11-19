---
title: Agent Profiles
type: atlas-page
path: frontend/src/pages/AgentProfiles.tsx
confidence: high
updated: 2026-09-25
tags: [type/page, domain/atlas-ui]
---
# Agent Profiles

**Component**: `frontend/src/pages/AgentProfiles.tsx`
**Route**: `/agent-profiles` (defined in `frontend/src/config/routes.ts`, `requiresAuth: true`, icon `user`)
**Last Updated**: 2026-09-10

## Purpose

Master-detail page for managing AI agent profiles (agents). Users create, edit, delete, and duplicate agents; configure provider/model, system prompt (optionally from templates), generation parameters (temperature/top_p/max_tokens), and a memory toggle; assign a cognitive profile (the "deep agent" pipeline configuration, or "None" for a shallow/basic-LLM agent); manage per-agent tool assignments; filter the agent list by team membership; upload profile images; and save any agent as a reusable template.

## Key Features

- **Master-detail layout** with a collapsible right sidebar (toggle persisted in the store) and a main `ProfileDetail` editor; an empty state prompts creating the first profile.
- **Agent CRUD** — create, edit, delete, and duplicate agents via `profileService` (`/api/v1/agents` endpoints). Duplicate selects the new agent for editing.
- **Two sidebar view modes** (`viewMode` in store): `list` (`ProfileList`) and `table` (`AgentTable` with sort, filter, pagination, row selection, and bulk actions).
- **Collective filtering** — sidebar dropdown filters profiles to members of the selected collective (membership derived from `team.items[].entity_id`). Collectives are optional; load failures degrade to an empty collective list.
- **Cognitive profile assignment** ("deep/shallow agent config") — the Cognitive tab lets users assign a cognitive profile via `CognitiveProfileSelector`; "None" = shallow agent (basic LLM chat only), a profile = deep agent whose pipeline strategies (context builder, executor, memory, response formatter) run when the agent executes. Cognitive profile id is persisted on the agent (`cognitive_profile_id`).
- **Memory toggle** — Behavior tab "Enable Memory" checkbox (marked "coming soon"); persisted as `memory` on the agent.
- **Provider/model selection** — tiered model fetching: `modelBrowserService.browseModels` (provider model browser) → curated models (`getCuratedModelsForProvider`) → manual entry; Ollama model info card with family/params/quantization/size; model picked in the model browser is round-tripped via `sessionStorage.selectedModel` + router location state.
- **System prompt templates** — Behavior tab lists templates (`GET /api/v1/agents/system-templates`) and applies one with default variables to render the system prompt.
- **Generation parameters** — Advanced tab sliders for temperature/top_p/max_tokens plus quick presets (Precise/Balanced/Creative/Reset).
- **Profile image upload** — PNG/JPEG/WebP via multipart `POST /api/v1/agents/{id}/image`; the URL is kept **relative** (`/static/<name>.png`) — the browser resolves it against whatever origin serves the page (the old API-base absolutization was removed 2026-09-10).
- **Save as Template modal** — saves the selected agent as a reusable template (`POST /api/v1/agents/templates/from-agent/{id}`) with name, description, tags, and public flag; success/failure surfaced via notifications.
- **Manage Tools modal** — per-agent `AgentToolManager` (enable/disable/configure tools and priority); also reachable from the detail editor's Tools tab (`AgentToolsTab`).
- **Collections tab** — manage which collections the agent belongs to (`CollectionsTab` + `collectionsService`).
- **Unsaved-changes persistence** — `ProfileService.saveFormState/getFormState/clearFormState` restore in-progress edits when switching profiles; form state is cleared after a successful save.
- **Background sync** — `ProfileService` re-pulls agents from the backend every 60 seconds; page state updates reactively via subscription.
- **Loading skeleton** — dedicated loading layout while profiles fetch; top error alert bar with dismiss button.

## Components Used

| Component | Path | Purpose |
|---|---|---|
| `ErrorBoundary` | `frontend/src/components/ErrorBoundary` | Wraps the entire page; catches render errors. |
| `ProfileList` | `frontend/src/components/AgentProfiles/ProfileList.tsx` | Sidebar list view: alphabetical sort, search by name/description, duplicate action, add-to-collection, team filter dropdown, view-mode toggle. |
| `ProfileDetail` | `frontend/src/components/AgentProfiles/ProfileDetail.tsx` | Main editor with tabs: basic, provider, behavior, advanced, collections, tools, cognitive. Owns the form state, template/model fetching, image selection, and submit/delete/save-as-template actions. |
| `AgentTable` | `frontend/src/components/AgentProfiles/AgentTable.tsx` | Sidebar table view: sort (name/provider/model/status), search, provider/status filters, pagination, row selection, bulk actions; per-row duplicate/delete/manage-tools. |
| `AgentToolManager` | `frontend/src/components/features/agentTools/AgentToolManager/AgentToolManager.tsx` | Manage Tools modal: lists agent tools + all tools, enable/disable, edit config/priority (via `ToolConfigModal`). |
| `ProfileImageUpload` (nested in ProfileDetail) | `frontend/src/components/AgentProfiles/ProfileImageUpload.tsx` | Image picker/preview used on save. |
| `CollectionsTab` (nested in ProfileDetail) | `frontend/src/components/AgentProfiles/CollectionsTab.tsx` | Edit-mode tab for agent ↔ collection membership. |
| `AgentToolsTab` (nested in ProfileDetail) | `frontend/src/components/AgentProfiles/AgentToolsTab.tsx` | Edit-mode tab embedding `AgentToolManager` for the profile. |
| `CognitiveProfileSelector` (nested in ProfileDetail) | `frontend/src/components/features/cognitive/CognitiveProfileSelector.tsx` | Radio-card picker of cognitive profiles with part-code badges (e.g. `d-f-d-d`) and memory labels; "None" option. |

## Hooks Used

| Hook | Path | Purpose |
|---|---|---|
| `usePageTitle` | `frontend/src/hooks/usePageTitle.tsx` | Sets document title ("Agent Profiles" + suffix) and meta description via `react-helmet-async`; restores previous title on cleanup. |
| `useProviderConfig` (in ProfileDetail) | `frontend/src/hooks/useProviderConfig.ts` | Loads the dynamic provider list from the backend for the provider dropdown. |
| `useNavigate` / `useLocation` (in ProfileDetail) | `react-router-dom` | Clears model-browser selection state after applying `sessionStorage.selectedModel`. |
| `useState` / `useEffect` / `useMemo` / `useCallback` | React | Local state (profiles, loading, error, isSaving, teams, template modal fields, tools modal agent) and memoized team filtering / selected-profile lookup. |

## Data Flow

1. **Profile load (mount)**: `profileService.loadFromBackend()` issues `GET /api/v1/agents?page=1&page_size=100`. The backend's `{agents, total, page, page_size}` envelope is mapped to frontend `Profile[]` via `ProfileService.convertToProfile` (the row's own sampling declaration carried through — or NOTHING, never a fallback pair; `cognitive_profile_id` mapped through; the served `output_budget` + `budget_ceiling` passed through). Results are cached in the singleton and subscribers notified. The page subscribes via `profileService.subscribe(setProfiles)` — all later mutations (create/update/delete/duplicate/image upload) update the cache and re-notify, so the page list stays in sync without manual refresh. A background interval re-runs the load every 60 s.

   The list rows and the detail form render the served budget read: the row shows `declared → sent · reason` (and `· last N` when the last turn's carried number differs from the prediction), the form's Advanced tab shows `Sends … · declared … · <reason>` with `Last turn carried …` beneath it.
2. **Collectives (mount)**: `teamToolService.listTeams()` calls `GET /api/v1/teams` (cached 2 minutes) into `Collection[]`. Filtering: when `selectedTeamId !== 'all'`, the collective's member agent ids are read from `team.items[].entity_id` and profiles are filtered by membership (`profiles.filter(p => agentIds.includes(p.id))`); empty collectives yield an empty list.
3. **Create/edit save**: `ProfileDetail` builds `ProfileCreate` (generating a slug+random-suffix `id` for new agents), calls the page's `handleSaveProfile(data, imageFile)` → `profileService.createProfile` (`POST /api/v1/agents`) or `updateProfile` (`PUT /api/v1/agents/{id}`), then optionally `uploadProfileImage` (`POST /api/v1/agents/{id}/image`; image failures are logged but don't fail the save). The page then re-reads the updated profile from the service cache and calls `selectProfile(id, 'edit')` to keep the store in sync; `clearFormState()` is invoked by ProfileDetail on success.
4. **Delete/duplicate — the lifecycle (Phase D)**: `handleDeleteProfile` opens the BOM dialog (ProfileDetail's `deleteDialog` state): it discloses what will be removed (tool links, memory, workspace folder — the depth marker 'deep' shows when the agent has a workspace_key). Confirming calls `DELETE /api/v1/agents/{id}` — the response IS the result report (bom + archived_path), shown in the dialog ("Profile deleted" + the archive path) — then `resetSelection()`. `handleDuplicateProfile` → `POST /api/v1/agents/{id}/duplicate` then selects the new profile. Errors are set into the error alert and rethrown.
5. **Restore (Phase D)**: on mount the page calls `profileService.listDeleted()` (`GET /api/v1/agents/deleted`) into `deletedAgents`. When no profile is selected (the empty state), a "Deleted profiles (N)" section lists them with their archive paths + a Restore button → `profileService.restoreProfile(id)` (`POST /api/v1/agents/{id}/restore`) — the archived workspace moves back, the markers clear, the agent is live again. ADDITIVE recovery, explicit, never automatic (the destructive-UX rule).
6. **Save as template**: `POST /api/v1/agents/templates/from-agent/{id}` with `{name, description, is_public, tags}`; success → success notification + modal close; failure → error notification with backend `detail`.
7. **Detail-form data**: templates fetched on mount (`GET /api/v1/agents/system-templates`), applied via `POST /api/v1/agents/system-templates/apply` (rendered prompt written into `system_prompt`); models fetched via `modelBrowserService.browseModels(providerId)` → curated fallback; cognitive profiles via `cognitiveProfileService.list()` (`GET /api/v1/cognitive-profiles`) rendered by `CognitiveProfileSelector` and written into `formData.cognitive_profile_id`; tools via `agentToolService` (see endpoints); collections via `collectionsService`.
8. **Routing interplay**: a model selected in `/providers/:providerId/models` is stored in `sessionStorage.selectedModel` and read back in ProfileDetail on mount, setting provider + model, then the router state is cleared.

## State Management

| Store/Service | Path | Usage |
|---|---|---|
| `useAgentProfilesStore` (Zustand + `persist` to localStorage key `agent-profiles-storage`, `devtools` in dev) | `frontend/src/stores/agentProfilesStore.ts` | Persistent UI state: `sidebarCollapsed`, `viewMode` (`'list' | 'table'`), `selectedTeamId` (`string | 'all'`), `selectedProfileId`, `action` (`'create' | 'edit'`); actions `toggleSidebar`, `setViewMode`, `setSelectedTeamId`, `selectProfile`, `resetSelection`. This is the source of truth for which profile is open and in which mode. |
| `ProfileService` (singleton, non-React) | `frontend/src/services/domain/ProfileService.ts` | In-memory profile cache + subscriber set (reactive updates), 60 s background sync, application-level form state (unsaved changes), API mapping frontend↔backend. Not a Zustand store but the page's primary data store. |
| `useNotificationStore` | `frontend/src/stores/notificationStore.ts` | `addNotification` (page) / `addSuccess`, `addError` (ProfileDetail, ProfileList) for toasts on save-as-template, delete, add-to-collection, etc. |
| Local `useState` | AgentProfiles.tsx | `profiles` (mirror of service cache), `loading`, `error`, `isSaving`, `teams`, `loadingTeams`, template modal fields, `toolsModalAgent`, `deletedAgents` + `showDeleted` (the restore view). |

## API Endpoints Called

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/agents?page=1&page_size=100` | Load all agent profiles (initial + 60 s background sync) — `ProfileService.loadFromBackend`. |
| POST | `/api/v1/agents` | Create an agent profile — `ProfileService.createProfile` (sends `cognitive_profile_id`, parameters, etc.). |
| PUT | `/api/v1/agents/{id}` | Update an agent profile — `ProfileService.updateProfile`. |
| DELETE | `/api/v1/agents/{id}` | **The recoverable delete** — soft-deletes + archives; the response is the result report (bom + archived_path) shown in the BOM dialog — `ProfileService.deleteProfile`. |
| GET | `/api/v1/agents/deleted` | Soft-deleted agents + archive paths — the restore view — `ProfileService.listDeleted`. |
| POST | `/api/v1/agents/{id}/restore` | Restore a soft-deleted agent (additive) — `ProfileService.restoreProfile`. |
| POST | `/api/v1/agents/{id}/duplicate` | Duplicate an agent; returns the new agent — `ProfileService.duplicateAgent`. |
| POST | `/api/v1/agents/{id}/image` | Upload profile image (multipart FormData; PNG/JPEG/WebP) — `ProfileService.uploadProfileImage`. |
| GET | `/api/v1/agents/system-templates` | List system prompt templates (Behavior tab) — `ProfileService.getTemplates`. |
| POST | `/api/v1/agents/system-templates/apply` | Render a template with variables → prompt — `ProfileService.applyTemplate`. |
| POST | `/api/v1/agents/templates/from-agent/{id}` | Save the selected agent as a reusable template — page `handleSaveAsTemplate` via `apiClient.post`. |
| GET | `/api/v1/teams` | List teams for the team filter dropdown — `teamToolService.listTeams` (2 min cache). |
| GET | `/api/v1/providers/{providerId}/models` | Browse provider models (Tier 1 model list in Provider tab) — `modelBrowserService.browseModels`. |
| GET | `/api/v1/providers/ollama/models` | List Ollama models (available via `ProfileService.getOllamaModels`). |
| GET | `/api/v1/cognitive-profiles` | List cognitive profiles for assignment (Cognitive tab) — `cognitiveProfileService.list` (via `CognitiveProfileSelector`). |
| GET | `/api/v1/tools/agents/{agentId}/tools` | List tools assigned to an agent — `agentToolService.listAgentTools` (Manage Tools modal + Tools tab). |
| POST | `/api/v1/tools/agents/{agentId}/tools` | Enable/assign a tool to an agent — `agentToolService.enableToolForAgent`. |
| PUT | `/api/v1/tools/agents/{agentId}/tools/{toolId}` | Update agent-tool config/priority — `agentToolService.updateAgentTool`. |
| POST | `/api/v1/tools/agents/{agentId}/tools/{toolId}/disable` | Soft-disable a tool for an agent — `agentToolService.disableToolForAgent`. |
| DELETE | `/api/v1/tools/agents/{agentId}/tools/{toolId}` | Remove a tool from an agent (hard delete) — `agentToolService.removeToolFromAgent`. |
| GET/POST/PUT/DELETE | `/api/v1/collections` (+ item routes) | Collections tab membership management — `collectionsService` (CollectionsTab). |

## Related Pages

- [[AgentTemplates]] — browse/use templates created from agents via "Save as Template".
- [[CognitivePipeline]] — manage cognitive profiles (strategies + memory profiles) that this page assigns to agents.
- [[TeamsManagement]] / [[TeamDetail]] — teams used for filtering agent profiles by membership.
- [[ToolManagement]] — global tool registry used by the per-agent tool manager.
- [[ProviderDashboard]] / [[ProviderModelsBrowser]] — provider models browsed from the Provider tab (round-trip via `sessionStorage.selectedModel`).
- [[CollectionsManagement]] — collections an agent can belong to (Collections tab).
