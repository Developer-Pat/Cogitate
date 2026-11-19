/**
 * messagingFeed — the SSE feed into the EventAggregator (Phase E,
 * 2026-08-24, the multi-consumer rework).
 *
 * Bridges the backend's /api/v1/messaging/stream SSE endpoint into
 * the frontend eventBus. ONE connection, ONE union of topics.
 *
 * THE MULTI-CONSUMER MODEL (2026-08-24): multiple consumers need
 * the stream (useNotifyBridge wants notify:*, useAgentSync wants
 * agent:*, the estimator wants workflow:*+batch:*). The feed is a
 * SINGLETON with a topic registry: each consumer calls
 * addTopics()/removeTopics(); the feed reconnects with the UNION
 * when the set changes, and closes when it empties. No consumer
 * can silently kill another's stream.
 *
 * WHY FETCH, NOT EventSource: the backend sends 'event: <topic>'
 * with DYNAMIC topic names (workflow:<uuid>:started) — the browser
 * only dispatches named events to listeners registered in advance,
 * which is impossible for unknown UUIDs. A fetch-based reader
 * parses every SSE line itself and emits on the bus regardless of
 * the event name — the robust wildcard path.
 *
 * Auto-reconnect: on stream close/error, retry with a backoff.
 */

import { eventBus } from './eventBus'
import { API_BASE_URL } from './apiClient'
import { frontendLoggingService } from './frontendLoggingService'

let controller: AbortController | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let reconnectDelay = 3000
let topicGroups = new Set<string>()
let activeTopics = ''

// THE VISIBILITY GATE (2026-09-07, fix A of the connection budget —
// see wiki/dev-notes/architecture/connection-budget.md): the feed is
// held only while the tab is VISIBLE. A hidden tab has no toasts to
// show and no sync the user can see; releasing its connection slot
// keeps the browser's ~6-per-host budget for the ACTIVE tab's page
// fetches (the silent multi-tab hangs). The topic registry survives
// the close — the visible handler reopens with the same union. The
// CHAT EXEMPTION: this gate is the idle feed ONLY — in-flight reply
// streams (StreamingService) are never touched by it.
let visibilityGateInstalled = false

function handleVisibilityChange(): void {
  if (document.visibilityState === 'hidden') {
    // release the connection — the union (topicGroups) is preserved
    disconnectMessaging()
  } else if (topicGroups.size > 0) {
    // the tab is back — reopen the feed with the surviving union
    reconnectAndOpen()
  }
}

function ensureVisibilityGate(): void {
  if (visibilityGateInstalled || typeof document === 'undefined') return
  visibilityGateInstalled = true
  document.addEventListener('visibilitychange', handleVisibilityChange)
}

/** Register a consumer's topic group (the union drives the stream). */
export function addTopics(topics: string): void {
  const added = !topicGroups.has(topics)
  topicGroups.add(topics)
  ensureVisibilityGate()
  if (added) {
    reconnectAndOpen()
  }
}

/** Remove a consumer's topic group; close when the union empties. */
export function removeTopics(topics: string): void {
  const removed = topicGroups.delete(topics)
  if (removed && topicGroups.size === 0) {
    disconnectMessaging()
  } else if (removed) {
    reconnectAndOpen()
  }
}

/**
 * Legacy single-topic API (kept for the existing callers). A new
 * connection REPLACES the registry — use addTopics for the
 * multi-consumer path.
 */
export function connectMessaging(topics: string): void {
  topicGroups = new Set([topics])
  ensureVisibilityGate()
  reconnectAndOpen()
}

function reconnectAndOpen(): void {
  disconnectMessaging()
  const union = Array.from(topicGroups).join(',')
  if (!union) return
  activeTopics = union
  reconnectDelay = 3000
  void open()
}

async function open(): Promise<void> {
  if (!activeTopics) return
  // THE VISIBILITY GATE: never hold the stream in a hidden tab —
  // the visibilitychange handler reopens on the way back to visible.
  if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
  controller = new AbortController()
  // THE LOCAL-CONTROLLER CAPTURE (2026-09-05, the 'message center
  // doesn't work' report): the mount churn (the agent panel + the
  // sync hooks each addTopics on load) races reconnectAndOpen — a
  // newer open() REASSIGNS the module-level controller before the
  // older open's catch runs. Checking the module variable misreads
  // the intentional aborts as stream errors (the error-log storm at
  // 13:22:49) + schedules spurious reconnects. Each open closes
  // over ITS OWN controller: an abort of it = a silent close.
  const myController = controller
  const url = `${API_BASE_URL}/api/v1/messaging/stream?topics=${encodeURIComponent(activeTopics)}`

  try {
    const resp = await fetch(url, { signal: controller.signal })
    if (!resp.ok || !resp.body) {
      throw new Error(`messaging stream HTTP ${resp.status}`)
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let eventName = 'message'
    let eventData = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // parse the SSE lines (event:/data:/blank)
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        const trimmed = line.replace(/\r$/, '')
        if (trimmed === '') {
          // dispatch the completed event
          if (eventName && eventName !== 'heartbeat') {
            let payload: unknown = {}
            try {
              payload = JSON.parse(eventData || '{}')
            } catch {
              payload = eventData
            }
            eventBus.emit(eventName, payload)
          }
          eventName = 'message'
          eventData = ''
        } else if (trimmed.startsWith('event:')) {
          eventName = trimmed.slice(6).trim()
        } else if (trimmed.startsWith('data:')) {
          eventData = (eventData ? eventData + '\n' : '') + trimmed.slice(5).trim()
        }
      }
    }
    // the stream closed — schedule the reconnect
    scheduleReconnect()
  } catch (err) {
    if (myController.signal.aborted) return // intentional close (silent)
    // A real interruption (navigation, network) — the stream comes
    // back on the schedule. Never an outage signal + never spam.
    if (err instanceof DOMException && err.name === 'AbortError') {
      scheduleReconnect()
      return
    }
    frontendLoggingService.error('messagingFeed', 'SSE stream error', err)
    scheduleReconnect()
  }
}

function scheduleReconnect(): void {
  if (reconnectTimer || !activeTopics) return
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    reconnectDelay = Math.min(reconnectDelay * 2, 30000)
    void open()
  }, reconnectDelay)
}

/** Close the messaging connection (no reconnect). */
export function disconnectMessaging(): void {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (controller) {
    controller.abort()
    controller = null
  }
  activeTopics = ''
}
