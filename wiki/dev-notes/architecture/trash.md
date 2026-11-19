---
title: The Trash
type: devnote
path: wiki/dev-notes/architecture/trash.md
confidence: high
updated: 2026-10-06
tags: [type/dev-notes, domain/architecture]
---

# The Trash

A delete in this app is a **move**. Retiring a test run, deleting an agent's
workspace, and the files that nothing else claims all land in `trash/` rather than
being erased, and the trash is what makes that recoverable rather than merely
claimed. This note is the contract: the domain, the shelves, the one distinction
they turn on, the API over them, and the rules that keep it honest.

## It is a domain, not a folder

`backend/app/domain/trash/` holds:

| File | Owns |
|------|------|
| `interface.py` | `TrashEntry` (one thing on a shelf, as a reader needs it) and the `TrashDomain` protocol — the contract every shelf answers |
| `registry.py` | The ONE map of shelves. `register_domain` / `get_domain` / `list_domains`; **registration order is tab order** |
| `services.py` | The one policy layer: `shelves`, `listing`, `restore`, `purge`, `empty` |
| `listing.py` | `scan_shelf` — reading a shelf directory into `TrashEntry`s (used by four shelves; the runs shelf keeps its own reader) |
| `mechanics.py` | The ONLY place that destroys anything: `assert_inside_trash`, `remove_entry`, `empty_shelf` |
| `adapters/` | One shelf each |

The verbs are **async on purpose**. Four shelves are pure filesystem work and one —
the agents — is ROW-BACKED: whether an entry can be restored, and what purging it
means, is a question only the database can answer. A synchronous contract would
have forced that shelf out of the registry and left every caller with a special
case.

## The two kinds of entry, and the one field that tells them apart

**Row-backed vs residue.** An entry a live record names can be **restored** (the
record is the destination); an entry no record names is **residue** and can only be
purged, because nothing knows where it came from. This is what
`TrashEntry.restorable` reports, per entry — and `TrashDomain.restorable` reports
it per shelf (does this shelf have a way back at all). Both matter, and the agents
shelf is where they differ.

`TrashEntry.note` is the shelf's OWN sentence about an entry — "residue, purge
only", "a retired backup — putting one back is never automatic", "the agent “Bob”
is trashed". It is prose for a reader. **Branch on `restorable`, never on `note`.**

## The shelves

| Shelf | Directory | Restorable | Reads the DB |
|-------|-----------|-----------|--------------|
| `agents` | `trash/agents/` | yes | **yes** (`needs_db`) |
| `test-runs` | `trash/test-runs/` | yes | no |
| `reports` | `trash/reports/` | no | no |
| `dbs` | `trash/dbs/` | no | no |
| `misc` | `trash/misc/` **plus the trash root** | no | no |

- **`test-runs` is a WRAPPER, not a reimplementation.** The move, the collision rule
  and the lock question already live in `app/domain/testing/trash.py`; the adapter
  puts that shelf behind the contract so the page, the API and Exa reach it the same
  way as every other shelf.
- **`dbs` holds RECOVERY MATERIAL.** Restoring a backup means overwriting a live
  database and nothing here does that automatically; a person copies one out and
  restores it by hand.
- **`misc` is the fallback**, and it exists so the trash root has no invisible
  content: whatever is not a registered shelf is an ENTRY on `misc`, including
  loose files in the root. A shelf's own directory is never listed as an entry, and
  `misc` refuses to purge a shelf by name.

## Adding a shelf

A shelf is **a file plus a registration**:

1. Write the adapter: the five class attributes (`key`, `label`, `restorable`,
   `needs_db`) and `directory()`, `entries()`, `restore()`, `purge()`, `empty()`.
2. Register it in `registry.py`.

Nothing else needs editing: the locator (`Paths.trash_dir_for(key)`), the API's
routes, the page's tabs and Exa's view all read the registry. The key is validated
**twice** — at registration (one clean path segment, no duplicates) and at the
locator — which is what stops a typo from planting `trash/agnts/`, a shelf nothing
renders.

## The surface

`/api/v1/trash` (`backend/app/api/v1/trash/router.py`) — five routes, the shelf in
the path:

```
GET  /trash                          the shelves, with the counts on their tabs
GET  /trash/{shelf}                  one shelf: the entries and where it lives
POST /trash/{shelf}/restore/{name}   put one entry back where it came from
POST /trash/{shelf}/purge/{name}     remove one entry for good
POST /trash/{shelf}/empty            remove every entry on the shelf
```

There is deliberately **no global empty**, and no verb prunes on a schedule.

### What a machine can rely on

Exa reads this surface and never sees the page, so the shape is part of the
contract (verified against the running app, every shelf and every error path):

- **One shape for all five shelves.** Listing top level:
  `count, directory, entries, key, label, restorable`. Entry:
  `files, is_dir, name, note, restorable, retired_at, size_bytes`. A reader needs no
  per-shelf decoder.
- **`retired_at` is an epoch float** — the entry's own mtime, an observation of this
  machine rather than a property of the thing.
- **`directory` is installation-relative** (`trash/test-runs`); the API never hands
  out an absolute path.
