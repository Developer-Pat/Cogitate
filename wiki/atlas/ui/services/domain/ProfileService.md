---
title: Profile Service
type: atlas-service
path: frontend/src/services/domain/ProfileService.ts
confidence: high
updated: 2026-09-25
tags: [type/service, domain/atlas-ui]
---
# Profile Service

**Path**: `frontend/src/services/domain/ProfileService.ts`
**Type**: service

## Purpose

Centralized profile state management for **agent profiles** (called "agents" by the backend). The service is the single source of truth for profile state in the frontend:

- **In-memory caching** of profiles to avoid repeated API calls
- **Reactive updates** via a subscriber pattern (components subscribe and get pushed fresh data)
- **Background sync** with the backend (every 60 seconds)
- **CRUD** for profiles: create, update, delete, duplicate
- **Profile image upload** (`POST /api/v1/agents/{profileId}/image`)
- **Ollama model listing** and **system prompt templates** (list + apply)
- **Cognitive profile selection** via the `cognitive_profile_id` field (bound to a cognitive pipeline configuration; UI wired through `CognitiveProfileSelector`)
- **Application-level form state persistence** — unsaved changes survive switching between profiles

The class is decoupled from React/Zustand; state is pushed to consumers through subscriptions. The file exports a singleton instance `profileService`, which is the object actually consumed by the app.

## Exported API (exact signatures)

Multi-export file: exports the `ProfileService` class, the singleton instance `profileService`, and the types `Profile`, `ProfileCreate`, `ProfileUpdate`, `OllamaModel`, `SystemPromptTemplate`.

```ts
export class ProfileService {
  // Cache reads
  getProfiles(): Profile[]                                          // snapshot of cached profiles
  getProfile(profileId: string): Profile | null                     // cached lookup by id

  // Subscription
  subscribe(callback: ProfileSubscriber): () => void                // fires callback immediately with current profiles; returns unsubscribe fn

  // Backend sync
  async loadFromBackend(): Promise<void>                            // GET /api/v1/agents?page=1&page_size=100; updates cache + notifies; re-entrancy guarded by isLoading

  // CRUD
  async createProfile(profileData: ProfileCreate): Promise<Profile> // POST /api/v1/agents; prepends to cache
  async updateProfile(profileId: string, updates: ProfileUpdate): Promise<void>            // PUT /api/v1/agents/{id}; merges into cache
  async deleteProfile(profileId: string): Promise<void>             // DELETE /api/v1/agents/{id}; no-op if id not in cache
  async uploadProfileImage(profileId: string, file: File): Promise<string>                 // POST /api/v1/agents/{id}/image (multipart 'file'); returns the image URL (kept relative)

  // Models & templates
  async getOllamaModels(): Promise<OllamaModel[]>                   // GET /api/v1/providers/ollama/models; [] on error
  async getTemplates(): Promise<SystemPromptTemplate[]>             // GET /api/v1/agents/system-templates; [] on error
  async applyTemplate(templateId: string, variables: Record<string, string>): Promise<string> // POST /api/v1/agents/system-templates/apply; returns rendered prompt or ''

  // Duplicate + conversion
  async duplicateAgent(agentId: string): Promise<Profile>           // POST /api/v1/agents/{id}/duplicate; prepends to cache
  convertProfileToAgent(profile: Profile): Agent                    // Profile -> Agent (consumed by domain AgentService)

  // Lifecycle / state
  clearAll(): void                                                  // empties cache + notifies
  stopBackgroundSync(): void                                        // clears 60s sync interval
  destroy(): void                                                   // stopBackgroundSync() + clears subscribers
  getStatus(): { profileCount: number; subscriberCount: number; isLoading: boolean; lastSyncTime: Date | null }

  // Form state persistence (application-level unsaved changes)
  saveFormState(profileId: string | null, formData: ProfileCreate | ProfileUpdate | null): void
  getFormState(profileId: string | null): ProfileFormState          // empty state when switching to a different profile
  clearFormState(): void
  hasUnsavedChanges(): boolean
}

export const profileService = new ProfileService()                  // singleton instance
```

Notes on the API:

