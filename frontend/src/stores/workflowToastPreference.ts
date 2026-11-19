import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

/**
 * The workflow-toast preference (Phase G, 2026-08-18).
 *
 * ALL-OR-NOTHING for now: a single switch gates whether the
 * delivery toasts (the folder-watcher "do something") appear.
 * Later this can expand to per-type filtering.
 *
 * Persisted so the choice survives reloads. The hook still POLLS
 * + advances the cursor while off (no backlog flood on re-enable);
 * it just stops SHOWING the toasts.
 */
interface WorkflowToastPreference {
  toastsEnabled: boolean;
  setToastsEnabled: (enabled: boolean) => void;
  toggleToasts: () => void;
}

const STORAGE_KEY = 'workflow_toasts_enabled';

export const useWorkflowToastPreference = create<WorkflowToastPreference>()(
  persist(
    (set) => ({
      toastsEnabled: true,
      setToastsEnabled: (enabled) => set({ toastsEnabled: enabled }),
      toggleToasts: () => set((s) => ({ toastsEnabled: !s.toastsEnabled })),
    }),
    { name: STORAGE_KEY, storage: createJSONStorage(() => localStorage) }
  )
);

export default useWorkflowToastPreference;
