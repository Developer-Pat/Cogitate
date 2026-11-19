---
title: ToolConfigModal
type: atlas-component
path: frontend/src/components/features/agentTools/AgentToolManager/ToolConfigModal.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ToolConfigModal

**Path**: `frontend/src/components/features/agentTools/AgentToolManager/ToolConfigModal.tsx`
**Last Updated**: 2026-08-01

## Purpose

Modal dialog for configuring an agent's tool settings. The form is generated dynamically from the tool's JSON Schema (`agentTool.tool.config_schema`), so the modal supports any tool definition without hardcoded fields. It offers two editing modes behind a tab switch: a generated **Form** view (typed inputs per schema property) and a raw **JSON Editor** view with live validation. Saving delegates to the `onSave(toolId, config)` callback — the component itself makes no direct API calls; the parent (`AgentToolManager`) persists the config via `agentToolService.updateAgentTool` → `PUT /api/v1/tools/agents/{agentId}/tools/{toolId}`.

## Props Interface

```typescript
export interface ToolConfigModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal is closed */
  onClose: () => void;
  /** Callback when configuration is saved */
  onSave: (toolId: string, config: unknown) => void;
  /** Agent tool data */
  agentTool: AgentToolResponse;
}
```

`AgentToolResponse` is imported from `../../../../types/tools` — it extends `AgentTool` (`id`, `agent_id`, `tool_id`, `is_enabled`, `priority`, `config`, `created_at`, `updated_at`) with `tool: ToolSummary | null`. `ToolSummary` carries the schema used for form generation: `{ id, name, slug, description, icon, color, category, config_schema: Record<string, unknown> }`.

The component is a **named export** (`export const ToolConfigModal: React.FC<ToolConfigModalProps>`), not a default export. `ToolConfigModalProps` is exported alongside it for consumers.

### Internal FormField shape (derived from the tool's JSON Schema)

```typescript
interface FormField {
  name: string;
  label: string;
  type: string;
  description?: string;
  default?: unknown;
  required: boolean;
  enum?: string[];
  minimum?: number;
  maximum?: number;
  pattern?: string;
  format?: string;
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useState`, `useEffect`) | Library | Local state + schema→form initialization effect on `agentTool` change |
| `AgentToolResponse` (`../../../../types/tools`) | Type | Props typing — agent-tool association plus embedded `ToolSummary` with `config_schema` |
| FontAwesome icon classes (`fa-solid fa-times` / `fa-sliders` / `fa-code` / `fa-gear` / `fa-info-circle`) | Icon library | Close button, tab icons, empty-state icon, JSON hint icon |
| Tailwind + DaisyUI classes | Styling | Modal overlay/panel, tabs, form controls, `tooltip tooltip-right` on the password field |
| `agentToolService` (via parent) | Service (indirect) | **Not imported here** — the parent `AgentToolManager` persists saves via `agentToolService.updateAgentTool` (`PUT /api/v1/tools/agents/{agentId}/tools/{toolId}`) |

Note: the component makes **no direct API/network calls** — it is a controlled, presentational modal. All persistence flows through the `onSave` prop to the parent.

## Usage Example

The parent `AgentToolManager` (same directory) renders it when a tool row's configure action fires:

```tsx
{selectedTool && (
  <ToolConfigModal
    isOpen={configModalOpen}
    onClose={handleCloseConfig}
    onSave={handleSaveConfig}
    agentTool={selectedTool}
  />
)}
```

Parent-side save handler (the actual persistence path):

```tsx
const handleSaveConfig = async (toolId: string, config: unknown) => {
  await agentToolService.updateAgentTool(agentId, toolId, { config: config as Record<string, unknown> });
  // ...then updates local agentTools state with the new config
};
```

## State Used

All state is local `useState` — no external store selectors:

| State | Type | Purpose |
|---|---|---|
| `config` | `Record<string, unknown>` | Current configuration object; seeded from `agentTool.config` merged with schema defaults |
| `configJson` | `string` | Pretty-printed JSON mirror of `config`, edited in the JSON tab |
| `jsonError` | `string \| null` | `'Invalid JSON'` when the JSON tab content fails to parse; `null` otherwise. Non-null disables the Save button |
| `activeTab` | `'form' \| 'json'` | Active editor tab |
| `formFields` | `FormField[]` | Fields generated from `agentTool.tool.config_schema` in the `useEffect([agentTool])` |

- The `useEffect([agentTool])` regenerates fields and re-seeds `config`/`configJson` whenever the `agentTool` prop changes: existing `agentTool.config` values win; schema `default`s fill in missing keys.
- `handleFormChange` keeps both `config` and `configJson` in sync; `handleJsonChange` parses the textarea and back-propagates into `config`, or sets `jsonError` on parse failure.
- `handleSave` calls `onSave(agentTool.tool_id, config)` — note it passes `tool_id` (the tool id on the association), not the association's `id`.

## Save Behavior & Form Generation

- **Schema → fields**: `generateFormFields(schema)` maps each `schema.properties` key to a `FormField`, reading `title` (label, fallback: key), `type` (default `'string'`), `description`, `default`, `required` (membership in `schema.required`), `enum`, `minimum`, `maximum`, `pattern`, `format`. A schema with no/empty `properties` yields `[]`, and the Form tab renders "This tool has no configuration options."
- **Field rendering by type**: `string` + `format === 'password'` → password input wrapped in a DaisyUI tooltip ("Sensitive value - will be encrypted"); `string` + `enum` → `<select>`; plain `string` → text input; `number`/`integer` → number input honoring `min`/`max`; `boolean` → checkbox; any other type → JSON textarea that falls back to keeping the raw string when the content is not valid JSON.
- **Save**: `handleSave` fires `onSave` only while `jsonError` is `null`; the Save Configuration button is disabled whenever the JSON tab holds invalid JSON. The modal does not close itself on save — the parent's handler decides what happens next; Cancel, the ✕ button, and the background overlay all call `onClose`.

## Related Components

- **Parent**: `AgentToolManager` — `frontend/src/components/features/agentTools/AgentToolManager/AgentToolManager.tsx` (owns `configModalOpen` / `selectedTool` state and the `handleOpenConfig` / `handleCloseConfig` / `handleSaveConfig` handlers, including the `agentToolService` call)
- **Service (via parent)**: `agentToolService` — `frontend/src/services/domain/AgentToolService.ts` (`updateAgentTool` → `PUT /api/v1/tools/agents/{agentId}/tools/{toolId}`)
- **Types**: `frontend/src/types/tools.ts` (`AgentToolResponse`, `AgentTool`, `ToolSummary`)
- **Barrel export**: `frontend/src/components/features/agentTools/index.ts` re-exports `ToolConfigModal` and `ToolConfigModalProps`
