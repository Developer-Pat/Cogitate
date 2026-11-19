---
title: TestRunner
type: atlas-component
path: frontend/src/components/features/testing/TestRunner.tsx
confidence: high
updated: 2026-09-14
tags: [type/component, domain/atlas-ui]
---
# TestRunner

> **REMOVED.** This component no longer exists in the codebase, and this
> page is kept as a **removal record** — the history of what the simulation-era
> Testing Dashboard was built from.
>
> **Why.** The user-testing page was rebuilt from a SIMULATION into a real page. The
> four components documented alongside this one (`TestSuiteManager`, `TestRunner`,
> `ResultViewer`, `BenchmarkTool`) rendered hardcoded suite data and an animated
> progress bar over it — the page fabricated its results. The rebuild replaced them
> with a catalog DERIVED from the test tree and reports READ from disk, so every
> number on the page now comes from a file.
>
> **Successors:** `frontend/src/components/features/testing/CatalogTable.tsx`,
> `ReportsTable.tsx`, `TestDetailsModal.tsx`, over
> `backend/app/domain/testing/catalog.py` and `reports.py`.


**Path**: `frontend/src/components/features/testing/TestRunner.tsx`
**Last Updated**: 2026-08-01

## Purpose
Runs a selected test suite and reports per-test results (running/passed/failed/skipped with duration + error). Wrapped in ErrorBoundary. Fully client-side (part of the simulated Testing Dashboard).

## Props Interface
```typescript
interface TestResult {
  id: string
  name: string
  status: 'running' | 'passed' | 'failed' | 'skipped'
  duration?: number
  error?: string
  timestamp: string
}

interface TestRunnerProps {
  selectedSuite?: TestSuite    // from TestSuiteManager
  onTestComplete?: (results: TestResult[]) => void
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| ErrorBoundary | components/ErrorBoundary.tsx | Error containment |
| TestSuite | TestSuiteManager type | Suite data |

## Usage Example
```tsx
<TestRunner selectedSuite={suite} onTestComplete={setResults} />
```

## State Used
- results (TestResult[]), running state — local

## Related Components
- features/testing/TestSuiteManager.tsx — suite source
- features/testing/ResultViewer.tsx — results display
- pages/TestingDashboard.tsx — owner