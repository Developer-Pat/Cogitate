---
title: The Cross-Window Sync
type: dev-note
path: wiki/dev-notes/agents/cross-window-sync.md
created: 2026-08-25
tags: [type/dev-note, domain/messaging]
---

# The Cross-Window Sync

The mutating routers announce their mutations on the bus; every
open tab's shared store (or page-local state) converges. The
full map: [[atlas/messaging/Message map|Message Map]].

## The pattern (the canonical form)

- **The backend**: each mutating router gains a `_announce(event,
  payload)` helper (the try/except + the loud logger) + the CRUD
  endpoints publish `<domain>:<id>:<event>` with the explicit
  `event` field in the payload.
- **The frontend**: a `use*Sync` hook (the `addTopics` + the
  `subscribe` + the switch on the event + the store's apply or
  the page's reload + the cleanup):
  - The SHARED-store domains (agents, sessions, macros) mount in
    the AppSyncBridge — the events apply directly to the zustand
    store.
  - The PAGE-LOCAL domains (collections, teams, tools, lists,
    packages, permissions) use the generic `useDomainSync(domain,
    reload)` — the events call the page's reload.

## The bulk wipes (one event for a whole-list change)

A single session's mutation publishes `session:<id>:<event>`. A BULK wipe has no
single id, so it publishes ONCE with `scope='all'`:

- `DELETE /api/v1/sessions` (Clear All) → `session:all:cleared`
- `DELETE /api/v1/sessions/all` (Delete All) → `session:all:deleted_all`

The payload is `{event, count, scope: 'all'}` and carries **no** `session_id`, so
the frontend's `useSessionSync` handles the bulk case BEFORE its id guard and
reloads the list. One event per deleted session would flood the bus for a
whole-database clear; a delete-all that deleted nothing stays silent (a reload in
every open tab is noise).

## The phases (2026-08-25, the roadmap: local/cross-window-sync/)

1. The sessions (the user's audit catch — the tabs were stale!)
2. The agents (the adopt announced; the delete/rename didn't!)
3. The collections (the kits' CRUD — the PackageTab's names!)
4. The teams (the collectives!)
5. The macros (the shared store's reload!)
6. The remaining user-facing (the tools, the lists, the registry,
   the packages, the permissions, the workflow-lists — 3 workers
   in parallel!)
7. The system-internal (the debug/diagnostics/logs/providers/
   runtime-config/settings — the announces live; the frontend
   consumers are the known gap!)
8. THE DOCS (this + the Message map!)

## The pitfalls (learned)

- The INDENTATION: the routers' deep try/except nesting — the
  announce must sit at the SAME level as the endpoint's return (a
  wrong indent = IndentationError, seen in the macros router).
- The payloads' event field is MANDATORY — the deleted vs the
  updated must never be guessed from the shape.
- The frontend's page-local domains need the page's OWN
  subscription — the shared-store hooks can't touch the local
  state.
- **A literal path is swallowed by a path parameter unless the
  parameter is constrained.** `/all` was declared after
  `/{session_id}`, so `DELETE /sessions/all` reached the int
  parameter first and 422'd — the endpoint was unreachable. The
  `:int` converter makes the id route match digits only, so a
  literal sibling can never be eaten by it. (The same ordering
  rule the agents router notes for `/agents/deleted`.)
- **A hidden tab holds NO stream** (the connection budget), so it
  hears nothing while hidden and catches up from the ring replay
  when it becomes visible again. Two tabs must be made VISIBLE
  before a sync can be observed at all, or the test measures the
  gate instead of the sync.

## The companion rule: a failed mutation is never silent

The sync applies a mutation to the store optimistically — the row
leaves BEFORE the request is sent — which makes a swallowed
rejection a lie: the UI claims a deletion the backend never made,
and no other tab hears about it (there was no event). So every
optimistic path reloads the list on failure (the row comes back)
and raises an error notification: `useSessionManagement`'s delete
and its title save. "The row is already gone locally" is exactly
what makes the silence dangerous.
