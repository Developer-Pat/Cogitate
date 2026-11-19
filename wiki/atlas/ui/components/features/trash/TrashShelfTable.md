---
title: TrashShelfTable
type: atlas-component
path: frontend/src/components/features/trash/TrashShelfTable.tsx
confidence: high
updated: 2026-10-06
tags: [type/component, domain/atlas-ui]
---

# TrashShelfTable

**Path**: `frontend/src/components/features/trash/TrashShelfTable.tsx`

## Purpose

One shelf's entries, and the two verbs that are true of them: what the entry is,
what it holds, how big and how old it is, and **Restore** / **Delete forever**.

**The column-variance rule is applied here rather than assumed.** A column that
reads one value on every live row carries nothing, so the shelf's own sentence
about its entries (`note`) is MEASURED at render: on four shelves it is one string
repeated down the column (hoisted into the card's blurb instead), and on the agents
shelf it differs — a trashed agent beside residue — so it stays a column. The
measurement lives in one exported place, `shelfShape()`, which returns
`{sharedNote, mixedStates}` so the page's blurb and this table cannot disagree
about what is shared.

**Two levels of Restore refusal, both stated rather than shown as a dead button:**

- a shelf that never restores (`listing.restorable === false`) gets **no Restore
  control at all** — a column of disabled buttons reads as a broken app, and the
  blurb already says why this shelf has no way back;
- on a shelf that does restore, an entry with no record keeps the button
  **disabled**, with the shelf's own sentence as its tooltip.

**Delete forever is on every row** and never disabled: the irreversible act is
always reachable by a person who asks for it.

`holds()` keeps the "Holds" cell honest in the space a cell has: a folder of three
files reads as its names, a retired backup holding fifteen reads as a count (with
the names on the title as a convenience). The entry's NAME is the access path to
knowing what a thing is.

## Props Interface

```typescript
interface TrashShelfTableProps {
  listing: TrashListing | null
  isLoading: boolean
  /** The entry whose Restore is in flight — that row says so, the others do not. */
  busyName: string | null
  onRestore: (entry: TrashEntry) => void
  onPurge: (entry: TrashEntry) => void
}
```

## Related

- [[atlas/ui/pages/Trash|Trash page]] — the page that owns the calls
- [[atlas/ui/components/features/trash/PurgeEntryModal|PurgeEntryModal]] — where Delete forever leads
