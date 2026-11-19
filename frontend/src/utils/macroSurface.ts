/**
 * THE MACRO SURFACE (2026-09-03, the akeys roadmap Phase 5a — the
 * surface split). Agent chat + the Exa page render the SAME
 * ChatInterface, so the F-selection and the A-source were ONE shared
 * state. The split: Agent vs Exa x F vs A = FOUR independent
 * meta-topic selections, each persisted under its own key.
 *
 * LEGACY COMPAT: the agent surface keeps the ORIGINAL keys (no
 * suffix) — every existing user's selection survives untouched.
 * The exa surface gets ':exa'-suffixed keys.
 *
 *   base key                    | agent          | exa
 *   ----------------------------|----------------|--------------
 *   cogitate_selected_meta_topic| (legacy, bare) | ...:exa
 *   cogitate_akeys_meta_topic   | (legacy, bare) | ...:exa
 *
 * PURE module — unit-testable, no store.
 */

export type MacroSurface = 'agent' | 'exa'

export const SURFACE_EXA_SUFFIX = ':exa'

/** The F-selection keys (the M/F topic, fly-on-the-fly). */
export const F_SELECTION_BASE_KEY = 'cogitate_selected_meta_topic'

/** The A-source keys (the action-key bank source). */
export const AKEYS_BASE_KEY = 'cogitate_akeys_meta_topic'

/** The F-side fallback default — stays GLOBAL (the boot default; not
 * part of the four-state split). */
export const F_DEFAULT_KEY = 'cogitate_default_meta_topic'

/** The surface-scoped form of a base key: the agent surface keeps the
 * legacy bare key; every other surface gets a suffix. */
export function surfaceKey(base: string, surface: MacroSurface): string {
  return surface === 'agent' ? base : `${base}${SURFACE_EXA_SUFFIX}`
}

/** True when the surface's key differs from the bare/legacy key. */
export function isExaSurface(surface: MacroSurface): boolean {
  return surface === 'exa'
}

export function loadScopedId(base: string, surface: MacroSurface): number | null {
  try {
    const saved = localStorage.getItem(surfaceKey(base, surface))
    if (saved !== null) {
      const parsed = parseInt(saved, 10)
      return isNaN(parsed) ? null : parsed
    }
  } catch {
    // localStorage unavailable
  }
  return null
}

export function saveScopedId(base: string, surface: MacroSurface, id: number | null): void {
  try {
    if (id !== null) {
      localStorage.setItem(surfaceKey(base, surface), String(id))
    } else {
      localStorage.removeItem(surfaceKey(base, surface))
    }
  } catch {
    // localStorage unavailable
  }
}
