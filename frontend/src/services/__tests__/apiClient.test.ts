import { beforeEach, describe, expect, it, vi } from 'vitest'
import { EnhancedApiClient } from '../apiClient'
import { notifyBus } from '../notifyBus'
import { outageGate } from '../outageGate'

// THE OUTAGE-NOTIFICATION TESTS (2026-09-04, the _34 consolidation):
// the machinery ported from the deleted domains/shared client — the
// 3rd-consecutive flood threshold, the 10s rate limit, the recovery
// toast, and the real params support. The client fires through the
// notifyBus (the leaf edge — the notification/logging stacks depend
// on the client and can never be imported by it); the tests
// REGISTER spy handlers and assert through them.
const errorSpy = vi.fn()
const successSpy = vi.fn()
const logSpy = vi.fn()

const jsonResp = (status: number, body: unknown) =>
  ({ ok: status >= 200 && status < 300, status, json: async () => body }) as Response

describe('the apiClient outage tracker (the _34 port)', () => {
  let client: EnhancedApiClient
  beforeEach(() => {
    errorSpy.mockClear()
    successSpy.mockClear()
    logSpy.mockClear()
    notifyBus.register({ error: errorSpy, success: successSpy, log: logSpy })
    outageGate.reset() // the episode gate's state must not leak either
    client = new EnhancedApiClient() // the singleton's streak/rate-limit state must not leak
  })

  it('an EXTERNAL abort (navigation) is NOT an outage — untracked + unlogged', async () => {
    // the user's 13:01 report: page navigations cancel in-flight
    // fetches -> the AbortErrors tripped the 'Backend Unavailable'
    // false positives. An external abort must never count toward
    // the streak nor hit the log.
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new DOMException('The operation was aborted.', 'AbortError')
      }),
    )
    const first = await client.get('/api/v1/test')
    const second = await client.get('/api/v1/test')
    const third = await client.get('/api/v1/test')
    expect(first.error?.code).toBe('ABORTED')
    // 3+ aborts and NO notification (the streak never moved)
    expect(errorSpy).not.toHaveBeenCalled()
    // and no log spam
    expect(logSpy).not.toHaveBeenCalled()
    expect(second.error?.code).toBe('ABORTED')
    expect(third.error?.code).toBe('ABORTED')
  })

  it('the TELEMETRY opt-out: a flagged request never trips the outage gate', async () => {
    // the log funnel's flush (2026-09-05): best-effort telemetry —
    // three slow/dropped log POSTs must not raise 'Backend
    // Unavailable' nor hit the bus log.
    vi.stubGlobal('fetch', vi.fn(async () => jsonResp(500, { detail: 'boom' })))
    await client.post('/api/v1/logs/frontend', { source: 'x' }, { excludeFromOutageTracking: true })
    await client.post('/api/v1/logs/frontend', { source: 'x' }, { excludeFromOutageTracking: true })
    await client.post('/api/v1/logs/frontend', { source: 'x' }, { excludeFromOutageTracking: true })
    expect(errorSpy).not.toHaveBeenCalled()
    expect(logSpy).not.toHaveBeenCalled()
    // and an UNflagged failure right after still tracks normally —
    // the opt-out doesn't poison the tracker
    await client.get('/api/v1/test')
    await client.get('/api/v1/test')
    await client.get('/api/v1/test')
    expect(errorSpy).toHaveBeenCalledTimes(1)
  })

  it('a REAL timeout still counts once + logs once', async () => {
    // the client's own timeout abort = the request genuinely hung —
    // a failure signal (tracked, logged), but never retried.
    vi.useFakeTimers()
    try {
      vi.stubGlobal(
        'fetch',
        vi.fn(
          (_url: string, opts: RequestInit) =>
            new Promise<Response>((_, reject) => {
              const signal = opts.signal as AbortSignal
              signal.addEventListener('abort', () =>
                reject(new DOMException('The operation was aborted.', 'AbortError')),
              )
            }),
        ),
      )
      const pending = client.get('/api/v1/slow', { timeout: 5000 })
      await vi.advanceTimersByTimeAsync(5001)
      const result = await pending
      expect(result.error?.code).toBe('ABORTED')
      expect(logSpy).toHaveBeenCalledTimes(1)
      expect(logSpy.mock.calls[0][1]).toContain('timed out')
      // the timeout is a tracked failure — a 3rd hang would notify
    } finally {
      vi.useRealTimers()
    }
  })

  it('the 1st + 2nd failures track SILENTLY — the notification fires at the 3rd consecutive', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResp(500, { detail: 'boom' })))
    await client.get('/api/v1/test')
    await client.get('/api/v1/test')
    expect(errorSpy).not.toHaveBeenCalled()
    await client.get('/api/v1/test')
    expect(errorSpy).toHaveBeenCalledTimes(1)
    expect(errorSpy.mock.calls[0][0]).toBe('Backend Unavailable')
  })

  it('a single success resets the streak — one 500 after two good calls never notifies', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResp(200, { ok: true }))
      .mockResolvedValueOnce(jsonResp(200, { ok: true }))
      .mockResolvedValueOnce(jsonResp(500, { detail: 'boom' }))
    vi.stubGlobal('fetch', fetchMock)
    await client.get('/api/v1/test')
    await client.get('/api/v1/test')
    await client.get('/api/v1/test')
    expect(errorSpy).not.toHaveBeenCalled()
  })

  it('the RECOVERY toast fires on the first success after a 3+ failure streak', async () => {
    const fetchMock = vi.fn(async () => jsonResp(500, { detail: 'boom' }))
    vi.stubGlobal('fetch', fetchMock)
    await client.get('/api/v1/test') // 1
    await client.get('/api/v1/test') // 2
    await client.get('/api/v1/test') // 3 -> the down toast
    expect(errorSpy).toHaveBeenCalledTimes(1)
    // the RECOVERY shares the 10s rate limit with the down-toast
    // (anti-spam — a recovery 2s after the outage toast is
    // redundant) — advance the clock past the window first.
    const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 11000)
    fetchMock.mockResolvedValue(jsonResp(200, { ok: true }))
    await client.get('/api/v1/test') // the first success
    expect(successSpy).toHaveBeenCalledTimes(1)
    expect(successSpy.mock.calls[0][0]).toBe('Backend Connection Restored')
    nowSpy.mockRestore()
    // the streak is reset — more successes stay silent
    await client.get('/api/v1/test')
    expect(successSpy).toHaveBeenCalledTimes(1)
  })

  it('the params reach the URL (the hard-delete flag finally travels)', async () => {
    let seenUrl = ''
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: string | URL | Request) => {
        seenUrl = String(input)
        return jsonResp(200, { ok: true })
      })
    )
    await client.delete('/api/v1/profiles/abc', { params: { hard: true } })
    expect(seenUrl).toContain('/api/v1/profiles/abc?hard=true')
  })

  it('params merge onto an existing query with the & separator', async () => {
    let seenUrl = ''
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: string | URL | Request) => {
        seenUrl = String(input)
        return jsonResp(200, { ok: true })
      })
    )
    await client.get('/api/v1/logs?page=2', { params: { level: 'error' } })
    expect(seenUrl).toContain('/api/v1/logs?page=2&level=error')
  })

  it('the params builder skips undefined/null values', async () => {
    let seenUrl = ''
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: string | URL | Request) => {
        seenUrl = String(input)
        return jsonResp(200, { ok: true })
      })
    )
    await client.get('/api/v1/things', { params: { a: '1', b: undefined, c: null } })
    expect(seenUrl).toContain('a=1')
    expect(seenUrl).not.toContain('b=')
    expect(seenUrl).not.toContain('c=')
  })

  it("a STREAM with the caller's signal hands fetch a REAL AbortSignal (the brand check)", async () => {
    // The 2026-09-05 Bob report: 'Window.fetch: signal member of
    // RequestInit does not implement interface AbortSignal' — the
    // stream() used to hand fetch a Proxy-over-EventTarget fake
    // (never a genuine AbortSignal; the WebIDL brand check threw).
    let capturedSignal: unknown
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init: RequestInit) => {
        capturedSignal = init.signal
        return { ok: true, status: 200 } as Response
      }),
    )
    const controller = new AbortController()
    const response = await client.stream('/api/v1/chat/stream', { model: 'x' }, { signal: controller.signal })
    expect(response.ok).toBe(true)
    expect(capturedSignal).toBeInstanceOf(AbortSignal)
  })

  it("the caller's abort cancels an in-flight STREAM", async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init: RequestInit) => {
        // mimic fetch: reject when the signal fires
        await new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () =>
            reject(new DOMException('The operation was aborted.', 'AbortError')),
          )
        })
      }),
    )
    const controller = new AbortController()
    const streamPromise = client.stream('/api/v1/chat/stream', { model: 'x' }, { signal: controller.signal })
    controller.abort()
    await expect(streamPromise).rejects.toThrow('Streaming request aborted')
  })

  it('the all-retries-failed path logs through the bus (the final-error log)', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('fetch failed') }))
    // the retry backoff (1s+2s+4s) — bound the wait with fake timers
    vi.useFakeTimers()
    const p = client.get('/api/v1/test')
    await vi.advanceTimersByTimeAsync(10000)
    await p
    vi.useRealTimers()
    expect(logSpy).toHaveBeenCalledTimes(1)
    expect(logSpy.mock.calls[0][1]).toContain('Request failed after 3 retries')
  })
})
