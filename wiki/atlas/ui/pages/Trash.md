---
title: Trash
type: atlas-page
path: frontend/src/pages/Trash.tsx
confidence: high
updated: 2026-10-06
tags: [type/page, domain/atlas-ui]
---
# Trash

**Component**: `frontend/src/pages/Trash.tsx`
**Route**: `/trash` (protected, requiresAuth: true, icon `trash`, breadcrumb `Trash`). Nav: **System**.
**Last Updated**: 2026-10-06

## Purpose

The ONE surface over every shelf of the trash. A delete in this app is a move —
a retired run, a deleted agent's workspace, a file nothing claims — and this page
is where the moved things are visible, with the way back off each.

**The tabs come from the server.** They are rendered from `GET /api/v1/trash`
(the shelf registry, read out), never hand-listed, so a sixth shelf appears here
the day it is registered rather than the day someone edits this file. Each tab
carries the shelf's own count, read at that moment; a shelf with no directory
reports zero rather than vanishing.

**A tab is a view, so the URL is the shelf** (`?shelf=dbs`), written with
`replace` — Back leaves the page rather than walking the tabs visited. A stale or
unknown value falls back to the first shelf that has something on it, and the URL
is corrected rather than left claiming a surface that is not on screen.

## Key Features

- **The two verbs, honestly labelled.** **Restore** is offered only where a
  RECORD backs an entry; a shelf that never restores shows no Restore control at
  all (a column of dead buttons reads as a broken app), and on a shelf that does,
  an entry with no record keeps the button disabled with the shelf's own sentence
  as its tooltip. **Delete forever** is on every row — the per-entry dialog names
  the entry, its directory, what it holds and that nothing can restore it.
- **`Empty this shelf…`** is the bulk form of the same irreversible act, behind a
  confirmation that names the shelf, its directory and the count. Nothing is
  typed; both forms are buttons.
- **The column-variance rule, measured at render.** The shelf's own sentence about
  its entries (`note`) is hoisted into the card's blurb when every row says the
  same thing and kept as a column when they differ — which is the agents shelf,
  where a trashed agent sits beside residue. `shelfShape()` is the one place that
  measures it, so the blurb and the table cannot disagree.
- **No pruning, ever.** Nothing arrives on a shelf on its own; there is no
  retention rule and nothing is emptied on a schedule.
- Confirmations and failures go through the app's toaster
  (`useNotificationStore`), never inline alerts.

## Components Used

| Component | Path | Purpose |
|---|---|---|
| `PageContainer` / `PageBanner` / `HelpButton` | `frontend/src/components/ui/…`, `components/help` | The house page shell; help opens `wiki/help/trash.md` |
| `TrashShelfTable` | `frontend/src/components/features/trash/TrashShelfTable.tsx` | One shelf's entries: name, what it holds, size, when it was retired, and the two verbs |
| `PurgeEntryModal` | `frontend/src/components/features/trash/PurgeEntryModal.tsx` | The single-entry irreversible delete, and its confirmation |
| `EmptyShelfModal` | `frontend/src/components/features/trash/EmptyShelfModal.tsx` | Emptying a whole shelf |
| `TrashModal` | `frontend/src/components/features/trash/TrashModal.tsx` | The feature's modal shell (native `<dialog className="modal">` + house panel) |
| `TrashService` | `frontend/src/services/domain/TrashService.ts` | The client: shelves, one shelf, restore, purge, empty |

## Related

- [[atlas/api/routers/trash|Trash — API]] — the surface this page renders
- [[atlas/ui/components/features/trash/Trash Index|Trash components]]
- [[help/trash|Trash (help)]] — the user-facing account
- [[atlas/ui/pages/TestingDashboard|Testing Dashboard]] — retires runs into this trash and links here
