---
title: CatalogTable
type: atlas-component
path: frontend/src/components/features/testing/CatalogTable.tsx
confidence: high
updated: 2026-09-20
tags: [type/component, domain/atlas-ui]
---
# CatalogTable

**Path**: `frontend/src/components/features/testing/CatalogTable.tsx`

## Purpose

The test catalog as a selectable table — one row per test MODULE, with its derived
description, its cluster, its time class and its tab. Presentational only: it owns no
state and fetches nothing. Selection, the view action and the run action are all
lifted to the parent page through callbacks, which is what lets the page own the run
lock and the modal.

The two badge maps are the column's whole vocabulary:

| time class | badge | meaning |
| --- | --- | --- |
| `short` | `badge-success` | no I/O, pure logic |
| `medium` | `badge-info` | local I/O — database, filesystem, the app itself |
| `variable` | `badge-warning` | depends on an external service |

| tab | badge |
| --- | --- |
| `runnable` | none (the default state needs no decoration) |
| `conditional` | `badge-warning` |
| `quarantine` | `badge-ghost` |

## Props Interface

```typescript
interface CatalogTableProps {
  entries: CatalogEntry[]
  selected: Set<string>
  onToggle: (path: string) => void
  onToggleAll: () => void
  onView: (entry: CatalogEntry) => void
  onRun: (entry: CatalogEntry) => void
  runBlocked?: string | null
  isLoading?: boolean
}
```

`runBlocked` is why a Run cannot start right now — the LOCK's own sentence when a run
holds it, or the profile's answer when the view is empty. Each row's Run is DISABLED
while it is set and carries the reason as its tooltip rather than failing on click.

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `CatalogEntry` | Type | The derived row shape, from the testing service |
| `Tooltip` | Component | Every control carries one — including wrapping a disabled control so its reason is still hoverable |

## Related Components

- [[atlas/ui/components/features/testing/TestDetailsModal|TestDetailsModal]] — opened by `onView`
- [[atlas/ui/pages/TestingDashboard|TestingDashboard]] — the parent; owns selection and the modal
