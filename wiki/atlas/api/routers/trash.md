---
title: Trash
type: atlas-api
path: backend/app/api/v1/trash/router.py
category: api-atlas
order: 43
confidence: high
updated: 2026-10-06
tags: [type/api, domain/trash, status/active]
---

# Trash — API

> Router: `backend/app/api/v1/trash/router.py` (`/api/v1/trash`).
> Domain: `backend/app/domain/trash/` (the `TrashDomain` contract, the registry of
> five shelves, the service, and one adapter per shelf). Status: **ACTIVE** — the
> ONE surface over every shelf.

## Purpose

A delete anywhere in this app is a **move**, and the trash is where the moved
things land. This router is the second reader of the shelf REGISTRY — the page is
the first, Exa the third — and it exists so that neither has to know a shelf's name
in advance: `GET /trash` returns the shelves, which is what makes a sixth shelf a
file plus a registration rather than an endpoint plus a page edit.

The page (`/trash`) renders its tabs from that list; Exa calls the same endpoints
and never sees the page. Nothing here composes a trash path: the directory comes
from the locator (`Paths.trash_dir_for(shelf)`), and a misspelled shelf is refused
before any directory is touched.

## The five shelves

| Shelf | Holds | Restorable |
|-------|-------|-----------|
| `agents` | Workspaces of deleted agents, and the residue beside them | **Yes** — a row names the workspace, so a trashed agent can be put back; a folder no row names is residue and can only be purged |
| `test-runs` | Retired run folders, whole with `report.md` / `report.xml` / `events.jsonl` | **Yes** — restoring puts the folder back in the runs dir (and `renamed: true` when the name had been taken since) |
| `reports` | Report areas moved out of the way | No — nothing records where they came from |
| `dbs` | Retired database backups (recovery material) | No — deliberately: putting a backup back means overwriting a live database, and nothing here does that automatically |
| `misc` | Everything no other shelf claims — loose files in the trash root, unregistered directories | No — by construction |

`agents` is the one shelf that reads the database (`needs_db`), because only a row
can say whether an entry is a trashed agent or residue.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/trash` | Every shelf with its count, label, `restorable` and directory — **the page's tabs, rendered from here**. A shelf with no directory reports `count: 0` rather than being absent: a tab that vanishes cannot tell you it is empty |
| `GET` | `/trash/{shelf}` | One shelf read out: `key`, `label`, `restorable`, `directory`, `count`, and `entries[]` — each with `name`, `is_dir`, `size_bytes`, `retired_at`, `files`, `restorable` and `note` |
| `POST` | `/trash/{shelf}/restore/{name}` | Put ONE entry back. The answer adds `restored: true` to the SHELF's own report. 404 when the entry is not on the shelf · 400 when the shelf has no way back, in its own words |
| `POST` | `/trash/{shelf}/purge/{name}` | Remove ONE entry **permanently**. Body `{"confirm": true}` — required, see below. `{purged, shelf, name}`. 404 when nothing by that name is there · 400 when the shelf refuses (the `misc` bucket declining to take a SHELF) or when the flag is missing |
| `POST` | `/trash/{shelf}/empty` | Remove **every** entry on ONE shelf. Body `{"confirm": true}` — required. `{emptied, domain, deleted: <count>}`. 404 for an unknown shelf · 400 without the flag |

There is deliberately **no global empty**, and no verb prunes on a schedule.

## The JSON a machine reads

Verified against the running app (every shelf, plus the error paths) rather than
assumed — this is the part Exa depends on:

- **One shape for all five shelves.** The listing's top level is
  `count, directory, entries, key, label, restorable` and an entry is
  `files, is_dir, name, note, restorable, retired_at, size_bytes` — identical
  across shelves (measured field-for-field on all five). A reader needs no
  per-shelf decoder.
- **`retired_at` is an epoch float** — the entry's own mtime. An observation of
  this machine, not a property of the thing.
- **`directory` is installation-relative** (`trash/test-runs`). A caller that wants
  to touch the filesystem has to resolve it against the installation root; the API
  never hands out an absolute path.
- **`restorable` appears twice, and both matter**: on the shelf (has this shelf a
  way back at all) and on the entry (does a RECORD back this one). The agents shelf
  is where they differ — a trashed agent sits beside residue.
- **`note` is the shelf's own sentence** about why an entry is or is not
  restorable. It is prose for a reader, not a code to branch on; `restorable` is
  the thing to branch on.
- **The restore report is the SHELF's, not a common body.** `restored: true` is
  shared, and the rest is not: a run answers `name` / `restored_to` / `renamed`, an
  agent answers `agent_id` / `name` / `workspace_key`. A machine may rely on the
  flag; it must not assume the fields beside it.
- **The codes mean different things and both are actionable**: **404** is "look
  elsewhere" (an unknown shelf, refused by the registry, or an entry that is not
  there — a stale row), **400** is the shelf's refusal in its own words (restoring
  from `reports`/`dbs`/`misc`; purging a SHELF through `misc`).

## What guards the irreversible act

Two things, and neither is a gate against a caller who means it.

**The intent flag — a stop for the accident.** `purge` and `empty` require
`{"confirm": true}` in the body; without it they answer 400 and touch nothing. Any
caller can send `true`, so this is not authentication — it is what makes the
accidental shapes FAIL rather than delete: a stray `curl` with no body, a retry
whose body was dropped, a script defaulting to "everything". Restore carries no
flag: it is additive and recoverable.

**Containment — enforced, mechanical.** Nothing outside the trash is ever removed
(the rule lives in `domain/trash/mechanics.py`, and every destroying path goes
through it). The typed phrase that used to gate emptying is out of the product: it
named the wrong thing for a single entry, and a sentence retyped from the dialog in
front of you is a speed bump rather than a guard. The confirmation a person gives is
the page's dialog
([[atlas/ui/components/features/trash/EmptyShelfModal|EmptyShelfModal]]).
**A caller who means it can still empty a shelf in one request — that is the
design.**

## One tab's removal reaches the others

Every mutating verb announces on the bus — `trash:<shelf>:<event>`, the payload
carrying `id` (the shelf) and `event` (`restored`/`purged`/`emptied`). The page
subscribes via `useDomainSync('trash')` and re-reads, so a purge in one tab does
not leave another rendering a row that is gone. The kind rides in the payload
because the bus hands a handler only the payload.

## Status

**ACTIVE** — the trash page (`/trash`) is its consumer, and Exa is its machine
reader. The three delegates that used to stand under `/api/v1/testing` are gone,
in the same commit as their last caller.

## Related

- [[atlas/ui/pages/Trash|Trash page]] — the surface that renders these shelves
- [[atlas/api/routers/testing|Testing — API]] — where a run is retired INTO the trash
- [[dev-notes/architecture/trash|Trash dev notes]] — the contract, the shelves, the containment rule
- [[help/trash|Trash (help)]] — the user-facing account
