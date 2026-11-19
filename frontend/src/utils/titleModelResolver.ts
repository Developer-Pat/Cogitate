/**
 * THE TITLE-MODEL RESOLVER (2026-09-03, the Local Services arc)
 *
 * ONE place that turns the user's title-model preference
 * (settings.general.titleModelPreference) into the model string the
 * backend title capability receives. Both rename surfaces use it:
 * the chat-page rename (useAgentInteraction) and the Sessions-page
 * smart rename — so "which model renames" is consistent everywhere.
 *
 * Semantics (match the backend resolution in TitleService):
 * - 'agent'           -> "<provider>/<model>" of the session's agent
 * - 'custom'          -> the user-typed LiteLLM model string (if set)
 * - 'backend_default' -> null — the backend uses the DB default
 *                        provider row
 */
import type { Agent } from '../types/agentInteraction'

export interface TitleModelPreferenceSettings {
  titleModelPreference?: 'agent' | 'backend_default' | 'custom'
  titleCustomModel?: string
}

export function resolveTitleModel(
  agent: Pick<Agent, 'provider' | 'model'> | null | undefined,
  settings: TitleModelPreferenceSettings
): string | null {
  const pref = settings?.titleModelPreference ?? 'agent'
  if (pref === 'agent') {
    if (!agent?.provider || !agent?.model) return null
    return `${agent.provider}/${agent.model}`
  }
  if (pref === 'custom') {
    const custom = settings?.titleCustomModel?.trim() ?? ''
    return custom || null
  }
  // 'backend_default' -> null (the backend resolves its own default)
  return null
}
