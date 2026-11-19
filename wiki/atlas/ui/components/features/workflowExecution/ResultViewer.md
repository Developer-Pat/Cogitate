---
title: ResultViewer (workflowExecution)
type: atlas-component
path: frontend/src/components/features/workflowExecution/ResultViewer.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ResultViewer (workflowExecution)

**Path**: `frontend/src/components/features/workflowExecution/ResultViewer.tsx`
**Last Updated**: 2026-08-01

## Purpose
Workflow execution results viewer — tabs for Outputs / Logs / Steps, expandable log entries, copy actions via frontendLoggingService.

## Props Interface
```typescript
interface ResultViewerProps {
  execution: WorkflowExecution
  className?: string
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| WorkflowExecution | types/workflows | Execution data |
| frontendLoggingService | Service | Copy/log actions |

## Usage Example
```tsx
<ResultViewer execution={exec} />
```

## State Used
- activeTab ('outputs' | 'logs' | 'steps'), expandedLogs (Set<number>)

## Related Components
- features/workflowExecution/WorkflowRunner.tsx — owner
- features/testing/ResultViewer.tsx — testing-area variant (different data shape)