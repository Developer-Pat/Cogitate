---
title: Messaging
type: atlas-api
path: wiki/atlas/api/routers/messaging.md
category: api-atlas
order: 5
confidence: high
updated: 2026-08-24
tags: [type/api, domain/messaging, status/active]
---

# Messaging — API

> Routers: `backend/app/api/v1/messaging/router.py` — the SSE
> bridge. Service: `backend/app/domain/messaging/services.py` —
> the event bus.
> Status: **ACTIVE** — the application's pub-sub transport (the
> generic event backbone; the Boss-Batching pipeline is ONE
> consumer, not the center).

## Purpose

The application event bus + its outward stream. Publishers emit
events (workflow lifecycle, batch progress, the Boss's proposals,
agent updates, notifications); subscribers receive them. The
frontend subscribes via SSE; agents publish via the `publish`
tool. The toaster is a consumer of `notify:*` — untouched itself.

## Endpoints

### The SSE bridge (`messaging/router.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/messaging/stream?topics=...` | The event stream — SSE over sse-starlette's EventSourceResponse; comma-separated topic patterns (`workflow:*,batch:*`); replays the ring buffer on connect (late subscribers catch up); heartbeats every 15s (injectable via `?heartbeat=`); cleanup on disconnect |

## The service (`domain/messaging/services.py`)

The `EventBusService` — an in-process pub-sub on blinker:

- `publish(topic, payload)` — sync fan-out; NEVER raises
  (handler exceptions isolated).
- `subscribe(topic_pattern, handler)` — wildcard patterns
  (`workflow:*` matches everything under `workflow:`).
- `recent(topic_pattern, limit)` — the ring-buffer replay (the
  last 200 events, bounded).
- THE TOPIC CONVENTION (settled 2026-08-24): all-colon
  `namespace:sub:event` — `workflow:<id>:started`, `batch:<id>:done`,
  `the_boss:proposed`, `agent:<id>:updated`, `notify:<kind>`,
  `system:<kind>`. A `namespace:*` wildcard ALWAYS matches
  everything under it (the early `:`/`.` mix broke this).

## The publishers (who emits)

- The workflow engine — `workflow:<id>:started/:completed/:failed`
  (execute + run_workflow_async).
- The Boss-Batching executor — `batch:<id>:done` (rows +
  total_batches — the estimate data).
- The Boss node — `the_boss:proposed` (the consolidation report).
- The agent-update router — `agent:<id>:updated` (the cross-window
  sync: every open tab refreshes).
- The `publish` tool — any agent announces (`notify:<kind>`,
  `agent:<id>:published`, ...) through the standard tool surface.

## The consumers (who subscribes)

- The frontend `eventBus` (the MVVM EventAggregator) + the
  `messagingFeed` (fetch-based SSE reader — EventSource can't
  dispatch dynamic topic names).
- `useNotifyBridge` — the toaster opt-in (`notify:*`).
- `useAgentSync` — the cross-window refresh (`agent:*` — invalidates
  the React Query agent keys).
- `useRunEstimator` — the run-time estimate (`batch:*`).

## The chat stream (the migration, 2026-08-24)

The chat's cognitive trace rides the bus: the pipeline publishes
`chat:<session>:<kind>` events (context_built, executor_started/
completed, memory_updated, response_formatted, trace_complete) —
the payload enriched with the `kind` discriminator (the bus
handler can't see the topic). The requesting client's SSE stream
is UNCHANGED (the direct yields kept). The frontend's UI pump
(`useTracePanel`) subscribes `chat:*` and drives the cognitive
indicator — re-rendering only on trace events (targeted
rendering). The raw token chunks stay on the direct stream (they
never rode the bus — high-frequency, transport-specific). The
migration: `local/chat-stream-migration/` (proposal, design,
roadmap).

## The design decisions (the proposal)

- live-only + a bounded ring (200 events) for late subscribers —
  the history tables own full durability.
- SSE, not WebSocket — one-way events, auto-reconnect.
- No broker — the broker-swappable interface is PARKED (an
  advanced future feature; the seam exists).
- The toaster stays untouched (a consumer, opt-in).

See [[atlas/api/cross-cutting|Cross-cutting]] (the SSE section) +
the proposal `local/proposals/messaging-service.md` + the roadmap
`local/roadmaps/messaging-service-roadmap.md`.
