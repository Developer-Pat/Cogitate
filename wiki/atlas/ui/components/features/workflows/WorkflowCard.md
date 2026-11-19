---
title: WorkflowCard
type: atlas-component
path: frontend/src/components/features/workflows/WorkflowCard.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# WorkflowCard

**Path**: `frontend/src/components/features/workflows/WorkflowCard.tsx`
**Last Updated**: 2026-08-01

## Purpose

Presentational card that displays a workflow **template** (not an execution) in a compact, selectable card format. It surfaces the template's identity (name, description, category, version, author), visibility (Public/Private badge), complexity level, tags, and execution statistics (executions, success rate, average execution time), and exposes action buttons for Execute / Edit / Export. Clicking anywhere on the card selects the template via `onSelect`; it is used wherever templates are shown as cards (e.g. template galleries/selection grids). The card is fully controlled — it holds no internal state and delegates all behavior to its callbacks. Note that the Edit button is currently rendered `disabled` ("not yet implemented"), while Execute and Export are active.

The component is a **default export** (`export default WorkflowCard`) typed as `React.FC<WorkflowCardProps>`.

## Props Interface

Defined in `frontend/src/types/workflows.ts` (imported as `WorkflowCardProps` from `../../../types/workflows`):

```typescript
export interface WorkflowCardProps {
  template: WorkflowTemplate;
  onSelect: (template: WorkflowTemplate) => void;
  onExecute: (templateId: string, inputs?: Record<string, unknown>) => void;
  onEdit: (template: WorkflowTemplate) => void;
  onExport: (template: WorkflowTemplate) => void;
  isSelected?: boolean;
  className?: string;
}
```

The `template` prop is a `WorkflowTemplate` (also from `types/workflows.ts`):

```typescript
export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  author: string;
  tags: string[];
  steps: WorkflowStep[];
  inputs: WorkflowInput[];
  outputs: WorkflowOutput[];
  metadata: WorkflowMetadata; // { complexity: 'simple' | 'medium' | 'complex'; ... }
  createdAt: string;
  updatedAt: string;
  isPublic: boolean;
  isCustomizable: boolean;
  executionCount: number;
  successRate: number;
  averageExecutionTime: number;
  /** Workflow type (simple, advanced, agent, etc.) — used for filtering/sorting */
  workflowType?: string;
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` | library | `React.FC`, `React.MouseEvent` typing for click handlers |
| `WorkflowCardProps` (from `../../../types/workflows`) | type import | Props interface plus the `WorkflowTemplate` shape rendered by the card |

No hooks, stores, services, or context are used — the component is pure/presentational.

## Usage Example

```tsx
import WorkflowCard from './components/features/workflows/WorkflowCard';
import type { WorkflowTemplate } from './types/workflows';

const handleSelect = (t: WorkflowTemplate) => setSelected(t);
const handleExecute = (id: string) => runWorkflow(id);
const handleEdit = (t: WorkflowTemplate) => openEditor(t);
const handleExport = (t: WorkflowTemplate) => exportTemplate(t);

<WorkflowCard
  template={template}
  onSelect={handleSelect}
  onExecute={handleExecute}
  onEdit={handleEdit}
  onExport={handleExport}
  isSelected={selectedId === template.id}
  className="w-full"
/>
```

## State Used

None — the component is stateless. Selection styling (`border-blue-500 ring-2 ring-blue-200` when `isSelected`) and any layout overrides (`className`) are driven entirely by props.

## Related Components

- `frontend/src/components/features/workflows/WorkflowEditor.tsx` — editing surface reached via the `onEdit` callback (same `WorkflowTemplate` shape)
- `frontend/src/components/features/workflows/WorkflowPreview.tsx` — detail/preview surface for a template
- `frontend/src/components/features/workflows/WorkflowTemplateTable.tsx` (+ `WorkflowTemplateTableRow.tsx`) — table-based alternative to the card for listing templates
- `frontend/src/components/features/workflows/WorkflowSelectionModal.tsx` — modal picker that can host cards for selection
- `frontend/src/components/features/workflows/WorkflowImport.tsx` — import flow paired with `onExport`
- `frontend/src/components/features/workflows/WorkflowListCard.tsx` — card for workflow *lists* (groupings), distinct from this template card
- `frontend/src/types/workflows.ts` — source of `WorkflowCardProps`, `WorkflowTemplate`, and all workflow types
