/**
 * Curated Model Lists Configuration
 *
 * THE A2 SHRINK (2026-09-09, the seeding removal): this file once
 * carried the curated model seed-data (mirrored into the DB by the
 * 0049-era migrations). The DB is now the single source of truth
 * for curated state and fresh installs boot with an EMPTY curated
 * table — the collaboration arc fills it, never a shipped seed.
 *
 * What remains: the shared TYPES (the API + the manager import
 * them) and the getCuratedModelsForProvider helper, which now
 * always returns [] — the profile picker's Tier-3 fallback falls
 * straight through to the live browse.
 */

/**
 * Model Category — a row's OPTIONAL one-word descriptor of what the model is FOR.
 *
 * ONE AXIS. The cost fact is not here: it is the `isFree` badge's own column, and the words
 * that used to sit here for it ("budget", "performance") only repeated it. Neither is the
 * retired editorial flag — the app does not privilege models. And a row may state NOTHING:
 * an absent category means nobody has described it yet.
 */
export type ModelCategory =
  | 'chat'           // The everyday conversational driver
  | 'code'           // Coding and tool work
  | 'reasoning'      // Hard, multi-step problems
  | 'vision'         // Takes images

/**
 * The capability dimensions — the substitution matcher's axes.
 *
 * THE BACKEND IS THE AUTHORITY: `THINKING_LEVELS`
 * (`app/services/cognitive_pipeline/reasoning_support.py`) and `MODEL_LOCATIONS`
 * (`app/domain/providers/curated_models_service.py`). The API validates every write
 * against those and refuses anything else with a 422, so this copy decides only what the
 * form OFFERS — and its stale-copy failure is benign in both directions: a value added to
 * the backend and not here is simply not selectable (an API caller can still send it),
 * and nothing the UI can send is ever refused.
 *
 * `mandatory` is not a fourth degree of effort: it says the driver cannot be told not to
 * think, so its output-budget floor is a property of the driver rather than a policy.
 * `any` is the matcher's SPEC-side tolerance, not a home a row can state.
 */
export const THINKING_LEVELS = ['none', 'low', 'medium', 'high', 'mandatory'] as const
export type ThinkingLevel = (typeof THINKING_LEVELS)[number]

export const MODEL_LOCATIONS = ['local', 'cloud'] as const
export type ModelLocation = (typeof MODEL_LOCATIONS)[number]

/**
 * Curated Model Entry (the API row shape)
 */
export interface CuratedModel {
  id: string              // Model ID (e.g., "nvidia/nemotron-3-super-120b-a12b:free")
  name: string            // Display name
  provider: string        // Provider name (openrouter, ollama, etc.)
  category?: ModelCategory // Optional one-word descriptor; absent = not described
  description?: string    // Short description
  contextLength?: number  // Context window size
  isFree?: boolean | null  // free / paid / unknown (nobody has priced it) — Phase 4
  verified?: boolean      // Seen in the live catalog cache
  thinking?: ThinkingLevel // Declared thinking level — ranks the matcher, floors the budget
  location?: ModelLocation // Runtime home
  curatedRowId?: number   // The DB row id (the manager's rows)
}

/**
 * The seed is gone. Runtime curated lists come from the API
 * (GET /api/v1/curated-models); this empty record keeps the
 * legacy import surface compiling while the callers migrate.
 */
export const curatedModelLists: Record<string, CuratedModel[]> = {}

/**
 * Tier-3 fallback for the profile picker: the empty seed means no
 * static recommendations — the picker falls through to the live
 * browse (the Tier 2) and the manual entry.
 */
export function getCuratedModelsForProvider(_provider: string): CuratedModel[] {
  return []
}
