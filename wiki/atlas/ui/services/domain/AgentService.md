---
title: Agent Service
type: atlas-service
path: frontend/src/services/domain/AgentService.ts
confidence: high
updated: 2026-09-10
tags: [type/service, domain/atlas-ui]
---
# Agent Service

**Path**: `frontend/src/services/domain/AgentService.ts`
**Type**: service

## Purpose

`AgentService` is a class that manages agent selection and persistence for the frontend. It loads agents from the backend (via `ProfileService`), converts backend profiles into `Agent` objects (derived from `profileService` on every call — it keeps **no** local cache of its own), and persists the currently selected agent ID to `sessionStorage`. The source comment says it was "Extracted from useAgentSelection.ts". It is **not** a singleton: each consumer creates `new AgentService()` and therefore gets its own selection state (there is no agent cache; every instance derives from the shared `profileService`).

## Exported API

Single named export: `export class AgentService`. No default export and no shared singleton instance — consumers must instantiate it.

```typescript
class AgentService {
  async getAgents(): Promise<Agent[]>
  async selectAgent(agentId: string, agents?: Agent[]): Promise<Agent>
  getSelectedAgentId(): string | null
  async getSelectedAgent(agents?: Agent[]): Promise<Agent | null>
  async getAgent(agentId: string): Promise<Agent | null>
  clearCache(): void
  clearSelection(): void
  // private: persistSelection(agentId: string): void
  // private: restoreSelectionFromStorage(): string | null
}
```

- `getAgents(): Promise<Agent[]>` — Calls `profileService.loadFromBackend()` **every time** (no local cache — the profiles are the ONE home), maps `profileService.getProfiles()` through `convertProfileToAgent(profile)`, stamps freshness metadata (`loadedFrom: 'backend'`, `lastRefreshed: <ISO timestamp>`, `isStale: false`), and returns. Throws `new Error('Failed to load agent profiles')` on failure.
- `selectAgent(agentId: string, agents?: Agent[]): Promise<Agent>` — Resolves the agent from the supplied array or a fresh `getAgents()`; throws `Error('Agent with ID "<agentId>" not found')` if absent; otherwise records the selection and persists it to `sessionStorage` (key `agent-store`) via `persistSelection`.
- `getSelectedAgentId(): string | null` — Returns the in-memory selected ID, or lazily restores it from `sessionStorage` via `restoreSelectionFromStorage()`.
- `getSelectedAgent(agents?: Agent[]): Promise<Agent | null>` — Resolves the selected agent from the supplied array or `getAgents()`. If the persisted ID no longer exists, logs a warning, calls `clearSelection()`, and returns `null`.
- `getAgent(agentId: string): Promise<Agent | null>` — Looks up one agent via `profileService.getProfiles()` (in-memory only — no network call here), converts and stamps freshness metadata; returns `null` on not-found or any error.
- `clearCache(): void` — Clears the ONE home: delegates to `profileService.clearAll()`, so the next `getAgents()` re-fetches from the backend. (There is no `agentsCache` any more.)
- `clearSelection(): void` — Clears the in-memory selection and removes the `agent-store` key from `sessionStorage`.

Module-level constant (not exported): `AGENT_SELECTION_STORAGE_KEY = 'agent-store'`.

## Endpoints

`AgentService` makes no direct HTTP calls — all backend access is delegated to `profileService`:

| Endpoint | Method | Trigger |
|---|---|---|
| `/api/v1/agents?page=1&page_size=100` | GET | Via `profileService.loadFromBackend()` on every `getAgents()` call (also reached from `selectAgent`/`getSelectedAgent` when no `agents` array is supplied) |

Note: `getAgent()` does **not** hit the network; it reads `profileService.getProfiles()` from memory, so it only returns data if profiles were previously loaded (e.g. by an earlier `getAgents()`).

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `profileService` (`./ProfileService`) | domain service singleton | Loads profiles from backend (`loadFromBackend`), exposes cached list (`getProfiles`), converts profiles to agents (`convertProfileToAgent`) |
| `frontendLoggingService` (`../frontendLoggingService`) | service | Debug/info/warning/error logging tagged `'AgentService'` |
| `Agent` (`../../types/agentInteraction`) | type | Agent shape incl. freshness metadata (`loadedFrom`, `lastRefreshed`, `isStale`) |
| `sessionStorage` | browser API | Persistence of the selected agent ID under key `agent-store` |
| browser high-resolution timer (`performance.now()`) | browser API | Load-duration measurement in `getAgents()` |

