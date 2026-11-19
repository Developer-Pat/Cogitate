---
title: ProviderConfigModal
type: atlas-component
path: frontend/src/components/features/providers/ProviderConfigModal.tsx
confidence: high
updated: 2026-08-03
tags: [type/component, domain/atlas-ui]
---
# ProviderConfigModal

**Path**: `frontend/src/components/features/providers/ProviderConfigModal.tsx`
**Last Updated**: 2026-08-03

## Purpose

Phase 4 modal dialog for adding and editing provider configurations (API-key-managed providers such as Ollama, OpenAI, Anthropic, OpenRouter, Deepseek). Rendered as a fixed-position overlay with a centered card (max-w-4xl, scrollable body), it hosts a react-hook-form form driven by a Zod schema and delegates persistence entirely to the caller via the `onSave` callback — the modal itself makes no API calls. In `add` mode it collects a full `ProviderConfigCreate` payload; in `edit` mode it submits a partial `ProviderConfigUpdate` (name and provider_type are immutable once created). The API key field is masked with a show/hide toggle, and the modal communicates key-state to the user: on edit, the hint reflects `provider.has_api_key` — "A key is already stored — leave blank to keep it, or enter a new one to replace it" vs "No key stored yet — enter one to enable this provider"; on add, "Your API key will be encrypted". A `HelpButton` (context `providers-config`) sits in the modal header next to the close button (Phase 3, 2026-08-03).

## Props Interface

```typescript
interface ProviderConfigModalProps {
  provider: ProviderConfig | null;
  mode: 'add' | 'edit';
  onSave: (config: ProviderConfigCreate | ProviderConfigUpdate) => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
}
```

Supporting types (from `frontend/src/types/providers.ts`, Phase 4 section):

```typescript
export interface ProviderConfig {
  id: number;
  name: string;
  display_name: string | null;
  provider_type: string;
  base_url: string | null;
  is_active: boolean;
  priority: number;
  config: Record<string, unknown> | null;
  has_api_key: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProviderConfigCreate {
  name: string;
  display_name?: string;
  provider_type: string;
  base_url?: string;
  api_key?: string;
  is_active?: boolean;
  priority?: number;
  config?: Record<string, unknown>;
}

export interface ProviderConfigUpdate {
  display_name?: string;
  base_url?: string;
  api_key?: string;
  is_active?: boolean;
  priority?: number;
  config?: Record<string, unknown>;
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useState`, `useEffect`) | Hook | `showApiKey` visibility toggle; populates form fields when `provider`/`mode` change in edit mode |
| `react-hook-form` (`useForm`, `SubmitHandler`, `Resolver`) | Library | Form state, registration, `handleSubmit`, `onChange` validation mode, `isValid` gate for the submit button |
| `@hookform/resolvers/zod` (`zodResolver`) | Library | Bridges the Zod schema into react-hook-form as the resolver |
| `zod` (`z`) | Library | `configFormSchema` — field validation (name min/max, base_url URL format, priority 1–999) |
| `../../../types/providers` | Types | `ProviderConfig`, `ProviderConfigCreate`, `ProviderConfigUpdate` |

## Usage Example

Used by `frontend/src/pages/ProviderDashboard.tsx` (rendered conditionally when the config modal is open):

```tsx
import ProviderConfigModal from '../components/features/providers/ProviderConfigModal';

{showConfigModal && (
  <ProviderConfigModal
    provider={editingProvider}
    mode={modalMode}                 // 'add' | 'edit'
    onSave={handleSaveProvider}      // async (config) => Promise<void> — calls the provider config service API
    onCancel={handleCancelModal}
    loading={providersLoading}
  />
)}
```

## State Used

- `showApiKey` (`useState<boolean>`, default `false`) — toggles the API key input between `password` and `text` types.
- `useForm<ConfigFormData>` state — all form field values (`name`, `display_name`, `provider_type`, `base_url`, `api_key`, `is_active`, `priority`), plus `errors` and `isValid` from `formState`. Defaults: `name: ''`, `display_name: ''`, `provider_type: 'ollama'`, `base_url: ''`, `api_key: ''`, `is_active: true`, `priority: 99`.
- `useEffect` — in `edit` mode, seeds the form from `provider` via `setValue` (name, display_name, provider_type, base_url, is_active, priority). Note: `api_key` is intentionally NOT populated on edit — it is write-only.
- Local Zod schema `configFormSchema` (module scope) — `name` (required, ≤100 chars), `display_name` (optional, ≤100), `provider_type` (required), `base_url` (optional URL or empty string), `api_key` (optional), `is_active` (default `true`), `priority` (number 1–999, default 99).
- Local `providerTypes` list (module scope inside component) — `ollama` (Ollama (Local)), `openai`, `anthropic`, `openrouter`, `deepseek`.

## Related Components

- `frontend/src/pages/ProviderDashboard.tsx` — parent page; owns the modal's open state, `editingProvider`, `modalMode`, and the `handleSaveProvider` callback that performs the actual create/update API call.
- `frontend/src/types/providers.ts` — source of `ProviderConfig`, `ProviderConfigCreate`, `ProviderConfigUpdate`, and the `IProviderConfigService` interface (`createProvider` / `updateProvider` methods backing the save flow).
