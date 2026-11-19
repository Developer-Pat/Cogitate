---
title: SessionDetailsModal
type: atlas-component
path: frontend/src/components/sessions/SessionDetailsModal.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---

# SessionDetailsModal

**Path**: `frontend/src/components/sessions/SessionDetailsModal.tsx`
**Last Updated**: 2026-08-01

## Purpose

Modal dialog that displays the details of a single conversation session: session title, associated agent (avatar + name), active-session status, models used, a metadata grid (message count, total tokens, average response time, last activity), created/last-updated timestamps, and a scrollable preview of all messages (role badges, model/provider badges, relative timestamps, per-message token counts, and 150-character content previews).

It is a controlled component — it renders nothing unless `isOpen` is `true` and `session` is non-null. The primary action, "Open in Chat", reloads the session from the backend, sets it as the active session in the Cognitive Hub store, and navigates to the `/agent-interaction` chat page.

## Props Interface

```typescript
interface AgentInfo {
  id: string | number;
  name: string;
  profile_image_url?: string;
}

interface SessionDetailsModalProps {
  session: ConversationSession | null;
  agents?: AgentInfo[];
  isOpen: boolean;
  onClose: () => void;
}
```

`ConversationSession` and `ConversationMessage` are imported from `../../types/agentInteraction` (`id`, `title`, `agentId`, `messages?`, `createdAt`, `updatedAt`, `isActive`, `status?`, `cognitiveConfig?`; messages carry `role`, `content`, `timestamp`, and `metadata` with `tokenCount`, `totalTimeMs`, `model`, `provider`, etc.).

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react-router-dom` — `useNavigate` | hook | Navigates to `/agent-interaction` after "Open in Chat" |
| `../../stores/cognitiveHubStore` — `useCognitiveHubStore` | store | `getState().setActiveSession(...)` sets the reloaded session as the active session |
| `../../services/domain/AgentService` | service class | `getAgents()` resolves agent names/avatars for the session's `agentId`; `selectAgent(id)` selects the session's agent before opening chat |
| `../../services/sessionSyncService` — `sessionSyncService` | service (dynamic import) | `getSession(session.id)` reloads the latest session from the backend; `convertToFrontendSession(...)` maps it to the frontend shape |
| `../../services/frontendLoggingService` | service | Logs `info`/`warning`/`error` events for opening a session, backend reload fallback, and failures |
| `../../types/agentInteraction` — `ConversationSession`, `ConversationMessage` | types | Session and message data shapes |

## Usage Example

```tsx
import { SessionDetailsModal } from '../components/sessions/SessionDetailsModal';
import { useCognitiveHubStore } from '../stores/cognitiveHubStore';

const { sessions, agents } = useCognitiveHubStore();
const [selectedSession, setSelectedSession] = useState<ConversationSession | null>(null);
const [isModalOpen, setIsModalOpen] = useState(false);

<SessionDetailsModal
  session={selectedSession}
  agents={agents}
  isOpen={isModalOpen}
  onClose={() => setIsModalOpen(false)}
/>
```

## State Used

- **No local `useState`** — the modal is fully controlled via the `isOpen` and `session` props (returns `null` early when closed or sessionless).
- **External store state**: `useCognitiveHubStore.getState().setActiveSession(...)` (called imperatively, not via hook subscription) to set the active session when opening a session in chat.
- Derived values computed per render from `session.messages`: `getUniqueModels()`, `getTotalTokens()`, `getAverageResponseTime()`, `getMessagePreview()`, `getRoleBadgeClass()`, plus `formatDateTime()` / `formatRelativeTime()` helpers.

## Related Components

- `frontend/src/pages/Sessions.tsx` — the sessions list page that renders this modal (passes `selectedSession`, `filters.agents`, `isModalOpen`, `handleCloseModal`).
- `frontend/src/components/features/monitoring/SessionManager.tsx` — monitoring panel with its own local (separate) `SessionDetailsModal` definition used for its session table.
- `frontend/src/stores/cognitiveHubStore` — store whose `setActiveSession` action the modal invokes.
- `frontend/src/components/features/monitoring/SessionManager.tsx` / `frontend/src/pages/Sessions.tsx` — entry points into the session-management UI.
