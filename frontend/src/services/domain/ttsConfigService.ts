/**
 * TtsConfigService — the TTS preferences + the provider's voices.
 *
 * GET/PUT /api/v1/tts/config — {provider, voice, rate, enabled} (the
 * UserSettings-backed store; the provider build 2026-08-30).
 * GET /api/v1/tts/voices — the configured provider's selectable
 * voices (the dynamic list — the picker's options).
 */

import { apiClient } from '../apiClient';

export interface TtsConfig {
  provider: string;
  voice: string;
  rate: number;
  enabled: boolean;
  /** the sticky-alerts' voice mode (the TTS P3, 2026-08-31): "siren"
      (the wav-loop) vs "spoken" (the content read aloud once). */
  sticky_mode: 'siren' | 'spoken';
  /** LEGACY (2026-09-04, the chat-audio rework P1): the voice-source
      axis ('browser' vs the provider) is GONE — the browser path was
      ditched. The backend still returns the field; the frontend no
      longer sends or reads it. */
  source?: string;
}

export interface TtsVoice {
  name: string;
  lang: string;
  default: boolean;
}

/** `GET /api/v1/tts/voices` — the engine's voices, and which one a FRESH choice should be. */
export interface TtsVoiceOptions {
  provider: string;
  voices: TtsVoice[];
  /**
   * The voice a fresh choice on this engine should be: the app's configured voice when the engine
   * offers it, else the engine's first. It is how a voice left over from a PREVIOUS engine is
   * repaired — the engine is changed on /providers/capabilities, where nothing knows about voices,
   * so the repair happens wherever this list is read.
   */
  default: string | null;
}

export class TtsConfigService {
  private basePath = '/api/v1/tts/config';

  async getConfig(): Promise<TtsConfig> {
    const resp = await apiClient.get<TtsConfig>(this.basePath);
    return resp.data as TtsConfig;
  }

  /**
   * The PREFERENCES only. `provider` is retired (phase 6, G2-F4): which engine speaks is the `tts`
   * capability's answer, changed on /providers/capabilities — `PUT /tts/config` refuses the field.
   */
  async updateConfig(
    partial: Partial<Pick<TtsConfig, 'voice' | 'rate' | 'enabled' | 'sticky_mode'>>
  ): Promise<TtsConfig> {
    const resp = await apiClient.put<TtsConfig>(this.basePath, partial);
    return resp.data as TtsConfig;
  }

  async getVoices(): Promise<TtsVoiceOptions> {
    const resp = await apiClient.get<TtsVoiceOptions>('/api/v1/tts/voices');
    return {
      provider: resp.data?.provider ?? '',
      voices: resp.data?.voices ?? [],
      default: resp.data?.default ?? null,
    };
  }
}

export const ttsConfigService = new TtsConfigService();
