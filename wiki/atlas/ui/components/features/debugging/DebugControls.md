---
title: DebugControls
type: atlas-component
path: frontend/src/components/features/debugging/DebugControls.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# DebugControls

**Path**: `frontend/src/components/features/debugging/DebugControls.tsx`
**Last Updated**: 2026-08-01

## Purpose

Debug controls panel shown inside the Debugging page's "Debug Actions" tab. It lists available debug actions (grouped by category), lets the user execute them with live status badges and per-action result feedback, and exposes a toggle for enabling/disabling debug breakpoints.

Key behaviors:

- Loads the action list from `debugActionsService` on mount and **fails loudly** (re-throws) if the backend is unavailable, logging an explicit error that `GET /api/v1/debug/actions` must be implemented.
- Subscribes to action-list and status updates from the service (unsubscribes on unmount).
- Renders a confirmation modal before executing actions that `requiresConfirmation` (with extra warning copy for `dangerous` actions).
- Shows a "Quick Actions Summary" counting actions per status (`idle`/`running`/`completed`/`failed`/`cancelled`).
- Displays a "Mock Actions - Coming Soon" badge and warning alert — actions currently execute with simulated results until real backend integration lands.
- Named export (`export const DebugControls`), not a default export.

## Props Interface

```typescript
interface DebugControlsProps {
  onActionExecute?: (action: DebugAction) => void
  onBreakpointToggle?: (enabled: boolean) => void
}
```

> Note: `DebugControlsProps` is **not exported** from the module. `DebugAction` is imported from `frontend/src/services/domain/DebugActionsService.ts`:
>
> ```typescript
> export interface DebugAction {
>   id: string
>   name: string
>   description: string
>   category: DebugActionCategory // 'system' | 'performance' | 'diagnostic' | 'maintenance'
>   requiresConfirmation: boolean
>   dangerous: boolean
>   endpoint?: string
>   method?: 'POST' | 'DELETE' | 'PUT' | 'GET'
>   enabled: boolean
> }
> ```

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `useState`, `useEffect` | React hooks | Local UI state (actions, breakpoints, modal, results, loading) and lifecycle wiring (load on mount, subscribe, cleanup on unmount) |
| `ErrorBoundary` | Component (`../../ErrorBoundary`, i.e. `frontend/src/components/ErrorBoundary`) | Wraps both the loading and main card renders so render errors are contained |
| `debugActionsService`, `DebugAction`, `DebugActionStatus`, `ActionResult` | Domain service + types (`../../../services/domain/DebugActionsService.ts`) | Lists debug actions (`loadActions`), executes them (`executeAction`), queries per-action status (`getActionStatus`), and pushes updates via `subscribe` / `subscribeToStatus` |
| `frontendLoggingService` | Frontend logging service (`../../../services/frontendLoggingService`) | Structured `info` / `debug` / `error` logging for mount, unmount, action execution, breakpoint toggling, and backend failures |

## Usage Example

As used by the hosting page `frontend/src/pages/Debugging.tsx` (rendered inside the "actions" tab):

```tsx
import { DebugControls } from '../components/features/debugging/DebugControls'

<DebugControls
  onActionExecute={handleActionExecute}
  onBreakpointToggle={handleBreakpointToggle}
/>
```

## State Used

All state is local (`useState`) — the component does not use global stores (no Zustand/Redux):

| State | Type | Purpose |
| --- | --- | --- |
| `actions` | `DebugAction[]` | Action list, updated from the `debugActionsService.subscribe` callback |
| `breakpointsEnabled` | `boolean` | Whether debug breakpoints are enabled; toggled by the checkbox and reported via `onBreakpointToggle` |
| `selectedAction` | `DebugAction \| null` | Action awaiting confirmation in the modal |
| `showConfirmation` | `boolean` | Whether the confirmation modal is open |
| `actionResults` | `Record<string, ActionResult>` | Per-action execution results keyed by action id, shown as success/error alerts |
| `isLoading` | `boolean` | True until the first actions update arrives; shows a spinner while loading |

The service (`DebugActionsService`) owns the authoritative action list, per-action status map, and history; the component mirrors the list into local state via subscription.

## Related Components

- `frontend/src/pages/Debugging.tsx` — hosting page; renders `DebugControls` in the "Debug Actions" tab and supplies the `onActionExecute` / `onBreakpointToggle` callbacks.
- `frontend/src/components/ErrorBoundary` — error boundary wrapping the component's render output.
- Sibling components in `frontend/src/components/features/debugging/`: `TraceControls.tsx`, `LogViewer.tsx`, `CognitiveTraceViewer.tsx`, `BackendTraceViewer.tsx`, `TraceAnalysis.tsx`, `SystemDiagnostics.tsx`, `ErrorAnalysis.tsx`, `LiveMonitoring.tsx`, `DatabaseTools.tsx` — other panels of the Debugging feature.
