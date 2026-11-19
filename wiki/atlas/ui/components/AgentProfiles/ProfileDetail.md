---
title: ProfileDetail
type: atlas-component
path: frontend/src/components/AgentProfiles/ProfileDetail.tsx
confidence: high
updated: 2026-09-25
tags: [type/component, domain/atlas-ui]
---

# ProfileDetail

**Path**: `frontend/src/components/AgentProfiles/ProfileDetail.tsx`
**Last Updated**: 2026-09-10

## Purpose

ProfileDetail is the detail pane of the Agent Profiles master-detail page (`pages/AgentProfiles.tsx`). At 1401 lines it is the largest component in the codebase. It is a dual-mode form: `action='create'` builds a new agent profile and `action='edit'` edits an existing one, using an 8-tab layout covering identity (Basic Info), provider/model config (Provider Settings), behavior (system prompt), sampling parameters (Advanced), collections, tool assignments, the cognitive profile, and the agent package.

It follows the **hybrid delegation pattern**: ProfileDetail performs its own READ-side calls (system prompt templates, model lists, provider list, agent export/import, cognitive-memory reset) while delegating all CRUD mutations (create/update/delete/image upload) to the parent via the `onSave` / `onDelete` / `onSaveAsTemplate` props.

## Props Interface

```typescript
interface ProfileDetailProps {
  profile?: Profile | null
  action: 'create' | 'edit'
  onSave: (profileData: ProfileCreate | ProfileUpdate, imageFile?: File) => Promise<void>
  onCancel: () => void
  onDelete?: (profileId: string) => Promise<Record<string, unknown> | null>  // the delete REPORT (bom + archived_path) — the recoverable delete (Phase D)
  onSaveAsTemplate?: () => void
  isSaving?: boolean
}
```

The prop types `Profile`, `ProfileCreate`, `ProfileUpdate` are exported from `services/domain/ProfileService.ts`. The budget-relevant shape (the rest of the fields are the package/kit/depth/health reads):

```typescript
// The DECLARATION lives in `llm_spec.max_output` — the one slot the resolver
// reads. `parameters` is the sampling settings only; a budget sent there is
// refused by name.
parameters?: {
  temperature?: number
  top_p?: number
}
llm_spec?: {
  kind?: string
  thinking?: string
  location?: string
  min_context?: number
  max_output?: number | null
} | null

// THE DECLARED-VS-SENT READ: what the row declares and what a turn would send,
// resolved by the BACKEND's resolver, plus the last turn's own record. Both
// are served on the agent read — the page never re-does the arithmetic.
output_budget?: {
  declared: number | null
  effective: number
  reason: string
  path: string
  observed?: {
    sent: number
    declared: number | null
    reason: string
    path: string
    at?: string | null
  } | null
} | null
// The DERIVED ceiling every declaration is checked against, served with it.
budget_ceiling?: number
```

`ProfileCreate` / `ProfileUpdate` carry the same `parameters` + `llm_spec` shapes (a create or an edit writes the declaration through `llm_spec.max_output`); neither has a budget default — an agent that declares nothing runs on the resolver's fallback.

Prop-driven behavior:

- `action === 'edit'` with no `profile` renders the empty state ("Select a profile to edit").
- The Collections / 🛠️ Tools / 🧠 Cognitive tabs render only when `action === 'edit' && profile`.
- `onSave` receives the assembled `ProfileCreate`/`ProfileUpdate` plus an optional image `File`; the parent performs the actual create/update and image upload (see API Endpoints).
- `onDelete` is optional; the red Delete Profile button renders only when it is provided (edit mode).
- `onSaveAsTemplate` is optional; the Save as Template button renders only when provided.
- `isSaving` (default `false`) disables every input/button and swaps the Save button label for a spinner.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `profileService` — `services/domain/ProfileService.ts` | Service singleton | `getTemplates()` (system prompt templates), `applyTemplate()` (render template into prompt), and application-level form-state persistence: `getFormState` / `saveFormState` / `clearFormState` (unsaved-changes restore when switching profiles) |
| `modelBrowserService` — `services/domains/providers/modelBrowserService.ts` | Service | Tier-1 model resolution: `browseModels(providerId, { page_size: 50 })` → `GET /api/v1/providers/{id}/models/browse` |
| `getCuratedModelsForProvider` — `config/curatedModels.ts` | Config helper | Tier-2 fallback: curated model list for the selected provider |
| `useProviderConfig` — `hooks/useProviderConfig.ts` | Hook | DB-backed provider list for the Provider dropdown (`providerConfigService.getProviders` → `GET /api/v1/providers/config`) |
| `useNotificationStore` — `stores/notificationStore.ts` | Zustand store | `addSuccess` / `addError` toasts for export/import/reset-memory outcomes |
| `frontendLoggingService` — `services/frontendLoggingService.ts` | Service | debug/info/warning/error logging across all handlers |
| `ProfileImageUpload` — `components/AgentProfiles/ProfileImageUpload.tsx` | Child component | Avatar preview + upload; calls `profileService.uploadProfileImage` → `POST /api/v1/agents/{id}/image` |
| `CollectionsTab` — `components/AgentProfiles/CollectionsTab.tsx` | Child component | Collections membership management (edit mode) |
| `AgentToolsTab` — `components/AgentProfiles/AgentToolsTab.tsx` | Child component | Thin wrapper rendering `AgentToolManager` with toast/logging callbacks (edit mode) |
| `CognitiveProfileSelector` — `components/features/cognitive/CognitiveProfileSelector.tsx` | Child component | Radio-card cognitive profile picker; `cognitiveProfileService.list()` → `GET /api/v1/cognitive-profiles?include_builtin=true` |

