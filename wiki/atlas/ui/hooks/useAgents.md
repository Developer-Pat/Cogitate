---
title: useAgents
type: atlas-hook
path: frontend/src/hooks/useAgents.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---

# useAgents

**Path**: `frontend/src/hooks/useAgents.ts`
**Type**: hook

## Purpose

Multi-export hook module (9 exports) providing React Query-backed data access for agent management: listing agents, fetching a single agent and its metrics, creating/updating/deleting agents, lifecycle actions (start/stop/restart/test), and reference data (agent types and capabilities). It is the frontend's primary bridge between the agent REST API (`/api/v1/agents` via the LLM-domain `agentService`) and the Zustand `systemStore`, mirroring fetched agents into the store as `AgentConfig[]`.

Queries use `@tanstack/react-query` with auto-refetch (agents every 30 s, metrics every 10 s) and a 5-minute staleness window for reference data (types/capabilities). Every hook unwraps `ApiResponse<T>` and throws `new Error(response.error.message)` when `response.error` is set.

## Exported API

### `useAgents(): UseQueryResult<AgentInfo[], Error>`

Fetch all agents. Query key `['agents']`, refetch interval 30 000 ms. On success, maps each `AgentInfo` to an `AgentConfig` and pushes the array into the system store via `setAgentConfigurations`.

```ts
export function useAgents() {
  const setAgentConfigurations = useSystemStore((state) => state.setAgentConfigurations);

  const query = useQuery({
    queryKey: ['agents'],
    queryFn: async () => {
      const response = await agentService.getAgents();
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    refetchInterval: 30000, // Refetch every 30 seconds
  });

  // Update Zustand store when data is fetched
  if (query.data) {
    const agentConfigs: AgentConfig[] = query.data.map(agent => ({
      id: agent.id,
      name: agent.name,
      type: agent.type,
      parameters: agent.configuration || {},
      enabled: agent.status === 'active',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }));
    setAgentConfigurations(agentConfigs);
  }

  return query;
}
```

Side effect: `AgentInfo` → `AgentConfig` conversion (`configuration` → `parameters`, `status === 'active'` → `enabled`, timestamps synthesized client-side at render time).

### `useAgentById(id: string): UseQueryResult<AgentInfo, Error>`

Fetch a single agent by ID. Query key `['agent', id]`; `enabled: !!id` — only fetches when an ID is provided (detail pages / selection). Throws if the API request fails.

### `useAgentMetrics(id: string): UseQueryResult<AgentMetrics, Error>`

Fetch live performance metrics for an agent (`requestsProcessed`, `averageResponseTime`, `errorRate`, `memoryUsage`). Query key `['agent-metrics', id]`; `enabled: !!id`; refetch interval 10 000 ms for real-time updates.

### `useCreateAgent(): UseMutationResult<AgentConfig, Error, Omit<AgentConfig, 'id' | 'createdAt' | 'updatedAt'>>`

Create an agent. `mutate(config)` posts the config (id and timestamps are server-generated). On success invalidates `['agents']` so the list refetches.

### `useUpdateAgent(): UseMutationResult<AgentConfig, Error, { id: string; config: Partial<AgentConfig> }>`

Update an agent. `mutate({ id, config })`. On success: calls `updateAgentConfiguration(data)` on the system store (replaces the matching entry in `agentConfigurations`), then invalidates `['agents']` and `['agent', data.id]`.

### `useDeleteAgent(): UseMutationResult<{ message: string }, Error, string>`

Delete an agent by ID. `mutate(id)`. On success invalidates `['agents']`.

### `useAgentActions(): { startAgent; stopAgent; restartAgent; testAgent }`

Four independent `UseMutationResult` objects, each invoked with `mutate(id: string)`:

- `startAgent` / `stopAgent` / `restartAgent` — call `agentService.startAgent|stopAgent|restartAgent(id)` returning `ApiResponse<{ message: string; agent: AgentInfo }>`; each invalidates `['agents']` on success.
- `testAgent` — calls `agentService.testAgent(id)` returning `ApiResponse<{ connected: boolean; latency?: number }>`; does **not** invalidate any query.

### `useAgentTypes(): UseQueryResult<string[], Error>`

Fetch the list of supported agent type names. Query key `['agent-types']`; `staleTime: 300000` (5-minute cache to reduce API calls).

### `useAgentCapabilities(): UseQueryResult<Record<string, string[]>, Error>`

Fetch capabilities available per agent type, e.g. `{ 'llm': ['chat', 'analysis'], 'tool': ['execute', 'schedule'] }`. Query key `['agent-capabilities']`; `staleTime: 300000`.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `@tanstack/react-query` (`useQuery`, `useMutation`, `useQueryClient`) | library | Query/mutation lifecycle, caching, invalidation, refetch intervals |
| `agentService` (from `'../services'` → `services/domains/llm/agentService.ts`) | service singleton (`IAgentService`) | All REST calls: `getAgents`, `getAgentById`, `getAgentMetrics`, `createAgent`, `updateAgent`, `deleteAgent`, `startAgent`, `stopAgent`, `restartAgent`, `testAgent`, `getAgentTypes`, `getAgentCapabilities` — wraps `apiClient` at base path `/api/v1/agents` |
| `useSystemStore` (from `'../stores/systemStore'`) | Zustand store | `setAgentConfigurations` (in `useAgents`), `updateAgentConfiguration` (in `useUpdateAgent`) — keeps `agentConfigurations: AgentConfig[]` in sync |
| `AgentConfig`, `AgentInfo`, `AgentMetrics` (from `'../types'`) | types | Request/response shapes (defined in `types/index.ts`) |

