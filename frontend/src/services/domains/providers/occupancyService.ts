/**
 * The local-occupancy types + fetch (A3, 2026-09-09).
 */
import { apiClient } from '@/services/apiClient'

export type LocalDaemonState = 'healthy' | 'down-by-occupancy' | 'down'

export interface LocalDaemon {
  provider_id: number | null
  name: string
  display_name: string
  provider_type: string
  base_url: string | null
  state: LocalDaemonState
  loaded_models: string[]
}

export interface LocalOccupancy {
  daemons: LocalDaemon[]
  running: string[]
  generated_at: string
}

export async function fetchLocalOccupancy(): Promise<LocalOccupancy> {
  const response = await apiClient.get<LocalOccupancy>('/api/v1/providers/local/occupancy')
  if (!response.data) {
    throw new Error('The occupancy response was empty')
  }
  return response.data
}
