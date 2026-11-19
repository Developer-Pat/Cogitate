---
title: Components — features/trash
type: atlas-index
path: frontend/src/components/features/trash
confidence: high
updated: 2026-10-06
tags: [type/index, domain/atlas-ui]
---

# Components — features/trash

The trash page's components: the shelf table, the shell every dialog here is built
on, and the two confirmations for the one irreversible act in the app.

**One rule runs through all four:** the page renders what the SERVER said. The
shelves, the counts, whether an entry can be restored, and the shelf's own
sentence about what an entry is — all read from `/api/v1/trash`, none re-derived
here.

## Inventory

- [[atlas/ui/components/features/trash/TrashShelfTable|TrashShelfTable]] — one shelf's entries, and the two verbs
- [[atlas/ui/components/features/trash/TrashModal|TrashModal]] — the modal shell (native `<dialog className="modal">` + house panel)
- [[atlas/ui/components/features/trash/PurgeEntryModal|PurgeEntryModal]] — delete ONE entry forever
- [[atlas/ui/components/features/trash/EmptyShelfModal|EmptyShelfModal]] — empty a whole shelf

## Related

- [[atlas/ui/pages/Trash|Trash page]] — the page that composes them
- [[atlas/api/routers/trash|Trash — API]] — the surface they read and act through