ProfileService trace: these hooks do **not** use `ProfileService`. The class-based `services/domain/AgentService.ts` (agent selection, localStorage persistence, backed by `profileService.loadFromBackend` / `getProfiles` / `convertProfileToAgent`) is a separate service consumed by `hooks/useAgentSelection.ts` and the Sessions/Teams UI — not by this module. `useAgents.ts` only uses the LLM-domain REST `agentService` singleton.

## Usage Example

```tsx
import {
  useAgents, useAgentById, useAgentMetrics,
  useCreateAgent, useUpdateAgent, useDeleteAgent,
  useAgentActions, useAgentTypes, useAgentCapabilities,
} from '../hooks';

function AgentList() {
  const { data: agents, isLoading, error } = useAgents();
  if (isLoading) return <div>Loading agents...</div>;
  if (error) return <div>Error: {error.message}</div>;
  return (
    <ul>
      {agents?.map(agent => (
        <li key={agent.id}>{agent.name} — {agent.status}</li>
      ))}
    </ul>
  );
}

function AgentDetail({ id }: { id: string }) {
  const { data: agent, isLoading } = useAgentById(id);
  const { data: metrics } = useAgentMetrics(id);
  if (isLoading) return <div>Loading agent details...</div>;
  return (
    <div>
      <p>{agent?.name} ({agent?.type})</p>
      <p>Requests: {metrics?.requestsProcessed}</p>
      <p>Avg Response: {metrics?.averageResponseTime}ms</p>
      <p>Error Rate: {(metrics?.errorRate * 100).toFixed(2)}%</p>
    </div>
  );
}

function CreateAgentForm() {
  const { mutate: createAgent, isPending } = useCreateAgent();
  return (
    <button
      disabled={isPending}
      onClick={() => createAgent({ name: 'New Agent', type: 'llm', parameters: { model: 'gpt-4' }, enabled: true })}
    >
      Create Agent
    </button>
  );
}

function AgentControls({ id }: { id: string }) {
  const { startAgent, stopAgent, restartAgent, testAgent } = useAgentActions();
  return (
    <>
      <button onClick={() => startAgent.mutate(id)}>Start</button>
      <button onClick={() => stopAgent.mutate(id)}>Stop</button>
      <button onClick={() => restartAgent.mutate(id)}>Restart</button>
      <button onClick={() => testAgent.mutate(id)}>Test</button>
    </>
  );
}

function AgentTypePicker() {
  const { data: agentTypes } = useAgentTypes();
  const { data: capabilities } = useAgentCapabilities();
  return (
    <select>
      {agentTypes?.map(type => <option key={type} value={type}>{type}</option>)}
    </select>
  );
}
```

## State / Data Flow

- **Query keys / invalidation contract**: `['agents']`, `['agent', id]`, `['agent-metrics', id]`, `['agent-types']`, `['agent-capabilities']`. Create/delete/start/stop/restart invalidate `['agents']`; update invalidates `['agents']` + `['agent', data.id]`; `testAgent` invalidates nothing.
- **Refetch / staleness**: agents refetch every 30 s; metrics every 10 s; types and capabilities use `staleTime` 5 min; `useAgentById` and `useAgentMetrics` are gated by `enabled: !!id`.
- **Zustand store sync**: `useAgents` mirrors the fetched list into `systemStore.agentConfigurations` as `AgentConfig[]` (status → enabled mapping; note `createdAt`/`updatedAt` are synthesized, not server values). `useUpdateAgent` patches the store entry in place via `updateAgentConfiguration`.
- **API wiring**: all calls go through the LLM-domain `agentService` singleton → `apiClient` → `/api/v1/agents`. Polling (no SSE) via `refetchInterval`. Service responses are `ApiResponse<T>` (`{ data?, error?, status, timestamp }`); every hook throws `new Error(response.error.message)` when `response.error` is present.
- **No ProfileService involvement** in this module (see Dependencies).

## Related

- Barrel re-export: `frontend/src/hooks/index.ts` (all 9 hooks under "Agents Hooks").
- Service: `frontend/src/services/domains/llm/agentService.ts` (`IAgentService`, `agentService` singleton); `frontend/src/services/apiClient.ts`; barrel `frontend/src/services/index.ts`.
- Store: `frontend/src/stores/systemStore.ts` — `setAgentConfigurations`, `updateAgentConfiguration`, and the `useAgentConfigurations` selector.
- Types: `frontend/src/types/index.ts` — `AgentInfo`, `AgentConfig`, `AgentMetrics`, `ApiResponse`, `ApiError`.
- Distinct service (not used by these hooks): `frontend/src/services/domain/AgentService.ts` — ProfileService-backed class used by `hooks/useAgentSelection.ts`, `components/sessions/SessionFilters.tsx`, `SessionTable.tsx`, `SessionDetailsModal.tsx`, `components/Teams/TeamMembersTab.tsx`.
- No components in the current source tree import these hooks directly; they are consumed through the `hooks` barrel where used.
