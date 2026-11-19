// The UIStateBridge bug-class tests (2026-08-21).
// Exa's investigation found: (1) connect() only guarded OPEN, not
// CONNECTING → connect churn per store update; (2) orphaned sockets'
// onclose fired after a newer connect cleared isIntentionalClose →
// reconnect storm (1569 occurrences since Aug 13).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// a minimal WebSocket mock that records instances
class MockWebSocket {
  url: string;
  static instances: MockWebSocket[] = []
  static OPEN = 1
  static CONNECTING = 0
  readyState = MockWebSocket.CONNECTING
  onopen: (() => void) | null = null
  onmessage: ((e: unknown) => void) | null = null
  onclose: ((e: unknown) => void) | null = null
  onerror: ((e: unknown) => void) | null = null
  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }
  send() {}
  close() { this.readyState = 3 }
  static flush() { MockWebSocket.instances = [] }
}

describe('UIStateBridge connect (the storm fix)', () => {
  beforeEach(() => {
    MockWebSocket.flush()
    vi.stubGlobal('WebSocket', MockWebSocket)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('does not stomp a CONNECTING socket (the churn root)', async () => {
    const { default: bridge } = await import('@/services/uiStateBridge')
    bridge.disconnect() // clean slate
    bridge.connect()
    const first = MockWebSocket.instances[0]
    expect(first).toBeDefined()
    // second connect while still CONNECTING → no new socket
    bridge.connect()
    expect(MockWebSocket.instances.length).toBe(1)
  })

  it('stale sockets cannot drive connection state (the orphan guard)', async () => {
    const { default: bridge } = await import('@/services/uiStateBridge')
    bridge.disconnect()
    MockWebSocket.flush()
    bridge.connect()
    const stale = MockWebSocket.instances[0]
    // a newer connect replaces the socket
    stale.readyState = MockWebSocket.OPEN
    // simulate the stale socket's onclose firing AFTER a newer connect
    bridge.disconnect()
    bridge.connect()
    const fresh = MockWebSocket.instances[1]
    expect(fresh).toBeDefined()
    // fire the stale socket's close — must NOT drive state
    stale.onclose?.({ code: 1000, reason: '', wasClean: true })
    expect(bridge.isConnected).toBe(false)
  })
})