- `ProfileSubscriber` and `ProfileFormState` are internal (non-exported) interfaces; `ProfileFormState` is still used as the return type of `getFormState`.
- `convertToProfile(agent)` (private) maps backend agent records to `Profile`, carrying the row's own sampling declaration **or nothing** — never a fallback pair, so a row that declares no sampling reaches the form as an absence. Also `tools: []`, `memory: false`, and `profile_image_url` kept **relative** (the browser resolves `/static/...` against whatever origin serves the page; prefixing an origin baked the dev origin into stored values).
- `createProfile` sends `is_active: true` and the caller's `parameters` — an undeclared create goes as an explicit `null`, so the row stores one shape for "declares nothing". `updateProfile` sends an explicit `null` too when the caller means to CLEAR the declaration, while an ABSENT key leaves the row's sampling untouched (the API reads `exclude_unset`).
- `convertProfileToAgent` carries the profile's declared pair without inventing one; an undeclared field stays undefined on the `Agent` shape as well.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/agents?page=1&page_size=100` | Load all profiles (list) |
| POST | `/api/v1/agents` | Create profile |
| PUT | `/api/v1/agents/{profileId}` | Update profile |
| DELETE | `/api/v1/agents/{profileId}` | Delete profile |
| POST | `/api/v1/agents/{profileId}/image` | Upload profile image (multipart field `file`) |
| POST | `/api/v1/agents/{profileId}/duplicate` | Duplicate agent |
| GET | `/api/v1/agents/system-templates` | List system prompt templates |
| POST | `/api/v1/agents/system-templates/apply` | Apply template with variables; returns rendered prompt |
| GET | `/api/v1/providers/ollama/models` | List Ollama models |

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `../apiClient` (`apiClient`) | HTTP client (`get`/`post`/`put`/`delete`/`upload`) | All backend calls |
| `../frontendLoggingService` | logging service | `debug`/`info`/`error` logging for sync, CRUD, uploads |
| `../../types/agentInteraction` (`Agent`) | type | Output type of `convertProfileToAgent` |

## Usage Example

```ts
import { profileService, type ProfileCreate } from '../services/domain/ProfileService'

// Subscribe to profile changes (fires immediately with current cache)
const unsubscribe = profileService.subscribe(setProfiles)

// Load from backend once
await profileService.loadFromBackend()

// Create a profile (cognitive_profile_id selects a cognitive pipeline)
const created: Profile = await profileService.createProfile({
  id: '', name: 'Researcher', description: '',
  provider: 'ollama', model: 'llama3.1',
  system_prompt: 'You are a research assistant.',
  tools: [], memory: false, cognitive_profile_id: 2
})

// Upload an image
const imageUrl = await profileService.uploadProfileImage(created.id, file)

unsubscribe()
```

## Data Flow / Notes

- The singleton constructor immediately starts a **background sync** (`setInterval(..., 60000)` -> `loadFromBackend()`) every 60 seconds; `stopBackgroundSync()` / `destroy()` tear it down (call on unmount to avoid leaks).
- `loadFromBackend()` is re-entrancy-guarded by the private `isLoading` flag and **throws** on failure; the page-level caller handles the error.
- **create vs update asymmetry**: `createProfile` sends `name`, `description`, `provider`, `model`, `system_prompt`, `is_active: true`, `parameters` (defaults if absent), `template_id`, `cognitive_profile_id` — it does **not** send `tools`, `memory`, or `image_url`. `updateProfile` sends every field that is defined, including `tools`, `memory`, `image_url`.
- Backend `parameters` are normalized into the frontend `Profile.parameters` shape (`temperature`/`top_p`) in `convertToProfile`; `tools: []` and `memory: false` are hardcoded defaults on read (the backend response fields are not read back). The budget the resolver would send, the ceiling it is checked against and the last turn's own record (`output_budget`, `budget_ceiling`) pass through unmapped, so the UI renders the server's numbers instead of computing them.
- Image URLs are kept **relative** (`/static/<name>.png`) in both `convertToProfile` and `uploadProfileImage`; the browser resolves them against the serving origin. (The old `VITE_API_URL`/`baseUrl` absolutization was removed 2026-09-10 — it baked the dev origin into the stored value, which then round-tripped back into the DB on save and broke the avatar off-localhost.)
- Form state methods keep a single application-level `ProfileFormState` slot; `getFormState(profileId)` returns an empty state when called for any profile other than the one holding saved changes.
- Error handling: API failures are rethrown as `Error` with the backend `detail` message (via the internal `ApiErrorResponse` shape); template/Ollama fetches swallow errors and return `[]` / `''`.
- Source quirk: `ProfileCreate` declares `cognitive_profile_id?: number | null` twice (lines 114-115) — a harmless duplicate key in the TS interface.
- `traceService.trace(...)` calls are commented out throughout the file (logging goes through `frontendLoggingService` instead).

