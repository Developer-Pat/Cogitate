---
title: BenchmarkTool
type: atlas-component
path: frontend/src/components/features/testing/BenchmarkTool.tsx
confidence: high
updated: 2026-09-14
tags: [type/component, domain/atlas-ui]
---
# BenchmarkTool

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


**Path**: `frontend/src/components/features/testing/BenchmarkTool.tsx`
**Last Updated**: 2026-08-01

## Purpose

Performance benchmarking card for the Testing Dashboard. Renders three preset benchmarks (API Response Time, Database Query, Data Processing) and lets the user run them individually or all at once, with a progress bar, per-benchmark result stats (average/min/max duration, throughput in ops/sec), a performance rating bar, and an aggregate summary block.

**The benchmarks are fully simulated client-side — there are no backend/API calls.** Each iteration generates a random duration via `Math.floor(10 + Math.random() * 90)` (10–99 ms) and waits 10 ms via `setTimeout` so the UI can update. Results are computed purely from these synthetic numbers. The component is a named export (`export const BenchmarkTool: React.FC<BenchmarkToolProps>`), not a default export.

## Props Interface

```typescript
interface BenchmarkToolProps {
  onBenchmarkComplete?: (results: BenchmarkResult[]) => void
}
```

The component also exports the result type:

```typescript
export interface BenchmarkResult {
  id: string
  name: string
  iterations: number
  averageDuration: number
  minDuration: number
  maxDuration: number
  throughput: number
  timestamp: string
  status: 'idle' | 'running' | 'completed' | 'failed'
}
```

All props are optional — `TestingDashboard` renders `<BenchmarkTool />` with no props. `onBenchmarkComplete` is invoked after a full "Run All Benchmarks" pass completes (see run behavior notes below).

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `useState` (React) | Hook | Local state: `benchmarks`, `isRunning`, `currentBenchmark`, `progress` |
| `ErrorBoundary` | Component (`frontend/src/components/ErrorBoundary.tsx`) | Wraps the whole card to catch render errors |
| DaisyUI classes (`btn`, `badge`, `progress`, `card`) | CSS framework | Styling of buttons, status badges, progress bar, and cards |
| CSS design tokens (`--card-shadow`, `--card-radius`, `--card-padding`, `--card-gap`, `--button-radius`, `--button-padding`, `--button-transition`) | CSS variables | Theming consistent with the rest of the UI atlas |

No stores, services, or fetch/axios calls are used — the component is self-contained.

## Usage Example

```tsx
import { BenchmarkTool, type BenchmarkResult } from '../components/features/testing/BenchmarkTool'

// Minimal usage (as in TestingDashboard):
<BenchmarkTool />

// With the optional completion callback:
<BenchmarkTool
  onBenchmarkComplete={(results: BenchmarkResult[]) => {
    console.log('Benchmark pass finished', results)
  }}
/>
```

## State Used

| State | Type | Purpose |
|---|---|---|
| `benchmarks` | `BenchmarkResult[]` | The three preset benchmarks; holds results and per-benchmark status after runs |
| `isRunning` | `boolean` | True while a full "Run All" pass is in progress; disables all buttons |
| `currentBenchmark` | `string` | Name of the benchmark currently executing (drives the progress bar label) |
| `progress` | `number` | 0–100 progress of the current benchmark's iteration loop |

## Related Components

- `TestingDashboard` — `frontend/src/pages/TestingDashboard.tsx` (renders `<BenchmarkTool />` in the "Performance Benchmarking" section)
- `TestSuiteManager` — `frontend/src/components/features/testing/TestSuiteManager.tsx` (sibling on the dashboard)
- `TestRunner` — `frontend/src/components/features/testing/TestRunner.tsx` (sibling on the dashboard)
- `ResultViewer` — `frontend/src/components/features/testing/ResultViewer.tsx` (sibling on the dashboard)
- `ErrorBoundary` — `frontend/src/components/ErrorBoundary.tsx` (wrapper)

## Run Behavior & Notes

- **Run single**: `runSingleBenchmark` marks the benchmark `running`, then `runBenchmark` loops `iterations` times, generating a random duration (10–99 ms) per iteration, updating `progress`, and sleeping 10 ms between iterations for UI updates. On completion it computes average/min/max duration and throughput (`(iterations / (averageDuration * iterations / 1000)) * 1000` ≈ `1,000,000 / averageDuration` ops/sec), stamps `timestamp` with `new Date().toISOString()`, and sets status to `completed` via a functional state update.
- **Run all**: `runAllBenchmarks` sets `isRunning`, then iterates the `benchmarks` array running each one sequentially (skipping any already `running`), then clears `isRunning` and calls `onBenchmarkComplete?.(benchmarks)`.
- **Reset**: `resetBenchmarks` zeroes durations/throughput, clears timestamps, and returns all statuses to `idle`.
- **Status lifecycle**: `idle → running → completed`. The `'failed'` status exists in the `BenchmarkResult` union and has a badge color in `getStatusColor`, but nothing in the component ever sets it.
- **Performance rating** (`getPerformanceRating`): avg duration < 20 ms → "Excellent", < 50 ms → "Good", < 100 ms → "Fair", else "Poor". The rating bar width is `(averageDuration / 200) * 100`%, capped at 100%.
- **Known quirk**: `onBenchmarkComplete` receives the `benchmarks` array captured in the closure at render time (the loop iterates a stale snapshot, and per-benchmark results are written with functional updates), so the callback's results are the *original* pre-run benchmark objects, not the updated ones. The summary stats block renders from live state, so it is correct; only the callback payload is stale.
