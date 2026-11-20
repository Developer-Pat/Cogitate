/**
 * The install's readiness — ONE call, one verdict.
 *
 * The verdict is measured in the backend (`domain/providers/readiness.py`) because a page
 * cannot know what it has not asked: the Setup checklist used to compute this from three
 * browser calls and a hardcoded provider id, while the Dashboard showed nothing at all.
 */
import { apiClient } from './apiClient'

export type ReadinessState = 'ok' | 'unmet' | 'blocked' | 'optional'

export interface ReadinessItem {
  key: string
  label: string
  state: ReadinessState
  detail: string
  href: string
  /** The optional runtime is not counted — Exa is a decision, not a requirement. */
  counted: boolean
}

export interface ReadinessReport {
  ready: boolean
  remaining: number
  items: ReadinessItem[]
}

export const readinessService = {
  async get(): Promise<ReadinessReport> {
    const res = await apiClient.get('/api/v1/setup/readiness')
    return res.data as ReadinessReport
  },
}

export default readinessService
