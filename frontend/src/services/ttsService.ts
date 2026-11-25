/**
 * The TTS service (2026-08-30, the _24 P1 build + the provider path;
 * 2026-09-04, the chat-audio rework — P1 the browser path DITCHED,
 * P2 the playback state machine).
 *
 * THE ONE TRANSPORT: speak() asks the backend (the configured TTS
 * provider — piper offline / edge online) and plays the returned wav
 * through a single HTMLAudioElement.
 *
 * THE STATE MACHINE (P2, 2026-09-04): the service OWNS the playback
 * state — 'idle' | 'playing' | 'paused' — with subscribers
 * (subscribe(fn)); components render from it instead of holding
 * private state. pause() pauses the audio element (kept alive —
 * resume() continues from the same spot, no re-fetch); cancel() is
 * the full stop. The old isSpeaking() (speechSynthesis.speaking —
 * false while the wav played) is gone.
 *
 * THE FAILURE POLICY (the no-silent doctrine): an API failure = no
 * audio + a small VISIBLE notice (throttled 10s). An autoplay-
 * policy play rejection stays SILENT (the browser's policy, not a
 * failure to fall back from). A stop-cancel is NOT a failure.
 *
 * THE QUEUE POLICY: one voice at a time — a new speak() cancels the
 * current.
 */

import { normalizeForSpeech } from '../utils/text/speechNormalization';
import { API_BASE_URL } from './apiClient'
import { useNotificationStore } from '../stores/notificationStore'

export type TtsPlaybackState = 'idle' | 'playing' | 'paused'

export interface SpeakOptions {
  rate?: number
  onEnd?: () => void
  /** THE SPEAKING KEY (P3): which bubble this speech belongs to —
      the components render the controls on THAT message. */
  key?: string
}

let currentAudio: HTMLAudioElement | null = null
// THE PENDING-FETCH ABORT (2026-08-30, the user's stop-fix): the
// cancel must kill a STILL-SYNTHESIZING request — the stop during
// the provider's fetch was a no-op (no audio yet) and the voice
// played anyway when the fetch resolved.
let pendingAbort: AbortController | null = null
// THE FAILURE THROTTLE (P1): the visible notice fires at most once
// per 10s — a down provider must not spam the center.
let lastFailureNotice = 0

// THE PLAYBACK STATE (P2): the service owns it; components subscribe.
let playbackState: TtsPlaybackState = 'idle'
// THE SPEAKING KEY (P3): the bubble this speech belongs to (null =
// unattached speech — e.g. the sticky alerts). Cleared on the stop.
let speakingKey: string | null = null
const listeners = new Set<(state: TtsPlaybackState) => void>()
function setState(next: TtsPlaybackState): void {
  if (playbackState === next) return
  playbackState = next
  listeners.forEach((fn) => fn(next))
}

export const ttsService = {
  /** THE PLAYBACK STATE — components render from it (P2). */
  get state(): TtsPlaybackState {
    return playbackState
  },

  /** Subscribe to the playback-state changes. Returns the unsubscribe. */
  subscribe(fn: (state: TtsPlaybackState) => void): () => void {
    listeners.add(fn)
    return () => listeners.delete(fn)
  },

  /** THE ACTIVE SPEAKING KEY (P3): the bubble id the current speech
      belongs to (null when idle or the speech is unattached). */
  get activeKey(): string | null {
    return speakingKey
  },

  /**
   * Speak the text — THE ONE PATH: fetch the provider's wav, play it.
   * The queue policy: any current utterance is cancelled first. The
   * speech normalization runs before the send.
   */
  speak(text: string, opts?: SpeakOptions): void {
    const clean = normalizeForSpeech(text)
    if (!clean.trim()) return
    ttsService.cancel()
    speakingKey = opts?.key ?? null
    const url = `${API_BASE_URL}/api/v1/tts/speak?text=${encodeURIComponent(clean)}`
    const controller = new AbortController()
    pendingAbort = controller
    fetch(url, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) {
          // THE SERVER'S REASON WINS when it gave one: a 409 says speech is switched
          // off, and telling the user to "check the backend" sends them hunting in the
          // wrong place for a setting that is one press away.
          let detail = ''
          try {
            const body = await res.json()
            if (body && body.detail) detail = String(body.detail)
          } catch {
            // not JSON (a proxy page, an empty body) — fall through to the generic text
          }
          const error = new Error(detail || `tts api ${res.status}`) as Error & { fromServer?: boolean }
          error.fromServer = Boolean(detail)
          throw error
        }
        return res.blob()
      })
      .then((blob) => {
        const audio = new Audio(URL.createObjectURL(blob))
        currentAudio = audio
        const finish = () => {
          if (currentAudio === audio) currentAudio = null
          speakingKey = null
          setState('idle')
          opts?.onEnd?.()
        }
        audio.onended = finish
        audio.onerror = finish
        // THE AUTOPLAY-POLICY CASE (the auto-read has no gesture): a
        // play rejection stays SILENT (the site-sound setting allows
        // it) — NOT the wrong-voice fallback of old.
        audio.play().then(() => setState('playing')).catch(finish)
      })
      .catch((err) => {
        // THE STOP: the cancel's abort is NOT a failure — no notice.
        if (err instanceof DOMException && err.name === 'AbortError') {
          opts?.onEnd?.()
          return
        }
        // THE NO-SILENT-FAILURE POLICY (P1): a real API failure is
        // VISIBLE (throttled).
        const now = Date.now()
        if (now - lastFailureNotice > 10_000) {
          lastFailureNotice = now
          const fromServer = (err as { fromServer?: boolean } | null)?.fromServer
          useNotificationStore.getState().addError(
            'Voice unavailable',
            fromServer && err instanceof Error
              ? err.message
              : 'The speech service did not respond — check the backend.',
            3000
          )
        }
        opts?.onEnd?.()
      })
  },

  /** PAUSE (P2): the audio element pauses IN PLACE — resume()
      continues from the same spot (no re-fetch). */
  pause(): void {
    if (playbackState !== 'playing' || !currentAudio) return
    currentAudio.pause()
    setState('paused')
  },

  /** RESUME (P2): continue the paused audio from where it stopped. */
  resume(): void {
    if (playbackState !== 'paused' || !currentAudio) return
    currentAudio.play()
      .then(() => setState('playing'))
      .catch(() => {
        // a resume failure (rare) — treat it as the stop
        currentAudio?.pause()
        currentAudio = null
        speakingKey = null
        setState('idle')
      })
  },

  /**
   * THE ROUND-TRIP FEED (2026-08-31, the _27 Phase-1 build): fetch
   * the synthesized wav WITHOUT playing it — the test facility's
   * ear-feed (the piper speaks -> this blob -> the whisper hears).
   */
  synthesize(text: string): Promise<Blob> {
    const url = `${API_BASE_URL}/api/v1/tts/speak?text=${encodeURIComponent(text)}`
    return fetch(url, { cache: 'no-store' }).then((res) => {
      if (!res.ok) throw new Error(`TTS synthesize failed: ${res.status}`)
      return res.blob()
    })
  },

  /** THE FULL STOP: abort the pending fetch + silence the audio. */
  cancel(): void {
    if (pendingAbort) {
      pendingAbort.abort()
      pendingAbort = null
    }
    if (currentAudio) {
      currentAudio.pause()
      currentAudio = null
    }
    speakingKey = null
    setState('idle')
  },

  /** True while a wav is playing OR paused (audio active). */
  isSpeaking(): boolean {
    return playbackState !== 'idle'
  },
}
