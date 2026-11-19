---
title: Message Center
type: dev-note
path: frontend/src/stores/messageStore.ts
created: 2026-08-25
updated: 2026-09-05
tags: [type/dev-note, domain/messages, status/active]
---

# Message Center

## What it is

The system messaging queue. The bus's `notify:*` payloads land in the
**messageStore** (persisted, browser-local, `cogitate-messages`); the
Message Center page (`/messages`) renders them as a table; the bell +
the dashboard card surface the unread count.

## The arrival chain

```
backend bus ──▶ SSE fetch-stream feed (messagingFeed, topics notify:*)
              ──▶ eventBus ──▶ useNotifyBridge (App.tsx)
              ──▶ notificationStore.addNotification
              ──▶ messageStore.addMessage   ◀── the record
```

Each open tab hears its own SSE copy AND re-broadcasts it over the
cross-tab channel (`crossTabNotifyReceiver`) — the **eventId-scoped
dedupe** in `addMessage` collapses the transport duplicates to ONE
center record.

## The store rules (hard-won — do not regress)

- **eventId-scoped dedupe**: the same bus event (own SSE + synced
  copies from N tabs) records once. A **no-eventId local error records
  EVERY firing** (the Bob-errors doctrine — the local-error paths must
  stay observable).
- **Tombstones expire**: delete/clear-all tombstone the *content key*
  with a **60-minute TTL** (timestamped). A same-content event AFTER
  expiry records again; legacy un-timestamped tombstones count as
  already-expired (the center records new arrivals immediately).
- **Read state**: read rows dim; the unread count drives the bell
  badge + the page badges.

## The page surface (`/messages`)

- **Header**: the banner + the Help button only.
- **▸ Messaging Test Center** (an expander — the test controls AND
  the result panel live inside it):
  - **Full Test** — the whole-chain suite: a starting warning, then
    info → success → warning → error, ~1.5s apart, each verified to
    ARRIVE in the store within a 4s window; verdict PASSED / FAILED
    (naming the missing classes). Unique run-ids per run (the
    replay-guard can't eat repeats); every step is logged under
    `message-center-test` (Logs page + `backend/logs/frontend.log`).
  - **Single message** — one message of the chosen type (the picker
    sits after the button; defaults to *warning* after a reload); the
    echo confirms the round-trip.
  - **Visible-time windows**: arrival checks count VISIBLE milliseconds
    only — a backgrounded tab's throttled event stream must never
    false-fail the suite. Both tests warn when the tab is hidden.
- **The controls row** (below the expander): search · type filter
  (All types/…) · source filter · time range (All time / 5m / 20m /
  hour / 6h / day) · the count badges ("N unread" = error badge, the
  total = outline) · **Mark all read** · **Clear all** (caution) · the
  conditional bulk delete.
- **The table**: checkbox | Title | Type | Time | Source | Read —
  sortable headers; the View badge opens the full message (copy /
  close actions in the modal). All controls wear DaisyUI tooltips.

## The failure surface (current policies)

- **Aborts ≠ outages** (apiClient): navigation/external aborts return
  early — no streak, no error log; a genuine client timeout counts
  once. The telemetry flush opts out of outage tracking entirely.
  (The api-client dev-note carries the machinery.)
- **A fresh page load** reconnects the feed — arrivals in the first
  moments can miss the warm-up gap.
- **The sidebar/bridge dot is NOT the notify channel**: the dot is the
  WebSocket UI-state bridge; notifications travel on the SEPARATE SSE
  fetch-stream feed. A green dot does not mean the notify feed is
  alive — and the feed's death does not change the dot.

## Known issues (OPEN)

- The frontend log funnel's single-endpoint POSTs intermittently 500
  (`/api/v1/logs/frontend`) — entries land in the Logs page's
  in-memory store regardless; flush failures are outage-exempt. A
  dedicated dig is queued.
- The notify feed's fresh-load warm-up gap (above) can drop an
  arrival that fires in the first seconds after a reload — a
  re-send/re-run is the workaround.

## The phase-2 candidate (the backend queue)

The frontend store is browser-local. The durable upgrade: the bus's
publishes persist to a `system_messages` table + the endpoints
(list / mark-read / delete). The store's API is designed to swap the
source without UI changes.

## Unread vs total, and why the badge reaches 99+

**Two numbers, two jobs.** `selectUnreadCount` drives the nav bell's badge and the page's
"N unread"; the total drives the list. They are the same store, so they cannot disagree
about raw data.

**A notification is recorded on every firing.** Only a duplicate `eventId` is
suppressed; the same title arriving again is a new row. A repeating event — the same
"Market Watch" title every day — therefore adds one row per firing and nothing
self-clears, so the unread badge climbs to `99+`, where it tells you nothing. The store
caps at 500 rows.

**The badge also carries its count in the tooltip** (`"N unread — go to message
center"`), because the badge is `badge-xs` at `text-[10px]` and a single digit is easy to
misread at that size. The badge itself stays: **a hover-only count cannot alert anyone**,
which is the job the bell exists for.

## Telling "nothing arrived" from "I didn't look"

When a count looks wrong, **tombstones are the tell**:

```js
JSON.parse(localStorage['cogitate-messages']).state.tombstones
```

Non-zero means a delete/clear-all **ran** against this store; zero means it never did.
Two buttons in the app once both read "Clear all" and cleared *different* stores, which
makes "I cleared everything and the badge didn't move" look like a stuck count rather
than the wrong button. **Only the Message Center's is named "Clear all"**; the prompt
history's is **"Clear history"**.

A stale tab is a third explanation, and `hasHydrated` identifies it: the message store
persists to `localStorage` but **wires no `storage` event listener**, so a tab opened
before messages accumulated keeps its own in-memory copy while a fresh tab hydrates the
full one.
