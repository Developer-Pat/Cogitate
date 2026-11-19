/**
 * Cogitate DevTools — `window.__cogitate__` API for browser DevTools.
 *
 * Exposes a global `window.__cogitate__` object that allows developers to
 * inspect and manipulate the application state from the browser console.
 *
 * ## Usage
 *
 * ```js
 * // In browser DevTools console:
 * window.__cogitate__.getState()
 * window.__cogitate__.navigateTo('/agent-interaction')
 * window.__cogitate__.selectAgent('agent-id-string')
 * window.__cogitate__.onStateChange((state) => console.log('state changed', state))
 * ```
 *
 * ## Available Properties
 *
 * | Method / Property     | Description                                      |
 * |-----------------------|--------------------------------------------------|
 * | `getState()`          | Returns a snapshot of the full CognitiveHubStore |
 * | `navigateTo(path)`    | Programmatic navigation to any app route         |
 * | `selectAgent(id)`     | Select an agent by ID (string)                   |
 * | `selectSession(id)`   | Select a session by ID                           |
 * | `onStateChange(cb)`   | Subscribe to store changes (returns unsubscribe) |
 * | `getRoutes()`         | Returns the app's route configuration            |
 * | `getCognitiveState()` | Returns the current cognitive pipeline state     |
 * | `version`             | API version string                               |
 */

import type { AgentSlice } from '../stores/agentStore'
import type { CognitiveState } from '../services/domain/StreamingService'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Shape of the store state we expose via DevTools */
export interface CogitateStoreSnapshot {
  agents: AgentSlice['agents']
  activeAgent: AgentSlice['activeAgent']
  activeSession: AgentSlice['activeSession']
  sessions: AgentSlice['sessions']
}

export interface CogitateAPI {
  /** API version string */
  version: string

  /** Returns a snapshot of the CognitiveHubStore */
  getState: () => Promise<CogitateStoreSnapshot>

  /** Programmatic navigation to any app route */
  navigateTo: (path: string) => void

  /** Select an agent by ID (string) */
  selectAgent: (agentId: string) => Promise<void>

  /** Select a session by ID */
  selectSession: (sessionId: string) => Promise<void>

  /** Subscribe to store changes. Returns an unsubscribe function. */
  onStateChange: (cb: (state: CogitateStoreSnapshot) => void) => () => void

  /** Returns the app's route configuration */
  getRoutes: () => Array<{ path: string; title: string }>

  /** Returns the current cognitive pipeline state (from StreamingService) */
  getCognitiveState: () => CognitiveState | null

  /** Set a cognitive state reference for DevTools inspection */
  _setCognitiveStateRef: (ref: { current: CognitiveState | null }) => void
}

// ---------------------------------------------------------------------------
// Module-level state
// ---------------------------------------------------------------------------

let _cognitiveStateRef: { current: CognitiveState | null } = { current: null }
let _storeUnsubscribe: (() => void) | null = null
let _stateChangeCallbacks: Array<(state: CogitateStoreSnapshot) => void> = []

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Lazy-import the cognitive hub store to avoid circular deps at module load.
 */
async function _getStore(): Promise<typeof import('../stores/cognitiveHubStore')> {
  return import('../stores/cognitiveHubStore')
}

/**
 * Extract a serializable snapshot from the full store state.
 */
function _snapshot(state: {
  agents?: AgentSlice['agents']
  activeAgent?: AgentSlice['activeAgent']
  activeSession?: AgentSlice['activeSession']
  sessions?: AgentSlice['sessions']
}): CogitateStoreSnapshot {
  return {
    agents: state.agents ?? [],
    activeAgent: state.activeAgent ?? null,
    activeSession: state.activeSession ?? null,
    sessions: state.sessions ?? [],
  }
}

/**
 * Navigate via a custom DOM event that the app can listen for.
 */
