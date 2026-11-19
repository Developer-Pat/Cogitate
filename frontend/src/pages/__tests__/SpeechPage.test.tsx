/**
 * THE SPEECH PAGE after phase 6's G2-F4 — the engine is no longer chosen here.
 *
 * WHICH engine speaks/hears is the `tts`/`stt` capability's answer, changed on
 * `/providers/capabilities`. This page shows it, links there, and repairs a voice left over from a
 * PREVIOUS engine. Two behaviours are worth pinning:
 *
 * 1. the engine is a READ-OUT with a link, never a picker — the picker it replaced wrote the retired
 *    `provider` field, which `PUT /tts/config` now REFUSES (a stale bundle's flip must not read as a
 *    successful save);
 * 2. a stale voice is repaired on load, against the list the engine actually offers and with the
 *    default the backend publishes (`GET /tts/voices`'s `default`). Without it the next Speak fails
 *    on an unknown voice ("Unknown piper voice: …") and the Voice select shows a value none of its
 *    options match — because the engine is changed where nothing knows about voices.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'
import SpeechPage from '../SpeechPage'

const { getConfig, updateConfig, getVoices, getSttConfig, updateSttConfig } = vi.hoisted(() => ({
  getConfig: vi.fn(),
  updateConfig: vi.fn(),
  getVoices: vi.fn(),
  getSttConfig: vi.fn(),
  updateSttConfig: vi.fn(),
}))

vi.mock('@/services/domain/ttsConfigService', () => ({
  ttsConfigService: { getConfig, updateConfig, getVoices },
}))

vi.mock('@/services/sttService', () => ({
  getSttConfig,
  updateSttConfig,
  transcribeAudio: vi.fn(),
}))

vi.mock('@/services/ttsService', () => ({
  ttsService: { synthesize: vi.fn() },
}))

/** A stored preference whose voice belongs to a DIFFERENT engine (an edge voice, engine = piper). */
const CONFIG = {
  provider: 'piper',
  voice: 'en-US-JennyNeural',
  rate: 1,
  enabled: true,
  sticky_mode: 'siren' as const,
}

const VOICES = {
  provider: 'piper',
  voices: [
    { name: 'en_AU-natasha-medium', lang: 'en-US', default: false },
    { name: 'en_US-lessac-medium', lang: 'en-US', default: false },
  ],
  default: 'en_US-lessac-medium',
}

describe('SpeechPage — the engine is a read-out, and a stale voice is repaired', () => {
  beforeEach(() => {
    getConfig.mockReset()
    updateConfig.mockReset()
    getVoices.mockReset()
    getSttConfig.mockReset()
    updateSttConfig.mockReset()
    getSttConfig.mockResolvedValue({ provider: 'whisper', enabled: true })
  })

  it('repairs a voice the current engine cannot speak, with the default the backend names', async () => {
    getConfig.mockResolvedValue(CONFIG)
    getVoices.mockResolvedValue(VOICES)
    updateConfig.mockResolvedValue({ ...CONFIG, voice: 'en_US-lessac-medium' })

    render(<SpeechPage />)

    await waitFor(() =>
      expect(updateConfig).toHaveBeenCalledWith({ voice: 'en_US-lessac-medium' }),
    )
    const voice = (await screen.findByLabelText('Voice')) as HTMLSelectElement
    expect(voice.value).toBe('en_US-lessac-medium')
  })

  it('leaves a speakable voice alone — no write on load', async () => {
    getConfig.mockResolvedValue({ ...CONFIG, voice: 'en_US-lessac-medium' })
    getVoices.mockResolvedValue(VOICES)

    render(<SpeechPage />)

    await screen.findByLabelText('Voice')
    expect(updateConfig).not.toHaveBeenCalled()
  })

  it('shows the engine and links to the capability editor, with no picker', async () => {
    getConfig.mockResolvedValue({ ...CONFIG, voice: 'en_US-lessac-medium' })
    getVoices.mockResolvedValue(VOICES)

    render(<SpeechPage />)

    // BOTH cards point at the one place an engine is chosen
    const links = await screen.findAllByRole('link', { name: 'change it on Capabilities' })
    expect(links).toHaveLength(2)
    expect(links[0].getAttribute('href')).toBe('/providers/capabilities')

    // ...and the engine picker is GONE: nothing offers the engine names as choices
    expect(screen.queryByRole('option', { name: /piper \(the private\)/ })).toBeNull()
    expect(screen.queryByRole('option', { name: /edge \(the online/ })).toBeNull()
  })
})
