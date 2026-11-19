/**
 * UI State Bridge — WebSocket client for real-time UI state sync.
 *
 * Connects to the backend WebSocket endpoint at ``/api/v1/agent-chat/ws``
 * and provides:
 * - Real-time UI state push (route, sidebar, active agent/session, theme)
 * - Programmatic navigation via ``navigation_request`` messages
 * - Automatic reconnection with exponential backoff
 *
 * @see [`backend/app/api/v1/agent_chat/router.py`](../../backend/app/api/v1/agent_chat/router.py:773)
 *   for the backend WebSocket implementation.
 */

import { frontendLoggingService } from './frontendLoggingService'

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface UIState {
  current_route: string
  sidebar_collapsed: boolean
  theater_mode_active: boolean
  active_agent_id: string | null
  active_agent_name: string | null
  active_session_id: string | null
  active_session_title: string | null
  theme: string
  timestamp: string
}

export interface WSMessage {
  type: 'ui_state_update' | 'navigation_request' | 'ping' | 'pong' | 'error'
  payload?: Record<string, unknown>
  timestamp: string
}

export type UIStateListener = (state: UIState) => void
export type NavigationListener = (route: string, replace: boolean) => void
export type ConnectionListener = (connected: boolean) => void

// ─────────────────────────────────────────────────────────────────────────────
// WebSocket Bridge Client
// ─────────────────────────────────────────────────────────────────────────────

import { API_BASE_URL } from './apiClient'
const WS_URL = API_BASE_URL.replace(/^http/, 'ws') + '/api/v1/agent-chat/ws'

class UIStateBridge {
  private ws: WebSocket | null = null
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  private retryCount = 0
  private maxRetries = 10
  private baseRetryDelay = 1000 // 1 second
  private isIntentionalClose = false

  private stateListeners: Set<UIStateListener> = new Set()
  private navigationListeners: Set<NavigationListener> = new Set()
  private connectionListeners: Set<ConnectionListener> = new Set()

  private _isConnected = false
  private _latestState: UIState | null = null

  // THE VISIBILITY GATE (2026-09-07, fix A of the connection budget —
  // see wiki/dev-notes/architecture/connection-budget.md): this bridge
  // is an IDLE held-open stream — a hidden tab cannot see the UI state
  // it syncs, so its connection slot is released for the active tab's
  // page fetches (the silent multi-tab hangs). The gate closes on
  // hidden, reconnects + re-syncs on visible. NOT touched by the gate:
  // in-flight reply streams (the chat with Bob) — active work is
  // always exempt.
  private visibilityHandler: (() => void) | null = null

  // ── Getters ──────────────────────────────────────────────────────────────

  get isConnected(): boolean {
    return this._isConnected
  }

  get latestState(): UIState | null {
    return this._latestState
  }

  // ── Connection Management ────────────────────────────────────────────────

  /**
   * Connect to the WebSocket endpoint.
   * Automatically retries on failure with exponential backoff.
   */
  connect(): void {
    this.ensureVisibilityGate()
    if (
      this.ws &&
      (this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING)
    ) {
      return // Already connected (or connecting) — don't stomp the socket
    }

    this.isIntentionalClose = false

    try {
      const socket = new WebSocket(WS_URL)
      this.ws = socket

      socket.onopen = () => {
        if (this.ws !== socket) return // Stale socket — a newer one owns the bridge
        this._isConnected = true
        this.retryCount = 0
        frontendLoggingService.info('UIStateBridge', 'WebSocket connected', {
          url: WS_URL,
        })
        this.notifyConnectionListeners(true)
      }

      socket.onmessage = (event: MessageEvent) => {
        if (this.ws !== socket) return
        try {
          const message: WSMessage = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (error) {
          frontendLoggingService.error(
            'UIStateBridge',
            'Failed to parse WebSocket message',
            error as Error,
            { data: event.data?.toString().slice(0, 200) },
          )
        }
      }

      socket.onclose = (event: CloseEvent) => {
        if (this.ws !== socket) return // Stale socket — a newer one owns the bridge
        this._isConnected = false
        this.notifyConnectionListeners(false)

        if (!this.isIntentionalClose) {
          frontendLoggingService.warning(
            'UIStateBridge',
            'WebSocket disconnected, reconnecting...',
            {
              code: event.code,
              reason: event.reason,
              wasClean: event.wasClean,
            },
          )
          this.scheduleReconnect()
        } else {
          frontendLoggingService.info('UIStateBridge', 'WebSocket closed intentionally')
        }
      }

      socket.onerror = (event: Event) => {
        if (this.ws !== socket) return
        frontendLoggingService.error('UIStateBridge', 'WebSocket error', event)
      }
    } catch (error) {
      this.ws = null
      frontendLoggingService.error(
        'UIStateBridge',
        'Failed to create WebSocket',
        error as Error,
      )
      this.scheduleReconnect()
    }
  }

  /**
   * Disconnect from the WebSocket endpoint.
   */
  disconnect(): void {
    this.isIntentionalClose = true
    this.cancelReconnect()

    if (this.ws) {
      this.ws.close(1000, 'Client disconnecting')
      this.ws = null
    }

    this._isConnected = false
    this.notifyConnectionListeners(false)
  }

  // THE VISIBILITY GATE: installed once (this is an app-lifetime
  // singleton); a hidden tab disconnects (intentional — no reconnect
  // storm), a visible one reconnects.
  private ensureVisibilityGate(): void {
    if (this.visibilityHandler || typeof document === 'undefined') return
    this.visibilityHandler = () => {
      if (document.visibilityState === 'hidden') {
        this.disconnect()
      } else {
        this.connect()
      }
    }
    document.addEventListener('visibilitychange', this.visibilityHandler)
  }

  /**
   * Send a UI state update to the backend.
   */
  sendUIState(state: Partial<UIState>): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      // Silently drop — the state will be sent on next connect or periodic sync
      return
    }

