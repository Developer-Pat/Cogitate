---
title: TestSuiteManager
type: atlas-component
path: frontend/src/components/features/testing/TestSuiteManager.tsx
confidence: high
updated: 2026-09-14
tags: [type/component, domain/atlas-ui]
---
# TestSuiteManager

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


**Path**: `frontend/src/components/features/testing/TestSuiteManager.tsx`
**Last Updated**: 2026-08-01

## Purpose

`TestSuiteManager` is the left-column test management panel of the Testing Dashboard. It renders a searchable, tag-filterable list of test suites and exposes two actions per suite: **View** (delegated to the parent via `onSuiteSelect`) and **Run** (delegated via `onSuiteRun`, with local status simulation). The component is fully client-side: the suite list is seeded from hardcoded local state, and "running" a suite only mutates local React state — there is no backend, API, or store involvement. Note that this component has **no suite creation UI**; suites exist only as seed data in local state. It is a named export (`export const TestSuiteManager`), not a default export.

## Props Interface

```typescript
interface TestSuiteManagerProps {
  onSuiteSelect?: (suite: TestSuite) => void
  onSuiteRun?: (suite: TestSuite) => void
}
```

The component also exports the `TestSuite` data type used by its props and by sibling components:

```typescript
export interface TestSuite {
  id: string
  name: string
  description: string
  testCount: number
  lastRun?: string
  status: 'idle' | 'running' | 'passed' | 'failed'
  tags: string[]
}
```

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `useState` (React) | Hook | Local state for the suite list, search term, and tag filter |
| `ErrorBoundary` (`../../ErrorBoundary` → `frontend/src/components/ErrorBoundary.tsx`) | Component | Wraps the whole panel so render errors are caught and surfaced instead of crashing the dashboard |

The component imports nothing else — no services, stores, or custom hooks. All data is hardcoded seed state; all run logic is a local `setTimeout` simulation.

## Usage Example

Used by the Testing Dashboard page (`frontend/src/pages/TestingDashboard.tsx`), which wires both callbacks to local state:

```tsx
import { useState } from 'react'
import { TestSuiteManager, type TestSuite } from '../components/features/testing/TestSuiteManager'

const [selectedSuite, setSelectedSuite] = useState<TestSuite | undefined>()

const handleSuiteSelect = (suite: TestSuite) => setSelectedSuite(suite)
const handleSuiteRun = (suite: TestSuite) => setSelectedSuite(suite)

<TestSuiteManager
  onSuiteSelect={handleSuiteSelect}
  onSuiteRun={handleSuiteRun}
/>
```

## State Used

- `suites: TestSuite[]` — seeded in the `useState` initializer with 4 hardcoded suites (unit, integration, benchmark/load, and API suites, with test counts 45/23/12/34, `lastRun` ISO timestamps, and statuses `passed`, `passed`, `idle`, `failed`). Mutated only by `handleRunSuite`.
- `searchTerm: string` — free-text filter; matches suite `name` or `description` (case-insensitive).
- `selectedTag: string` — tag filter, default `'all'`; `allTags` is derived from the union of all suite tags.

Run behavior (`handleRunSuite`): the target suite's status is set to `'running'` and `onSuiteRun?.(suite)` is invoked; a `setTimeout` (2000 ms) then flips the status to `'passed'` with ~80% probability (`Math.random() > 0.2`) or `'failed'`, and stamps `lastRun` with the current ISO time. The Run button is disabled and shows a spinner while `status === 'running'`.

Filtering: `filteredSuites` combines the search and tag predicates; an empty result renders a "No test suites found matching your criteria." message.

Status rendering: `getStatusColor` maps status to a DaisyUI badge class (`badge-warning`/`badge-success`/`badge-error`/`badge-neutral`); `getStatusText` maps status to a label (`Running`/`Passed`/`Failed`/`Idle`). Styling uses DaisyUI classes plus design-token CSS custom properties (`var(--card-*)`, `var(--form-input-*)`, `var(--button-*)`).

## Related Components

- `frontend/src/pages/TestingDashboard.tsx` — parent page; renders `TestSuiteManager` in the left column and passes `onSuiteSelect`/`onSuiteRun` handlers that set `selectedSuite` for the runner.
- `frontend/src/components/features/testing/TestRunner.tsx` — sibling; imports the `TestSuite` type from this module and consumes the selected suite.
- `frontend/src/components/features/testing/ResultViewer.tsx` — sibling on the dashboard; shows results produced by the runner.
- `frontend/src/components/features/testing/BenchmarkTool.tsx` — sibling on the dashboard; independent benchmarking panel.
- `frontend/src/components/ErrorBoundary.tsx` — shared error boundary wrapping this component (and the dashboard).
