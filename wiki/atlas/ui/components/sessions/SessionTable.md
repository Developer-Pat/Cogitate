---
title: SessionTable
type: atlas-component
path: frontend/src/components/sessions/SessionTable.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# SessionTable

**Path**: `frontend/src/components/sessions/SessionTable.tsx`
**Last Updated**: 2026-08-01

## Purpose

`SessionTable` is the primary data table for the Sessions page. It renders the list of conversation sessions as a DaisyUI table with a checkbox column (row selection), row number, title (with inline rename), agent badge, message count, relative created/updated timestamps, and a per-row actions menu (open in chat, view details, rename, delete). It is a controlled, presentational component: all session data, selection state, and mutation callbacks are passed in from the parent (`Sessions.tsx` page). It also handles the "Open in chat" fallback flow internally — when no `onOpenInChat` callback is provided, it loads the associated agent and the latest backend session, sets it as active in the Cognitive Hub store, and navigates to the chat page. It renders loading and empty states, plus a bulk-selection action bar above the table.

## Props Interface

```typescript
interface AgentInfo {
  id: string | number;
  name: string;
  profile_image_url?: string;
}

interface SessionTableProps {
  sessions: ConversationSession[];
  agents?: AgentInfo[];
  onDeleteSession: (sessionId: string) => void;
  onRenameSession: (sessionId: string, newTitle: string) => void;
  onViewDetails: (session: ConversationSession) => void;
  onOpenInChat?: (session: ConversationSession) => void;
  isLoading?: boolean;
  selectedIds?: Set<string>;
  onSelectionChange?: (ids: Set<string>) => void;
}

export const SessionTable: React.FC<SessionTableProps> = ({ ... })
```

- `sessions` — the (already filtered/sorted) list of sessions to display; sourced from `filteredSessions` state in `Sessions.tsx`.
- `agents` — optional agent lookup list used to resolve agent names/badges; defaults to `[]`.
- `onDeleteSession` — invoked with the session id when the delete action is clicked.
- `onRenameSession` — invoked with `(sessionId, newTitle)` when an inline rename is submitted.
- `onViewDetails` — invoked with the full session when the title or details action is clicked (opens the details modal).
- `onOpenInChat` — optional callback; when provided it is used for the chat action, otherwise the component runs its internal agent-load + store-set + navigate flow.
- `isLoading` — when true, renders a spinner card instead of the table; defaults to `false`.
- `selectedIds` — controlled row-selection set; defaults to an empty `Set`.
- `onSelectionChange` — called with the next selection `Set` on row toggle, select-all, or clear.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react-router-dom` (`useNavigate`) | Hook | Navigates to `/agent-interaction` after opening a session in chat (fallback flow). |
| `useCognitiveHubStore` (`stores/cognitiveHubStore`) | Zustand store | `setActiveSession(...)` marks the session active before navigating to chat. |
| `AgentService` (`services/domain/AgentService`) | Service class | Fallback flow: `getAgents()` to resolve the session's agent and `selectAgent()` to set it as selected. |
| `sessionSyncService` (`services/sessionSyncService`, dynamic `import()`) | Service | Fallback flow: `getSession(id)` + `convertToFrontendSession(...)` to reload latest messages from backend. |
| `frontendLoggingService` (`services/frontendLoggingService`) | Service | Info/warning/error logging for open-in-chat and rename-related operations. |
| `ConversationSession` (`types/agentInteraction`) | Type | Session shape consumed by props and rendering. |
| `React.useState` | Hook | Local inline-rename state: `editingId`, `editingTitle`. |

## Usage Example

```tsx
// From frontend/src/pages/Sessions.tsx
<SessionTable
  sessions={filteredSessions}
  agents={filters.agents}
  onDeleteSession={handleDeleteSession}
  onRenameSession={handleRenameSession}
  onViewDetails={handleViewDetails}
  isLoading={isLoading}
  selectedIds={selectedIds}
  onSelectionChange={setSelectedIds}
/>
```

## State Used

Local state (inside the component):

- `editingId: string | null` — id of the session whose title is being edited inline; drives the rename input rendering.
- `editingTitle: string` — draft value of the inline rename input; submitted via Enter or the check button, cancelled via Escape or the X button.

Controlled props (owned by the sessions page):

- `selectedIds: Set<string>` — lives in `Sessions.tsx` (`useState`); toggled here via `toggleSelect`/`toggleSelectAll` and lifted back through `onSelectionChange`. The page uses `selectedIds.size > 1` to show the bulk-delete button and passes the ids to `handleBulkDelete`.
- `sessions` — derived from the Zustand `useCognitiveHubStore` `sessions` slice, filtered/sorted by the page into `filteredSessions`.
- `isLoading` — page-level flag set around `sessionsService.loadFromBackend(...)` calls.

## Related Components

- `frontend/src/pages/Sessions.tsx` — parent page; owns session data, filters, selection state, and all mutation callbacks.
- `frontend/src/components/sessions/SessionFilters.tsx` — sibling filter bar whose state (`filters.agents`, etc.) feeds the table's `agents` prop.
- `frontend/src/components/sessions/SessionDetailsModal.tsx` — modal opened via `onViewDetails` (`selectedSession` state in the page).
- `frontend/src/components/ui/PageContainer.tsx` / `frontend/src/components/ui/PageBanner.tsx` — layout chrome the table renders inside on the Sessions page.
