import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ttsService } from '../ttsService'

// THE AUDIO MOCK (2026-09-04, the chat-audio rework P1): the ONE
// transport is the HTMLAudioElement — the speechSynthesis mocks of
// old are gone with the browser path. A vi.fn CONSTRUCTOR so the
// instances carry play/pause spies.
let playShouldReject = false
const MockAudio = vi.fn().mockImplementation(function (this: {
  play: ReturnType<typeof vi.fn>
  pause: ReturnType<typeof vi.fn>
  onended: (() => void) | null
  onerror: (() => void) | null
}) {
  this.play = vi.fn(() => (playShouldReject ? Promise.reject(new Error('autoplay')) : Promise.resolve()))
  this.pause = vi.fn()
  this.onended = null
  this.onerror = null
})

const flush = () => new Promise((r) => setTimeout(r, 0))

const blobResp = () => Promise.resolve({ ok: true, blob: async () => new Blob(['wav']) })
const failResp = () => Promise.resolve({ ok: false, status: 500, blob: async () => new Blob() })

// THE NOTIFICATION MOCK: the failure policy's visible channel.
const addError = vi.fn()
vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: { getState: () => ({ addError }) },
}))

const lastAudio = () => MockAudio.mock.instances[MockAudio.mock.instances.length - 1] as {
  play: ReturnType<typeof vi.fn>
  pause: ReturnType<typeof vi.fn>
  onended: (() => void) | null
  onerror: (() => void) | null
}

