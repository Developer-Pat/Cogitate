---
title: ResultViewer
type: atlas-component
path: frontend/src/components/features/testing/ResultViewer.tsx
confidence: high
updated: 2026-09-14
tags: [type/component, domain/atlas-ui]
---
# ResultViewer

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


**Path**: `frontend/src/components/features/testing/ResultViewer.tsx`
**Last Updated**: 2026-08-01

## Purpose

Displays test results produced by the Testing Dashboard's `TestRunner` component. It renders a summary header (total tests, success rate, average duration, passed/failed counts), a scrollable, filterable list of individual test results (status icon + color-coded badge, name, timestamp, duration, inline error), and a detail modal opened by clicking a result. A dropdown Export menu downloads the results as JSON or CSV — either via an optional `onExport` callback prop or, when no callback is provided, a built-in fallback that generates a Blob and triggers a browser download.

The Testing Dashboard is **fully client-side**: `TestRunner` fabricates results with `Math.random()` + `setTimeout` (no network/API calls exist anywhere in the testing feature), and results flow down to this component via React state/props. This component is a **named export** (`export const ResultViewer`), not a default export. Note it is distinct from the unrelated default-export `ResultViewer` under `features/workflowExecution/`.

## Props Interface

```typescript
interface ResultViewerProps {
  results: TestResult[]
  onExport?: (format: 'json' | 'csv') => void
}
```

The `TestResult` shape (imported as a type from `./TestRunner`, where it is defined):

```typescript
export interface TestResult {
  id: string
  name: string
  status: 'running' | 'passed' | 'failed' | 'skipped'
  duration?: number
  error?: string
  timestamp: string
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `useState` (from `react`) | Hook | Local UI state: `selectedResult` (detail modal) and `filterStatus` (list filter) |
| `ErrorBoundary` (`../../ErrorBoundary`) | Component | Wraps the entire card so render errors in the viewer don't crash the page |
| `TestResult` (`./TestRunner`) | Type-only import | Defines the shape of each entry in `results`; no runtime dependency |

No hooks/services/stores are used — all data comes in via the `results` prop. Export uses browser APIs only (`Blob`, `URL.createObjectURL`, programmatic anchor click).

## Usage Example

As used by the parent page (`frontend/src/pages/TestingDashboard.tsx`):

```tsx
import { useState } from 'react'
import { TestRunner, type TestResult } from '../components/features/testing/TestRunner'
import { ResultViewer } from '../components/features/testing/ResultViewer'

export default function TestingDashboard() {
  const [testResults, setTestResults] = useState<TestResult[]>([])

  const handleTestComplete = (results: TestResult[]) => {
    setTestResults(results)
  }

  return (
    <>
      <TestRunner selectedSuite={selectedSuite} onTestComplete={handleTestComplete} />
      <ResultViewer results={testResults} />
    </>
  )
}
```

With a custom export handler (overrides the built-in Blob download):

```tsx
<ResultViewer
  results={results}
  onExport={(format) => {
    // format: 'json' | 'csv' — e.g. POST to a backend or show a toast
  }}
/>
```

## State Used

Local state only (all internal to the component):

| State | Type | Purpose |
|---|---|---|
| `selectedResult` | `TestResult \| null` | The result currently shown in the detail modal; set on card click, cleared by the Close button |
| `filterStatus` | `'all' \| 'passed' \| 'failed' \| 'running'` | Status filter for the results list, controlled by the dropdown (note: `'skipped'` results are only visible under `'all'` since the filter has no skipped option) |

Derived values (`passedCount`, `failedCount`, `runningCount`, `totalCount`, `successRate`, `averageDuration`) are computed inline on each render — no additional state.

## Export / Download Behavior

The Export dropdown offers **Export as JSON** and **Export as CSV**. If the `onExport` prop is set, it is called with the chosen format and no download happens. Otherwise the fallback runs:

- **JSON**: `{ summary: { total, passed, failed, running, successRate, averageDuration }, results }` serialized pretty-printed, downloaded as `test-results-YYYY-MM-DD.json` (`application/json`).
- **CSV**: rows with headers `Test Name, Status, Duration (ms), Timestamp, Error`, downloaded as `test-results-YYYY-MM-DD.csv` (`text/csv`). Name/error fields are quoted.

Both use `Blob` → `URL.createObjectURL` → programmatic `<a download>` click → `URL.revokeObjectURL`. There is **no copy-to-clipboard** functionality in this component.

## Related Components

- `frontend/src/pages/TestingDashboard.tsx` — parent page; owns `testResults` state and renders the viewer without `onExport`
- `frontend/src/components/features/testing/TestRunner.tsx` — produces the `TestResult[]` passed as `results`; defines the `TestResult` type
- `frontend/src/components/features/testing/TestSuiteManager.tsx` — sibling; selects/creates the suite the runner executes
- `frontend/src/components/features/testing/BenchmarkTool.tsx` — sibling; separate benchmarking section on the same page
- `frontend/src/components/ErrorBoundary.tsx` — error boundary wrapper
- `frontend/src/components/features/workflowExecution/ResultViewer.tsx` — **different** component with the same name (default export, workflow-execution results); do not confuse the two
