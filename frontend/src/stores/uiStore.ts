import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

interface UIStore {
  // UI state
  sidebarCollapsed: boolean
  theaterModeActive: boolean
  /**
   * The nav sidebar's Search box (2026-09-18) — P2 of
   * local/studies/exa-box-redesign-roadmap.md.
   *
   * UI STATE, not a preference: this is "the section is unrolled right
   * now", the same kind of fact as `sidebarCollapsed` beside it, and it
   * belongs in this store for the same reason (`appearance.keepCommandBoxOpen`
   * is the PREFERENCE, and it lives in the settings store).
   *
   * This is the ONE field the store persists — see the options below. It
   * was `askExaOpen` until the internal rename of 2026-09-19, so the
   * persisted key changed with it: a browser holding the old shape starts
   * closed once, which is the box's ordinary first-visit state.
   */
  navSearchOpen: boolean
  /**
   * THE FOCUS SIGNAL (2026-09-18) — how the app-wide Cmd/Ctrl+K gets the
   * caret into the box's input.
   *
   * The input's ref lives in `useCommandBox`, inside the sidebar section's
   * mount, so the shell cannot focus it directly. It does not try to: it sets
   * this flag, and the section — the ONE place the input exists — answers it
   * and clears it. A flag the section CONSUMES rather than a counter it
   * compares against, because the section is unmounted while the sidebar is
   * collapsed: a fresh mount must see a request that arrived before it
   * existed, and must not re-fire an old one.
   */
  navSearchFocusPending: boolean

  // Actions
  toggleSidebar: () => void
  setTheaterMode: (active: boolean) => void
  toggleNavSearch: () => void
  /**
   * THE APP-WIDE WAY IN — the one action the shell's single hotkey listener
   * performs. Raising the section is not enough on its own: the box's own
   * open flag is the hook's and the focus lives with it, so the request
   * travels as the signal above for the section to answer.
   *
   * Expanding the sidebar is part of the same fact: the section is not even
   * rendered while the rail is collapsed, so "open the box" means "show the
   * sidebar it lives in" — one store write, so a reader never sees an
   * expanded sidebar with the box still rolled up.
   */
  openNavSearch: () => void
  /**
   * THE CLOSE PATH (2026-09-19). Explicitly NOT `toggleNavSearch`: a close is
   * not a flip. The sidebar answers the hook's `close` with this — the panel's
   * ✕, Escape and a click away all arrive here — and a toggle would OPEN the
   * box in the one case where the two flags are already out of step.
   */
  closeNavSearch: () => void
  /** The section has put the caret in the input; drop the signal. */
  navSearchFocusSettled: () => void
}

export const useUIStore = create<UIStore>()(
  persist(
    (set, get) => ({
      // Initial state
      sidebarCollapsed: false,
      theaterModeActive: false,
      // Closed on arrival — but only on a FIRST arrival: the open state is
      // remembered, so a reader who left the box unrolled gets it back.
      navSearchOpen: false,
      // Nothing has asked for the caret yet.
      navSearchFocusPending: false,

      // Actions
      toggleSidebar: () => {
        const before = get().sidebarCollapsed
        console.log('[uiStore] toggleSidebar called, before:', before)
        set({ sidebarCollapsed: !before })
        const after = get().sidebarCollapsed
        console.log('[uiStore] toggleSidebar after set, after:', after)
      },
      setTheaterMode: (theaterModeActive: boolean) => set({ theaterModeActive }),
      /**
       * The expander's one control. No console.log companion to
       * `toggleSidebar`'s: that pair was added to chase a specific
       * report, and a second copy would only be noise.
       */
      toggleNavSearch: () => set({ navSearchOpen: !get().navSearchOpen }),
      /**
       * THE APP-WIDE WAY IN. One write, so the sidebar is expanded, the section
       * is unrolled and the caret is requested together — a reader cannot catch
       * it half-applied.
       */
      openNavSearch: () =>
        set({ sidebarCollapsed: false, navSearchOpen: true, navSearchFocusPending: true }),
      /**
       * One write, and only one direction: the box goes away. See the action's
       * own note on why this is not the toggle.
       */
      closeNavSearch: () => set({ navSearchOpen: false }),
      navSearchFocusSettled: () => set({ navSearchFocusPending: false }),
    }),
    {
      name: 'cogitate-ui',
      // localStorage, NOT sessionStorage: the expander's open state has to
      // survive a NEW TAB, and a new tab is a new session. sessionStorage is
      // the app's duration and would lose it exactly when it is wanted.
      storage: createJSONStorage(() => localStorage),
      /**
       * ONLY the expander's open state is remembered.
       *
       * `sidebarCollapsed` and `theaterModeActive` are facts about THIS
       * window as it is laid out right now, not decisions the reader made
       * about how the app should arrive; `navSearchFocusPending` is a one-shot
       * signal that must not outlive the moment it was raised. Persisting
       * any of them would change behaviour nobody asked to change.
       */
      partialize: (state) => ({ navSearchOpen: state.navSearchOpen }),
    }
  )
)

// Selectors for derived state
export const useSidebarCollapsed = () => useUIStore((state) => state.sidebarCollapsed)
export const useNavSearchOpen = () => useUIStore((state) => state.navSearchOpen)
