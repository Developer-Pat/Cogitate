import { describe, expect, it } from 'vitest'

import {
  SAMPLING_PRESETS,
  declaredSampling,
  describeSampling,
  hasDeclaredSampling
} from '../samplingDeclaration'

describe('the sampling declaration — declared, or nothing', () => {
  it('reads an undeclared pair as nothing, however it arrives', () => {
    expect(declaredSampling(undefined)).toBeNull()
    expect(declaredSampling(null)).toBeNull()
    expect(declaredSampling({})).toBeNull()
    // a key present but not a number is not a declaration either
    expect(declaredSampling({ temperature: undefined })).toBeNull()
  })

  it('keeps ZERO — a falsy value is a legal declaration', () => {
    // `temperature: 0` and `top_p: 0` are inside the bound the API enforces, so a
    // truthiness check here would silently drop exactly those two declarations.
    expect(declaredSampling({ temperature: 0 })).toEqual({ temperature: 0 })
    expect(declaredSampling({ top_p: 0 })).toEqual({ top_p: 0 })
    expect(declaredSampling({ temperature: 0, top_p: 0 })).toEqual({ temperature: 0, top_p: 0 })
  })

  it('carries one field without inventing the other', () => {
    expect(declaredSampling({ temperature: 0.4 })).toEqual({ temperature: 0.4 })
    expect(hasDeclaredSampling({ temperature: 0.4 })).toBe(true)
    expect(hasDeclaredSampling(undefined)).toBe(false)
  })

  it('states what is sent, naming only the fields that are set', () => {
    expect(describeSampling(undefined)).toBeNull()
    expect(describeSampling({ temperature: 0.4 })).toBe('temperature 0.4')
    expect(describeSampling({ temperature: 0.4, top_p: 0.9 })).toBe(
      'temperature 0.4 · top_p 0.9'
    )
  })

  it('holds the three named presets, each a complete pair inside its bound', () => {
    expect(SAMPLING_PRESETS.map((p) => p.id)).toEqual(['precise', 'balanced', 'creative'])
    for (const preset of SAMPLING_PRESETS) {
      expect(typeof preset.tip).toBe('string')
      expect(preset.tip.length).toBeGreaterThan(0)
      expect(preset.values.temperature).toBeGreaterThanOrEqual(0)
      expect(preset.values.temperature).toBeLessThanOrEqual(2)
      expect(preset.values.top_p).toBeGreaterThanOrEqual(0)
      expect(preset.values.top_p).toBeLessThanOrEqual(1)
    }
  })

  it('has no preset that declares nothing — the clear is its own control', () => {
    // "Declare nothing" is the switch OFF (and the button that does the same), so no
    // preset may carry an empty pair: a preset is a decision, an absence is not.
    for (const preset of SAMPLING_PRESETS) {
      expect(declaredSampling(preset.values)).not.toBeNull()
    }
  })
})
