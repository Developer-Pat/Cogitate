/**
 * The AGENT ROSTER — the id and the name, for a picker that must send the BACKEND id.
 *
 * ⚠️ This is NOT `services/agentService.getAgents()`. That method is typed `AgentInfo[]`, but
 * `/api/v1/agents` answers an ENVELOPE — `{agents, total, page, page_size}` (the 2026-08-17
 * pagination-trap fix) — so its type has been wrong since the envelope landed: a caller reading
 * `.data` as an array is handed an object. `providers/CognitiveHubProvider.tsx` works around it the
 * same way this does (read `.data.agents`). This service exists so the capability read-out's agent
 * picker has ONE correctly-typed read rather than a third workaround — and so the id it sends is the
 * BACKEND id (`?agent_id=19`), because a picker that sent a frontend-shaped id would address a
 * different agent or none at all.
 */

import { apiClient } from '@/services/apiClient'

/** One selectable agent: the backend id and the name shown to the user. */
export interface AgentChoice {
  id: number
  name: string
}

/** What `/api/v1/agents` actually answers — the envelope, not the bare array. */
interface AgentListEnvelope {
  agents?: AgentChoice[]
}

class AgentRosterService {
  private readonly basePath = '/api/v1/agents'

  /** Every agent, as a picker needs them. Throws with the server's reason when the read fails. */
  async listAgents(): Promise<AgentChoice[]> {
    const response = await apiClient.get<AgentListEnvelope>(this.basePath)

    if (response.error) {
      throw new Error(`Could not list the agents — ${response.error.message}`)
    }

    return response.data?.agents ?? []
  }
}

export const agentRosterService = new AgentRosterService()
export { AgentRosterService }
