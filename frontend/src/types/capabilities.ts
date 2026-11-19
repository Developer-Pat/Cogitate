/**
 * The CAPABILITY READ-OUT's types — "which service does each part of the app use, and what are its
 * backups?" (the service-capability arc; the backend sub-area lives at
 * `backend/app/api/v1/providers/capabilities_router.py`).
 *
 * ⚠️ These are NOT the Model Browser's capability badges. `CapabilityInfo` in
 * `services/domains/providers/modelBrowserService.ts` is a MODEL's text/image/video flags — a
 * different question wearing a similar word. The names here are distinct on purpose: two
 * `interface` declarations of one name in a module MERGE silently and the union widens the
 * contract, which is how a type ends up claiming fields the endpoint never sends.
 */

/** What a caller RECEIVES from a capability: an LLM client, a speech engine, or a process. */
export type CapabilityKind = 'llm' | 'speech' | 'process'

/**
 * One attemptable service in a capability's chain.
 *
 * A candidate names its service in exactly ONE of three forms, and all three are carried so a
 * chain read from the API can be sent straight back as a write:
 * `provider_id` (a provider row) · `require_location` (a CLASS — 'prefer local') ·
 * `service_name` (a named engine/process that is not a provider row).
 */
export interface CapabilityCandidate {
  /** Position in the chain: 0 is the primary, the rest are backups in order. */
  ordinal: number
  /** The provider row's NAME (`deepseek`, `llama`) — the handle a failure names. */
  provider?: string | null
  provider_id?: number | null
  provider_type?: string | null
  /** The model to run; when absent the provider row's own `default_model` answers. */
  model?: string | null
  /** The class form, as WRITTEN — 'local' | 'cloud' (a class candidate expands into rows). */
  require_location?: string | null
  /** The resolved location of this candidate: 'local' | 'cloud'. */
  location?: string | null
  service_name?: string | null
  thinking?: string | null
  /** The row's own switch. A resolved candidate is always on (the resolution filters off rows out). */
  enabled?: boolean
  /**
   * Where this candidate came from: `row` / `class` / `named` on a configured chain, `stored` in the
   * edit path's list, and `agent`, `override` or `default` when a rung ABOVE the capability answered.
   */
  source: string
  // ── AVAILABILITY (the service-capability arc's group 5) ────────────────────────────────────
  // The state the ONE availability read last found for this candidate's service: `available` |
  // `down-by-occupancy` | `down` | `unconfigured` | `unknown`. `available` is the derived boolean a
  // surface keys on — and **null means "never checked", deliberately NOT false**, so the page says
  // so rather than calling an unprobed service broken. `checked_at` rides with it because the copy
  // must own the staleness window.
  availability_state?: string
  available?: boolean | null
  availability_reason?: string | null
  checked_at?: string | null
}

/** A capability and what it resolves to right now. */
export interface CapabilityReadout {
  key: string
  label?: string | null
  kind: CapabilityKind | string
  /** The capability's own off switch. OFF (`false`) resolves to nothing — it never falls through. */
  enabled: boolean
  /** Which rung answered: 'capability config' · 'global default' · 'agent profile' · 'override' · 'disabled' · 'none'. */
  reason: string
  /** `deepseek/deepseek-v4-flash -> llama/qwen3` — one line, for a log or a tooltip. */
  chain: string
  primary?: CapabilityCandidate | null
  backups: CapabilityCandidate[]
  /**
   * The capability's OWN stored rows, in order — what the EDIT path reads and writes.
   *
   * Deliberately NOT the same list as `primary`/`backups`: the ladder can answer with an agent's
   * declaration, a class candidate expands into every row it matches, and a row switched OFF is
   * filtered out of the resolution. Sending the resolution back would drop the disabled row.
   */
  configured: CapabilityCandidate[]
  /**
   * What the save cannot fix — null unless there is something to say.
   *
   * The write path RESETS the RAG vector stores, so a saved embedding model reaches the process on its
   * next use. What no reset repairs is the INDEX's width: an index keeps the width it was created at,
   * so a model of another width has to be followed by a re-ingest — and the backend composes that
   * sentence here.
   */
  note?: string | null
}

/** One candidate as a WRITE supplies it — exactly one of the three forms. */
export interface CapabilityCandidateInput {
  provider_id?: number | null
  require_location?: string | null
  service_name?: string | null
  model?: string | null
  thinking?: string | null
  enabled?: boolean
}

/**
 * A capability's WHOLE chain, plus its own two editable fields.
 *
 * `candidates` is required: this is a replace, not a patch — a candidate's position in the list IS
 * its ordinal, so no request can leave two attempts sharing one.
 */
export interface CapabilityUpdate {
  label?: string | null
  enabled?: boolean
  candidates: CapabilityCandidateInput[]
}

/** The whole read-out, plus the kinds this revision understands. */
export interface CapabilityReadoutResponse {
  capabilities: CapabilityReadout[]
  kinds: string[]
  total: number
}
