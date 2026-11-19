---
title: useWorkflowTemplates
type: atlas-hook
path: frontend/src/hooks/useWorkflowTemplates.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useWorkflowTemplates

**Path**: `frontend/src/hooks/useWorkflowTemplates.ts`
**Type**: hook

## Purpose
Workflow templates state + CRUD — manages the template list, filters (search/category/type/tags), selection, and a react-hook-form instance for create/edit. Wraps workflowService (domains/llm).

## Exported API
```typescript
export const useWorkflowTemplates = (): UseWorkflowTemplatesReturn

// Returned (from source):
//   templates, filteredTemplates, filters, loading, error
//   categories, tags
//   setFilters, refreshTemplates, selectedTemplate, setSelectedTemplate
//   createTemplate(templateData), updateTemplate(id, data), deleteTemplate(id)
//   form  // react-hook-form UseForm<WorkflowTemplateFormData> (zodResolver + workflowTemplateFormSchema)
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| workflowService | domains/llm/workflowService.ts | list/create/update/delete + categories/tags |
| useForm + zodResolver | react-hook-form | Create/edit form (workflowTemplateFormSchema) |

## Usage Example
```tsx
const { templates, filteredTemplates, filters, setFilters, createTemplate, deleteTemplate, form } = useWorkflowTemplates()
```

## State / Data Flow
- Single WorkflowTemplateState object: templates, filteredTemplates, filters (defaultFilters), loading, error, selectedTemplate, categories, tags
- createTemplate reloads the list after success; error messages from response.error or thrown errors

## Related
- pages/WorkflowTemplates.tsx — primary consumer
- services/domains/llm/workflowService.ts — the `getTemplateCategories()` normalization lives here