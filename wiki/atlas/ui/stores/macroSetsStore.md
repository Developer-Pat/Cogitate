---
title: macroSetsStore
type: atlas-store
path: frontend/src/stores/macroSetsStore.ts
confidence: high
updated: 2026-09-03
tags: [type/store, domain/atlas-ui]
---
# macroSetsStore

**Path**: `frontend/src/stores/macroSetsStore.ts`
**Type**: store (Zustand)

## Purpose
System macros store — macro sets + meta-topics state (SystemMacrosState), the F-topic + A-source selections, the ACTIVE SURFACE (agent vs exa), load/reload. Uses RAW fetch for meta-topics (bypasses metaTopicsService).

## State Shape
```typescript
interface SystemMacrosState {
  macroSets: any[];
  metaTopics: any[];
  surface: MacroSurface;            // 'agent' | 'exa' — set on mount (Phase 5a)
  selectedMetaTopicId: number | null;  // the F/M topic (surface-scoped)
  defaultMetaTopicId: number | null;   // the F fallback (surface-scoped)
  aKeysMetaTopicId: number | null;     // the A-KEY source (its OWN key, Phase 1)
  isLoading: boolean;
  isLoadingMetaTopics: boolean;
  hasNoTopics: boolean;
  macros: Record<string, string>[];
  error: string | null;
  setSurface: (surface: MacroSurface) => void;
  loadMetaTopics: () => void;
  selectMetaTopic: (id: number | null) => void;
  setAsDefaultTopic: (id: number | null) => void;
  setAKeysDefault: (id: number | null) => void;
  loadAllMacros: () => void;
  reloadMacros: () => void;
  clearErrors: () => void;
  clearData: () => void;
}
```

## Actions
- setSurface — flips the active surface + re-resolves the F-selection and the A-source from that surface's keys (no refetch; the topic list is surface-independent)
- loadMetaTopics (raw fetch /api/v1/macros/meta-topics) — resolves the F-selection (saved → default → first agent topic) AND the A-source cascade (explicit → seeded 'A-Key Macros' → null) surface-scoped
- selectMetaTopic (F selection — saves to `cogitate_selected_meta_topic`), setAsDefaultTopic (the F fallback — `cogitate_default_meta_topic`), setAKeysDefault (the A-source — `cogitate_akeys_meta_topic`)
- loadAllMacros, reloadMacros — `reloadMacros` is now the EVENT-BUS reload (called by `useMacroSync` on the backend's `macro:<id>:<event>` / `meta-topic:*` publishes — the visible refresh button was removed, Phase 5c)

## Selectors / Exports
```typescript
export const useSystemMacrosStore = create<SystemMacrosState>(...)
```

## Persistence (the SURFACE SPLIT, Phase 5a — `utils/macroSurface`)
| key | agent surface | exa surface |
|---|---|---|
| F selection | `cogitate_selected_meta_topic` (bare — legacy) | `cogitate_selected_meta_topic:exa` |
| A source | `cogitate_akeys_meta_topic` (bare) | `cogitate_akeys_meta_topic:exa` |

The four states (agent/exa × F/A) never read each other; agent keeps the legacy bare keys (no migration).

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| useNotificationStore | stores/notificationStore.ts | Notifications |
| macroSurface (`utils/macroSurface`) | Utils | loadScopedId / saveScopedId over the base keys |
| aKeysSource (`utils/aKeysSource`) | Utils | The A-source cascade resolver (explicit → seeded → null) |

## Usage Example
```tsx
const { metaTopics, selectedMetaTopicId, aKeysMetaTopicId, selectMetaTopic, setSurface } = useSystemMacrosStore()
// ChatInterface sets the surface on mount: setSurface(agentId === 'exa' ? 'exa' : 'agent')
```

## Data Flow / Notes
- loadMetaTopics uses raw fetch — metaTopicsService is bypassed (see its obsolete flag)
- The F-side and the A-side are INDEPENDENT: the A-source never reads the F selection (the conflation guard)

## Related
- pages/Macros.tsx, ChatInterface.tsx, TopicFlyoutButton.tsx (via MacroKeyboard) — consumers
- hooks/useModeMacros.ts, hooks/useMacroSync.ts — consumers
- services/metaTopicsService.ts — bypassed (dead-code candidate)

## Deprecation / Obsolete Notes
Active (5 consumers). No deprecation markers. Note: state interface named SystemMacrosState (legacy naming).