describe('the ttsService (the provider-only transport, 2026-09-04)', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:test') })
    vi.stubGlobal('Audio', MockAudio)
    MockAudio.mockClear()
    playShouldReject = false
    addError.mockClear()
    ttsService.cancel()
  })

  it('speaks through the provider — fetches the wav and plays it', async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url.includes('/tts/speak')) return blobResp()
      return Promise.reject(new Error('unexpected'))
    })
    vi.stubGlobal('fetch', fetchMock)
    ttsService.speak('Hello.')
    await flush()
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/v1/tts/speak?text=Hello.'), expect.anything())
    expect(lastAudio().play).toHaveBeenCalled()
  })

  it('applies the queue policy — a new speak cancels the current fetch', async () => {
    const holder: { signal: AbortSignal | null } = { signal: null }
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      if (url.includes('/tts/speak')) {
        if (!holder.signal) holder.signal = init?.signal ?? new AbortController().signal // the FIRST only
        const sig = holder.signal
        return new Promise((_, reject) => {
          sig?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
        })
      }
      return Promise.reject(new Error('unexpected'))
    }))
    ttsService.speak('first')
    await flush()
    expect(holder.signal).not.toBeNull()
    ttsService.speak('second') // cancels the first's pending fetch
    expect(holder.signal?.aborted).toBe(true)
  })

  it('fires onEnd when the audio ends', async () => {
    vi.stubGlobal('fetch', vi.fn(() => blobResp()))
    const onEnd = vi.fn()
    ttsService.speak('hi', { onEnd })
    await flush()
    lastAudio().onended?.()
    expect(onEnd).toHaveBeenCalledTimes(1)
  })

  it('stays silent when the browser blocks the play — NO fallback exists', async () => {
    vi.stubGlobal('fetch', vi.fn(() => blobResp()))
    playShouldReject = true
    const onEnd = vi.fn()
    ttsService.speak('hello', { onEnd })
    await flush()
    // the policy block is not an API failure — no toast, just the end
    expect(addError).not.toHaveBeenCalled()
    expect(onEnd).toHaveBeenCalledTimes(1)
  })

  it('shows the VISIBLE failure notice when the provider errors (no fallback)', async () => {
    vi.stubGlobal('fetch', vi.fn(() => failResp()))
    const onEnd = vi.fn()
    ttsService.speak('hello', { onEnd })
    await flush()
    expect(addError).toHaveBeenCalledWith('Voice unavailable', expect.stringContaining('backend'), 3000)
    expect(onEnd).toHaveBeenCalledTimes(1)
  })

  it('stops the pending synthesis — the cancel aborts the fetch, no notice', async () => {
    const holder: { signal: AbortSignal | null } = { signal: null }
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      if (url.includes('/tts/speak')) {
        holder.signal = init?.signal ?? new AbortController().signal
        const sig = holder.signal
        return new Promise((_, reject) => {
          sig?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
        })
      }
      return Promise.reject(new Error('unexpected'))
    }))
    const onEnd = vi.fn()
    ttsService.speak('hello', { onEnd })
    await flush()
    expect(holder.signal).not.toBeNull()
    ttsService.cancel()
    await flush()
    expect(addError).not.toHaveBeenCalled() // a stop is NOT a failure
    expect(onEnd).toHaveBeenCalledTimes(1)
  })

  it('isSpeaking reflects the audio element — real at last', async () => {
    vi.stubGlobal('fetch', vi.fn(() => blobResp()))
    expect(ttsService.isSpeaking()).toBe(false)
    ttsService.speak('x')
    await flush()
    expect(ttsService.isSpeaking()).toBe(true)
    ttsService.cancel()
    expect(ttsService.isSpeaking()).toBe(false)
  })

  // ===== THE P2 STATE MACHINE (2026-09-04) =====

  it('state: idle -> playing -> paused -> playing -> idle', async () => {
    vi.stubGlobal('fetch', vi.fn(() => blobResp()))
    expect(ttsService.state).toBe('idle')
    ttsService.speak('x')
    await flush()
    expect(ttsService.state).toBe('playing')
    const audio = lastAudio()
    ttsService.pause()
    expect(audio.pause).toHaveBeenCalled()
    expect(ttsService.state).toBe('paused')
    ttsService.resume()
    await flush() // the resume's setState rides the play promise
    expect(audio.play).toHaveBeenCalledTimes(2) // the resume continues the SAME audio
    expect(ttsService.state).toBe('playing')
    ttsService.cancel()
    expect(ttsService.state).toBe('idle')
  })

  it('resume continues the SAME audio element (no re-fetch)', async () => {
    const fetchMock = vi.fn(() => blobResp())
    vi.stubGlobal('fetch', fetchMock)
    ttsService.speak('x')
    await flush()
    const audio = lastAudio()
    ttsService.pause()
    ttsService.resume()
    await flush()
    expect(fetchMock).toHaveBeenCalledTimes(1) // pause/resume never refetches
    expect(lastAudio()).toBe(audio)
  })

  it('notifies the subscribers on every transition', async () => {
    vi.stubGlobal('fetch', vi.fn(() => blobResp()))
    const seen: string[] = []
    const unsub = ttsService.subscribe((s) => seen.push(s))
    ttsService.speak('x')
    await flush()
    ttsService.pause()
    ttsService.resume()
    await flush()
    ttsService.cancel()
    unsub()
    expect(seen).toEqual(['playing', 'paused', 'playing', 'idle'])
  })

  it('returns to idle when the audio ends naturally', async () => {
    vi.stubGlobal('fetch', vi.fn(() => blobResp()))
    ttsService.speak('x')
    await flush()
    expect(ttsService.state).toBe('playing')
    lastAudio().onended?.()
    expect(ttsService.state).toBe('idle')
  })

  it('returns to idle when the autoplay block rejects the play', async () => {
    vi.stubGlobal('fetch', vi.fn(() => blobResp()))
    playShouldReject = true
    ttsService.speak('x')
    await flush()
    expect(ttsService.state).toBe('idle')
    expect(addError).not.toHaveBeenCalled()
  })

  it('pause/resume are no-ops from the wrong states', () => {
    expect(ttsService.state).toBe('idle')
    ttsService.pause() // idle -> no-op
    expect(ttsService.state).toBe('idle')
    ttsService.resume() // idle -> no-op
    expect(ttsService.state).toBe('idle')
  })

  // ===== THE P3 SPEAK-KEY (2026-09-04) =====

  it('speak carries the key — the active bubble is queryable', async () => {
    vi.stubGlobal('fetch', vi.fn(() => blobResp()))
    expect(ttsService.activeKey).toBe(null)
    ttsService.speak('x', { key: 'msg-1' })
    await flush()
    expect(ttsService.state).toBe('playing')
    expect(ttsService.activeKey).toBe('msg-1')
    ttsService.pause() // the key survives the pause (resume-able)
    expect(ttsService.activeKey).toBe('msg-1')
    ttsService.cancel()
    expect(ttsService.activeKey).toBe(null)
  })

  it('the natural end clears the key', async () => {
    vi.stubGlobal('fetch', vi.fn(() => blobResp()))
    ttsService.speak('x', { key: 'msg-2' })
    await flush()
    lastAudio().onended?.()
    expect(ttsService.activeKey).toBe(null)
    expect(ttsService.state).toBe('idle')
  })
})
