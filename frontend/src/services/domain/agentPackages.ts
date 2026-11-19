/**
 * agentPackages — the packages API client (2026-08-25, the
 * package's UI half Phase 1). The package = the agent blueprint
 * (the toolkit ref + the skillset + the advisory llm_spec).
 */
import { apiClient } from '../apiClient'
import type { ApiResponse } from '@/types'

export interface AgentPackage {
  id: string
  name: string
  description?: string | null
  kit_id?: string | null
  skills: string[]
  llm_spec?: {
    kind?: string
    thinking?: string
    location?: string
    min_context?: number
  } | null
  is_active?: boolean
}

export const agentPackagesService = {
  /** The package list — the picker's source. */
  async list(): Promise<AgentPackage[]> {
    const r = await apiClient.get<ApiResponse<{ packages: AgentPackage[] }>>('/api/v1/agent-packages')
    const data = r.data as unknown as { packages: AgentPackage[] } | AgentPackage[]
    return Array.isArray(data) ? data : (data?.packages ?? [])
  },

  /** One package by id (the profile's provenance lookup). */
  async get(id: string): Promise<AgentPackage | null> {
    try {
      const r = await apiClient.get<ApiResponse<AgentPackage>>(`/api/v1/agent-packages/${id}`)
      return (r.data as unknown as AgentPackage) ?? null
    } catch {
      return null
    }
  },

  /** THE ADOPT (Phase 3, 2026-08-25): copy the package's kit +
      skills + llm_spec into the agent's OWN fields + set the
      provenance. The agent owns its copies; the package never owns
      the agent. */
  async adopt(agentId: string, packageId: string): Promise<void> {
    await apiClient.post<ApiResponse<unknown>>(`/api/v1/agents/${agentId}/adopt-package`, {
      package_id: packageId,
    })
  },
}
