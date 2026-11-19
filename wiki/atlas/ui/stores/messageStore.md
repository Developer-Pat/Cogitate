---
title: messageStore
type: atlas-store
path: frontend/src/stores/messageStore.ts
confidence: high
updated: 2026-09-15
tags: [type/store, domain/atlas-ui]
---
# messageStore

**Path**: `frontend/src/stores/messageStore.ts`
**Last Updated**: 2026-09-15

## Purpose

**The system message queue** — the Message Center's data, and the source of the unread
count that drives the top row's bell. It supersedes the older `exaUnreadStore` pulse
flag: the glowing agent button was replaced by a bell with a count.

The bus's `notify:*` payloads land here (the bridge); the unread count drives the bell
and the dashboard card; [[atlas/ui/pages/Messages]] renders the table.

```typescript
interface SystemMessage {
  id: string
  eventId?: string   // the bus-event id — the dedupe keys on it
  kind: string
  source: string
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  message: string
  timestamp: number
  read: boolean
}
```

## The write rule — "the center is the RECORD"

`addMessage` suppresses exactly **two** things:

1. **the same `eventId`** — one record per *event*, not one per delivery path. This is
   the cross-tab triples fix: one bus event reaches a tab via the bridge *and* the
   cross-tab sync, and every tab broadcasts its own copy.
2. **content explicitly deleted, still inside the tombstone TTL.**

**Everything else records, every time** — including repeats. That is deliberate, and it
is the user's own ruling:

> *"the user's 'the center records every firing': the same-key skip ate the REPEAT
> messages — the center kept only the first instance of each repeated warning. The
> ring-replay stays quiet at the BRIDGE (the seen-check); **the center is the RECORD —
> every firing lands**."*

**Consequence worth knowing:** a repeating event that carries no `eventId` adds one row
per firing. A long-running app therefore accumulates rows, and nothing self-clears — the
count only falls on `markAllRead` or `clearAll`. The badge tops out at `99+`.

## Constants

| Constant | Value | Meaning |
|---|---|---|
| `MAX_MESSAGES` | 500 | ring cap; oldest dropped |
| `MAX_TOMBSTONES` | 300 | bounds tombstone growth |
| `TOMBSTONE_TTL_MS` | 1 hour | a tombstone suppresses the same content for an hour, so a genuinely new occurrence records again |

The TTL exists because a permanent tombstone would mean deleting "Backend Unavailable"
once silently ate every future occurrence.

## Actions

| Action | Effect |
|---|---|
| `addMessage` | prepends (so index 0 is the NEWEST) after the two suppression checks |
| `markAllRead` | every message `read: true` |
| `deleteMessages(ids)` | removes those, tombstoning their content keys |
| `clearAll` | empties the list **and tombstones every key** |
| `tombstoneKey` | tombstones one key |

### The tombstone count is a diagnostic

`clearAll` writes a tombstone for **every** key it clears. So:

- **tombstones > 0** → a clear has run
- **tombstones == 0** → no clear has ever run against this store

That distinction is how a "the count is stuck" report is told apart from "the button
you pressed clears something else". It is worth checking before assuming a bug.

## Persistence

`persist` under the key `cogitate-messages` (localStorage).

**No storage-event listener is wired.** Each tab holds its own in-memory copy, so a tab
opened before messages accumulated can disagree with a freshly opened one until
something writes. `crossTabNotifyReceiver` keeps *new notifications* in sync across
tabs; the existing store state is not re-synced.

## Consumers

- [[atlas/ui/pages/AgentInteraction]] — `selectUnreadCount` → the bell and its tooltip
- [[atlas/ui/pages/Messages]] — the table, filters, mark-read, clear
- `components/dashboard/MessagePreviewCard.tsx` — the dashboard card
- `services/crossTab/crossTabNotifyReceiver.ts` — the cross-tab write path

## Related

- [[dev-notes/message-center|Message Center]] — the findings, the badge, and the *Clear all* collision
- [[atlas/ui/stores/notificationStore]] — the producer that feeds this store
