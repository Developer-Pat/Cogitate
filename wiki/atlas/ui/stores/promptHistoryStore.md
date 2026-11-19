---
title: promptHistoryStore
type: atlas-store
path: frontend/src/stores/promptHistoryStore.ts
confidence: high
updated: 2026-09-17
tags: [type/store, domain/atlas-ui]
---
# promptHistoryStore

**Path**: `frontend/src/stores/promptHistoryStore.ts`
**Last Updated**: 2026-09-17

## Purpose

**The prompt history.** A straight copy of what the user sends, written on send. It is
its own record — it does not derive from any session.

## The shape

```typescript
interface HistoryPrompt {
  id: string          // stable key for React + removal
  text: string        // trimmed
  sessionId: string | null   // recorded, NOT filtered on
  createdAt: number
}

interface PromptHistoryState {
  prompts: HistoryPrompt[]                       // ALPHABETICAL, deduplicated
  addPrompt: (text: string, sessionId: string | null) => void
  removePrompt: (id: string) => void
  clearAll: () => void
}
```

## Who writes it

The **send path** — `onSendMessage` in
[[atlas/ui/pages/AgentInteraction]], which records the prompt and then calls the real
handler. It records **before** the send, because it is a record of what the user asked,
not of what succeeded.

## Storage: sessionStorage, deliberately

Persisted with `createJSONStorage(() => sessionStorage)` under the key
`cogitate-prompt-history`. **Not localStorage**, and the reason is a decision rather
than an oversight:

- the requirement is *"persisted for the application duration; does not need to survive a
  restart"*;
- pure in-memory would satisfy that literally, but it dies on every page refresh — and a
  refresh wiping the history reads as a bug rather than a choice;
- sessionStorage survives a refresh and dies with the tab, **which is the application's
  duration**.

`partialize` persists only `prompts`, never the functions.

## Rules the store enforces

| Rule | Why |
|---|---|
| Blank text is ignored | attachments-only sends carry empty text; a blank row is noise the user cannot explain |
| Text is trimmed | trailing whitespace is not content |
| `id` is `` `${Date.now()}-${seq++}` `` | two identical sends in the same millisecond must not collide, or React renders one row for two |
| `MAX_HISTORY` = 200, **oldest dropped by timestamp** | the cap must drop the oldest — and under alphabetical order the array's tail is not the oldest, so entries are compared on `createdAt` |
| `MAX_DISPLAYED` = 100 | how many the panel draws; older entries stay stored |
| **A prompt already in the list is NOT added again** | the list is a **library of distinct prompts**, not a log. Re-sending on purpose (a retry) is a real event, but it does not become a second identical row. Matching is on a case-insensitive, whitespace-collapsed key, and a duplicate **keeps its existing place** rather than jumping |

## Ordering, and the migration

The stored list is kept **in alphabetical order** (case-insensitive) — a property of the
**store**, not the view, so anything reading `prompts` sees the same sequence.

A list persisted before the ordering existed is normalised **on load**: the persist config
carries `version: 1` with a `migrate`, so an older sessionStorage list is deduplicated and
sorted the moment it is read. Without that, a tab which was already open would keep showing
its pre-change list and the change would read as broken.

## The flat list, and the scope question left open

The list is **flat** — every prompt, whatever session it came from. `sessionId` is
recorded anyway, so the per-session/all-sessions scope that was weighed up becomes a
small filter rather than a rewrite. Nothing filters on it today.

## Tests

`frontend/src/stores/__tests__/promptHistoryStore.test.ts` — 18 tests covering ordering
(alphabetical, case-insensitive), deduplication and its match key, trimming, blank rejection,
id uniqueness, per-entry removal, `clearAll`, the oldest-by-timestamp cap, and the
**version-1 migration** (seeded with genuine old-format data and asserted to come back
normalised).

They exist because the real write path can only be exercised by sending a message, which
means a live LLM request. The tests state their own limit: they cannot prove the page
calls `addPrompt` on send — that is a two-line call site.

## Related

- [[atlas/ui/components/features/agentInteraction/PromptHistoryList]] — the view
- [[atlas/ui/pages/AgentInteraction]] — the send path that writes it
