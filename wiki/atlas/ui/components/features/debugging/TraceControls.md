---
title: TraceControls
type: atlas-component
path: frontend/src/components/features/debugging/TraceControls.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# TraceControls

**Path**: `frontend/src/components/features/debugging/TraceControls.tsx`
**Last Updated**: 2026-08-01

## Purpose

Runtime control panel for flow tracing. It lets the user enable/disable trace logging at runtime without a page reload:

- **Enable Tracing** — master switch for all trace logging (OFF by default to prevent log flooding).
- **Enable Flow Traces** — per-flow trace event logging (requires Enable Tracing to be ON).
- **Trace Sampling Rate** — percentage of traces to log (100% = all traces), rendered as a 0–100 slider mapped to a 0.0–1.0 rate.
- **Reset to Defaults** — restores the logging configuration via `loggingConfigService.reset()`.
- **Status Indicator** — live readout: "Tracing Active", "Tracing Enabled (Flow Traces OFF)", or "Tracing Disabled".
- **How to Use** — collapsible usage tips (default state, enable steps, when to use, trace log format `[FLOW TRACE #N]`).

All changes are applied immediately by writing through the `loggingConfigService` singleton. Note: this component is a configuration panel (toggles/slider/reset), not a record/stop/clear capture widget — there are no record/stop/clear buttons and no log-level selectors in the source.

## Props Interface

```typescript
interface TraceControlsProps {
  onConfigChange?: (config: TraceConfig) => void
}

interface TraceConfig {
  enableTracing: boolean
  enableFlowTraces: boolean
  traceSamplingRate: number
}
```

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `loggingConfigService` (`../../../services/domain/LoggingConfigService`) | Singleton service | Source of truth for logging config; `getConfig()` hydrates state on mount, `updateConfig()` persists changes, `reset()` restores defaults |
| `frontendLoggingService` (`../../../services/frontendLoggingService`) | Singleton service | Emits `info` log entries when trace config is updated or reset |
| `useState`, `useEffect` | React hooks | Local `TraceConfig` state; `useEffect` loads the current config once on mount |

## Usage Example

```tsx
import { TraceControls } from '../../../components/features/debugging/TraceControls'
import type { TraceConfig } from '../../../components/features/debugging/TraceControls'

const handleTraceConfigChange = (config: TraceConfig) => {
  // React to trace config changes (e.g., refresh trace views)
}

// Rendered inside the Debugging page's "Trace Analysis" tab:
<TraceControls onConfigChange={handleTraceConfigChange} />
```

## State Used

- Local `config: TraceConfig` via `useState`, initialized to `{ enableTracing: false, enableFlowTraces: false, traceSamplingRate: 1.0 }`.
- Hydrated once on mount from `loggingConfigService.getConfig()` inside a `useEffect` with an empty dependency array.
- `updateConfig(updates)` merges partial updates into local state, persists the full config to `loggingConfigService.updateConfig()`, logs the change via `frontendLoggingService.info('TraceControls', ...)`, then notifies the parent via `onConfigChange?.(newConfig)`.
- `resetToDefaults()` calls `loggingConfigService.reset()`, re-reads defaults with `getConfig()`, updates local state, logs the reset, then calls `onConfigChange?.(config)` — note it passes the pre-reset `config` value from the render closure rather than the freshly reset defaults.
- UI state derived from config: the Flow Traces toggle is disabled unless `enableTracing` is true; the sampling slider is disabled unless both `enableTracing` and `enableFlowTraces` are true; the status indicator derives its text/color from both booleans.

## Related Components

- `frontend/src/pages/Debugging.tsx` — host page; renders `<TraceControls onConfigChange={handleTraceConfigChange} />` inside the "Trace Analysis" tab
- `frontend/src/components/features/debugging/TraceAnalysis.tsx` — sibling shown alongside TraceControls in the same tab; displays the captured trace logs (`[FLOW TRACE #N]` prefix)
- `frontend/src/components/features/debugging/LiveMonitoring.tsx`, `DatabaseTools.tsx`, `BackendTraceViewer.tsx` — sibling debugging components on the Debugging page
