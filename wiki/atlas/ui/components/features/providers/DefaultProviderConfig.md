---
title: DefaultProviderConfig
type: atlas-component
path: frontend/src/components/features/providers/DefaultProviderConfig.tsx
confidence: high
updated: 2026-08-03
tags: [type/component, domain/atlas-ui]
---
# DefaultProviderConfig

**Path**: `frontend/src/components/features/providers/DefaultProviderConfig.tsx`
**Last Updated**: 2026-08-03

## Purpose
Controlled provider + model selector panel used to configure the default provider for chat. Renders a provider dropdown and a **searchable model picker** (filter input + select), loading the list of managed providers and the models for the selected provider from the backend. Selections are reported upward via the `onProviderChange` / `onModelChange` callbacks — the component does **not** persist anything itself; the parent (`ProviderDashboard`) collects the pending changes and saves them with `PUT /api/v1/providers/default`. Named export (`export const DefaultProviderConfig`), no default export.

## Intuitiveness changes (2026-08-03, Phase 3)
- **Provider labels** no longer show the type parenthetically when it equals the name (`ollama` instead of `ollama (ollama)`); the type is shown only when it differs (`openrouter (openrouter)` → `openrouter`).
- **Model selection is searchable**: a filter input (`modelSearch` state) narrows the provider's catalog by name/display-name before rendering the select; resets on provider change. This fixes the previous 341-option unscrollable native select.
- The model dropdown still loads via `GET /api/v1/providers/managed/{providerId}/models` — which now returns Ollama Cloud models too (discovery dispatch gained the `ollama_cloud` branch; see discovery_service atlas note).

## Props Interface
```typescript
interface DefaultProviderConfigProps {
  currentProviderId?: number;
  currentProviderName?: string;
  currentProviderType?: string;
  currentModel?: string;
  onProviderChange: (providerId: number, providerName: string, providerType: string) => void;
  onModelChange: (model: string) => void;
  className?: string;
}
```

Internal data shapes (not exported):
```typescript
interface ProviderInfo {
  id: number;
  name: string;
  provider_type: string;
  is_active: boolean;
  is_default: boolean;
}

interface ModelInfo {
  name: string;
  display_name?: string;
}
```

Destructuring defaults: `currentProviderName = 'ollama'`, `currentProviderType = 'ollama'` (captured as `_currentProviderType`, unused), `currentModel = 'llama3.2:latest'`, `className = ''`.

## Dependencies
| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useState`, `useEffect`) | Hooks | Local state for provider/model lists, loading flags and selections; loads providers on mount, syncs internal state when props change, reloads models whenever `selectedProviderId` changes |
| `apiClient` (`../../../services/apiClient`) | Service | HTTP client used for the two read-only API calls below |

API calls made by this component (read-only):
- `GET /api/v1/providers/managed` → `{ providers: ProviderInfo[] }` — fetch managed providers on mount.
- `GET /api/v1/providers/managed/{providerId}/models` → `{ models: ModelInfo[] }` — fetch models for the selected provider (on failure, `models` is reset to `[]`).

Save behavior: saving is **not** performed here. The parent page persists the selection via `PUT /api/v1/providers/default` with body `{ provider_id, model }` (see `handleSaveDefaultConfiguration` in `ProviderDashboard.tsx`).

## Usage Example
```tsx
<DefaultProviderConfig
  currentProviderId={defaultProvider.provider_id}
  currentProviderName={defaultProvider.provider_name}
  currentProviderType={defaultProvider.provider_type}
  currentModel={defaultProvider.model_name}
  onProviderChange={handleDefaultProviderChange}
  onModelChange={handleDefaultModelChange}
/>
```

## State Used
| State | Type | Notes |
|---|---|---|
| `providers` | `ProviderInfo[]` | Loaded once on mount from `/api/v1/providers/managed`; empty until fetch completes |
| `models` | `ModelInfo[]` | Reloaded whenever `selectedProviderId` changes; cleared on fetch failure |
| `loadingProviders` / `loadingModels` | `boolean` | Drive the `disabled` attribute and "Loading..." placeholder options |
| `selectedProviderId` | `number` | Initialized to `currentProviderId || 1`; re-synced from props on change |
| `selectedModel` | `string` | Initialized to `currentModel`; reset to `''` when the provider changes |
| `modelSearch` | `string` | Filter text for the model picker; reset to `''` when the provider changes |
| `selectedProviderName` | `string` | Set via `setSelectedProviderName` but never read (write-only) |

All state is local via `useState`; no stores or context are used.

## Related Components
- `frontend/src/pages/ProviderDashboard.tsx` — parent; renders the component (Overview tab, ~line 516), owns `pendingProvider`/`defaultProvider` state, and persists the selection with `PUT /api/v1/providers/default` followed by `refreshDefaultProvider()`.
- `frontend/src/services/apiClient.ts` — shared HTTP client used for fetching providers and models.