- **The restore report is the SHELF's.** `restored: true` is shared and the rest is
  not: a run answers `name` / `restored_to` / `renamed`, an agent answers
  `agent_id` / `name` / `workspace_key`. Rely on the flag; do not assume the fields
  beside it.
- **The status codes are the branching rule.** **404** — an unknown shelf (refused
  by the registry before any directory is touched) or an entry that is not there (a
  stale row). **400** — the shelf's own refusal in its own words: restoring from
  `reports`/`dbs`/`misc`, or purging a shelf through `misc`.

Restore is the only verb that consults the listing first, and it has to: three
shelves answer "not there" and "I cannot do that" with the same exception, so the
listing is what tells a 404 from a 400. Purge needs no such check — its boolean
already says which — and asking the shelf first is what lets `misc` refuse a SHELF
in its own words.

**The destructive verbs take a body.** `purge` and `empty` require
`{"confirm": true}` — without it, 400 and nothing is touched (see *What guards
destruction*). Restore does not. A machine reader has to send it.

## One tab's removal reaches the others

Every mutating verb announces on the message bus — the topic is
`trash:<shelf>:<event>` and the payload carries `id` (the shelf) and `event`
(`restored` / `purged` / `emptied`), plus `name` where there is one. The page
subscribes through `useDomainSync('trash')` and re-reads, so a purge in one tab
does not leave another showing a row that is gone.

The KIND travels in the payload because the bus hands a handler only the payload:
a `trash:*` subscriber receiving all three could not tell them apart otherwise.

## What guards destruction

Three things, and it is worth being exact about each.

**Containment — enforced, mechanical.** `mechanics.py` is the only code that
destroys anything, and every path goes through `assert_inside_trash`: nothing
outside the trash directory is ever removed, and the trash itself cannot be. This
is the check that must never drift, and it is why a shelf's `empty()` cannot be
written as a bare `rmtree` in an adapter.

**The intent flag — a stop for the ACCIDENT, not for the caller.** `purge` and
`empty` require `confirm: true` in the body; without it they answer 400 and touch
nothing. It is not a gate and is not meant to be one — any caller can send `true`
— and what it buys is that the accidental shapes FAIL instead of delete: a stray
`curl` with no body, a retry whose body was dropped, a script whose default
happened to be "empty everything". Restore deliberately carries no flag: it is
additive and recoverable, and a confirmation on the way BACK would be a checkpoint
with nothing behind it.

**The confirmation — the caller's, deliberately.** Beyond the flag, `purge` and
`empty` ask no phrase and no password. A typed phrase used to gate emptying,
checked by the service; it is out of the product because it named the wrong thing
(the sentence for emptying a shelf is not the sentence for removing one entry) and
because a sentence read off the dialog in front of you and typed back is a speed
bump rather than a guard. What remains is the act: an irreversible removal asked
for deliberately, in a dialog that names what goes
([[atlas/ui/components/features/trash/PurgeEntryModal|PurgeEntryModal]],
[[atlas/ui/components/features/trash/EmptyShelfModal|EmptyShelfModal]]). **The
consequence, stated rather than implied: a caller who MEANS it — a script, Exa,
`curl` with the flag — can empty a shelf in one request. That is the design, not
an oversight.**

## Verifying anything on this surface

**Create your own entry; never exercise a verb against the installation's real
trash.** The trash holds the operator's retired work — runs, agent workspaces,
database backups — and `purge`/`empty` cannot be undone. A verification that fires
a mutating call "to see the refusal" destroys real state the moment the refusal is
not the one expected. Build the entry you need (a directory under
`trash/<shelf>/`, a run folder via the API), then drive the whole lifecycle against
that — retire, list, restore, re-retire, purge — and check the installation's trash
is exactly as it was.

Everything else is cheap to check by reading: `GET /trash` for the shelf list, `GET
/trash/{shelf}` for one shelf, and the error paths, which are read-only.

## Pitfalls

- **An absent shelf directory is an EMPTY shelf, not an error.** An installation
  starts without a trash; a shelf with no directory reports `count: 0` rather than
  vanishing (a tab that disappears cannot tell you it is empty).
- **Dot-entries are skipped** by `scan_shelf` — they are bookkeeping, not shelf
  contents. The runs shelf's reader reports only directories.
- **`purge` returns False, it does not raise,** when there is nothing to remove; the
  router turns that into a 404 rather than claiming a destruction that did not
  happen.
- **`list_trash` reports a folder, not a fixed file list** — the runs shelf's entries
  carry the files actually present, so a run that never wrote its `report.xml` is
  reported honestly.
- **The agents shelf needs a session.** Call it without one and it says so
  (`needs_db`); the service passes the session per call rather than holding it, so
  the service stays stateless.

## Related

- [[atlas/api/routers/trash|Trash — API]] — the route table this note describes
- [[atlas/ui/pages/Trash|Trash page]] — the human surface
- [[help/trash|Trash (help)]] — the user-facing account
- [[dev-notes/agents/agent-lifecycle|Agent lifecycle]] — the agents shelf's owner
- [[dev-notes/architecture/Paths and Path Resolution|Paths and Path Resolution]] — the locator and `Paths.trash_dir_for`
