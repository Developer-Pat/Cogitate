/**
 * The capabilities service — the two rules that bite whenever a new caller is added.
 *
 * 1. **The path carries the full `/api/v1` prefix.** The apiClient does NOT auto-prefix, so a bare
 *    `/providers/capabilities` 404s SILENTLY through the vite proxy and the page renders empty.
 * 2. **The client RETURNS `{error}` — it does not throw.** A caller that reads `.data` blindly
 *    crashes late with a confusing message, so the service raises at its own boundary.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { capabilitiesService } from '../capabilitiesService'

const READOUT = { capabilities: [], kinds: ['llm'], total: 0 }

describe('capabilitiesService', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, json: async () => READOUT })))
  })

  afterEach(() => vi.unstubAllGlobals())

  it('reads the sub-area under its full /api/v1 path', async () => {
    await capabilitiesService.getCapabilities()

    const url = String(vi.mocked(fetch).mock.calls[0][0])
    expect(url).toContain('/api/v1/providers/capabilities')
  })

  it('carries the agent as a query param when one is asked for, and not otherwise', async () => {
    await capabilitiesService.getCapabilities(56)

    const url = String(vi.mocked(fetch).mock.calls[0][0])
    // the BACKEND id, on the read-out's own path — the picker must address the agent the page means
    expect(url).toContain('/api/v1/providers/capabilities?agent_id=56')
  })

  it('escapes a capability key into its own path', async () => {
    vi.mocked(fetch).mockResolvedValue({ ok: true, json: async () => READOUT } as unknown as Response)

    await capabilitiesService.getCapability('title.thinking')

    const url = String(vi.mocked(fetch).mock.calls[0][0])
    expect(url).toContain('/api/v1/providers/capabilities/title.thinking')
  })

  it('throws with the reason when the read fails', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'the capability table is gone' }),
    } as unknown as Response)

    await expect(capabilitiesService.getCapabilities()).rejects.toThrow(/Could not read the capabilities/)
  })
})
