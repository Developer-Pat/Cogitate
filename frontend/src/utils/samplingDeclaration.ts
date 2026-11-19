/**
 * The sampling an agent declares — one home for what a preset sets and what "nothing" means.
 *
 * An agent declares its own sampling (`AgentParameters`: temperature 0-2, top_p 0-1) or it
 * declares NOTHING, and "nothing" is a legitimate state with a named consequence: the field
 * is left absent, the completion request carries no such setting, and the provider's own
 * default applies (`backend/app/domain/runtime_config/sampling.py`). Everything here keeps an
 * absent field absent from the form to the wire — no value is invented to fill the slot.
 *
 * The BOUNDS are not enforced here: they live on the backend model (`AgentParameters`' own
 * `ge`/`le`), which is the guard. These numbers only give the sliders their limits.
 */
export interface SamplingDeclaration {
  temperature?: number
  top_p?: number
}

export interface SamplingPreset {
  id: string
  label: string
  emoji: string
  tip: string
  values: Required<SamplingDeclaration>
}

/** A preset CLICK is a deliberate act — the one path that sets a pair without a drag. */
export const SAMPLING_PRESETS: SamplingPreset[] = [
  {
    id: 'precise',
    label: 'Precise',
    emoji: '📊',
    tip: 'Temperature 0.3, top_p 0.9 — low variance',
    values: { temperature: 0.3, top_p: 0.9 }
  },
  {
    id: 'balanced',
    label: 'Balanced',
    emoji: '⚖️',
    tip: 'Temperature 0.7, top_p 0.9 — the middle of the range',
    values: { temperature: 0.7, top_p: 0.9 }
  },
  {
    id: 'creative',
    label: 'Creative',
    emoji: '🎨',
    tip: 'Temperature 1.2, top_p 0.95 — wider sampling, more variety',
    values: { temperature: 1.2, top_p: 0.95 }
  }
]

/**
 * Where a slider RESTS while its field is undeclared — a control's position, never a value.
 * The readout beside it says "not set" and the payload carries nothing until a drag, so the
 * thumb's position cannot be mistaken for a declared number.
 */
export const SAMPLING_SLIDER_REST: Required<SamplingDeclaration> = { temperature: 1, top_p: 0.5 }

/** The sliders' own limits (the API's guard is the authority; these shape the control). */
export const SAMPLING_BOUNDS = {
  temperature: { min: 0, max: 2, step: 0.1 },
  top_p: { min: 0, max: 1, step: 0.1 }
} as const

/**
 * The declared pair, or null when nothing is declared.
 *
 * `typeof === 'number'` rather than truthiness, on purpose: `0` is a legal temperature and
 * a legal top_p, and a falsy check would drop exactly those declarations.
 */
export function declaredSampling(
  parameters: SamplingDeclaration | null | undefined
): SamplingDeclaration | null {
  if (!parameters) return null
  const declared: SamplingDeclaration = {}
  if (typeof parameters.temperature === 'number') declared.temperature = parameters.temperature
  if (typeof parameters.top_p === 'number') declared.top_p = parameters.top_p
  return Object.keys(declared).length > 0 ? declared : null
}

/** Whether this agent declares any sampling at all. */
export function hasDeclaredSampling(
  parameters: SamplingDeclaration | null | undefined
): boolean {
  return declaredSampling(parameters) !== null
}

/** The one-line reading of a declaration, for the form's own statement of its state. */
export function describeSampling(
  parameters: SamplingDeclaration | null | undefined
): string | null {
  const declared = declaredSampling(parameters)
  if (!declared) return null
  const parts: string[] = []
  if (declared.temperature !== undefined) parts.push(`temperature ${declared.temperature}`)
  if (declared.top_p !== undefined) parts.push(`top_p ${declared.top_p}`)
  return parts.join(' · ')
}
