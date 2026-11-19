---
title: Sessions
type: atlas-api
path: wiki/atlas/api/routers/sessions.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-09-19
tags: [type/api, domain/sessions, status/active]
---

# Sessions — API

## Purpose

Chat session lifecycle: CRUD, per-agent sessions, search, bulk ops, clear-all.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `DELETE` | `/api/v1/sessions` | Clear All Sessions |
| `GET` | `/api/v1/sessions` | List Sessions |
| `POST` | `/api/v1/sessions` | Create Session |
| `GET` | `/api/v1/sessions/agent/{agent_id}` | Get Agent Sessions |
| `DELETE` | `/api/v1/sessions/all` | Delete All Sessions |
| `POST` | `/api/v1/sessions/bulk-delete` | Bulk Delete Sessions |
| `GET` | `/api/v1/sessions/search` | Search Sessions |
| `DELETE` | `/api/v1/sessions/{session_id}` | Delete Session |
| `GET` | `/api/v1/sessions/{session_id}` | Get Session |
| `PUT` | `/api/v1/sessions/{session_id}` | Update Session |
| `POST` | `/api/v1/sessions/{session_id}/messages` | Append a message (the EXTERNAL surface's save path — the Exa bridge). Body: `{role, content}`. The normal chat persists inside its pipeline handler; Exa has no pipeline, so this is the explicit save |


## The bus announcements (the cross-window sync)

Every mutating endpoint publishes on the bus so the other open tabs converge
([[dev-notes/agents/cross-window-sync|Cross-Window Sync]]): the single-session
paths as `session:<id>:<event>` (`created` / `updated` / `deleted`), and each
**bulk wipe once** with `scope='all'` — `session:all:cleared` (Clear All) and
`session:all:deleted_all` (Delete All), payload `{event, count, scope}`, no
`session_id`; the frontend's `useSessionSync` reloads the list on them (a
delete-all that deleted nothing stays silent).

`/{session_id}` carries the `:int` converter and it is **LOAD-BEARING**: `/all`
is declared after it, so an unconstrained id route swallows the literal path
(the request reaches an int parameter and 422s — the endpoint unreachable,
the debugging Database Tools' button failing). Constrained, the id route matches
digits only, so no literal sibling can be eaten by it.


## The list response, and `message_count`

`GET /api/v1/sessions` and `GET /api/v1/sessions/search` default to a **titles-only**
fast path: `include_messages=false`, which returns `messages: []` deliberately. That
left callers with nothing honest to display, so `SessionResponse` gained:

```
message_count: Optional[int] = None
```

Filled by a **single grouped COUNT** across the page's ids (`SessionService.message_counts`)
— not a lazy load per row. `None` means "not asked for" (the `include_messages` path),
while `0` is a real zero.

**A caller cannot use `messages` for a count.** It is empty by design on this path, and
the lazily-loaded array a client may hold is empty for any session not yet opened. Read
`message_count`.

## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/api/routers/chat|Chat]]
- [[atlas/ui/pages/Sessions|Sessions page]]
