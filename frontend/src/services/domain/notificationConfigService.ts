/**
 * NotificationConfigService — the notification preferences.
 *
 * GET/PUT /api/v1/notifications/config — {suppressed, audio_enabled,
 * sound_id} (the UserSettings-backed store; the audio slice landed
 * with the wav-assets; the airplane-mode UI arrives with the
 * notifications-upgrade).
 */

import { apiClient } from '../apiClient';

export interface NotificationConfig {
  suppressed: boolean;
  audio_enabled: boolean;
  sound_id: string;
  /** the scheduled-mute's end (epoch seconds; null = no end). */
  mute_until: number | null;
  /** the audio-ping's loudness (0.0-1.0 — the HTMLAudio volume). */
  volume: number;
  /** THE PER-CLASS SOUNDS (2026-08-30, the F4 design): the class-
      specific wavs — the container plays the class's sound; sound_id
      is the fallback. */
  sound_success: string;
  sound_warning: string;
  sound_error: string;
  /** the sound LEVEL — the minimum class that pings (info < success < warning < error). */
  sound_level: 'info' | 'success' | 'warning' | 'error';
}

export interface TestNotificationPayload {
  title: string
  message: string
  type?: 'info' | 'success' | 'warning' | 'error'
  sticky?: boolean
}

export class NotificationConfigService {
  private basePath = '/api/v1/notifications/config';

  async getConfig(): Promise<NotificationConfig> {
    const resp = await apiClient.get<NotificationConfig>(this.basePath);
    return resp.data as NotificationConfig;
  }

  async updateConfig(
    partial: Partial<Pick<NotificationConfig, 'suppressed' | 'audio_enabled' | 'sound_id' | 'mute_until' | 'volume' | 'sound_success' | 'sound_warning' | 'sound_error' | 'sound_level'>>
  ): Promise<NotificationConfig> {
    const resp = await apiClient.put<NotificationConfig>(this.basePath, partial);
    return resp.data as NotificationConfig;
  }

  /** THE TEST BUTTON's edge (2026-09-05): publish a notify event
   * through the REAL bus — the SSE carries it to every open tab;
   * the bridge toasts it + the center records it. The whole-chain
   * verification the user's test-culture asks for. */
  async sendTest(payload: TestNotificationPayload): Promise<void> {
    const resp = await apiClient.post('/api/v1/notifications/test', payload)
    if (resp.error) {
      throw new Error(resp.error.message || 'Test notification send failed')
    }
  }
}

export const notificationConfigService = new NotificationConfigService();
