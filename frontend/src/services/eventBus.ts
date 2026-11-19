/**
 * EventBus — the frontend EventAggregator (Phase E, 2026-08-24).
 *
 * The MVVM-style messaging layer (the EventAggregator / Messenger
 * pattern): typed channels, subscribe/unsubscribe with cleanup,
 * UI-thread marshaling. The backend's SSE bridge (Phase B) feeds
 * it; components consume it without knowing the transport.
 *
 * - channels: any string; the backend topics come through as-is
 *   (workflow:<id>:started, batch:<id>:done, the_boss:proposed,
 *   notify:*, system:*).
 * - handlers receive (payload) — the topic is the channel.
 * - UI-thread marshaling: events arriving from the SSE client are
 *   dispatched synchronously (they already arrive on the main
 *   thread via EventSource); the aggregator itself never touches
 *   the DOM.
 */

export type BusHandler = (payload: unknown) => void

interface Subscription {
  channel: string
  handler: BusHandler
}

/**
 * The EventAggregator — a minimal, dependency-free pub-sub.
 */
class EventBusImpl {
  private subscriptions: Subscription[] = []
  private wildcards: Subscription[] = []

  /**
   * Subscribe to a channel. Supports the backend's wildcard
   * convention: 'workflow:*' matches any topic starting with
   * 'workflow:'.
   *
   * Returns an unsubscribe function (the React effect cleanup —
   * the MVVM rule: every subscribe has its cleanup).
   */
  subscribe(channel: string, handler: BusHandler): () => void {
    const sub: Subscription = { channel, handler }
    if (channel.endsWith('*')) {
      this.wildcards.push(sub)
    } else {
      this.subscriptions.push(sub)
    }
    return () => this.unsubscribe(channel, handler)
  }

  /** Remove a specific handler (no-op if already removed). */
  unsubscribe(channel: string, handler: BusHandler): void {
    this.subscriptions = this.subscriptions.filter(
      (s) => !(s.channel === channel && s.handler === handler),
    )
    this.wildcards = this.wildcards.filter(
      (s) => !(s.channel === channel && s.handler === handler),
    )
  }

  /** Clear ALL subscriptions (the app teardown / hot reload). */
  clear(): void {
    this.subscriptions = []
    this.wildcards = []
  }

  /** Dispatch an event to the matching handlers. */
  emit(channel: string, payload: unknown): void {
    for (const s of this.subscriptions) {
      if (s.channel === channel) {
        this.safeDispatch(s, payload)
      }
    }
    for (const s of this.wildcards) {
      const prefix = s.channel.slice(0, -1) // 'workflow:*' -> 'workflow:'
      if (channel.startsWith(prefix)) {
        this.safeDispatch(s, payload)
      }
    }
  }

  /** Handler isolation (the bus rule): one bad handler can't break
   * the fan-out. */
  private safeDispatch(sub: Subscription, payload: unknown): void {
    try {
      sub.handler(payload)
    } catch (err) {
      console.error(`[eventBus] handler for ${sub.channel} raised:`, err)
    }
  }

  /** The subscriber count (diagnostics). */
  get size(): number {
    return this.subscriptions.length + this.wildcards.length
  }
}

/** The app-wide singleton. */
export const eventBus = new EventBusImpl()
