/**
 * Provider CAPABILITIES service — the read-out that answers "which service does each part of the
 * app actually use, and what are its backups?".
 *
 * The backend sub-area is `/api/v1/providers/capabilities` (the service-capability arc's phase 1.4,
 * edited from phase 6). ⚠️ The paths carry the FULL `/api/v1` prefix because the apiClient does not
 * auto-prefix: a bare `/providers/capabilities` 404s SILENTLY through the vite proxy, and a caller
 * that swallows the failure shows an empty page with no error.
 */

import { apiClient } from '@/services/apiClient'
import type {
  CapabilityReadout,
  CapabilityReadoutResponse,
  CapabilityUpdate,
} from '@/types/capabilities'

class CapabilitiesService {
  private readonly basePath = '/api/v1/providers/capabilities'

  /**
   * Every capability, with the ordered chain each one resolves to right now.
   *
   * `agentId` asks the read-out through the ladder's AGENT rung — *"what will this agent use?"*. The
   * backend applies it only to the capabilities a LIVE CONSUMER passes an agent for, so a card never
   * shows a chain the capability would not use; every other card answers exactly as the sessionless
   * view does. Omit it for the sessionless view. An unknown id is a 404, which arrives here as an
   * error rather than as a silent sessionless answer.
   */
  async getCapabilities(agentId?: number | null): Promise<CapabilityReadoutResponse> {
    const url =
      agentId === null || agentId === undefined
        ? this.basePath
        : `${this.basePath}?agent_id=${encodeURIComponent(String(agentId))}`
    const response = await apiClient.get<CapabilityReadoutResponse>(url)

    if (response.error) {
      throw new Error(`Could not read the capabilities — ${response.error.message}`)
    }

    return response.data!
  }

  /** One capability's resolution. An unknown key is a 404, which arrives here as an error. */
  async getCapability(key: string): Promise<CapabilityReadout> {
    const response = await apiClient.get<CapabilityReadout>(
      `${this.basePath}/${encodeURIComponent(key)}`,
    )

    if (response.error) {
      throw new Error(`Could not read the '${key}' capability — ${response.error.message}`)
    }

    return response.data!
  }

  /**
   * Replace a capability's whole ordered chain.
   *
   * A refusal (400) is a candidate that cannot be attempted and names which one; a 404 is a key that
   * is not a capability. Both arrive as thrown errors carrying the server's own detail, because that
   * message is what tells the user which attempt to fix.
   */
  async updateCapability(key: string, update: CapabilityUpdate): Promise<CapabilityReadout> {
    const response = await apiClient.put<CapabilityReadout>(
      `${this.basePath}/${encodeURIComponent(key)}`,
      update,
    )

    if (response.error) {
      throw new Error(response.error.message)
    }

    return response.data!
  }
}

export const capabilitiesService = new CapabilitiesService()
export { CapabilitiesService }
