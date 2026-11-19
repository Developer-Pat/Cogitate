---
title: ReportsTable
type: atlas-component
path: frontend/src/components/features/testing/ReportsTable.tsx
confidence: high
updated: 2026-09-20
tags: [type/component, domain/atlas-ui]
---
# ReportsTable

**Path**: `frontend/src/components/features/testing/ReportsTable.tsx`

## Purpose

The test runs that exist **on disk**, newest first, with an expandable detail panel per
report. It lists what actually ran — not what was requested — so a report whose counts
are missing shows as unparsed rather than as zero, and a skip keeps its REASON.

**The skip reasons are the point.** "12 tests are not running because Ollama is down" is
something a person can act on; a bare count is not.

Counts are coloured by meaning: `failed`/`error` in `text-error`, `skipped` in
`text-warning`, `passed` in `text-success`, `warnings` dimmed.

## Props Interface

```typescript
interface ReportsTableProps {
  reports: RunSummary[]
  isLoading?: boolean
  onDelete?: (run: RunSummary) => void
  runningRunId?: string | null
}
```

`runningRunId` is the run the LOCK names: that row's Delete is disabled with its reason
("it cannot be deleted while it is writing") rather than failing on click. Delete is the
page's action — this table only asks for it.

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `DetailPanel` | Local component | Fetches and renders ONE report in full when a row is expanded |
| `RunSummary` | Type | The on-disk run's summary shape, from the testing service |

## Related Components

- [[atlas/ui/components/features/testing/CatalogTable|CatalogTable]] — what COULD run; this is what DID
- [[atlas/ui/pages/TestingDashboard|TestingDashboard]] — the parent