## Related

Consumers of `profileService` (the singleton):

| Consumer | Usage |
|---|---|
| `pages/AgentProfiles.tsx` | Main consumer: `loadFromBackend()`, `subscribe(setProfiles)`, `createProfile`, `updateProfile`, `deleteProfile`, `duplicateAgent`, `uploadProfileImage`, `getProfile` |
| `components/AgentProfiles/ProfileDetail.tsx` | `getTemplates`, `applyTemplate`, `saveFormState`, `getFormState`, `clearFormState`; renders `CognitiveProfileSelector` bound to `cognitive_profile_id` |
| `components/AgentProfiles/ProfileImageUpload.tsx` | `uploadProfileImage` |
| `components/AgentProfiles/ProfileList.tsx` | `duplicateAgent` |
| `services/domain/AgentService.ts` | Wraps the singleton: `loadFromBackend()`, `getProfiles()`, `convertProfileToAgent()`; adds freshness metadata (`loadedFrom`, `lastRefreshed`, `isStale`) and sessionStorage selection |
| `services/domain/__tests__/AgentService.test.ts` | Mocks `../ProfileService` |

**Relationship to the other agent services (who uses what):**

- **`services/domain/ProfileService.ts` (this file)** — the data source of truth. Consumed directly by the AgentProfiles page/components and by `domain/AgentService`.
- **`services/domain/AgentService.ts`** — selection/persistence layer **built on top of** `profileService`. Instantiated ad hoc via `new AgentService()` in `hooks/useAgentSelection.ts` (chat/cognitive-hub flow), `components/sessions/SessionFilters.tsx`, `SessionTable.tsx`, `SessionDetailsModal.tsx`, `components/Teams/TeamMembersTab.tsx`. It derives `Agent[]` from the shared profiles and persists the selected agent id in `sessionStorage` under key `agent-store`.
- **`services/agentService.ts` (root, legacy)** — a separate *object* service (`agentService`) hitting the same `/api/v1/agents` base plus lifecycle endpoints (`/start`, `/stop`, `/restart`, `/test`, `/metrics`, `/types`, `/capabilities`). Re-exported from `services/index.ts` **only as `legacyAgentService`** ("Import legacy services for backward compatibility"); **no direct consumers**.
- **`services/domains/llm/agentService.ts` (new domain service)** — implements `IAgentService` and is exported as `agentService` from `services/index.ts`. Its only consumer is `hooks/useAgents.ts` (the `useAgents` / `useAgentById` / `useCreateAgent` / ... hook family).

## Deprecation / Obsolete Notes

- **ProfileService itself: NOT deprecated.** No `@deprecated` / `legacy` / `unused` markers; active consumers (AgentProfiles page + domain `AgentService`). The only outstanding marker in the source is a commented-out verbose log ("clogs logs").
- **Root `services/agentService.ts`:** legacy. Re-exported as `legacyAgentService` for backward compatibility only; **zero direct consumers** anywhere in `src`. Its lifecycle/metrics endpoints are not referenced by any component — strong removal candidate.
- **`hooks/useAgents.ts`:** the `useAgents` hook family (which wraps the *new* `domains/llm/agentService`) has **zero consumers** — it is only re-exported from `hooks/index.ts`; no page/component calls `useAgents()`, `useAgentById()`, `useCreateAgent()`, etc. Effectively dead code. Note the task brief's "useAgents hook" therefore points at `domains/llm/agentService`, not this file.
- The task brief's mention of "execution mode" does **not** apply to this service: `execution_mode` appears only in the separate template flow (`pages/AgentTemplates.tsx`); `ProfileService` handles `cognitive_profile_id` but no execution-mode field.

## The lifecycle methods (2026-08-16, agent-lifecycle Phase D)

- `deleteProfile(id)` — returns the DELETE response as the result
  REPORT (`bom` + `archived_path`) for the BOM dialog to show.
- `listDeleted()` — `GET /api/v1/agents/deleted` — soft-deleted
  agents + their archive paths (the restore view's data).
- `restoreProfile(id)` — `POST /api/v1/agents/{id}/restore` —
  additive recovery; reloads the cache on success.
- `convertToProfile` maps `workspace_key` (the depth marker's
  source; `null` = shallow agent).
