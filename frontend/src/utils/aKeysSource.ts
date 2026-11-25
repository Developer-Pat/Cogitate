/**
 * THE A-KEY SOURCE (2026-09-03, the A-keys-as-a-second-macro-bank arc)
 *
 * The A1-A5 action keys are a SECOND macro bank fed by a meta-topic
 * (see local/akeys/01-roadmap.md). This module owns the A source's
 * persistence + resolution — PURE, no store, so the cascade is
 * unit-testable in isolation.
 *
 * THE CONFLATION GUARD (the user's design rule): the A source is a
 * SEPARATE concept from the F/M defaults:
 *   - 'cogitate_selected_meta_topic[:exa]' -> the ACTIVE topic (F/M)
 *   - 'cogitate_default_meta_topic'         -> the F-side FALLBACK
 *   - 'cogitate_akeys_meta_topic[:exa]'     -> the ACTION-KEY SOURCE
 * A never reads the F/M keys; the F/M paths never touch this key.
 * (The surface split, 2026-09-03 Phase 5a: agent keeps the legacy
 * bare keys; exa gets ':exa' — see macroSurface.ts.)
 *
 * THE CASCADE (the roadmap decision 4): explicit A-default -> the
 * seeded "A-Key Macros" meta-topic -> NULL + a visible reason. NOT
 * first-available: A content is semantic (conversational/diagnostic
 * utility), so wrong content is worse than none. Missing source =
 * the A-row deactivates (the caller renders the reason).
 */
import {
  AKEYS_BASE_KEY,
  loadScopedId,
  saveScopedId,
  type MacroSurface,
} from './macroSurface'

/** The seeded out-of-box source name (the code-seed pattern; Phase 3
 * creates the actual rows). The resolver knows it by convention. */
export const AKEYS_SEED_META_TOPIC_NAME = 'A-Key Macros'

export interface AKeySourceTopic {
  id: number
  name: string
}

export function loadAKeysSourceId(surface: MacroSurface): number | null {
  return loadScopedId(AKEYS_BASE_KEY, surface)
}

export function saveAKeysSourceId(surface: MacroSurface, id: number | null): void {
  saveScopedId(AKEYS_BASE_KEY, surface, id)
}

/**
 * THE CASCADE RESOLVER: which meta-topic feeds the A1-A5 flyouts?
 *   1) the explicit saved A-default — if it still exists
 *   2) the SHIPPED PACK's A binding for this surface — the initialization
 *      answer a fresh install has no browser storage to remember
 *   3) the seeded "A-Key Macros" topic — if present (the older out-of-box)
 *   4) NULL — deactivated (never first-available; the caller shows
 *      "No Action-key source" instead of arbitrary content)
 */
export function resolveAKeysSource(
  metaTopics: AKeySourceTopic[],
  surface: MacroSurface,
  savedId: number | null = loadAKeysSourceId(surface),
  shippedId: number | null = null,
): number | null {
  // 1) Explicit A-default (still exists)
  if (savedId !== null && metaTopics.some((mt) => mt.id === savedId)) {
    return savedId
  }
  // 2) The shipped pack's binding (GET /macros/macro-packs)
  if (shippedId !== null && metaTopics.some((mt) => mt.id === shippedId)) {
    return shippedId
  }
  // 3) The seeded out-of-box topic
  const seed = metaTopics.find((mt) => mt.name === AKEYS_SEED_META_TOPIC_NAME)
  if (seed) return seed.id
  // 4) Deactivated — never arbitrary content
  return null
}