## Usage Example

Real usage from the parent page `pages/AgentProfiles.tsx` (master-detail layout, ProfileDetail as the right pane):

```tsx
<ProfileDetail
  profile={action === 'edit' ? selectedProfile : null}
  action={action}
  onSave={handleSaveProfile}
  onCancel={handleCancel}
  onDelete={handleDeleteProfile}
  onSaveAsTemplate={action === 'edit' ? openSaveAsTemplateModal : undefined}
  isSaving={isSaving}
/>
```

## Tab Layout

`activeTab` is typed `'basic' | 'provider' | 'behavior' | 'advanced' | 'collections' | 'tools' | 'cognitive' | 'package'`.

| Tab | Visible | Contents |
|---|---|---|
| Basic Info | always | `ProfileImageUpload`, Profile Name (required), Description |
| Provider Settings | always | Provider select (DB list with hardcoded fallback), Model select/input (3-tier resolution), Browse Models button (enabled only for ollama/openrouter/deepseek/groq), Ollama model info card |
| Behavior | always | System Prompt Template selector, System Prompt textarea, Enable Memory toggle (marked "Coming Soon") |
| Advanced | always | a **Declare sampling** switch over the Temperature / Top P sliders (OFF on a new agent; while it is off the sliders are disabled and read "not set", and the line beneath states the consequence), Max Tokens input (the DECLARATION, written to `llm_spec.max_output`, with the resolved declared-vs-sent readout and the last turn's carried number beneath it), Quick Presets (Precise / Balanced / Creative / Declare nothing) |
| Collections | edit only | `CollectionsTab` (the profile's collection memberships) |
| 🛠️ Tools | edit only | `AgentToolsTab` → `AgentToolManager` (tool enable/disable/priority/config) |
| 🧠 Cognitive | edit only | `CognitiveProfileSelector` bound to `formData.cognitive_profile_id` |
| 📦 Package | edit only | `PackageTab` — the agent's package (read-only provenance + contents plus the Phase-2 picker/preview; resolves the kit name from `package_id`/`kit_id`) |

Feature-area mapping: identity = Basic Info; provider/model config = Provider Settings; sampling config = Advanced; cognitive pipeline = Cognitive tab (a cognitive profile defines the context builder, executor, memory, and response formatter pipeline strategies used when running the agent); memory = the Enable Memory toggle (Behavior tab) plus the Reset Memory footer button; tools and collections = their eponymous tabs.

### Cognitive profile wiring

The 🧠 Cognitive tab is the component's entire cognitive-pipeline surface. It renders `CognitiveProfileSelector` with `value={formData.cognitive_profile_id}` and writes the chosen id back into the form on change. The selector shows a "--- None ---" option (no pipeline, basic LLM chat only) plus one radio card per cognitive profile with a part-code badge (context-builder / executor / response-formatter / memory-profile dimensions), description, and memory label. The id is persisted through `onSave` → parent → `PUT /api/v1/agents/{id}` with `cognitive_profile_id` in the body.

> ⚠️ **New-agent-architecture fields are NOT in this component.** `execution_mode` (hybrid/shallow), `behavior_config`, `preferred_providers`, `fallback_enabled`, and `allow_delegation` do not appear anywhere in ProfileDetail or in the `Profile`/`ProfileCreate`/`ProfileUpdate` types. A repo-wide grep places them only in `pages/AgentTemplates.tsx` (the agent-template editor) and in backend-generated `types/api.generated.ts`. ProfileDetail shows and edits exactly one cognitive-architecture field: `cognitive_profile_id`.

## State Used

Local `useState`:

- `formData: ProfileCreate` — the whole form. Defaults: provider `ollama`, model `llama3.2:latest`, **no sampling and no budget** — `parameters` starts `undefined` and `llm_spec` starts `{}`, so a new agent declares neither. An undeclared sampling pair runs on the provider's own default; an undeclared budget runs on the resolver's fallback. Edit mode hydrates from `profile` (or from `profileService.getFormState(profile.id)` when unsaved changes exist) and carries the row's OWN declaration — or its absence; create mode resets to the undeclared state. `parameters` is sent as the declared pair or as an explicit `null`, so the row keeps one shape for "declares nothing".
- `declareSampling: boolean` — whether this agent declares sampling at all. OFF on a new agent and hydrated on edit from whether the row declares anything. ON with nothing set is a real state: the sliders become usable and NOTHING is written until one is dragged, so flipping the switch cannot invent a pair — and `handleSubmit` refuses that state by name.
- `samplingSummary` / `samplingState` (derived, not state) — the plain line under the switch: the consequence when nothing is declared, or what a turn sends.
- `activeTab` — current tab (see Tab Layout).
- `error` — inline form error (validation plus save/delete failures).
- `selectedImageFile: File | null` — pending avatar file, cleared on profile switch.
- `resetCounter` — bumped on profile switch to reset `ProfileImageUpload`.
- `availableModels`, `loadingModels`, `modelError` — 3-tier model resolution state.
- `templates`, `loadingTemplates`, `selectedTemplateId` — system prompt template list plus current selection.

Local `useRef`: `importFileInputRef` (hidden file input for Import Agent). (The earlier dead `fileInputRef` is gone — image upload is owned entirely by `ProfileImageUpload`.)

External state:

- `useNotificationStore` — `addSuccess` / `addError`.
- `useProviderConfig` — `providers`, `providersLoading`.
- `profileService` form-state store — every `handleInputChange` / `handleParametersChange` calls `saveFormState(profileId, updatedData)` so unsaved edits survive profile switches; cleared on successful save.

Every sampling control — the sliders (`handleParametersChange`), the switch, a preset click and **Declare nothing** — routes through `applySamplingDeclaration`, which saves the form state like the other inputs do, so an unsaved sampling edit survives a profile switch. A save with the switch ON and nothing set is refused by name, and any of those controls clears the refusal banner.

## Data Flow

1. Mount: fetch system prompt templates (`profileService.getTemplates()`) and resolve models for the default provider (browser → curated → manual).
2. Provider change: re-runs the 3-tier model resolution (`useEffect` on `formData.provider`).
3. Browse Models button: writes `returnToProfile` + `selectedModel` to `sessionStorage` and navigates to `/providers/{providerId}/models`; on return, `location.state.modelSelected` triggers rehydration of provider/model from `sessionStorage` (the round-trip values are cleared afterward).
4. Template select: `profileService.applyTemplate(templateId, {assistant_name, role, tone, user_name, style, focus})` renders the prompt into `system_prompt`.
5. Save (`handleSubmit`): validates name + model; on create, generates `id` from a slugified name plus a 6-char random suffix; calls `onSave(dataToSave, selectedImageFile || undefined)`; clears form state on success.
6. Delete: `confirm()` dialog, then `onDelete(profile.id)` (parent performs `DELETE /api/v1/agents/{id}`).
7. Export: raw `fetch('/api/v1/agents/{id}/export')`, downloads the JSON blob as `agent-{name}.json`.
8. Import: raw `POST /api/v1/agents/import` with the parsed JSON bundle.
9. Reset Memory: `confirm()` dialog, then raw `DELETE /api/v1/cognitive/memory/agent/{id}` (clears stored facts, summaries, and conversation history).

## API Endpoints

| Method | Endpoint | Origin | Purpose |
|---|---|---|---|
| GET | `/api/v1/agents/system-templates` | `profileService.getTemplates` | System prompt template list (Behavior tab) |
| POST | `/api/v1/agents/system-templates/apply` | `profileService.applyTemplate` | Render template with variables into `system_prompt` |
| GET | `/api/v1/providers/{id}/models/browse?page_size=50` | `modelBrowserService.browseModels` | Tier-1 model list for the provider |
| GET | `/api/v1/providers/config` | `useProviderConfig` → `providerConfigService` | Provider dropdown options (DB-backed) |
| GET | `/api/v1/agents/{id}/export` | raw `fetch` | Export Agent (JSON download) |
| POST | `/api/v1/agents/import` | raw `fetch` | Import Agent (JSON bundle) |
| DELETE | `/api/v1/cognitive/memory/agent/{id}` | raw `fetch` | Reset Memory |
| POST | `/api/v1/agents/{id}/image` | `ProfileImageUpload` → `profileService.uploadProfileImage` | Avatar upload |
| GET | `/api/v1/cognitive-profiles?include_builtin=true` | `CognitiveProfileSelector` → `cognitiveProfileService.list` | Cognitive profile options |
| GET | `/api/v1/collections` (+ membership mutations) | `CollectionsTab` → `collectionsService` | Collection memberships of the agent |
| (various) | agent/tool assignment endpoints | `AgentToolManager` → `agentToolService` / `toolService` | Tool enable/disable/priority/config |
| POST | `/api/v1/agents` | delegated → parent `handleSaveProfile` → `profileService.createProfile` | Create (via `onSave`) |
| PUT | `/api/v1/agents/{id}` | delegated → parent `profileService.updateProfile` | Update (via `onSave`) |
| DELETE | `/api/v1/agents/{id}` | delegated → parent `handleDeleteProfile` → `profileService.deleteProfile` | Delete (via `onDelete`) |

The create/update/delete rows are parent-owned: ProfileDetail only invokes the props; the parent page performs the network mutations. Save-as-template is also parent-owned — the `onSaveAsTemplate` prop only opens the parent's modal.

> ✅ **Resolved: `onUpdated` is a declared prop.** The import handler calls `if (onUpdated) onUpdated();` (ProfileDetail.tsx:1260) and `onUpdated?: () => void` is declared in the props interface (line 33) — the earlier undeclared-identifier `ReferenceError` no longer applies.

## Flags

- ⚠️ **Bugs**: none known here (the `onUpdated` ReferenceError, the dead `fileInputRef`, and the duplicate `cognitive_profile_id` key are all resolved — see above).
- ⚠️ **Not implemented**: the Enable Memory toggle is explicitly "Coming Soon" (tooltip plus helper copy "not yet implemented") — it is stored in the form and persisted, but the memory feature is not wired on the backend.
- ⚠️ **Scope**: new-agent-architecture fields (`execution_mode`, `behavior_config`, `preferred_providers`, `fallback_enabled`, `allow_delegation`) live in the AgentTemplates flow, not in ProfileDetail.

## Related Components

- **Parent**: `pages/AgentProfiles.tsx` — master-detail page; owns `handleSaveProfile`, `handleDeleteProfile`, `openSaveAsTemplateModal`, and the save-as-template modal.
- **Sibling**: `components/AgentProfiles/ProfileList.tsx` — left-side profile list on the same page.
- **Children**:
  - `components/AgentProfiles/ProfileImageUpload.tsx`
  - `components/AgentProfiles/CollectionsTab.tsx`
  - `components/AgentProfiles/AgentToolsTab.tsx` → `components/features/agentTools/AgentToolManager/AgentToolManager.tsx`
  - `components/features/cognitive/CognitiveProfileSelector.tsx`
- **Services**: `services/domain/ProfileService.ts`, `services/domain/CognitiveProfileService.ts`, `services/domains/providers/modelBrowserService.ts`, `services/domains/providers/providerConfigService.ts`, `services/domain/CollectionsService.ts`, `services/domain/AgentToolService.ts`, `services/domain/ToolService.ts`
- **Config**: `config/curatedModels.ts`; **Hook**: `hooks/useProviderConfig.ts`; **Store**: `stores/notificationStore.ts`

## The lifecycle UI (2026-08-16, agent-lifecycle Phase D)

- **Depth marker** — the "deep" badge next to the title when the
  profile has a `workspace_key` (the on-disk identity exists).
- **The BOM delete dialog** — Delete Profile opens a state-driven
  overlay (`deleteDialog`) that DISCLOSES what will be removed
  (tool links, memory, workspace folder) + the archive note
  (recovery is possible). Confirming calls `onDelete` — the
  response is the result REPORT, shown in the dialog ("Profile
  deleted" + where the workspace went). Built on the recoverable
  delete: the workspace MOVES onto the trash's agents shelf
  (`trash/agents/`), the row is soft-deleted, history is kept.
- The dialog is deliberate: it opens on a confirm click, the
  confirm button shows "Deleting…" while the request runs, and
  the result reports where recovery lives (additive, explicit).
