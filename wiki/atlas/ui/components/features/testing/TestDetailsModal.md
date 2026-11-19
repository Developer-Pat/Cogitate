---
title: TestDetailsModal
type: atlas-component
path: frontend/src/components/features/testing/TestDetailsModal.tsx
confidence: high
updated: 2026-09-14
tags: [type/component, domain/atlas-ui]
---
# TestDetailsModal

**Path**: `frontend/src/components/features/testing/TestDetailsModal.tsx`

## Purpose

One test module in full: its description, its cluster and tab, its time class with the
REASON (not just the label), the markers it declares, and its last known result when one
exists.

The time class is carried with its explanation — "short" alone invites the reading "fast
on my machine", which is the claim the tier model exists to avoid. The tiers describe
DEPENDENCY, so the modal states the dependency.

Uses the supported `modal-box` size (`max-w-2xl`–`6xl`); the smaller `max-w-*` sizes
render at 8px, see the modal dialogs dev note.

## Props Interface

```typescript
interface TestDetailsModalProps {
  entry: CatalogEntry
  lastResult?: { status: 'passed' | 'failed' | 'skipped'; when: string; note?: string } | null
  onClose: () => void
}
```

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `CatalogEntry` | Type | The row being shown in full |
| `Row` | Local component | The label/value pair, so every field is laid out identically |

## Related Components

- [[atlas/ui/components/features/testing/CatalogTable|CatalogTable]] — opens this via `onView`
- [[atlas/ui/pages/TestingDashboard|TestingDashboard]] — the parent; owns the open entry