function _navigate(path: string): void {
  try {
    window.dispatchEvent(
      new CustomEvent('__cogitate_navigate', { detail: { path } }),
    )
  } catch {
    console.warn('[__cogitate__] Navigation failed')
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

const api: CogitateAPI = {
  version: '0.1.0',

  async getState(): Promise<CogitateStoreSnapshot> {
    try {
      const { useCognitiveHubStore } = await _getStore()
      return _snapshot(useCognitiveHubStore.getState())
    } catch (err) {
      console.error('[__cogitate__] Failed to get state:', err)
      return { agents: [], activeAgent: null, activeSession: null, sessions: [] }
    }
  },

  navigateTo(path: string): void {
    _navigate(path)
  },

  async selectAgent(agentId: string): Promise<void> {
    try {
      const { useCognitiveHubStore } = await _getStore()
      const state = useCognitiveHubStore.getState()
      const agent = state.agents?.find((a) => a.id === agentId)
      if (agent) {
        state.setActiveAgent(agent)
        console.log(`[__cogitate__] Selected agent: ${agent.name} (id=${agentId})`)
      } else {
        console.warn(`[__cogitate__] Agent not found: id=${agentId}`)
      }
    } catch (err) {
      console.error('[__cogitate__] Failed to select agent:', err)
    }
  },

  async selectSession(sessionId: string): Promise<void> {
    try {
      const { useCognitiveHubStore } = await _getStore()
      const state = useCognitiveHubStore.getState()
      const session = state.sessions?.find((s) => s.id === sessionId)
      if (session) {
        state.setActiveSession(session)
        console.log(
          `[__cogitate__] Selected session: ${session.title} (id=${sessionId})`,
        )
      } else {
        console.warn(`[__cogitate__] Session not found: id=${sessionId}`)
      }
    } catch (err) {
      console.error('[__cogitate__] Failed to select session:', err)
    }
  },

  onStateChange(cb: (state: CogitateStoreSnapshot) => void): () => void {
    _stateChangeCallbacks.push(cb)

    // Subscribe to the store on first call
    if (!_storeUnsubscribe) {
      _getStore().then(({ useCognitiveHubStore }) => {
        _storeUnsubscribe = useCognitiveHubStore.subscribe((storeState) => {
          const snapshot = _snapshot(storeState)
          for (const callback of _stateChangeCallbacks) {
            try {
              callback(snapshot)
            } catch {
              // Swallow individual callback errors
            }
          }
        })
      })
    }

    return () => {
      _stateChangeCallbacks = _stateChangeCallbacks.filter((fn) => fn !== cb)
      if (_stateChangeCallbacks.length === 0 && _storeUnsubscribe) {
        _storeUnsubscribe()
        _storeUnsubscribe = null
      }
    }
  },

  getRoutes() {
    return [
      { path: '/', title: 'Dashboard' },
      { path: '/agent-interaction', title: 'Chat' },
      { path: '/agent-profiles', title: 'Agent Profiles' },
      { path: '/teams', title: 'Teams' },
      { path: '/tools', title: 'Tool Management' },
      { path: '/toolboxes', title: 'Toolboxes' },
      { path: '/workflow-execution', title: 'Workflow Execution' },
      { path: '/workflow-templates', title: 'Workflow Templates' },
      { path: '/provider-dashboard', title: 'Provider Dashboard' },
      { path: '/sessions', title: 'Sessions' },
      { path: '/logs', title: 'Logs' },
      { path: '/settings', title: 'Settings' },
      { path: '/macros', title: 'Macros' },
      
      { path: '/debugging', title: 'Debugging' },
      { path: '/analytics', title: 'Analytics' },
      { path: '/docs/*', title: 'Application Atlas' },
    ]
  },

  getCognitiveState(): CognitiveState | null {
    return _cognitiveStateRef.current
  },

  _setCognitiveStateRef(ref: { current: CognitiveState | null }): void {
    _cognitiveStateRef = ref
  },
}

// ---------------------------------------------------------------------------
// Install the global
// ---------------------------------------------------------------------------

if (typeof window !== 'undefined') {
  ;(window as unknown as Record<string, unknown>).__cogitate__ = api
  console.log(
    '%c🧠 Cogitate DevTools loaded',
    'color: #a78bfa; font-weight: bold; font-size: 14px;',
  )
  console.log(
    '%c   Try window.__cogitate__.getState()',
    'color: #94a3b8; font-size: 12px;',
  )
}

export default api
