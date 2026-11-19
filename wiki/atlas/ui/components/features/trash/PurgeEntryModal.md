---
title: PurgeEntryModal
type: atlas-component
path: frontend/src/components/features/trash/PurgeEntryModal.tsx
confidence: high
updated: 2026-10-06
tags: [type/component, domain/atlas-ui]
---

# PurgeEntryModal

**Path**: `frontend/src/components/features/trash/PurgeEntryModal.tsx`

## Purpose

The confirmation for deleting ONE entry **forever** — the irreversible act, one
thing wide. Everywhere else in this app a delete is a MOVE; this is the control that
takes an entry off the trash for good.

**Buttons, not typing.** The dialog's job is to say what is about to be destroyed —
the entry by name, the shelf and directory it comes off, what it holds, and that
nothing can restore it — and then to offer the two things a person can do about it.
It does **not** ask for a typed confirmation: retyping a name already visible on the
row behind the dialog adds nothing to the decision, and the shelf's phrase would be
the wrong sentence to demand for one entry. (A typed phrase survives only where a
SERVER checks it — see [[atlas/ui/components/features/trash/EmptyShelfModal|EmptyShelfModal]]'s
note: it does not, any more.)

**The shelf's own sentence is shown, not reworded.** `entry.note` says what this is
(a trashed agent, residue, a retired backup), and on a shelf WITH a way back the
dialog points at Restore as the alternative instead of presenting destruction as the
only option.

## Props Interface

```typescript
interface PurgeEntryModalProps {
  entry: TrashEntry
  shelfLabel: string
  directory: string
  /** Whether this shelf has a way back, so the copy can point at Restore or not. */
  shelfRestorable: boolean
  pending: boolean
  /** A refusal from the server, verbatim (it is the shelf's own sentence). */
  error: string | null
  onClose: () => void
  onConfirm: () => void
}
```

## Related

- [[atlas/ui/components/features/trash/TrashShelfTable|TrashShelfTable]] — where Delete forever is pressed
- [[atlas/ui/components/features/trash/TrashModal|TrashModal]] — the shell
