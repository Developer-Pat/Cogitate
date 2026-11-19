---
title: Agent Interaction
type: atlas-page
path: frontend/src/pages/AgentInteraction.tsx
confidence: high
updated: 2026-09-19
tags: [type/page, domain/atlas-ui]
---
# Agent Interaction

**Component**: `frontend/src/pages/AgentInteraction.tsx`
**Route**: `/agent-interaction` (registered as `Chat` in `frontend/src/config/routes.ts`, title "Agent Chat", `requiresAuth: true`)
**Last Updated**: 2026-09-17

## Purpose

The Agent Interaction page is the main chat interface for talking to AI agents. It wires together agent selection, conversation session management, and token-by-token streaming responses (SSE) into a single orchestrated UI. The page itself is a thin composition shell: virtually all behavior lives in the `useAgentInteraction` orchestrator hook, the `agentInteraction` feature components, and the `StreamingService`.

## Key Features

- **Streaming chat (SSE)** — messages are streamed via `POST /api/v1/chat/stream`; chunks are accumulated in `StreamingService`, throttled to 100ms UI updates, and can be aborted (Stop button → `AbortController`).
- **Agent + collective selection** — `AgentSelector` dropdown for the active agent and `AgentListSelector` (collectives = collections) that filters the agent list; both selections persist to `sessionStorage` (`agent-selection-store`, `team-selection-store` — the per-tab doctrine, 2026-09-10).
- **Session management sidebar** — list/search/filter/sort sessions, rename, delete, bulk-delete, export, reload, clear memory, create new session (lazy temp-session pattern with backend commit after streaming).
- **Macro keyboard** — F1–F5 topic macro buttons, M1–M5 topic/mapping selectors, and the A1–A5 ACTION-KEY bank (data-driven flyouts fed by the A-source meta-topic — not hardcoded). Each bank has an icon-only selector beside its keys (F after M5, A beside the A keys — select = set = persist, surface-scoped); on the Exa page the ACP trio rides the keyboard's afterAKeys slot after the A selector.
- **Meta-topic handling** — `TopicFlyoutButton` (via `MacroKeyboard`) + `useSystemMacrosStore` drive the macro keyboard; meta-topics load from `/api/v1/macros/meta-topics` and macro sets from `/api/v1/macros?all=true`. FOUR selections persist independently (agent/exa × F-topic/A-source — `cogitate_selected_meta_topic` / `cogitate_akeys_meta_topic`, `:exa`-suffixed for the Exa surface). Auto-sync via `useMacroSync` (the backend's `macro:*`/`meta-topic:*` publishes) — no manual reload button.
- **Cognitive pipeline instrumentation** — SSE `cognitive_*` events are parsed into a `CognitiveState` (context built / executor stages / memory updated / trace complete); shown as a `CognitiveIndicator` on the last message and a full dev overlay (`CognitiveTraceDebugOverlay`, Ctrl+Shift+D).
- **Attachments** — file picker with validation (10MB, allow-list of extensions), preview row, and upload via `POST /api/v1/chat/{sessionId}/attachments`; attachment IDs are passed into the stream request.
- (The `ToolPicker` modal was REMOVED — no tool-gating modal exists on this page anymore.)
- **Auto title generation** — after the first assistant message, a background job calls `POST /api/v1/chat/generate-title` (respects `enableAutoTitle` / `titleModelPreference` settings).
- **Rich rendering** — `ResponseStream` renders markdown (GFM, syntax highlighting, mermaid diagrams), tool-result bubbles, message metrics (time/tokens/tok/s/model), and copy actions.
- **Provider health gate** — `handleSendMessage` refuses to send if the active provider is marked `down` in the hub store.

## Components Used

| Component | Path | Purpose |
|---|---|---|
| `ErrorBoundary` | `frontend/src/components/ErrorBoundary.tsx` | Wraps the whole page to catch render errors |
| `HelpButton` | `frontend/src/components/help/HelpButton.tsx` | "Help" button; opens `HelpModal` which fetches `/api/v1/wiki/help?context=chat` |
| `AgentSelector` | `frontend/src/components/features/agentInteraction/AgentSelector.tsx` | Dropdown to pick the active agent — avatars, a **provider badge** (tip: provider + the model it is configured with) and an **availability badge** (tip: available / unavailable in words) |
| `AgentListSelector` | `frontend/src/components/features/agentInteraction/AgentListSelector.tsx` | Team/agent-list dropdown backed by `collectionsService` (auto-selects "Default" team) |
| `ResponseStream` | `frontend/src/components/features/agentInteraction/ResponseStream.tsx` | Renders message bubbles, markdown/mermaid, tool results, cognitive indicator |
| `ChatInterface` | `frontend/src/components/features/agentInteraction/ChatInterface.tsx` | Input box: the macro keyboard row + the send column (Send; under it Collapse long responses + Layout controls); attachments; character count; clear/stop |
| `SessionManager` | `frontend/src/components/features/agentInteraction/SessionManager.tsx` | Right sidebar: session list CRUD, bulk delete, export, quick settings |
| `TopicFlyoutButton` | `frontend/src/components/features/agentInteraction/TopicFlyoutButton.tsx` | Bank-aware meta-topic selector flyout; used INSIDE `MacroKeyboard` (two icon-only instances: bank='f' after M5, bank='a' beside the A keys) |
| `CognitiveTraceDebugOverlay` | `frontend/src/components/features/agentInteraction/CognitiveTraceDebugOverlay.tsx` | Dev-only overlay showing raw cognitive pipeline events (Ctrl+Shift+D) |
| Transitive | `MacroKeyboard`, `TopicFlyoutButton` (via MacroKeyboard), `AttachmentPreview`, `LoadingIndicator`, `CognitiveIndicator`, `SessionList`, `SessionListItem`, `QuickSettingsPanel`, `AvatarWithFallback`, `MessageMetadata` | `frontend/src/components/features/agentInteraction/` | Sub-components used by the above |

## Hooks Used

| Hook | Path | Purpose |
|---|---|---|
| `usePageTitle` | `frontend/src/hooks/usePageTitle.ts` | Sets document title to "Chat" with description |
| `useAgentInteraction` | `frontend/src/hooks/useAgentInteraction.ts` | **Orchestrator** — composes all chat behavior and exposes the handlers/state the page renders |
| `useAgentSelection` (via orchestrator) | `frontend/src/hooks/useAgentSelection.ts` | Loads agents (`GET /api/v1/agents`), restores/auto-selects agent, refreshes selection from backend |
| `useSessionManagement` (via orchestrator) | `frontend/src/hooks/useSessionManagement.ts` | Loads sessions on mount, CRUD, lazy message loading, temp-session replace |
| `useChatStreaming` (via orchestrator) | `frontend/src/hooks/useChatStreaming.ts` | Thin React wrapper around `StreamingService`; exposes `startStream`/`stopStream`, syncs `cognitiveState` |
| `useChatPersistence` (via orchestrator) | `frontend/src/hooks/useChatPersistence.ts` | Saves/restores selected agent + session IDs to `sessionStorage` (`utils/chatStateStorage.ts`) |
| Store hooks (transitive) | `useSystemMacrosStore`, `useCognitiveHubStore`, `useNotificationStore`, `useSettingsStore`, `useUIStore` | `frontend/src/stores/` | Zustand stores consumed by components (see State Management) |

> Note: `useChatMacros.ts` is DELETED; `useModeMacros.ts` still exists in `hooks/` but is legacy/unimported — macro behavior lives in `useSystemMacrosStore` + `MacroKeyboard`.

## Data Flow

1. **Mount**: `useAgentSelection` fetches agents (via `AgentService` → `ProfileService`, `GET /api/v1/agents`) into the Cognitive Hub store and restores the persisted selection; `useSessionManagement` loads session titles (`GET /api/v1/sessions?include_messages=false`, lazy message loading); `ChatInterface` loads meta-topics and macro sets.
2. **Team/agent selection**: the selected team ID filters the agent dropdown via `collectionsService.getCollectionItems(id)` (`GET /api/v1/collections/{id}/items`, keeping `entity_type === 'agent'` ids). Both selections are persisted to `localStorage` and restored on next visit; agent selection is also re-validated against the backend (`GET /api/v1/agents/{id}`).
3. **Send message** (`handleSendMessage`): provider health check from hub store → optional attachment uploads (`POST /api/v1/chat/{sessionId}/attachments`) → `StreamingService.startStream` → `chatService.createStreamingChatCompletion` → `POST /api/v1/chat/stream` with `{agent_id, message, session_id, stream: true, attachment_ids}`.
4. **Streaming**: `StreamingService` creates optimistic user + assistant messages in the store (via `onAddMessage`), parses the SSE body line-by-line: content chunks (`choices[0].delta.content`) accumulate with throttled `onUpdateMessage` updates; a backend `session_id` event replaces the temp session id in the store; `cognitive_*` events update `CognitiveState`; `[DONE]` / `done+metadata` finalize. Truncation (`finish_reason: length`) is flagged in metadata and surfaced as a notification.
5. **Completion** (`onStreamComplete`): final assistant message replaces the streaming placeholder → if the session was a temp id (`session-{ts}-{rand}`), `commitPendingSession` creates it on the backend (`POST /api/v1/sessions`) and replaces it in the store → auto-title job is queued (`POST /api/v1/chat/generate-title`) once ≥2 messages exist.
6. **Session switch**: `switchSession` fetches full history (`GET /api/v1/sessions/{id}`), preserves locally-changed titles, and upserts into the hub store; `currentSessionService.setContext` keeps a compatibility context object in sync.
7. **Persistence**: the Cognitive Hub store (Zustand `persist`) writes agents/sessions/active context to `localStorage` under `cogitate-hub-storage`; chat agent/session ids go to `sessionStorage`; team/agent selections use `sessionStorage`; meta-topic selections use their own `localStorage` keys.

## State Management

| Store | Path | Role |
|---|---|---|
| `useCognitiveHubStore` | `frontend/src/stores/cognitiveHubStore.ts` | **Central source of truth** — composed of `agentStore` (agents, activeAgent, sessions, activeSession), `streamStore`, `providerHealthStore`, `syncQueueStore`; persisted to `localStorage` (`cogitate-hub-storage`) with a scoped-storage wrapper |
| `useSystemMacrosStore` | `frontend/src/stores/macroSetsStore.ts` | Meta-topics, macro sets, the F selection + the A-source + the active surface (`selectedMetaTopicId`, `aKeysMetaTopicId`, `surface` — persisted surface-scoped: `cogitate_selected_meta_topic` / `cogitate_akeys_meta_topic` + `:exa` suffixes) |
| `useNotificationStore` | `frontend/src/stores/notificationStore.ts` | Toasts (title generation, truncation, copy, delete, bulk ops) |
| `useSettingsStore` | `frontend/src/stores/settingsStore.ts` | `showPipelineIndicators`, `enableAutoTitle`, `titleModelPreference`, `titleCustomModel` |
| `useUIStore` | `frontend/src/stores/uiStore.ts` | Sidebar toggle used by `ChatInterface` |

`localStorage` keys: `cogitate-hub-storage`, `cogitate_selected_meta_topic` (+ `:exa`), `cogitate_akeys_meta_topic` (+ `:exa`), `cogitate_default_meta_topic`. `sessionStorage`: `agent-selection-store`, `team-selection-store`, `agent-store` (AgentService's selection key), plus chat state via `utils/chatStateStorage.ts`.

## API Endpoints Called

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/chat/stream` | SSE streaming chat completion — **the core conduit**; body carries `agent_id` (profile/conduit routing to the target agent), `message`, `session_id`, `stream: true`, `attachment_ids` (via `chatService`) |
| POST | `/api/v1/chat/completions` | Non-streaming completion (defined in `chatService`; not used by this page) |
| GET | `/api/v1/agents` | List agents (via `ProfileService`, base path `/api/v1/agents`) |
| GET | `/api/v1/agents/{id}` | Validate/refresh a single agent (staleness check before streaming, selection refresh) |
| GET | `/api/v1/sessions?include_messages=false` | List sessions, titles only (lazy loading) |
| POST | `/api/v1/sessions` | Create backend session (temp-session commit, session creation) |
| GET | `/api/v1/sessions/{id}` | Fetch one session with full messages (on switch/select) |
| PUT | `/api/v1/sessions/{id}` | Rename/update session title |
| DELETE | `/api/v1/sessions/{id}` | Delete a session |
| POST | `/api/v1/sessions/bulk-delete` | Bulk-delete selected sessions (`SessionManager`) |
| POST | `/api/v1/chat/sessions/{id}/export` | Export conversation to file (`SessionManager`) |
| POST | `/api/v1/chat/generate-title` | Background LLM title generation (`TitleService`) |
| POST | `/api/v1/chat/{sessionId}/attachments` | Upload file attachment (10MB limit, extension allow-list) |
| GET | `/api/v1/collections` | List collectives (`AgentListSelector`) |
| GET | `/api/v1/collections/{id}/items` | Get collection items to filter agents by team |
| GET | `/api/v1/macros/meta-topics` | Load meta-topics for macro keyboard (`macroSetsStore`) |
| GET | `/api/v1/macros?all=true` | Load all macro sets (`macroSetsStore`) |
| GET | `/api/v1/wiki/help?context=chat` | Help modal content for this page (`HelpButton`/`HelpModal`) |

All calls go through `apiClient` (`frontend/src/services/apiClient.ts`, base `VITE_API_URL || http://localhost:8000`, Bearer token from `auth_token`, 3 retries).

## The header's navigation buttons

- The **Ask-Exa box** (the right-most control) — opens a flyout that
  takes a prompt and answers it, or takes you somewhere: the `nav` /
  `list` / `search` / `info` / `dev` / `atlas` commands, a streaming Exa
  answer,
  and the destinations you use most in a clickable list. The old
  open-the-Exa-page jump lives inside it as **Full page**.
  See [[atlas/ui/components/features/agentInteraction/ExaPromptFlyout|ExaPromptFlyout]]
  and [[dev-notes/frontend/command-box|The Command Box]].
- The **message-button** (the bell) — opens the Message Center, with the unread count on
  a badge **and in its tooltip** (`"N unread — go to message center"`). The count is
  `selectUnreadCount` from [[atlas/ui/stores/messageStore]]. The tooltip carries the
  number as well because the badge is `badge-xs` at `text-[10px]` and a single digit is
  easy to misread at that size — but the badge stays, because a hover-only count cannot
  alert anyone.
- The **sidebar-toggle** — the app navigation panel.

## Related Pages

- [[Sessions]] — standalone session-management page over the same session data
- [[Macros]] — manage macro sets and meta-topics that drive the macro keyboard
- [[CognitivePipeline]] — configure the cognitive pipeline strategies surfaced by the `cognitive_*` SSE events
- [[AgentProfiles]] — agent profiles (the `Agent` objects selected here)
- [[TeamsManagement]] / [[TeamDetail]] — agent collectives; `AgentListSelector` lists collections used as collectives
- [[CollectionsManagement]] — collections (agent lists) used to filter the agent dropdown

## The prompt history

The page owns **two hand-offs** that exist only because the panels are siblings:

```tsx
const [pendingPrompt, setPendingPrompt] = useState<string | null>(null)
```

- **write side** — `onSendMessage` calls `addPrompt(msg, currentSession?.id ?? null)`
  into [[atlas/ui/stores/promptHistoryStore]] **before** the real send: it records what
  the user asked, not what succeeded.
- **read side** — `SessionManager` receives `onUsePrompt={setPendingPrompt}`, and
  `ChatInterface` receives `pendingPrompt` + `onPendingPromptConsumed`, appends it to the
  composer and clears it. **It never sends.**

The composer's text state is local to `ChatInterface`, so the page is the only place the
two can meet.
