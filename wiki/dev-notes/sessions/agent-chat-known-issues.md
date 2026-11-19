---
title: Agent-Chat Session Known Issues
type: devnote
path: wiki/dev-notes/sessions/agent-chat-known-issues.md
confidence: high
updated: 2026-09-09
tags: [type/dev-notes, domain/sessions, domain/agent-chat]
---

# Agent-Chat Session Known Issues

The agent-chat session-lifecycle issue register: the failure
classes that made the panel "not track", their root causes, and
the guards that hold them. CURRENT STATE only — an issue is FIXED
when the guard ships. Written as a diagnosis reference: if a
symptom returns, start from its entry and check the listed
signals before changing anything.

## The vanished assistant bubble + the lost current session — FIXED

The session's reply streams and persists (the DB row + messages
exist), but no assistant bubble renders, and the active session
appears to leave the panel.

**Root cause — the temp-swap message routing.** A fresh chat runs
in a LOCAL temp session (id `session-<ts>-<rand>`, no backend
row). The backend creates the real row at request time and emits a
`session_id` SSE event mid-stream; the frontend swaps the temp id
for the real id in the store. But the streaming callbacks captured
the TEMP id at stream start, so the assistant-message writes look
up a session that no longer exists — the store's add-message path
returns silently on "session not found", dropping the message.
The swap also left the message's `updatedAt` unbumped, so the
panel sort never moved.

**Guard**: the message-write callbacks resolve the LIVE session
before writing (if the requested id is gone and the active session
is a non-temp, they write there — the swap lands the real row
active). `useAgentInteraction.ts` — `resolveLiveSessionId`.

**Diagnosis signals**: the DB has the messages but the UI does
not; the frontend log shows the stream's "Backend session created
during streaming" / "Session ID updated in store" followed by
add-message calls against the old id.

## The dead rehydration — the "[object Object]" storage — FIXED

Every page reload loses the active session: no highlight in the
panel, no current-session pin, the fresh "New Session" never
appears — the session system appears to "track nothing".

**Root cause**: the hub store's custom scoped storage was handed
directly to zustand v5's `persist`. v5 passes the storage a
SERIALIZED StorageValue OBJECT; a plain string storage coerces it
— the stored value becomes the literal string `"[object Object]"`
and every rehydrate parses nothing, so the store starts empty on
each load.

**Guard**: the storage is wrapped in `createJSONStorage` —
`cognitiveHubStore.ts`'s persist config.

**Diagnosis signals**: `localStorage["cogitate-hub-storage"]`
contains `[object Object]`; the console logs "[CognitiveHubStore]
Rehydration failed".

## The permanently untitled sessions — FIXED

A fresh conversation stays titled "New Session <timestamp>"
forever; the auto-title never fires. (Also produced duplicate
rename notifications once generation ran twice.)

**Root causes** (five, all required):
1. The chat request hardcoded `generate_title: false` (a
   "DISABLED FOR DEBUGGING" leftover), killing the backend's
   finalization path.
2. The finalization's placeholder check matched only the exact
   titles `None` / `"New Session"` / `"Untitled"` — the commit
   fallback titles sessions "New Session <timestamp>", which
   slipped through.
3. The chat-path session creator wrote `title=None` directly
   (bypassing the create-endpoint's "New Session" default).
4. The frontend's own title service fired against the TEMP id —
   the API 404'd before the real row existed.
5. The backend's `session_title` event was ignored while the
   frontend generated its own title — two LLM calls and two
   rename announcements per fresh session.

**Guards**: `generate_title` is true (the backend finalization
self-limits to placeholder-titled sessions); the placeholder check
matches the whole "New Session ..." class; the chat-path creator
defaults to "New Session"; the frontend job skips when a real
title already landed; the backend's title event is APPLIED to the
store session instead of ignored.

**Diagnosis signals**: the DB row's title is `None` or "New
Session ..." after a completed conversation; the backend log shows
no "Generated title" line; two "Generated title" lines for one
session = the double-fire returned.

## The rename that did not persist — FIXED

Renaming a brand-new session appears to work, then reverts; the
console logs "The rename did NOT persist".

**Root cause**: renames PUT to `/api/v1/sessions/<id>`. A temp
session's id does not exist on the backend — the PUT 404s. The
rename lived only in the store and evaporated when the temp
committed.

**Guard**: the rename handler skips the PUT for temp ids — the
commit flow carries the temp's title into the real row.

**Diagnosis signals**: the frontend log's "The rename did NOT
persist" error; the session id in the failing PUT starts with
`session-`.

## The session panel not sorting by activity — FIXED

Sessions stay in stale positions; a freshly-used conversation does
not rise to the top.

**Root cause**: `chat_sessions.updated_at` only moved on
title-generation. The message-persist path (`add_message`) never
touched it, so the sort key did not reflect conversation
activity.

**Guard**: `add_message` stamps the session's `updated_at`; the
panel sorts committed sessions by it (newest first) and pins the
active session above the list regardless.

**Diagnosis signals**: the DB row's `updated_at` unchanged after
new messages; the panel order differs from the DB order by
`updated_at DESC`.

## The dying agent — the HYBRID deep pass dropped its tool calls — FIXED

An agent turn ends mid-investigation: the last bubble promises
work ("Let me read his persona...") and nothing follows. The user
nudges, the agent "comes back blank", and the cycle repeats — it
reads as the agent dying. (Bob's session "Top World Headlines
Today", 2026-09-09 — the turns at 22:38 and 22:41, each a
narration with no follow-through.)

**Root cause**: when a turn's context triggers the conduit's HYBRID
deep pass (`chat/router.py`, the Route.HYBRID branch), that pass's
LLM request still carries the agent's tools (only `tool_choice` is
popped). The model can legitimately answer with another round of
tool calls — continuing an investigation — but the pass harvested
only `accumulated_content` and SILENTLY DISCARDED the calls. The
turn finalized on the narration alone (~124 chars vs a real
answer's hundreds), with the tool calls never executed.

**Guard**: the HYBRID deep pass is now a bounded tool-loop (5
rounds) mirroring the main tool loop: the tracker's loop/spam
guard filters the calls, `_execute_tools` runs them, the results
are recorded + streamed, and the pass re-requests until the model
answers without tools.

**Diagnosis signals**: a "Conduit: HYBRID pass complete —
content_len=N" log where N is small (~100-200) after a stream
whose "Streaming summary" said `has_tool_calls=True`; the frontend
shows a narration bubble promising tool work that never happened.
(Note: the compaction log at the same moment is a red herring —
coincidental timing.)

## The quick-reference table

| Symptom | First check |
|---|---|
| Reply persisted but no bubble | DB has the message; the frontend log's temp-swap trail |
| Active session lost on reload | `localStorage` hub key == `[object Object]` |
| Stuck "New Session ..." title | DB title; "Generated title" log lines (none = the flag/path; two = the double-fire) |
| Rename reverts | The failing PUT's id starts with `session-` |
| Panel order wrong | DB `updated_at` vs the panel; `add_message` not stamping |
| Agent narrates tool work then goes silent | `HYBRID pass complete — content_len~100` right after a `has_tool_calls=True` stream |
