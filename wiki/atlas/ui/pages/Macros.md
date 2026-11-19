---
title: Macros
type: atlas-page
path: frontend/src/pages/Macros.tsx
confidence: high
updated: 2026-08-25
tags: [type/page, domain/atlas-ui]
---
# Macros

**Component**: `frontend/src/pages/Macros.tsx`
**Route**: `/macros` (registered as `Macros` in `frontend/src/config/routes.ts` — title "Macros", description "Create and manage system macro sets and meta topics", `requiresAuth: true`, icon `collection`, breadcrumb "Macros")
**Last Updated**: 2026-08-13

## Purpose

Dedicated page for macro management (moved out of the old ChatSettings surface to get more UI space). It lets users organize **meta-topics** (named collections of up to five topic mappings) and the **macro sets** behind them — the F1–F5 macro texts that the chat page's macro keyboard inserts. It also provides file-based backup/restore of meta-topics and inline editing of every macro field.

## Key Features

- **Two-panel layout** — left panel lists the selected meta-topic's five topic slots (M1–M5), right panel is the F-key editor for the currently selected slot's macro set.
- **Meta-topic selection** — `TopicFlyoutButton` ("Select Meta") opens a flyout to pick a meta-topic + mark one as default (★). No reload control (auto-sync). The A-KEY SOURCE readout (the current source of the last-used surface) sits under the name — changes happen on the chat keyboard's A selector (the three-button stack was removed, Phase 5d).
- **Meta-topic CRUD** — create a new empty meta-topic, delete the selected one (with confirmation dialog), clear the selection, rename it inline, and edit its description inline.
- **The toolbar (2026-09-03)** — beside Select Meta: the three-dot (⋮) action menu (Create / Delete / Clear selection / Save to file / Load from file). The refresh buttons are GONE (the page header's + the toolbar's — 2026-09-03, Phase 5c: `useMacroSync` auto-reloads on the backend's publishes). The Ask Exa + Help remain.
- **The right-pane Clear (2026-08-25)** — a Clear button left of the Save Macro wipes the F-key fields WITHOUT deselecting the meta-topic; selecting an empty M-slot also clears the form (the old behavior kept the stale values).
- **Topic-slot management** — the five slots render as sortable rows; drag (`≡`) to reorder mappings, `✕` to remove a mapping, and a per-row flyout to remove from topic or delete the underlying macro set. "Add Topic" opens a picker of macro sets not yet mapped (capped at 5 mappings total).
- **F-key macro editor** — per macro set: rename topic, edit description, and edit `f1`–`f5` macro texts with a Save button; empty slots show `Slot M1`…`Slot M5` placeholders.
- **Backup / restore to file** — "💾" saves the selected meta-topic to a server file (`POST .../save`); "📂" lists saved meta-topics and loads one back into the store and editor.
- **Ask Exa (builder hand-off, 2026-08-13)** — the header's "Ask Exa" button opens the Exa panel with a MACRO-GENERATION hand-off: it embeds the `cogitate-macro-management` skill (discover existing sets, then create/update macro sets + meta-topics via the API). The panel is the builder's assistant for the tedious hand-editing; the hand-off surfaces with Send/Discard (no auto-fire) and needs fix-mode for writes.
- All mutations surface success/error toasts via `useNotificationStore`.

## Components Used

| Component | Path | Purpose |
|---|---|---|
| `TopicFlyoutButton` | `frontend/src/components/features/agentInteraction/TopicFlyoutButton.tsx` | "Select Meta" button + flyout listing all meta-topics; select the active topic, mark a default (★). No reload control (the auto-sync) |
| `SortableTopicRow` | Defined inline in `Macros.tsx` (lines ~21–53) | Sortable row per topic slot: drag handle (`≡`), label, delete button (`✕`) |
| `DndContext` / `SortableContext` | `@dnd-kit/core`, `@dnd-kit/sortable` (node_modules) | Drag-and-drop container + sortable list for reordering topic mappings (closest-center collision, vertical list strategy) |
| `Plus` / `Trash2` / `RotateCcw` | `lucide-react` | Left-panel toolbar icons: create meta-topic, delete meta-topic, clear selection |

## Hooks Used

| Hook | Path | Purpose |
|---|---|---|
| `usePageTitle` | `frontend/src/hooks/usePageTitle.tsx` | Sets document title to "Macros" with description "Manage your macro sets and meta topics" |
| `useSystemMacrosStore` | `frontend/src/stores/macroSetsStore.ts` | Zustand store hook — reads `metaTopics`, `macroSets`, `selectedMetaTopicId`, `aKeysMetaTopicId`, `surface` (the audit readout); exposes `loadMetaTopics`, `loadAllMacros`, `selectMetaTopic` |
| `useNotificationStore` | `frontend/src/stores/notificationStore.ts` | Success/error/warning toasts for every create/update/delete/save/load operation |
| `useState`, `useEffect` | `react` | Local UI state (editor form, flyouts, rename modes, saving flags); mount loads; store subscription |
| `useSystemMacrosStore.subscribe` | `zustand` (via store) | Subscribes to `selectedMetaTopicId` changes and bumps a `storeSync` counter to force re-render |
| `useSensor` / `useSensors` / `useSortable` | `@dnd-kit/core`, `@dnd-kit/sortable` | Pointer sensor (8px activation distance) and per-row sortable behavior |

## Data Flow

1. **Mount** — a `useEffect` calls `useSystemMacrosStore.getState().loadAllMacros()` (`GET /api/v1/macros?all=true`) and `loadMetaTopics()` (`GET /api/v1/macros/meta-topics`). Both are raw `fetch` calls inside the store.
2. **Selection resolution** — `loadMetaTopics` keeps the saved selection (`localStorage` key `cogitate_selected_meta_topic`) if it still exists, otherwise falls back to the user's default topic (`cogitate_default_meta_topic`), then the built-in "System Guide" topic, then the first available; fires a warning toast when no topics exist.
3. **Editor population** — an effect watches `selectedMetaTopicId` / `metaTopics` / `macroSets` / `selectedTopicIndex` and derives `editingMacro` by looking up `topic.topic_mappings[selectedTopicIndex]` in `macroSets`, mapping backend fields `f1_macro`–`f5_macro` to editor fields `f1`–`f5`.
4. **Selection changes** — `TopicFlyoutButton` calls `selectMetaTopic(id)` on the store; the page's store subscription bumps `storeSync`, re-rendering the slot list and editor.
5. **Mutations** — the page calls the API directly with raw `fetch` (JSON bodies), then refreshes the store (`loadMetaTopics()` / `loadAllMacros()`) and shows a toast. Examples: rename, description edit, topic reorder (`arrayMove` on mappings), add/remove mapping, delete macro set, create/delete meta-topic.
6. **Backup/restore** — save posts the meta-topic to a server file; the load flow fetches the saves list, `POST`s the chosen folder, then reloads meta-topics, selects the returned `meta_topic_id`, reloads macro sets, and repopulates `editingMacro` directly from store state.

## State Management

| Store | Path | Role |
|---|---|---|
| `useSystemMacrosStore` | `frontend/src/stores/macroSetsStore.ts` | **Source of truth** for `macroSets`, `metaTopics`, `selectedMetaTopicId`, `defaultMetaTopicId`, `aKeysMetaTopicId`, `surface`, `hasNoTopics`, loading flags; actions `loadMetaTopics`, `loadAllMacros`, `reloadMacros` (event-bus), `selectMetaTopic`, `setAsDefaultTopic`, `setAKeysDefault`, `setSurface`. Selections persisted surface-scoped (`cogitate_selected_meta_topic` / `cogitate_akeys_meta_topic` + `:exa` suffixes) |
| `useNotificationStore` | `frontend/src/stores/notificationStore.ts` | Toasts for all operations (renamed, saved, deleted, reordered, loaded, plus error variants) |
| Local component state | `Macros.tsx` | `editingMacro`, `selectedTopicIndex`, rename/description/topic rename modes, flyout visibility (`showDeleteFlyout`, `showAddPicker`, `showLoadPicker`, `confirmDeleteMetaTopic`), `availableSaves`, `savingMeta`/`loadingMeta`/`isSaving` flags |

> Note: the unused `MACROS_PAGE_STORAGE_KEY` constant was removed from the page (2026-09-03 — the audit flagged the stale note).

## API Endpoints Called

All calls use raw `fetch` (page and store) with `Content-Type: application/json` where a body is sent.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/macros?all=true` | Load all macro sets (`macroSetsStore.loadAllMacros`) |
| GET | `/api/v1/macros/meta-topics` | List all meta-topics (`macroSetsStore.loadMetaTopics`; response `{meta_topics: [...]}`) |
| POST | `/api/v1/macros/meta-topics` | Create a new meta-topic (`{name: 'New Meta-Topic', description: '', topic_mappings: [], namespace: 'agent', is_active: true}`) |
| PUT | `/api/v1/macros/meta-topics/{id}` | Update meta-topic: rename (`{name}`), edit description (`{description}`), or replace `topic_mappings` (reorder / add / remove topics) |
| DELETE | `/api/v1/macros/meta-topics/{id}` | Delete the selected meta-topic |
| POST | `/api/v1/macros/meta-topics/{id}/save` | Backup: save the meta-topic to a file on the server; response carries a `message` |
| GET | `/api/v1/macros/saves` | List saved meta-topics (`{saves: [{folder, name, description, macro_set_count}]}`) for the load picker |
| POST | `/api/v1/macros/meta-topics/load/{folder}` | Restore: load a meta-topic from a saved file; returns `{meta_topic_id}` |
| PUT | `/api/v1/macros/{id}` | Update a macro set: `{topic, description, f1_macro, f2_macro, f3_macro, f4_macro, f5_macro}` |
| DELETE | `/api/v1/macros/{id}` | Delete a macro set (and remove its mapping from the meta-topic) |

## Related Pages

- [[AgentInteraction]] — chat page whose macro keyboard (F1–F5 / M1–M5) is driven by the same `useSystemMacrosStore` and `TopicFlyoutButton`; the Macros page is where those macro sets and meta-topics are authored
