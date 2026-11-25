/* Macros store — fetches from the main macros API. */
import { create } from 'zustand';
import { useNotificationStore } from './notificationStore';
import { resolveAKeysSource, saveAKeysSourceId } from '../utils/aKeysSource';
import {
  F_DEFAULT_KEY,
  F_SELECTION_BASE_KEY,
  loadScopedId,
  saveScopedId,
  type MacroSurface,
} from '../utils/macroSurface';

const DEFAULT_META_TOPIC_NAME = 'System Guide';

/** THE SHIPPED PACK BINDINGS (GET /macros/macro-packs): which meta-topic the
 * install's packs put on each surface's F keys and A keys. This is the
 * INITIALIZATION answer — a fresh browser has no saved selection, so without it
 * the F keys fall back to a name constant and "whatever sorts first", and the A
 * keys to a name constant. Behind the user's own saved choice, and below it. */
export interface PackBindings {
  agent: { f: number | null; a: number | null }
  exa: { f: number | null; a: number | null }
}

const NO_BINDINGS: PackBindings = {
  agent: { f: null, a: null },
  exa: { f: null, a: null },
}

async function fetchPackBindings(): Promise<PackBindings | null> {
  try {
    const resp = await fetchWithTimeout('/api/v1/macros/macro-packs');
    if (!resp.ok) return null;
    const data = await resp.json();
    const b = data && data.bindings;
    if (!b || typeof b !== 'object') return null;
    return {
      agent: { f: b.agent?.f ?? null, a: b.agent?.a ?? null },
      exa: { f: b.exa?.f ?? null, a: b.exa?.a ?? null },
    };
  } catch {
    // An unknown binding is not an error — the older fallbacks still apply.
    return null;
  }
}

function loadSavedMetaTopicId(surface: MacroSurface): number | null {
  return loadScopedId(F_SELECTION_BASE_KEY, surface);
}

function saveMetaTopicId(surface: MacroSurface, id: number | null): void {
  saveScopedId(F_SELECTION_BASE_KEY, surface, id);
}

function loadDefaultMetaTopicId(): number | null {
  try {
    const saved = localStorage.getItem(F_DEFAULT_KEY);
    if (saved !== null) {
      const parsed = parseInt(saved, 10);
      return isNaN(parsed) ? null : parsed;
    }
  } catch {
    // localStorage unavailable
  }
  return null;
}

// THE MACRO-FETCH GUARD (2026-09-03, the selector-hang + silent-
// failure dig): the bare fetch() calls below had NO timeout — when
// the vite proxy held the connection (backend down), the flyout
// spinnered forever (the topic-selector hang the user reported).
// And failures were console.error-only — never reached the message
// center. Both fixed: every fetch gets a timeout + a throttled
// addError that lands in the center (the notificationStore choke
// point). Throttle: max one per 10s (the apiClient's rate).
let lastMacroLoadErrorAt = 0;

