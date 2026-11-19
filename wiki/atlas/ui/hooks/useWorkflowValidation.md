---
title: useWorkflowValidation
type: atlas-hook
path: frontend/src/hooks/useWorkflowValidation.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useWorkflowValidation

**Path**: `frontend/src/hooks/useWorkflowValidation.ts`
**Type**: hook

## Purpose
Workflow validation helpers — validate templates, executions, and individual steps, returning errors + warnings.

## Exported API
```typescript
export const useWorkflowValidation = (): UseWorkflowValidationReturn

interface UseWorkflowValidationReturn {
  validateTemplate: (template: WorkflowTemplate) => Promise<{ isValid: boolean; errors: string[]; warnings: string[] }>
  validateExecution: (templateId: string, inputs: Record<string, unknown>) => Promise<{ isValid: boolean; errors: string[]; warnings: string[] }>
  validateStep: (step: WorkflowStep) => Promise<{ isValid: boolean; errors: string[]; warnings: string[] }>
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| workflowService | domains/llm/workflowService.ts | Validation endpoints (trace actual calls) |
| WorkflowTemplate, WorkflowStep | types/workflows | Data shapes |

## Usage Example
```tsx
const { validateTemplate } = useWorkflowValidation()
const { isValid, errors } = await validateTemplate(template)
```

## State / Data Flow
- Thin wrapper over workflowService validation; no local state

## Related
- features/workflows/WorkflowEditor.tsx / WorkflowImport.tsx — consumers
- services/domains/llm/workflowService.ts