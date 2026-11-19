// THE STT SERVICE (2026-08-30, the _26 build — the ttsConfigService
// mirror): the ONE frontend wrapper for the STT provider-API — the
// config (the raw convention) + the transcribe (the round-trip's
// ear through the UI).
import { apiClient } from './apiClient'

export interface SttConfig {
  provider: string
  enabled: boolean
}

export interface SttResult {
  provider: string
  text: string
  language: string
  duration: number
}

export async function getSttConfig(): Promise<SttConfig> {
  const res = await apiClient.get<SttConfig>('/api/v1/stt/config')
  return res.data as SttConfig
}

/**
 * The PREFERENCES only. `provider` is retired (phase 6, G2-F4): which engine transcribes is the
 * `stt` capability's answer, changed on /providers/capabilities — `PUT /stt/config` refuses it.
 */
export async function updateSttConfig(
  updates: Partial<Pick<SttConfig, 'enabled'>>,
): Promise<SttConfig> {
  const res = await apiClient.put<SttConfig>('/api/v1/stt/config', updates)
  return res.data as SttConfig
}

export async function transcribeAudio(file: File): Promise<SttResult> {
  const form = new FormData()
  form.append('file', file)
  // THE MULTIPART (2026-08-31, the test-facility catch): the
  // apiClient's post JSON-stringifies the body — the FormData must
  // ride the house's upload (the multipart) or the backend gets
  // '{}' and no file.
  // THE SLOW-WHISPER TIMEOUT (2026-09-04, the 'result is undefined'
  // dig): the whisper on this box takes ~6s+ for a short clip (the
  // load pushes it over) — the DEFAULT 10s timeout aborted the
  // transcribe mid-flight. 60s rides the stream default.
  const res = await apiClient.upload<SttResult>('/api/v1/stt/transcribe', form, { timeout: 60000 })
  // THE SILENT-FAILURE SHAPE (2026-09-04): the legacy apiClient
  // RETURNS { error } instead of throwing — a failure here used to
  // come back as undefined and the caller crashed with 'result is
  // undefined', discarding the real error. Surface it.
  if (res.error) {
    throw new Error(`STT transcribe failed: ${res.error.code} — ${res.error.message}`)
  }
  if (!res.data) {
    throw new Error('STT transcribe failed: the backend returned no result')
  }
  return res.data
}