    const message: WSMessage = {
      type: 'ui_state_update',
      payload: state as Record<string, unknown>,
      timestamp: new Date().toISOString(),
    }

    this.ws.send(JSON.stringify(message))
  }

  /**
   * Send a ping to keep the connection alive.
   */
  sendPing(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return

    const message: WSMessage = {
      type: 'ping',
      timestamp: new Date().toISOString(),
    }

    this.ws.send(JSON.stringify(message))
  }

  // ── Listener Management ──────────────────────────────────────────────────

  onUIState(listener: UIStateListener): () => void {
    this.stateListeners.add(listener)
    // Immediately notify with latest state if available
    if (this._latestState) {
      listener(this._latestState)
    }
    return () => {
      this.stateListeners.delete(listener)
    }
  }

  onNavigation(listener: NavigationListener): () => void {
    this.navigationListeners.add(listener)
    return () => {
      this.navigationListeners.delete(listener)
    }
  }

  onConnectionChange(listener: ConnectionListener): () => void {
    this.connectionListeners.add(listener)
    // Immediately notify with current state
    listener(this._isConnected)
    return () => {
      this.connectionListeners.delete(listener)
    }
  }

  // ── Private Helpers ──────────────────────────────────────────────────────

  private handleMessage(message: WSMessage): void {
    switch (message.type) {
      case 'ui_state_update':
        if (message.payload) {
          this._latestState = message.payload as unknown as UIState
          this.notifyStateListeners(this._latestState)
        }
        break

      case 'navigation_request':
        if (message.payload) {
          const route = (message.payload.route as string) || '/'
          const replace = (message.payload.replace as boolean) || false
          this.notifyNavigationListeners(route, replace)
        }
        break

      case 'pong':
        // Keep-alive response — nothing to do
        break

      case 'error':
        frontendLoggingService.error(
          'UIStateBridge',
          'Server error',
          undefined,
          { payload: message.payload },
        )
        break
    }
  }

  private notifyStateListeners(state: UIState): void {
    this.stateListeners.forEach((listener) => {
      try {
        listener(state)
      } catch (error) {
        frontendLoggingService.error(
          'UIStateBridge',
          'State listener error',
          error as Error,
        )
      }
    })
  }

  private notifyNavigationListeners(route: string, replace: boolean): void {
    this.navigationListeners.forEach((listener) => {
      try {
        listener(route, replace)
      } catch (error) {
        frontendLoggingService.error(
          'UIStateBridge',
          'Navigation listener error',
          error as Error,
        )
      }
    })
  }

  private notifyConnectionListeners(connected: boolean): void {
    this.connectionListeners.forEach((listener) => {
      try {
        listener(connected)
      } catch (error) {
        frontendLoggingService.error(
          'UIStateBridge',
          'Connection listener error',
          error as Error,
        )
      }
    })
  }

  private scheduleReconnect(): void {
    this.cancelReconnect()

    if (this.retryCount >= this.maxRetries) {
      frontendLoggingService.error(
        'UIStateBridge',
        'Max reconnection attempts reached',
        undefined,
        { maxRetries: this.maxRetries },
      )
      return
    }

    // Exponential backoff with jitter
    const delay = Math.min(
      this.baseRetryDelay * Math.pow(2, this.retryCount) + Math.random() * 1000,
      30000, // Max 30 seconds
    )

    this.retryCount++

    frontendLoggingService.info(
      'UIStateBridge',
      `Reconnecting in ${Math.round(delay)}ms (attempt ${this.retryCount}/${this.maxRetries})`,
    )

    this.reconnectTimeout = setTimeout(() => {
      this.connect()
    }, delay)
  }

  private cancelReconnect(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Singleton Export
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Singleton instance of the UI State Bridge.
 * Use this throughout the app to avoid duplicate WebSocket connections.
 */
export const uiStateBridge = new UIStateBridge()

export default uiStateBridge
