---
title: ErrorBoundary
type: atlas-component
path: frontend/src/components/ErrorBoundary.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ErrorBoundary

**Path**: `frontend/src/components/ErrorBoundary.tsx`
**Last Updated**: 2026-08-01

## Purpose

Class-based React error boundary that catches runtime errors thrown anywhere in its child component tree, logs them via the frontend logging service, and renders a fallback UI instead of letting the whole app crash. Used app-wide to wrap route pages (Dashboard, TestingDashboard, ProviderModelsBrowser, AgentInteraction, Debugging, Logs, AgentProfiles, WorkflowExecution) as well as feature components (testing, debugging panels). Also exports `ApiErrorBoundary` (a variant that only catches HTTP/Network errors and renders a connection-error alert) and `useErrorHandler` (a hook that logs errors with context and surfaces a warning).

## Props Interface

```typescript
interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}
```

- `children` — the component tree to wrap and protect.
- `fallback` — optional custom fallback UI rendered when an error is caught. When omitted, the built-in error card is shown.
- `onError` — optional callback invoked from `componentDidCatch` with the error and its `ErrorInfo`, after logging and state updates.

## Dependencies

| Dependency | Type | Purpose |
| --- | --- | --- |
| `react` (`Component`, `ErrorInfo`, `ReactNode`) | library | Base class, types, and lifecycle methods (`getDerivedStateFromError`, `componentDidCatch`) |
| `react-router-dom` (`Link`) | library | "Go Home" button in the built-in fallback UI navigates to `/` |
| `frontendLoggingService` (`../services/frontendLoggingService`) | internal service | Logs caught errors (`error` level with `componentStack`) in `componentDidCatch`; also used by `useErrorHandler` (`error` + `warning` levels) |

## Usage Example

```tsx
import { ErrorBoundary } from '../components/ErrorBoundary';

function App() {
  return (
    <ErrorBoundary
      fallback={<p>Something broke on this page.</p>}
      onError={(error, errorInfo) => {
        // custom reporting, e.g. send to analytics
      }}
    >
      <Dashboard />
    </ErrorBoundary>
  );
}
```

## State Used

```typescript
interface State {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
}
```

- `hasError` — set to `true` by `getDerivedStateFromError` (static, runs during render) so the fallback UI renders.
- `error` — the caught error, stored by `getDerivedStateFromError` and also via `setState` in `componentDidCatch`; displayed in a `mockup-code` block when `import.meta.env.DEV`.
- `errorInfo` — set in `componentDidCatch`; carries `componentStack`, shown in dev mode.

Recovery actions: `handleReset` clears `hasError`/`error`/`errorInfo` ("Try Again" button re-renders children), `handleReload` calls `window.location.reload()` ("Reload Page").

## Related Components

- `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/TestingDashboard.tsx`, `frontend/src/pages/ProviderModelsBrowser.tsx`, `frontend/src/pages/AgentInteraction.tsx`, `frontend/src/pages/Debugging.tsx`, `frontend/src/pages/Logs.tsx`, `frontend/src/pages/AgentProfiles.tsx`, `frontend/src/pages/WorkflowExecution.tsx` — pages wrapped by `ErrorBoundary`.
- `frontend/src/components/features/testing/CatalogTable.tsx`, `ReportsTable.tsx`, `TestDetailsModal.tsx` (the simulation-era `TestSuiteManager.tsx`, `TestRunner.tsx`, `ResultViewer.tsx`, `BenchmarkTool.tsx` are REMOVED) and `frontend/src/components/features/debugging/LiveMonitoring.tsx`, `SystemDiagnostics.tsx`, `TraceAnalysis.tsx`, `LogViewer.tsx`, `DebugControls.tsx`, `ErrorAnalysis.tsx` — feature components using the error boundary.
- `frontend/src/components/ErrorDisplay.tsx` — companion error/display component.
- `frontend/src/components/__tests__/ErrorBoundary.test.tsx` — unit tests.
- `frontend/src/services/frontendLoggingService.ts` — logging service used to record caught errors.
