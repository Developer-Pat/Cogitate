---
title: Sessions
type: atlas-page
path: frontend/src/pages/Sessions.tsx
confidence: high
updated: 2026-07-31
tags: [type/page, domain/atlas-ui]
---
# Sessions

**Component**: `frontend/src/pages/Sessions.tsx`
**Route**: `/sessions`
**Last Updated**: 2026-07-31

## Purpose
Session management page - browse, search, filter, rename, view details of, and delete conversation sessions. Reads sessions from the Zustand store (single source of truth) and syncs with the backend.

## Key Features
- **Session table** with multi-select + bulk delete (with confirmation modal)
- **Filters**: search query, sort (date/title/message count), date range (all/today/week/month), agent filter, unnamed-only
- Per-session actions: rename (inline), delete (confirm dialog), view details (modal)
- Refresh button (reloads from backend)
- Context help button (context: sessions)

## Components Used
| Component | Path | Purpose |
|-----------|------|---------|
| PageBanner | `components/ui/PageBanner.tsx` | Page header with icon/tooltip |
| PageContainer | `components/ui/PageContainer.tsx` | Layout wrapper |
| SessionFilters | `components/sessions/SessionFilters.tsx` | Filter controls |
| SessionTable | `components/sessions/SessionTable.tsx` | Session list/table with selection |
| SessionDetailsModal | `components/sessions/SessionDetailsModal.tsx` | Per-session detail view |
| HelpButton | `components/help/HelpButton.tsx` | Help drawer (context: sessions) |

## Hooks Used
| Hook | Path | Purpose |
|------|------|---------|
| usePageTitle | `hooks/usePageTitle.ts` | Sets document title |

## Data Flow
- **Load**: `sessionsService.loadFromBackend(includeMessages)` -> `sessionSyncService` -> `GET /api/v1/sessions` (`?include_messages=true/false`) -> writes into `cognitiveHubStore.sessions` (Zustand). Titles-only load by default (lazy), full messages when details needed.
- **Filtering**: client-side in React state via `useEffect` on `[sessions, filters]` - date range, unnamed detection, agent match, search, sort.
- **Delete**: `DELETE /api/v1/sessions/{id}` (direct fetch in page) or bulk `POST /api/v1/sessions/bulk-delete` with JSON id array; reloads after.
- **Rename**: optimistic update via `useCognitiveHubStore.getState().renameSessionById()` then `PUT /api/v1/sessions/{id}` `{title}`.

## State Management
- `cognitiveHubStore` - sessions array is the single source of truth (read via selector, mutated via store actions)
- `notificationStore` - success/error toasts for delete/rename/bulk operations
- Local state: filters, selection set, modal visibility, loading

## API Endpoints Called
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/sessions?include_messages=` | List sessions (titles or with messages) |
| DELETE | `/api/v1/sessions/{id}` | Delete one session |
| PUT | `/api/v1/sessions/{id}` | Rename session |
| POST | `/api/v1/sessions/bulk-delete` | Delete multiple sessions |

## Related Pages
- AgentInteraction - chat page that creates/uses sessions
- Dashboard - shows recent activity stats