## Usage Example

```typescript
import { AgentService } from '../../services/domain/AgentService'

const agentService = new AgentService()

const agents = await agentService.getAgents()
await agentService.selectAgent('agent-123')
const selected = await agentService.getSelectedAgent()
const selectedId = agentService.getSelectedAgentId()

agentService.clearCache()      // force re-fetch on next getAgents()
agentService.clearSelection()  // forget the persisted selection
```

## Data Flow / Notes

- Load path: `getAgents()` → `profileService.loadFromBackend()` (GET `/api/v1/agents?page=1&page_size=100`) → `profileService.getProfiles()` → `convertProfileToAgent()` per profile → `Agent[]` with freshness metadata stamped (`loadedFrom: 'backend'`, `isStale: false`).
- Selection path: `selectAgent()` sets `selectedAgentId` and persists `{ selectedAgentId }` to `sessionStorage['agent-store']`; `getSelectedAgentId()` restores it lazily; `getSelectedAgent()` clears stale persisted selections when the stored ID no longer resolves.
- Per-instance state: only the **selection** lives on the instance (there is no agent cache); separate `new AgentService()` instances do not share selection, but they all derive from the shared `profileService`.
- Consumers are expected to pass an already-fetched `agents` array to `selectAgent`/`getSelectedAgent` to avoid re-fetching (as `useAgentSelection` does).
- `getAgent()` is used for fire-and-forget background refresh of the selected agent in `useAgentSelection`; on failure the caller keeps the already-selected agent (the hook's own state) — AgentService holds no cache to fall back to.

## Related

Consumers (verified by import grep):

- `frontend/src/hooks/useAgentSelection.ts` — holds one instance per hook mount via `useRef(new AgentService())` (de-facto singleton for that hook); uses `getAgents`, `getAgent` (background refresh), `clearCache` (in `reloadAgents`), `getSelectedAgent` (restore). The hook's UI state lives in `cognitiveHubStore`; AgentService supplies backend loading, persistence, and refresh.
- `frontend/src/components/sessions/SessionFilters.tsx` — `new AgentService()` → `getAgents()` for the agent filter dropdown.
- `frontend/src/components/sessions/SessionTable.tsx` — `new AgentService()` → `getAgents()` + `selectAgent(String(session.agentId))`.
- `frontend/src/components/sessions/SessionDetailsModal.tsx` — `new AgentService()` → `getAgents()` + `selectAgent(String(session.agentId))`.
- `frontend/src/components/Teams/TeamMembersTab.tsx` — `new AgentService()` → `getAgents()`.
- `frontend/src/services/domain/__tests__/AgentService.test.ts` — unit tests (with `profileService` mocked).
- (`TraceAnalysis.tsx` mentions `'AgentService'` only as a string option value, not an import.)

Sibling agent services — do not confuse:

- `frontend/src/services/agentService.ts` (root) — object literal with `ApiResponse`-wrapped CRUD methods (`getAgents`, `getAgentById`, `getAgentMetrics`, `createAgent`, ...). Imported **only** by `services/index.ts` as `legacyAgentService` (backward-compat re-export); no component or hook imports it directly.
- `frontend/src/services/domains/llm/agentService.ts` — `IAgentService` interface + singleton `agentService` instance, re-exported from `services/index.ts` as `agentService`. Consumed by `hooks/useAgents.ts` (full CRUD, metrics, lifecycle, types, capabilities via react-query) and `ServiceFactory.getAgentService()`. This is the "agent management" service; the class documented here is the "selection/persistence" service.
- `frontend/src/services/domain/ProfileService.ts` — `profileService` singleton; the data source AgentService builds on.

## Deprecation / Obsolete Notes

- **Not deprecated**: `AgentService.ts` contains no `@deprecated` markers, and the class is actively imported by 5 consumer files plus its test suite.
- The source comment ("Extracted from useAgentSelection.ts") indicates this is the current home of agent loading/selection logic, not a leftover.
- The root `frontend/src/services/agentService.ts` object is the legacy sibling: `services/index.ts` imports it as `legacyAgentService` ("Import legacy services for backward compatibility") and it has zero direct consumers — flag it as obsolete if a cleanup pass is ever done.
- Consistency caveat: the JSDoc on `getAgent()` says "fresh from backend", but the implementation reads `profileService.getProfiles()` (in-memory) rather than triggering `loadFromBackend()`, so the result is only as fresh as the last profile sync.
