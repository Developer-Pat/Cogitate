---
title: Components — features/testing
type: atlas-index
path: frontend/src/components/features/testing
confidence: stub
updated: 2026-09-20
tags: [type/index, domain/atlas-ui]
---

# Components — features/testing

The testing components — the table, the reports list, and the detail modal behind
the user-testing page. Every number the page shows comes from a file: the catalog
is DERIVED from the test tree and the reports are READ from disk.

## Inventory

- [[atlas/ui/components/features/testing/CatalogTable|CatalogTable]] — the derived test catalog: tick, view, run
- [[atlas/ui/components/features/testing/LiveRunPanel|LiveRunPanel]] — the run in progress
- [[atlas/ui/components/features/testing/ReportsTable|ReportsTable]] — the reports on disk
- [[atlas/ui/components/features/testing/TestDetailsModal|TestDetailsModal]] — one module in full
- [[atlas/ui/components/features/testing/DeleteRunModal|DeleteRunModal]] — the delete confirmation

## Removed

The simulation-era components — `TestSuiteManager`, `TestRunner`, `ResultViewer`,
`BenchmarkTool`. They rendered hardcoded suite data and an animated progress bar over
it, so the page FABRICATED its results. Their pages are kept as removal records.

**The trash view** — `TrashView` and `EmptyTrashModal` — lived here while this page
owned the runs shelf. Both retired with `/testing/trash*`: the shelf view became
[[atlas/ui/pages/Trash|the trash page]] (one surface over all five shelves), the
typed-phrase empty became
[[atlas/ui/components/features/trash/EmptyShelfModal|EmptyShelfModal]] and the runs'
`confirmation_phrase` went out of the API with it.
