/**
 * The settings CONTRACT (2026-09-18).
 *
 * The type, the zod schema and the defaults are three copies of ONE shape, and
 * they drift silently: a field added to the type but forgotten in the schema is
 * accepted at compile time and rejected at RUNTIME, in a place that looks
 * unrelated to the edit. The cheap guard is to make the schema parse the
 * defaults and compare exactly — any divergence in either direction fails here.
 */
import { describe, it, expect } from 'vitest';
import { defaultSettings, SettingsSchema } from '../settings';

describe('the settings contract', () => {
  it('the schema accepts the defaults — so the three copies of the shape agree', () => {
    expect(SettingsSchema.parse(defaultSettings)).toEqual(defaultSettings);
  });

  it('the command box stays closed by default', () => {
    // integration-boundaries P4: capabilities start OFF, and the grant is
    // explicit. P1 of local/studies/exa-box-redesign-roadmap.md.
    expect(defaultSettings.appearance.keepCommandBoxOpen).toBe(false);
  });
});
