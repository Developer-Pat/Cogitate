---
title: The Messaging System
type: atlas-devnote
path: wiki/dev-notes/messaging-system.md
category: dev-notes
order: 1
confidence: high
updated: 2026-09-05
tags: [type/dev-notes, domain/messaging]
---

# The Messaging System

> The application's pub-sub transport (2026-08-24) — a MAJOR
> structural addition. The backend bus + the SSE bridge + the
> frontend aggregator, with the Boss-Batching pipeline as ONE
> consumer. The API surface: [[atlas/api/routers/messaging|Messaging
> API]]. The proposal + roadmap: `local/proposals/messaging-service.md`,
> `local/roadmaps/messaging-service-roadmap.md`.

## The shape (back to front)

```
publish tool / engine / agents
        │  publish(topic, payload)
        ▼
backend: EventBusService (blinker) ──ring buffer (200)──▶ recent()
        │
        ▼  SSE (sse-starlette)
GET /api/v1/messaging/stream?topics=...
        │
        ▼  fetch-based reader (NOT EventSource)
frontend: messagingFeed ──▶ eventBus (the EventAggregator)
        │
        ├──▶ useNotifyBridge  (the toaster, notify:*)
        ├──▶ useAgentSync     (cross-window refresh, agent:*)
        └──▶ useRunEstimator  (run-time estimate, batch:*)
```

## The pieces

| Piece | File | Role |
|---|---|---|
| the bus | `backend/app/domain/messaging/services.py` | `EventBusService` — publish/subscribe/recent; blinker + a ring buffer |
| the bridge | `backend/app/api/v1/messaging/router.py` | the SSE stream (sse-starlette) |
| the publish tool | `backend/app/domain/tools/builtin/publish_handler.py` | agents publish through the standard tool surface |
| the aggregator | `frontend/src/services/eventBus.ts` | the MVVM EventAggregator (typed channels, cleanup, isolation) |
| the feed | `frontend/src/services/messagingFeed.ts` | the SSE → bus bridge (the topic-union registry) |
| the consumers | `frontend/src/hooks/useNotifyBridge.ts`, `useAgentSync.ts`, `useRunEstimator.ts` | the toaster, the cross-window sync, the estimate |

## The conventions (the hard-won rules)

1. **THE TOPIC CONVENTION — all-colon**: `namespace:sub:event`
   (`workflow:1:started`, `batch:1:done`, `the_boss:proposed`,
   `agent:5:updated`, `notify:task-complete`, `system:ready`).
   A `namespace:*` wildcard ALWAYS matches everything under it.
   The early drafts mixed `:` and `.` — that BROKE the wildcard
   contract (caught by the standalone bus check).
2. **The feed is a topic-union registry**: `addTopics`/`removeTopics`
   — multiple consumers (notify + agent sync) must NOT kill each
   other's stream. The feed reconnects with the UNION; closes when
   it empties. (The first draft was a single-topics singleton —
   the second consumer would have silently closed the first's
   stream.)
2b. **Each `open()` owns its controller**: the reader captures its
   OWN local `AbortController` per connection. A newer `open()`
   (page-mount churn) must never touch an older stream's
   controller — the module-level-controller check made intentional
   aborts look like stream errors (error-log storms + dead
   streams). An abort now = a silent close; a navigation /
   interruption = a quiet reconnect.
3. **Fetch, not EventSource**: the backend sends `event: <topic>`
   with DYNAMIC names (`workflow:<uuid>:started`). The browser
   only dispatches named events to listeners registered in
   advance — impossible for unknown UUIDs. The fetch reader parses
   every SSE line itself.
4. **Live-only + the ring**: events published before a subscriber
   exists are LOST unless within the last 200 (the ring replays on
   connect). A test publishing before subscribing fails by design
   — subscribe first (the real flow: the stream opens before the
   run fires). A RECONNECT replays the ring again — the consumers
   dedupe: the toaster window-dedupes, and the message store's
   **eventId-scoped dedupe** keeps ONE center record per bus event
   even when every tab's own SSE copy + the cross-tab
   re-broadcasts all arrive (no-eventId local errors still record
   EVERY firing).
5. **Handler isolation**: one bad subscriber can't break the
   fan-out (backend + frontend both isolate).
6. **The frontend hooks need their providers**: `useAgentSync`
   calls `useQueryClient()` — it MUST be rendered inside the
   QueryProvider (the AppSyncBridge pattern). Calling it in the
   App() body crashed with 'No QueryClient set'.
7. **The logging API**: `frontendLoggingService.error(source, msg,
   err)` — there is NO `.log()` method (the crash that followed).
8. **The thread boundary**: the bus publishes from worker THREADS;
   the SSE generator runs on the event loop — the bridge uses
   `loop.call_soon_threadsafe`, never touches the asyncio queue
   from a foreign thread.

## The lifecycle events (the pipeline as the first consumer)

```
workflow:<id>:started      the run begins
batch:<id>:done            each batch (rows + total_batches)
the_boss:proposed          the Boss's consolidation report
workflow:<id>:completed    the run ends
```

## The frontend wiring (where the hooks mount)

- `App.tsx` body: `useWorkflowToasts()` + `useNotifyBridge()`.
- `App.tsx` inside the providers: `<AppSyncBridge />` (renders
  `useAgentSync` — the QueryClient requirement).
- `useRunEstimator` is per-view (it takes a workflowId).
- **The channels are distinct**: the header/sidebar status dot is
  the WebSocket UI-state BRIDGE (its own WS connection) — NOT the
  notify channel. Notifications ride this SSE fetch-stream feed
  (`notify:*` topics). A green bridge dot never implies the notify
  feed is alive, and a dead feed never changes the dot. The
  message-center test suite (Full Test) is the ground truth for
  the notify chain.

## The cross-window sync (the user's use case)

Each tab/window opens its OWN SSE connection to the backend (the
single source of truth). Changing an agent config → the backend
publishes `agent:<id>:updated` → every tab hears it → the React
Query agent keys invalidate → every open page refetches. The app
stays in sync across windows.

## The chat-stream migration (2026-08-24)

The chat's cognitive trace rides the bus (`chat:<session>:<kind>`
with the kind discriminator); the content chunks stay on the
direct stream. The UI pump (`useTracePanel`) drives the cognitive
indicator — targeted rendering. The full analysis + the design +
the roadmap: `local/chat-stream-migration/`. The STREAM's own
cognitive parsing is now DORMANT (the tool-purge absorbs the
surgical removal).

## The observability (the strain is visible, 2026-08-24)

The bus logs its crashes AND its strain — a bog-down is visible the
moment it happens:

- **The SSE queue is bounded** (maxsize 500 per client). A slow
  consumer's memory can no longer grow unbounded; a FULL queue logs
  `⚠️ SSE queue FULL (N/500) — dropped event <topic> (slow
  consumer)` — the QueueFull surfaces in the loop-side wrapper (the
  `call_soon_threadsafe` boundary), never in the foreign thread.
- **The disconnect-race drops log a WARNING** (`⚠️ SSE drop
  (disconnect race)` — the silent `pass` is gone).
- **The ring evictions count + log** (`🔄 Ring eviction #N` — the
  deque's silent oldest-drop is now observable; the high-frequency
  `record=False` topics never churn it).

The tests: `tests/unit/messaging/test_messaging_observability.py`.

## The parked items

- The broker-swappable interface — PARKED (an advanced future
  feature; the seam exists — callers only see
  publish/subscribe/recent).
- The unified agent-chat stream migration — future.
- The orderly-shutdown event (`workflow:<id>:cancelling`) — queued.
