---
title: EmptyShelfModal
type: atlas-component
path: frontend/src/components/features/trash/EmptyShelfModal.tsx
confidence: high
updated: 2026-10-06
tags: [type/component, domain/atlas-ui]
---

# EmptyShelfModal

**Path**: `frontend/src/components/features/trash/EmptyShelfModal.tsx`

## Purpose

Emptying ONE shelf — the bulk form of the irreversible act. The per-entry Purge is
the primary way to remove something; this is how a person says "I am done with all
of these". The dialog names the shelf, its directory and how many entries go, and
offers Cancel / Delete permanently.

**Buttons, not typing — and this is a change of contract, not a detail.** Emptying
used to demand a phrase the SERVER checked ("empty the databases trash"). The phrase
is out of the product: it was the wrong sentence for the neighbouring case (removing
ONE entry), and at best a speed bump for this one, because a sentence read off the
dialog in front of you and typed back adds nothing to a decision already made. The
server-side check went with it — `empty` takes no phrase — so the guard is now the
act itself: an irreversible removal asked for deliberately, in a dialog that says
what it takes.

**A shelf that cannot restore says so**, because "you can put them back
individually" is only true where a record exists — and on the reports, dbs and misc
shelves it does not.

## Props Interface

```typescript
interface EmptyShelfModalProps {
  shelfLabel: string
  directory: string
  /** How many entries go, so the number is on screen before the act. */
  count: number
  restorable: boolean
  pending: boolean
  error: string | null
  onClose: () => void
  onConfirm: () => void
}
```

## Related

- [[atlas/ui/pages/Trash|Trash page]] — where `Empty this shelf…` lives
- [[atlas/ui/components/features/trash/TrashModal|TrashModal]] — the shell
