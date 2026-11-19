---
title: SessionManager
type: atlas-component
path: frontend/src/components/features/agentInteraction/SessionManager.tsx
confidence: high
updated: 2026-09-17
tags: [type/component, domain/atlas-ui]
---

# SessionManager

**Path**: `frontend/src/components/features/agentInteraction/SessionManager.tsx`
**Last Updated**: 2026-09-17

## Purpose

Right-sidebar session management panel for the Agent Interaction chat page (`pages/AgentInteraction.tsx`). It lists, filters, sorts, selects, renames, deletes (single and bulk), exports, and creates conversation sessions, and toggles between a **Sessions** tab (session list) and a **History** tab (the user's own past prompts — see [[atlas/ui/components/features/agentInteraction/PromptHistoryList]]).

**Two tabs: Sessions and History.** Agent and theme settings live on the Agent Profiles and Settings pages; there is no settings surface in this panel. `QuickSettingsPanel` and the `useNavigate` import are both orphaned — kept only as `DEPRECATED(2026-09-15)` comments for a later grep.

The component is deliberately **presentational/controlled** for session data: it owns no session data of its own. All session data (`sessions`, `currentSession`) and all session operations (select/delete/rename/generate-title/import/new/reload/close/clear-memory) arrive as props from the parent page, which sources them from the `useAgentInteraction` hook. The only API calls made directly by this component are **bulk delete** (`POST /api/v1/sessions/bulk-delete`) and **export** (`POST /api/v1/chat/sessions/:id/export`) via `apiClient`; it does **not** import `sessionSyncService` — that service is used by the parent hook (`useAgentInteraction`), not by this component.

**The History tab is the exception to "no data of its own"**: it reads [[atlas/ui/stores/promptHistoryStore]] directly, because the prompt history is its own record rather than a view of a session.

## The header toolbar, in the user's order

The row is `justify-end`, so the LAST element emitted is the rightmost on screen.

| # | Control | Tooltip |
|---|---|---|
| — | New | `Create new session` |
| — | ⋮ Session actions | `Session actions` |
| 1 | **Deselect** | `Deselect — work with no session selected` |
| 2 | Refresh | `Reload all sessions with messages from database` |
| 3 | Expand / Collapse | `Expand` / `Collapse` |
| 4 | Trash (bulk delete mode) | `Bulk delete mode` |
| 5 | Delete confirmation ON/OFF | `Delete confirmation ON` / `OFF` |

`New` stays first (it is the create action, and it is labelled rather than an icon) and the ⋮ session-actions menu groups with it — it is session-level rather than view-level, and moving it forward keeps the five view controls contiguous with Delete-confirm holding the far right.

**Deselect lives in this header**, and **tracks the selection**: `disabled={!currentSession || isStreaming}`. Deselect with nothing selected is a no-op, so the control is disabled rather than offered. `isStreaming` is passed in from the page — this component holds no streaming state of its own. The page passes the same `handleDeselectSession` that ChatInterface receives.

### The bulk-delete bar

Shown while `isBulkDeleteMode` is on. It offers **All** and **None** for the selection, and
**Delete N** to remove the N selected — the count rides on the button, which stays disabled
until something is ticked.

There is deliberately **no "N of M selected" readout**: the Delete button already carries the
count that matters, so a third number in the row would be noise. (The `N of M sessions` line
under the filters is a **different** readout — filter results, not the selection.)

The tips here use `PortalTooltip` rather than a DaisyUI `data-tip`, and the wrapper does two
jobs: it escapes the panel's clipping ancestors for the long Delete tip, and it gives the
**disabled** Delete button a hover target — a disabled button fires no mouse events of its
own.

## Props Interface

```typescript
interface SessionManagerProps {
  sessions: ConversationSession[]
  currentSession: ConversationSession | null
  onSessionSelect: (session: ConversationSession) => Promise<void>
  onSessionDelete: (sessionId: string) => void
  onSessionRename?: (sessionId: string, newTitle: string) => void
  onGenerateTitle?: (sessionId: string) => Promise<void>
  onSessionImport?: (session: ConversationSession) => void
  onNewSession?: () => void
  onReloadSessions?: () => void
  isReloadingSessions?: boolean
  onCloseSession?: () => void
  onClearMemory?: () => void
  /** The same handler ChatInterface receives. */
  onDeselectSession?: () => void
  /** The guard the moved button carried in ChatInterface. */
  isStreaming?: boolean
  /** The History tab's "copy into the message box". The page owns the hand-off,
      because the composer's text state is local to ChatInterface and this panel is
      its SIBLING. */
  onUsePrompt?: (text: string) => void
}
```

Notes on prop usage:

- `onNewSession` is gated on an agent being selected (`useCognitiveHubStore.activeAgent`); otherwise a warning notification is shown.
- `onReloadSessions` is awaited after a successful bulk delete so the list refreshes before the success toast settles.
- `onSessionImport` is destructured as `_onSessionImport` and **not used** — the Import menu item currently only closes the actions dropdown (no-op stub).
- `onClearMemory` is destructured but **not referenced in the render** (vestigial prop).
- `onCloseSession` powers the "Close Session" item in the actions dropdown.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `useState`, `useMemo` | React hooks | Local UI state (search/filters/sort/bulk-selection/tabs/expanded) and derived `filteredSessions`, `uniqueAgents`, `canGenerateTitle` |
| ~~`useNavigate`~~ (react-router-dom) | Hook | Unused — kept as a `DEPRECATED` comment. |
| `useNotificationStore` (`../../../stores/notificationStore`) | Zustand store | `addNotification` for success/error/warning toasts (bulk delete, export, title generation, new-session gating) |
| `useCognitiveHubStore` (`../../../stores/cognitiveHubStore`) | Zustand store | `activeAgent` — single source of truth for the selected agent; gates "New" session creation and provides the agent name/model for settings |
| `apiClient` (`../../../services/apiClient`) | Service | Direct HTTP calls: `POST /api/v1/sessions/bulk-delete` and `POST /api/v1/chat/sessions/:id/export` |
| `frontendLoggingService` (`../../../services/frontendLoggingService`) | Service | Structured debug/info/warning/error logging under `SessionManager:*` channels (e.g. `SessionManager:bulkDelete`, `SessionManager:selection`) |
| `IdService` (`../../../services/domain/IdService`) | Service | `IdService.isTempId()` / `IdService.toBackend()` to filter out temp frontend IDs and map them to backend numeric IDs before bulk delete |
| `ConversationSession` (`../../../types/agentInteraction`) | Type | Session shape (`id`, `title`, `agentId`, `messages?`, `createdAt`, `updatedAt`, `isActive`, `status?`, `cognitiveConfig?`) |
| `SessionList` (`./SessionList`) | Child component | Renders the session rows, delete confirmation, inline rename, and bulk-selection checkboxes |
| ~~`QuickSettingsPanel`~~ (`./QuickSettingsPanel`) | Child component | Orphaned — no mount remains. Kept, commented, as a `DEPRECATED` marker. |
| `BadgeButton` (`../../ui/BadgeButton`) | Child component | "New" session button in the toolbar |
| `PortalTooltip` (`../../ui/PortalTooltip`) | Child component | Carries the bulk-delete bar's button tips. A DaisyUI `data-tip` would be clipped here: the Delete tip is long and sits against the panel's right edge, where an absolutely-positioned `::before` runs past the boundary |

**Wiring note (sessionSyncService)**: `services/sessionSyncService.ts` (`basePath = '/api/v1/sessions'`) is **not** imported here. It backs the parent hook `hooks/useAgentInteraction.ts` (createSession, updateSessionTitle, deleteMessage, syncMessage, reload with messages), whose returned handlers (`handleSessionSelect`, `handleSessionDelete`, `handleSessionRename`, `createNewSession`, `handleReloadSessions`, …) are passed into this component as props by `pages/AgentInteraction.tsx`.

### Direct API calls

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/sessions/bulk-delete` | `POST` | Body is a JSON array of backend (numeric) session IDs; response `{ total_deleted: number; deleted_ids: number[] }`; triggers `onReloadSessions()` on success |
| `/api/v1/chat/sessions/${currentSession.id}/export` | `POST` | Exports the current session; response `{ filename: string; message: string }`; success toast shows the filename |

## Usage Example

```tsx
// pages/AgentInteraction.tsx — collapsible right sidebar
<div className={sidebarOpen ? 'h-full flex flex-col' : 'hidden'}>
  <div className="flex-1 overflow-y-auto">
    <SessionManager
      sessions={sessions}
      currentSession={currentSession}
      onSessionSelect={handleSessionSelect}
      onSessionDelete={handleSessionDelete}
      onSessionRename={handleSessionRename}
      onGenerateTitle={handleGenerateTitle}
      onSessionImport={handleImportSession}
      onNewSession={createNewSession}
      onReloadSessions={handleReloadSessions}
      isReloadingSessions={isReloadingSessions}
      onCloseSession={handleCloseSession}
      onClearMemory={handleClearMessages}
    />
  </div>
</div>
```

The handlers come from `useAgentInteraction()` in the same page, e.g.:

```tsx
const {
  agents, sessions, state,
  handleSessionSelect, handleSessionDelete, handleSessionRename,
  handleGenerateTitle, handleImportSession, createNewSession,
  handleReloadSessions, handleCloseSession, handleClearMessages,
} = useAgentInteraction()
```

## State Used

**Local state** (all `useState`):

- `searchQuery: string` — filters sessions by title substring
- `filterAgent: string | null` — filters by `session.agentId`
- `sortBy: 'recent' | 'oldest' | 'alphabetical'` — default `'recent'` (by `updatedAt`; `oldest` by `createdAt`; `alphabetical` via `localeCompare` on title)
- `isExpanded: boolean` — default `false` (filters area collapsed by default)
- `requireDeleteConfirm: boolean` — default `false` (delete confirmation OFF by default)
- `selectedSessions: Set<string>` — bulk-delete selection
- `isBulkDeleteMode: boolean` — toggles the bulk-delete action bar and checkbox mode in `SessionList`
- `activeTab: 'sessions' | 'history'` — default `'sessions'` (the Settings tab is gone; History took the slot)
- `showActionsMenu: boolean` — actions dropdown open state

**Derived (useMemo)**: `uniqueAgents` (distinct `agentId`s across sessions), `filteredSessions` (search + agent filter + sort).

**Derived (inline)**: `canGenerateTitle` — true only when the current session has ≥ 2 messages **and** at least one `assistant` message; gates the "Rename (AI)" menu item.

**Stores read**: `useCognitiveHubStore(state => state.activeAgent)`; `useNotificationStore(state => state.addNotification)`.

**Props (external state)**: `sessions`, `currentSession`, `isReloadingSessions` (drives the reload spinner).

## Related Components

- Parent page: `frontend/src/pages/AgentInteraction.tsx`
- Backing hook (session ops + `sessionSyncService` usage): `frontend/src/hooks/useAgentInteraction.ts`
- Children: `frontend/src/components/features/agentInteraction/SessionList.tsx`, `frontend/src/components/features/agentInteraction/SessionListItem.tsx` (grandchild), `frontend/src/components/features/agentInteraction/QuickSettingsPanel.tsx`, `frontend/src/components/ui/BadgeButton.tsx`
- Services: `frontend/src/services/apiClient.ts`, `frontend/src/services/sessionSyncService.ts`, `frontend/src/services/domain/IdService.ts`, `frontend/src/services/frontendLoggingService.ts`
- Stores: `frontend/src/stores/cognitiveHubStore.ts`, `frontend/src/stores/notificationStore.ts`

> Note: a different, unrelated `SessionManager` exists at `frontend/src/components/features/monitoring/SessionManager.tsx` (monitoring feature) — this doc covers only the `features/agentInteraction` one.
