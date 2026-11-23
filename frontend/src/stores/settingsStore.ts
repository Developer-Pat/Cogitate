/**
 * Settings Store
 *
 * Zustand store for user settings with backend persistence.
 * Settings are synced to the backend on change (debounced).
 */

import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import { userSettingsService } from '../services/userSettingsService'
import { frontendLoggingService } from '../services/frontendLoggingService'
import type { Settings } from '../types/settings'

interface SettingsState {
  // State
  settings: Settings
  isLoading: boolean
  error: string | null
  lastSyncedAt: Date | null

  // Actions
  loadSettings: () => Promise<void>
  updateSettings: (updates: Partial<Settings>) => Promise<void>
  resetSettings: () => Promise<void>
  syncToBackend: () => Promise<void>
  clearError: () => void
}

const DEFAULT_USER_KEY = 'default'

export const useSettingsStore = create<SettingsState>()(
  devtools(
    (set, get) => ({
      // Initial state
      settings: {
        general: {
          language: 'en',
          timeZone: 'UTC-5',
          autoSave: true,
          showWelcomeScreen: false,
          enableAutoTitle: true,
          titleModelPreference: 'backend_default',
          titleCustomModel: '',
          // Both required by GeneralSettings; the store shipped without them, so a page that read
          // them before the backend load got `undefined`. zustand 5.1's stricter inference is what
          // surfaced it.
          showMacroIds: false,
          showPipelineIndicators: false,
        },
        appearance: {
          theme: 'auto',
          fontSize: 16,
          compactMode: false,
          showAnimations: true,
          chatBubbleGhost: false,
          loudness: 'normal',
          keepCommandBoxOpen: false,
        },
        notifications: {
          emailNotifications: true,
          pushNotifications: false,
          systemAlerts: true,
          agentStatusUpdates: true,
          errorReports: true,
          frequency: 'realtime',
        },
        lastUpdated: new Date().toISOString(),
        version: '1.0.0',
      },
      isLoading: false,
      error: null,
      lastSyncedAt: null,

      // Load settings from backend
      loadSettings: async () => {
        set({ isLoading: true, error: null })
        try {
          const backendSettings = await userSettingsService.getSettings(DEFAULT_USER_KEY)
          const currentState = get()

          // Merge backend settings with defaults — preserves fields the backend doesn't have
          const mergedSettings: Settings = {
            ...currentState.settings,
            ...backendSettings,
            general: {
              ...currentState.settings.general,
              ...backendSettings.general,
            },
            appearance: {
              ...currentState.settings.appearance,
              ...backendSettings.appearance,
            },
            notifications: {
              ...currentState.settings.notifications,
              ...backendSettings.notifications,
            },
            lastUpdated: backendSettings.lastUpdated ?? new Date().toISOString(),
            version: backendSettings.version ?? currentState.settings.version,
          }

          set({ settings: mergedSettings, isLoading: false, lastSyncedAt: new Date() })
          frontendLoggingService.info('SettingsStore', 'Settings loaded from backend', {
            lastUpdated: mergedSettings.lastUpdated
          })
        } catch (err) {
          const errorMsg = err instanceof Error ? err.message : 'Failed to load settings'
          frontendLoggingService.error('SettingsStore', 'Failed to load settings', err)
          set({ error: errorMsg, isLoading: false })
        }
      },

      // Update settings (local + backend sync)
      updateSettings: async (updates: Partial<Settings>) => {
        const currentState = get()
        const updatedSettings = {
          ...currentState.settings,
          ...updates,
          lastUpdated: new Date().toISOString(),
        }

        set({ settings: updatedSettings })

        // Sync to backend (debounced in future enhancement)
        try {
          await userSettingsService.updateSettings(updatedSettings, DEFAULT_USER_KEY)
          set({ lastSyncedAt: new Date() })
          frontendLoggingService.debug('SettingsStore', 'Settings synced to backend')
        } catch (err) {
          const errorMsg = err instanceof Error ? err.message : 'Failed to sync settings'
          frontendLoggingService.error('SettingsStore', 'Failed to sync settings', err)
          set({ error: errorMsg })
        }
      },

      // Reset to default settings
      resetSettings: async () => {
        const defaultSettingsValue: Settings = {
          general: {
            language: 'en',
            timeZone: 'UTC-5',
            autoSave: true,
            showWelcomeScreen: false,
            showPipelineIndicators: true,
            enableAutoTitle: true,
            titleModelPreference: 'backend_default',
            titleCustomModel: '',
              showMacroIds: false,
          },
          appearance: {
            theme: 'auto',
            fontSize: 16,
            compactMode: false,
            showAnimations: true,
          chatBubbleGhost: false,
          loudness: 'normal',
          keepCommandBoxOpen: false,
          },
          notifications: {
            emailNotifications: true,
            pushNotifications: false,
            systemAlerts: true,
            agentStatusUpdates: true,
            errorReports: true,
            frequency: 'realtime',
          },
          lastUpdated: new Date().toISOString(),
          version: '1.0.0',
        }

        set({ settings: defaultSettingsValue })

        try {
          await userSettingsService.updateSettings(defaultSettingsValue, DEFAULT_USER_KEY)
          set({ lastSyncedAt: new Date() })
          frontendLoggingService.info('SettingsStore', 'Settings reset to defaults and synced')
        } catch (err) {
          const errorMsg = err instanceof Error ? err.message : 'Failed to reset settings'
          frontendLoggingService.error('SettingsStore', 'Failed to reset settings', err)
          set({ error: errorMsg })
        }
      },

      // Manual sync to backend
      syncToBackend: async () => {
        const { settings } = get()
        try {
          await userSettingsService.updateSettings(settings, DEFAULT_USER_KEY)
          set({ lastSyncedAt: new Date(), error: null })
          frontendLoggingService.debug('SettingsStore', 'Manual sync completed')
        } catch (err) {
          const errorMsg = err instanceof Error ? err.message : 'Failed to sync'
          frontendLoggingService.error('SettingsStore', 'Manual sync failed', err)
          set({ error: errorMsg })
        }
      },

      // Clear error
      clearError: () => {
        set({ error: null })
      },
    }),
    {
      name: 'settings-store',
    }
  )
)

export default useSettingsStore
