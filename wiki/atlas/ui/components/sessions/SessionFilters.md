---
title: SessionFilters
type: atlas-component
path: frontend/src/components/sessions/SessionFilters.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# SessionFilters

**Path**: `frontend/src/components/sessions/SessionFilters.tsx`
**Last Updated**: 2026-08-01

## Purpose
Filter bar for the sessions page — search input, "Unnamed only" toggle, agent filter dropdown, date-range dropdown (All Time / Today / This Week / This Month with live counts), and sort dropdown (date/title/message-count × asc/desc). Also renders a stats row (total/today/week/month badges) computed from a `sessionsService` subscription. Every filter change is propagated up through `onFilterChange` with the full `FilterState`, including the loaded agent list.

## Props Interface
```typescript
interface SessionFiltersProps {
  onFilterChange: (filters: FilterState) => void;
}

interface FilterState {
  searchQuery: string;
  sortBy: 'date' | 'title' | 'count';
  sortOrder: 'asc' | 'desc';
  dateRange: 'all' | 'today' | 'week' | 'month';
  agents: AgentInfo[];
  agentFilter?: string | number;
  unnamedOnly: boolean;
}

interface SessionStats {
  total: number;
  today: number;
  week: number;
  month: number;
}

interface AgentInfo {
  id: string | number;
  name: string;
  profile_image_url?: string;
}
```

**onChange contract**: `onFilterChange` fires from a `useEffect` whenever `filters`, `agents`, or the callback identity changes, receiving `{ ...filters, agents }` — the complete merged filter state (agents are merged in so the parent's agent-filter options stay in sync). It fires once on mount with initial state, so the parent should treat it as state-initializing as well as state-updating. The parent should memoize the callback with `useCallback` to avoid redundant emissions.

## Dependencies
| Dependency | Type | Purpose |
|---|---|---|
| `sessionsService` (from `../../services/domain/SessionsService`) | domain service (singleton) | `subscribe(callback)` pushes the full session list; used to compute total/today/week/month stats counts (date buckets: today, last 7 days, last 30 days) |
| `AgentService` (from `../../services/domain/AgentService`) | domain service (class) | instantiated per mount; `getAgents()` loads agents for the agent filter dropdown, mapped to `AgentInfo` (`profileImageUrl` → `profile_image_url`) |

## Usage Example
```tsx
import { SessionFilters, FilterState } from '../components/sessions/SessionFilters';

const [filters, setFilters] = useState<FilterState | null>(null);
const handleFilterChange = useCallback((f: FilterState) => setFilters(f), []);

<SessionFilters onFilterChange={handleFilterChange} />
```

## State Used
- `filters` (`FilterState`) — local `useState`; `searchQuery`, `sortBy`, `sortOrder`, `dateRange`, `agentFilter`, `unnamedOnly`; merged with `agents` and emitted via `onFilterChange`
- `stats` (`SessionStats`) — total/today/week/month counts derived from the `sessionsService` subscription
- `agents` (`AgentInfo[]`) — loaded once on mount from `AgentService`; also injected into the emitted filter state

## Related Components
- `frontend/src/pages/Sessions.tsx` — parent page; consumes `onFilterChange` (renders `<SessionFilters onFilterChange={handleFilterChange} />`)
- `frontend/src/components/sessions/SessionTable.tsx` — sibling; displays the filtered session list
- `frontend/src/components/sessions/SessionDetailsModal.tsx` — sibling; detail view for a selected session
