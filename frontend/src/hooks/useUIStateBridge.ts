/**
 * Hook: useUIStateBridge
 *
 * Integrates the WebSocket UI State Bridge with the React app.
 * Handles:
 * - Connecting/disconnecting the WebSocket
 * - Pushing UI state changes (route, sidebar, theme, active agent/session)
 * - Handling incoming navigation requests (programmatic navigation)
 * - Tracking connection status
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { isConnected, latestState } = useUIStateBridge()
 *   return <div>WebSocket: {isConnected ? '🟢' : '🔴'}</div>
 * }
 * ```
 *
 * @see [`uiStateBridge.ts`](../services/uiStateBridge.ts) for the underlying WebSocket client.
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { frontendLoggingService } from '../services/frontendLoggingService'
import uiStateBridge, { type UIState } from '../services/uiStateBridge'
import { useUIStore } from '../stores/uiStore'
import { useCognitiveHubStore } from '../stores/cognitiveHubStore'
import { useSettingsStore } from '../stores/settingsStore'

// ─────────────────────────────────────────────────────────────────────────────
// Hook
// ─────────────────────────────────────────────────────────────────────────────

export interface UseUIStateBridgeResult {
  /** Whether the WebSocket is currently connected */
  isConnected: boolean
  /** The latest UI state received from the backend */
  latestState: UIState | null
  /** Manually trigger a state push to the backend */
  pushState: () => void
  /** Manually reconnect the WebSocket */
  reconnect: () => void
}

/**
 * Hook that integrates the WebSocket UI State Bridge with the app.
 *
 * Place this in a top-level component (e.g., ``Layout`` in ``App.tsx``)
 * so it runs for the lifetime of the app.
 */
export function useUIStateBridge(): UseUIStateBridgeResult {
  const location = useLocation()
  const navigate = useNavigate()

  const sidebarCollapsed = useUIStore((s) => s.sidebarCollapsed)
  const theaterModeActive = useUIStore((s) => s.theaterModeActive)
  const activeAgent = useCognitiveHubStore((s) => s.activeAgent)
  const activeSession = useCognitiveHubStore((s) => s.activeSession)
  const themeSetting = useSettingsStore((s) => s.settings.appearance.theme)

  const [isConnected, setIsConnected] = useState(false)
  const [latestState, setLatestState] = useState<UIState | null>(null)

  // Track previous values to avoid redundant pushes
  const prevRef = useRef({
    route: location.pathname,
    sidebarCollapsed,
    theaterModeActive,
    activeAgentId: activeAgent?.id ?? null,
    activeAgentName: activeAgent?.name ?? null,
    activeSessionId: activeSession?.id ?? null,
    activeSessionTitle: activeSession?.title ?? null,
    theme: themeSetting,
  })

  // ── Push state to backend ────────────────────────────────────────────────

  const pushState = useCallback(() => {
    const agentId = activeAgent?.id ? String(activeAgent.id) : null
    const sessionId = activeSession?.id ? String(activeSession.id) : null

    uiStateBridge.sendUIState({
      current_route: location.pathname,
      sidebar_collapsed: sidebarCollapsed,
      theater_mode_active: theaterModeActive,
      active_agent_id: agentId,
      active_agent_name: activeAgent?.name ?? null,
      active_session_id: sessionId,
      active_session_title: activeSession?.title ?? null,
      theme: themeSetting || 'light',
    })

    prevRef.current = {
      route: location.pathname,
      sidebarCollapsed,
      theaterModeActive,
      activeAgentId: activeAgent?.id ?? null,
      activeAgentName: activeAgent?.name ?? null,
      activeSessionId: activeSession?.id ?? null,
      activeSessionTitle: activeSession?.title ?? null,
      theme: themeSetting || 'light',
    }
  }, [
    location.pathname,
    sidebarCollapsed,
    theaterModeActive,
    activeAgent,
    activeSession,
    themeSetting,
  ])

  // ── Push state when tracked values change ────────────────────────────────

  useEffect(() => {
    const prev = prevRef.current
    const agentId = activeAgent?.id ?? null
    const sessionId = activeSession?.id ?? null

    const hasChanged =
      prev.route !== location.pathname ||
      prev.sidebarCollapsed !== sidebarCollapsed ||
      prev.theaterModeActive !== theaterModeActive ||
      prev.activeAgentId !== agentId ||
      prev.activeAgentName !== (activeAgent?.name ?? null) ||
      prev.activeSessionId !== sessionId ||
      prev.activeSessionTitle !== (activeSession?.title ?? null) ||
      prev.theme !== (themeSetting || 'light')

    if (hasChanged && uiStateBridge.isConnected) {
      pushState()
    }
  }, [
    location.pathname,
    sidebarCollapsed,
    theaterModeActive,
    activeAgent,
    activeSession,
    themeSetting,
    pushState,
  ])

  // ── Handle incoming navigation requests ──────────────────────────────────

  useEffect(() => {
    const unsubNavigation = uiStateBridge.onNavigation((route, replace) => {
      frontendLoggingService.info('useUIStateBridge', 'Navigation requested', {
        route,
        replace,
      })

      if (replace) {
        navigate(route, { replace: true })
      } else {
        navigate(route)
      }
    })

    return () => {
      unsubNavigation()
    }
  }, [navigate])

  // ── Track connection state ───────────────────────────────────────────────

  useEffect(() => {
    const unsubConnection = uiStateBridge.onConnectionChange((connected) => {
      setIsConnected(connected)
    })

    return () => {
      unsubConnection()
    }
  }, [])

  // ── Track incoming UI state updates ──────────────────────────────────────

  useEffect(() => {
    const unsubState = uiStateBridge.onUIState((state) => {
      setLatestState(state)
    })

    return () => {
      unsubState()
    }
  }, [])

  // ── Connect on mount, disconnect on unmount ──────────────────────────────

  // Latest pushState via ref — lets the mount-once connect effect push
  // initial state without depending on pushState's identity (which
  // changes on every store update and would otherwise churn the socket).
  const pushStateRef = useRef(pushState)
  useEffect(() => {
    pushStateRef.current = pushState
  }, [pushState])

  useEffect(() => {
    uiStateBridge.connect()

    // Push initial state after a short delay to ensure connection is established
    const initialPushTimeout = setTimeout(() => {
      pushStateRef.current()
    }, 500)

    // Periodic ping every 30 seconds to keep the connection alive
    const pingInterval = setInterval(() => {
      uiStateBridge.sendPing()
    }, 30000)

    return () => {
      clearTimeout(initialPushTimeout)
      clearInterval(pingInterval)
      uiStateBridge.disconnect()
    }
  }, [])

  // ── Reconnect helper ─────────────────────────────────────────────────────

  const reconnect = useCallback(() => {
    uiStateBridge.disconnect()
    setTimeout(() => {
      uiStateBridge.connect()
    }, 100)
  }, [])

  return {
    isConnected,
    latestState,
    pushState,
    reconnect,
  }
}

export default useUIStateBridge
