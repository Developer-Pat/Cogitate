/**
 * NotificationConfigStore — the notification preferences, shared by
 * the Sounds page (the picker) and the toast container (the audio
 * play hook). Loaded once on demand; the update writes through to
 * the backend (the UserSettings-backed config).
 */

import { create } from 'zustand'
import {
  notificationConfigService,
  type NotificationConfig,
} from '../services/domain/notificationConfigService'

interface NotificationConfigStore {
  config: NotificationConfig | null
  loaded: boolean
  load: (force?: boolean) => Promise<void>
  update: (partial: Partial<Pick<NotificationConfig, 'suppressed' | 'audio_enabled' | 'sound_id' | 'mute_until' | 'volume' | 'sound_success' | 'sound_warning' | 'sound_error' | 'sound_level'>>) => Promise<void>
}

export const useNotificationConfigStore = create<NotificationConfigStore>((set, get) => ({
  config: null,
  loaded: false,

  load: async (force = false) => {
    if (get().loaded && !force) return
    try {
      const config = await notificationConfigService.getConfig()
      set({ config, loaded: true })
    } catch {
      // the config is optional — the toast hook silently skips when null
      set({ loaded: true })
    }
  },

  update: async (partial) => {
    const config = await notificationConfigService.updateConfig(partial)
    set({ config, loaded: true })
  },
}))
