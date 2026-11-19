---
title: useRunStream
type: atlas-hook
path: frontend/src/hooks/useRunStream.ts
confidence: high
updated: 2026-09-20
tags: [type/hook, domain/atlas-ui]
---

# useRunStream

**Path**: `frontend/src/hooks/useRunStream.ts`
**Type**: hook

## Purpose

Follows ONE test run's live event stream and folds it into a `RunFeed`. The endpoint is
`GET /api/v1/testing/runs/{id}/events`, which serves the run's own `events.jsonl`: the
whole run is replayed from the start, then followed, and the server closes the response
when the run ends.

The page owns this hook (not the Live tab) so a run's feed survives a nav within the
page — switching to the catalog to read a row must not tear down a stream from a run
that takes half an hour.

## Exported API

### `useRunStream(runId: string | null): UseRunStreamReturn`

```typescript
interface UseRunStreamReturn {
  feed: RunFeed
  status: 'idle' | 'connecting' | 'open' | 'closed' | 'error'
  reload: () => void
}
```

`runId === null` means "nothing to follow": the feed resets and no socket is opened. A
different `runId`, or `reload()`, closes the current stream and starts the fold over
(without that reset, a previous run's lines would still be on screen under the new
run's counts).

## Why a raw `EventSource`

The house `SSEClient` retries on its own and then GIVES UP after `maxRetries` — fine
for a stream that is always short, wrong for a half-hour run, where a blip at minute
twenty would end the feed permanently. The browser's own reconnect is better here and
it is what the stream was built for: every frame carries its byte offset as its `id:`,
so a reconnecting `EventSource` sends `Last-Event-ID` by itself and resumes exactly
where it stopped instead of replaying the run.

## The two closing cases

- **The stream ends itself** — a `run_end`, `stream_end` or `error` frame is the end of
  the line, and the hook CLOSES the source on it and reports `closed`. This matters:
  `EventSource` treats a server-closed response as a dropped connection and
  RECONNECTS, so without the explicit close the tab sits on "stream interrupted —
  reconnecting" over a run that finished minutes ago, replaying its tail every few
  seconds. The browser cannot know the close was deliberate; the page can.
- **A real interruption** — an error while the stream is still open is a connection
  problem: the hook reports `error` and lets the browser retry.

## Frame handling

Frames are named by their `t` field, not by SSE `event:` names. A frame whose `t` this
build does not know is **ignored** rather than guessed at, so a newer plugin can add an
event kind without breaking the page. The one unchecked step (casting the parsed object
to `RunEvent`) sits in `parseFrame`, and the reducer reads every field through a
`typeof` guard.

## Related

- [[atlas/ui/pages/TestingDashboard|Testing Dashboard]] — the page that owns it
- [[dev-notes/testing/README|Testing dev notes]] — the event file's four line kinds
