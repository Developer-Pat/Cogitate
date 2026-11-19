/**
 * THE A-KEY SOURCE tests (2026-09-03, the akeys arc — updated 2026-09-03
 * for Phase 5a, the SURFACE SPLIT).
 *
 * Pin the behaviors:
 * 1. The CASCADE per surface: explicit A-default wins; the seeded
 *    "A-Key Macros" falls back; missing -> null (never arbitrary).
 * 2. THE SURFACE SEPARATION: agent and exa read/write DIFFERENT
 *    storage keys — setting the exa A-source never moves the agent's.
 * 3. Legacy compat: the agent surface uses the BARE keys.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import {
  AKEYS_SEED_META_TOPIC_NAME,
  loadAKeysSourceId,
  resolveAKeysSource,
  saveAKeysSourceId,
} from '../aKeysSource';
import { AKEYS_BASE_KEY, surfaceKey } from '../macroSurface';

const agent = 'agent' as const;
const exa = 'exa' as const;

const TOPICS = [
  { id: 1, name: 'System Guide' },
  { id: 2, name: AKEYS_SEED_META_TOPIC_NAME },
  { id: 3, name: 'Coding' },
]

beforeEach(() => {
  localStorage.clear()
})

describe('The A-key source CASCADE (per surface)', () => {
  it('the explicit A-default wins when it still exists', () => {
    saveAKeysSourceId(agent, 3)
    expect(resolveAKeysSource(TOPICS, agent)).toBe(3)
  })

  it('falls back to the seeded "A-Key Macros" when no explicit default is saved', () => {
    expect(resolveAKeysSource(TOPICS, agent)).toBe(2)
  })

  it('a stale explicit default (deleted topic) falls back to the seed', () => {
    saveAKeysSourceId(agent, 99)
    expect(resolveAKeysSource(TOPICS, agent)).toBe(2)
  })

  it('no seed and no default -> null (deactivated, never first-available)', () => {
    const noSeed = TOPICS.filter((t) => t.name !== AKEYS_SEED_META_TOPIC_NAME)
    expect(resolveAKeysSource(noSeed, agent)).toBeNull()
  })

  it('an explicit default survives even when the seed is absent', () => {
    const noSeed = TOPICS.filter((t) => t.name !== AKEYS_SEED_META_TOPIC_NAME)
    saveAKeysSourceId(agent, 1)
    expect(resolveAKeysSource(noSeed, agent)).toBe(1)
  })
})

describe('THE SURFACE SPLIT (the four-state separation)', () => {
  it('agent and exa read DIFFERENT storage keys', () => {
    expect(surfaceKey(AKEYS_BASE_KEY, agent)).toBe('cogitate_akeys_meta_topic')
    expect(surfaceKey(AKEYS_BASE_KEY, exa)).toBe('cogitate_akeys_meta_topic:exa')
    expect(surfaceKey(AKEYS_BASE_KEY, agent)).not.toBe(surfaceKey(AKEYS_BASE_KEY, exa))
  })

  it('setting the EXA A-source never moves the AGENT A-source', () => {
    saveAKeysSourceId(agent, 3)
    saveAKeysSourceId(exa, 1)
    expect(loadAKeysSourceId(agent)).toBe(3)
    expect(loadAKeysSourceId(exa)).toBe(1)
    expect(resolveAKeysSource(TOPICS, agent)).toBe(3)
    expect(resolveAKeysSource(TOPICS, exa)).toBe(1)
  })

  it('the agent surface keeps the LEGACY bare key (no migration)', () => {
    localStorage.setItem('cogitate_akeys_meta_topic', '3')
    expect(loadAKeysSourceId(agent)).toBe(3)
  })

  it('each surface resolves its own cascade independently', () => {
    // agent: explicit 3; exa: nothing saved -> seed (2)
    saveAKeysSourceId(agent, 3)
    expect(resolveAKeysSource(TOPICS, agent)).toBe(3)
    expect(resolveAKeysSource(TOPICS, exa)).toBe(2)
  })
})
