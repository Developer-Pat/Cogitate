/**
 * crossTab - the TAB-SERVICES harness (2026-08-28).
 *
 * The BroadcastChannel wrapper. The SESSION-CONTEXT service sits
 * on this (the inter-tab engage-context). The presence-registry +
 * the focus-message went OUT with the smart-tab experiment (the
 * user's call - the simple new-tab model!).
 *
 * The channel-name: 'cogitate-tabs'. Same-origin only.
 */

export interface NotifyMessage {
  type: 'notify'
  eventId?: string
  kind: string
  source: string
  messageType: string
  title: string
  message: string
  ts: number
}

export type CrossTabMessage = NotifyMessage

const CHANNEL_NAME = 'cogitate-tabs'

/**
 * THE CROSS-TAB HARNESS: the singleton channel + the message pump.
 */
class CrossTabHarness {
  private channel: BroadcastChannel | null = null
  private listeners = new Set<(msg: CrossTabMessage) => void>()

  /** subscribe to the cross-tab messages. */
  subscribe(fn: (msg: CrossTabMessage) => void): () => void {
    this.listeners.add(fn)
    this.ensureChannel()
    return () => this.listeners.delete(fn)
  }

  /** publish a local notification so the OTHER tabs' centers see it. */
  publishNotify(notify: Omit<NotifyMessage, 'type' | 'ts'>) {
    this.channel?.postMessage({
      type: 'notify',
      ...notify,
      ts: Date.now(),
    } satisfies NotifyMessage)
  }

  private ensureChannel() {
    if (this.channel) return
    this.channel = new BroadcastChannel(CHANNEL_NAME)
    this.channel.onmessage = (ev: MessageEvent) => {
      const msg = ev.data as CrossTabMessage | undefined
      if (!msg || typeof msg !== 'object') return
      this.listeners.forEach((fn) => fn(msg))
    }
  }
}

/** the singleton. */
export const crossTab = new CrossTabHarness()
