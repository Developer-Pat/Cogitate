---
title: LiveRunPanel
type: atlas-component
path: frontend/src/components/features/testing/LiveRunPanel.tsx
confidence: high
updated: 2026-09-20
tags: [type/component, domain/atlas-ui]
---

# LiveRunPanel

**Path**: `frontend/src/components/features/testing/LiveRunPanel.tsx`

## Purpose

The Run tab's face: what a running test suite has done, what it found, and what it is
saying right now. Presentational — it renders the fold of the run's own event stream
(`utils/runFeed.ts`, supplied by `useRunStream`) and fetches nothing.

Four rules are baked into the markup:

1. **Counted, never percentage-ed.** `312 of 1,190` against pytest's own collected
   total — no bar, no percentage, no ETA. Until the total arrives the number is shown
   as a count and no fraction is claimed.
2. **The counts say which count they are** — the live count while the run goes, or
   pytest's own final tally once it has a `summary`. Silently swapping one for the
   other is how a number becomes a claim.
3. **Watch-only when it is not ours.** A run the page did not start is shown live with
   **no Cancel**, and says who did start it (the lock's `origin` and pid).
4. **The cap is stated.** The per-test lines are capped in view and the panel names how
   many it is not showing; the run's own file holds them all.

Skips and failures are shown WITH their reason — "needs Ollama" is actionable where
"skipped" is not. The `ui` (vitest) group gets an explicit note instead of an empty
feed, because its per-test lines are pytest's alone.

## Props Interface

```typescript
interface LiveRunPanelProps {
  feed: RunFeed
  status: StreamStatus
  runId: string | null
  lock: RunLockInfo | null
  selection: { files: number; tests: number; label: string }
  canCancel: boolean
  cancelPending: boolean
  cancelNote: string | null
  cancelTone: 'ok' | 'warn' | 'plain'
  onCancel: () => void
}
```

`runId === null` renders the idle state, which states what Run would start.
`cancelTone` carries how loudly the cancel's outcome is said: a stop that worked is
`ok`, survivors or someone else's run is `warn`, and "it had already finished when
Cancel was clicked" is `plain` — not a warning.

## Related

- [[atlas/ui/pages/TestingDashboard|Testing Dashboard]] — the page that composes it
- [[atlas/ui/hooks/useRunStream|useRunStream]] — where the feed comes from
