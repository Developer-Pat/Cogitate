---
title: ExecutionControls
type: atlas-component
path: frontend/src/components/features/workflowExecution/ExecutionControls.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ExecutionControls

**Path**: `frontend/src/components/features/workflowExecution/ExecutionControls.tsx`
**Last Updated**: 2026-08-01

## Purpose
Workflow execution control buttons — Start/Pause/Resume/Stop driven by execution state, with appropriate enable/disable and status display.

## Props Interface
```typescript
interface ExecutionControlsProps {
  execution?: WorkflowExecution | null
  isExecuting: boolean
  onStart: () => void
  onPause: () => void
  onStop: () => void
  onResume: () => void
  className?: string
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| WorkflowExecution | types/workflows | Execution state |

## Usage Example
```tsx
<ExecutionControls execution={exec} isExecuting={running} onStart={start} onPause={pause} onStop={stop} onResume={resume} />
```

## State Used
None — fully controlled.

## Related Components
- features/workflowExecution/WorkflowRunner.tsx — run orchestration
- features/workflowExecution/ProgressTracker.tsx — progress display
- features/workflowExecution/ResultViewer.tsx — results display