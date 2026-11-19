---
tags: [type/dev-notes]
---

# The Connection Budget — the visibility gate (fix A) and the owner-tab path (fix B)

Status: **fix A = the design on the books (2026-09-07); fix B = the
future arc**. This note exists so B can be built on A's structure
without re-deriving the problem.

## The problem (CONFIRMED empirically, 2026-09-07)

The browser caps ~6 simultaneous HTTP/1.1 connections per host.
Every Cogitate tab holds long-lived streams that never free their
slot, so a second tab + a heavy page's data fetches queue behind
them — the page spins forever with zero console errors. The user
hit this three times in one QA session (the Dashboard + the
Workflow Templates page, each hung with a second tab open; closing
the extra tab loaded the page immediately). The templates page
also hung on a cold "open in new tab" (a cold tab opens its
streams first, then queues its fetches) while the warm in-app
click-through sailed.

## The inventory — what holds connections, per tab

| Stream | Transport | Scope | Idle? |
|---|---|---|---|
| messagingFeed (`/api/v1/messaging/stream`) | fetch-SSE | every tab, app-lifetime (notify + agent/macro/session sync) | **idle** — held open waiting for events |
| uiStateBridge (`/api/v1/agent-chat/ws`) | WebSocket | every tab, app-lifetime (route/sidebar/theme/active-session sync) | **idle** — held open waiting for state |
| chat reply stream (StreamingService) | fetch-SSE | page-lifetime, only WHILE a reply streams | **active work** — never idle |
| Exa surfaces (chat/consult/schedule) | WebSocket | page-only | active while in use |
| trace viewer, log tail, live monitoring | WS/ES | page-only | active while in use |

Baseline: 2 idle streams per open tab. Two tabs = 4 + the active
tab's page fetches → the budget blows.

## Fix A — the visibility gate (the call, 2026-09-07)

**The rule:** the IDLE app-level streams (the messagingFeed + the
uiStateBridge) are held only while the tab is the document the user
is looking at. A hidden tab closes them; focusing the tab
reconnects them.

### The guarantee (the chat exemption — the user's question)

> If I'm talking to Bob and waiting on his streaming/thinking, then
> navigate away or change tabs and come back — does that affect the
> connection?

**No — under A, never.** The gate applies ONLY to idle, held-open
connections that a background tab cannot see or use (its toasts
and its UI-state sync are invisible anyway). **Any connection
actively doing work is exempt** — and Bob's reply stream is active
work. Concretely:

- **The chat reply stream is a fetch that exists only while a reply
  is streaming** (StreamingService, page-owned). The browser keeps
  in-flight fetches alive in background tabs; the gate never
  touches it. Bob's reply completes whether the user is watching
  or not. (Note: "navigate away" within the SPA unmounts the chat
  page and its per-mount stream controller — that is existing
  behavior, unchanged by A. The orphaned fetch streams into the
  void and releases the connection when done; the completed message
  persists server-side and reappears on return. A future cleanup
  could abort explicitly on unmount.)
- The gate must be implemented as "close the idle streams on
  visibilitychange-to-hidden; reopen on visible" — never as a
  blanket abort of every open connection.

### What a hidden tab loses (and why it's acceptable)

- Its notification toasts (invisible anyway).
- Its real-time sync (agent/macro/session events). Recovered by
  the existing react-query refetch-on-window-focus on return.
- Its UI-state push. Re-synced on reconnect.

### The implementation surface (fix A, not yet built)

- `frontend/src/services/messagingFeed.ts` — the singleton feed:
  gate `open()` on `document.visibilityState === 'visible'`;
  listen for `visibilitychange` → `disconnectMessaging()` /
  `reconnectAndOpen()`. The reconnect engine already exists.
- `frontend/src/services/uiStateBridge.ts` + the
  `useUIStateBridge` hook — same treatment on the WebSocket:
  `disconnect()` on hide, `connect()` on visible.
- Both services already carry reconnect/backoff engines — the gate
  is a thin wrapper, not new machinery.

## Fix B — the owner-tab relay (the future arc)

One tab owns the live connections; the others hold ZERO live
connections and receive events via BroadcastChannel from the owner.
Every tab stays real-time even in the background.

### The groundwork already in the codebase

- The cross-tab machinery exists: `enableCrossTabNotifyReceiver()`
  (App.tsx), the cross-window session sync + macro sync
  (useSessionSync/useMacroSync — BroadcastChannel patterns).
- The messagingFeed's topic-union design (ONE connection, ONE
  union of topics) is the shape the owner would aggregate: all
  tabs' topic needs broadcast to the owner, which subscribes to
  the UNION and relays events back over the channel.

### What B must solve (not yet designed)

- Ownership election (which tab is the owner) + crash handover.
- The topic-union aggregation across tabs (each tab's
  addTopics/removeTopics must reach the owner).
- The chat exemption carried: the owner-relay covers the idle
  streams; the chat reply stream stays tab-local (it belongs to
  the tab running the conversation — relaying tokens through
  BroadcastChannel would add latency to the one thing that needs
  none).
- B builds ON A's structure: the visibility gate becomes the
  owner-lease signal (the visible tab is the natural owner).

## The decision record

- 2026-09-07: the finding banked (a local sweep note,
  discussion list) after the user's third silent hang; CONFIRMED
  empirically by the user's close-a-tab test.
- 2026-09-07: fix A chosen by the user ("A it is"). This note
  documents A + the B path. A is not yet implemented.
- Short term (until A lands): one Cogitate tab at a time.