async function fetchWithTimeout(url: string, ms = 8000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

function notifyMacroLoadFailure(title: string, message: string): void {
  const now = Date.now();
  if (now - lastMacroLoadErrorAt < 10000) return; // throttled
  lastMacroLoadErrorAt = now;
  useNotificationStore.getState().addError(title, message, 10000);
}

function saveDefaultMetaTopicId(id: number | null): void {
  try {
    if (id !== null) {
      localStorage.setItem(F_DEFAULT_KEY, String(id));
    } else {
      localStorage.removeItem(F_DEFAULT_KEY);
    }
  } catch {
    // localStorage unavailable
  }
}

function findDefaultTopic(metaTopics: any[], shippedDefaultId: number | null = null): number | null { // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
  // 1) Prefer user's saved default
  const savedDefault = loadDefaultMetaTopicId();
  if (savedDefault !== null && metaTopics.some((mt: any) => mt.id === savedDefault)) { // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
    return savedDefault;
  }
  // 2) The shipped pack's F binding for this surface (the initialization answer)
  if (shippedDefaultId !== null && metaTopics.some((mt: any) => mt.id === shippedDefaultId)) { // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
    return shippedDefaultId;
  }
  // 3) Fall back to the built-in named default
  const defaultTopic = metaTopics.find((mt: any) => mt.name === DEFAULT_META_TOPIC_NAME); // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
  if (defaultTopic) return defaultTopic.id;
  // 4) Fall back to first available
  if (metaTopics.length > 0) return metaTopics[0].id;
  // 5) No topics at all
  return null;
}

interface SystemMacrosState {
  macroSets: any[]; // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
  metaTopics: any[]; // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
  // THE SURFACE (2026-09-03, the akeys roadmap Phase 5a — the split):
  // which chat surface the F/A state belongs to. ChatInterface sets
  // it on mount (agentId === 'exa' ? 'exa' : 'agent'). Pages are
  // separate routes, never co-mounted, so ONE active surface is
  // correct — the components stay dumb; the storage keys scope by it.
  surface: MacroSurface;
  setSurface: (surface: MacroSurface) => void;
  selectedMetaTopicId: number | null;
  defaultMetaTopicId: number | null;
  // THE A-KEY SOURCE (2026-09-03, the akeys roadmap Phase 1): the
  // resolved meta-topic feeding the A1-A5 flyouts — its OWN persisted
  // default (cogitate_akeys_meta_topic), NEVER the F/M keys. The
  // cascade: explicit -> seeded 'A-Key Macros' -> null (deactivated).
  aKeysMetaTopicId: number | null;
  // THE SHIPPED PACK BINDINGS — see PackBindings above.
  packBindings: PackBindings;
  isLoading: boolean;
  isLoadingMetaTopics: boolean;
  hasNoTopics: boolean;
  loadMetaTopics: () => void;
  selectMetaTopic: (id: number | null) => void;
  setAsDefaultTopic: (id: number | null) => void;
  setAKeysDefault: (id: number | null) => void;
  loadAllMacros: () => void;
  reloadMacros: () => void;
  // THE BUILD FIX (2026-08-26, the tsc -b — the useModeMacros +
  // the Macros page read these; the state-type lagged the store).
  macros: Record<string, string>[]
  error: string | null
  clearErrors: () => void
  clearData: () => void
}

export const useSystemMacrosStore = create<SystemMacrosState>((set, get) => ({
  macroSets: [],
  metaTopics: [],
  // The agent surface is the legacy default (bare keys — no migration)
  surface: 'agent' as MacroSurface,
  setSurface: (surface: MacroSurface) => {
    // THE SURFACE SWITCH (2026-09-03): flip the active surface, then
    // re-resolve BOTH the F-selection and the A-source from that
    // surface's keys against the CURRENT metaTopics (no refetch — the
    // topic list is surface-independent; only the selection is not).
    const metaTopics = get().metaTopics;
    const bindings = get().packBindings[surface];
    const saved = loadSavedMetaTopicId(surface);
    const selectedId = saved !== null && metaTopics.some((mt: any) => mt.id === saved) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
      ? saved
      : findDefaultTopic(metaTopics, bindings.f);
    const aKeysSourceId = resolveAKeysSource(metaTopics, surface, undefined, bindings.a);
    set({ surface, selectedMetaTopicId: selectedId, aKeysMetaTopicId: aKeysSourceId });
    if (metaTopics.length > 0) saveMetaTopicId(surface, selectedId);
  },
  selectedMetaTopicId: loadSavedMetaTopicId('agent'),
  isLoading: false,
  isLoadingMetaTopics: false,
  defaultMetaTopicId: loadDefaultMetaTopicId(),
  aKeysMetaTopicId: resolveAKeysSource([], 'agent'), // resolved on load; [] -> null (seed absent until topics arrive)
   packBindings: NO_BINDINGS,
  hasNoTopics: false,
  macros: [],
  error: null,
  clearErrors: () => {},
  clearData: () => {},

  loadMetaTopics: async () => {
    set({ isLoadingMetaTopics: true });
    try {
      const [resp, fetched] = await Promise.all([
        fetchWithTimeout('/api/v1/macros/meta-topics'),
        fetchPackBindings(),
      ]);
      if (resp.ok) {
        const data = await resp.json();
        const metaTopics = data.meta_topics || data || [];

        // Determine which topic to select (surface-scoped, 2026-09-03)
        const surface = get().surface;
        const bindings = (fetched ?? get().packBindings)[surface];
        let selectedId: number | null = null;
        const saved = loadSavedMetaTopicId(surface);

        if (saved !== null && metaTopics.some((mt: any) => mt.id === saved)) { // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
          // Saved topic still exists — keep it
          selectedId = saved;
        } else {
          // No saved topic, saved topic was deleted, or topic list empty
          selectedId = findDefaultTopic(metaTopics, bindings.f);
        }

        // Show toast if no topics available at all
        const hasNoTopics = metaTopics.length === 0;
        if (hasNoTopics) {
          useNotificationStore.getState().addWarning(
            'No Macro Topics',
            'No macro meta-topics found. Please create one in the Macros page or select a topic using the Topic button.',
            8000,
          );
        }

        if (selectedId !== saved) {
          saveMetaTopicId(surface, selectedId);
        }

        // THE A-KEY SOURCE RESOLUTION (2026-09-03, the akeys Phase 1):
        // the cascade runs on every load — explicit A-default -> the
        // seeded 'A-Key Macros' -> null (deactivated). Independent of
        // the F-side selection above; the two never read each other.
        // Surface-scoped since Phase 5a (the split).
        const aKeysSourceId = resolveAKeysSource(metaTopics, surface, undefined, bindings.a);

        set({ metaTopics, selectedMetaTopicId: selectedId, hasNoTopics, isLoadingMetaTopics: false, aKeysMetaTopicId: aKeysSourceId, packBindings: (fetched ?? get().packBindings) });
      } else {
        set({ isLoadingMetaTopics: false });
      }
    } catch (e) {
      // THE VISIBLE FAILURE (2026-09-03): console.error alone was a
      // silent failure — the user saw an empty/hanging topic list
      // with no explanation and nothing in the message center.
      console.error('Failed to load meta-topics:', e);
      notifyMacroLoadFailure(
        'Macro Topics Unavailable',
        'Could not load the meta-topics. Check the backend connection and try again.',
      );
      set({ isLoadingMetaTopics: false });
    }
  },

  selectMetaTopic: (id: number | null) => {
    const surface = get().surface;
    saveMetaTopicId(surface, id);
    set({ selectedMetaTopicId: id });
  },

  setAsDefaultTopic: (id: number | null) => {
    saveDefaultMetaTopicId(id);
    set({ defaultMetaTopicId: id });
  },

  // THE A-KEY SOURCE SETTER (2026-09-03): persists to the A-keys'
  // OWN storage key — the F/M default keys are never touched. Called
  // from the Macros page ("Set as Action-key default" / Clear).
  setAKeysDefault: (id: number | null) => {
    const surface = get().surface;
    saveAKeysSourceId(surface, id);
    set({ aKeysMetaTopicId: id });
  },

  loadAllMacros: async () => {
    set({ isLoading: true });
    try {
      const resp = await fetchWithTimeout('/api/v1/macros?all=true');
      if (resp.ok) {
        const data = await resp.json();
        set({ macroSets: data.macro_sets || data || [], isLoading: false });
      } else {
        set({ isLoading: false });
      }
    } catch (e) {
      console.error('Failed to load macros:', e);
      notifyMacroLoadFailure(
        'Macros Unavailable',
        'Could not load the macro sets. Check the backend connection and try again.',
      );
      set({ isLoading: false });
    }
  },

  reloadMacros: async () => {
    set({ isLoading: true, isLoadingMetaTopics: true });
    try {
      const [metaResp, macroResp, fetched] = await Promise.all([
        fetchWithTimeout('/api/v1/macros/meta-topics'),
        fetchWithTimeout('/api/v1/macros?all=true'),
        fetchPackBindings(),
      ]);
      let metaTopics: any[] = []; // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
      if (metaResp.ok) {
        const data = await metaResp.json();
        metaTopics = data.meta_topics || data || [];
      }
      let macroSets: any[] = []; // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
      if (macroResp.ok) {
        const data = await macroResp.json();
        macroSets = data.macro_sets || data || [];
      }

      // Preserve current selection if it still exists (surface-scoped)
      const surface = get().surface;
      const packBindings = fetched ?? get().packBindings;
      const bindings = packBindings[surface];
      const currentId = get().selectedMetaTopicId;
      const selectedId = (currentId !== null && metaTopics.some((mt: any) => mt.id === currentId)) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
        ? currentId
        : findDefaultTopic(metaTopics, bindings.f);

      const hasNoTopics = metaTopics.length === 0;
      if (hasNoTopics) {
        useNotificationStore.getState().addWarning(
          'No Macro Topics',
          'No macro meta-topics found. Create one in the Macros page or select a topic using the Topic button.',
          8000,
        );
      }

      const aKeysSourceId = resolveAKeysSource(metaTopics, surface, undefined, bindings.a);

      set({ metaTopics, macroSets, selectedMetaTopicId: selectedId, hasNoTopics, isLoading: false, isLoadingMetaTopics: false, aKeysMetaTopicId: aKeysSourceId, packBindings });
    } catch (e) {
      console.error('Failed to reload macros:', e);
      notifyMacroLoadFailure(
        'Macros Unavailable',
        'Could not reload the macro banks. Check the backend connection and try again.',
      );
      set({ isLoading: false, isLoadingMetaTopics: false });
    }
  },
}));
