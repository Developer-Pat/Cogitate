/**
 * The agent roster read — the two rules that bite whenever a caller is added.
 *
 * 1. **`/api/v1/agents` answers an ENVELOPE** — `{agents, total, page, page_size}` (the 2026-08-17
 *    pagination-trap fix) — NOT the bare array `agentService.getAgents()` claims to return. A caller
 *    that trusted that type and iterated `.data` would be handed an object, so this service reads
 *    `.agents` explicitly and this test pins it.
 * 2. **The client RETURNS `{error}` — it does not throw** (the same contract the capabilities
 *    service documents), so the service raises at its own boundary.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { agentRosterService } from '../agentRosterService'

const ENVELOPE = {
  agents: [
    { id: 19, name: 'Bob' },
    { id: 56, name: 'Lois' },
  ],
  total: 2,
  page: 1,
  page_size: 2,
}

describe('agentRosterService', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve({ ok: true, json: async () => ENVELOPE })),
    )
  })

  afterEach(() => vi.unstubAllGlobals())

  it('reads the roster out of the envelope, with the backend ids a picker must send', async () => {
    const agents = await agentRosterService.listAgents()

    expect(agents).toEqual([
      { id: 19, name: 'Bob' },
      { id: 56, name: 'Lois' },
    ])
    expect(String(vi.mocked(fetch).mock.calls[0][0])).toContain('/api/v1/agents')
  })

  it('throws with the reason when the read fails', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'the agent table is gone' }),
    } as unknown as Response)

    await expect(agentRosterService.listAgents()).rejects.toThrow(/Could not list the agents/)
  })

  it('answers an empty roster rather than crashing when the envelope carries none', async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: true, json: async () => ({}) } as unknown as Response)

    expect(await agentRosterService.listAgents()).toEqual([])
  })
})
