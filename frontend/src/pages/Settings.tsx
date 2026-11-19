import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom';
import { PageBanner } from '../components/ui/PageBanner'
import { PageContainer } from '../components/ui/PageContainer'
import { HelpButton } from '../components/help'
import { usePageTitle } from '../hooks/usePageTitle'
import { ThemeSelector } from '../components/ui/settings/ThemeSelector'
import { useSettingsStore } from '../stores/settingsStore'
import { useNotificationStore } from '../stores/notificationStore'
import RetentionCard from '../components/features/workflows/RetentionCard'
import type { Settings, Language, TimeZone, NotificationFrequency } from '../types/settings'

/** The four tabs — the query-driven address below needs the list. */
type SettingsTab = 'appearance' | 'general' | 'notifications' | 'data'
const SETTINGS_TABS: SettingsTab[] = ['appearance', 'general', 'notifications', 'data']

/**
 * ?tab=... — THE ADDRESS THE ASK-EXA NAVIGATION USES (2026-09-15).
 *
 * "/settings?tab=appearance" is "the themes page"; without a real address
 * the picker inside Settings is unreachable, which is exactly what the
 * user's first navigation request ran into. An unknown value falls back to
 * the default rather than rendering an empty tab.
 */
function readTabFromUrl(): SettingsTab {
  const t = new URLSearchParams(window.location.search).get('tab')
  return SETTINGS_TABS.includes(t as SettingsTab) ? (t as SettingsTab) : 'appearance'
}

const Settings: React.FC = () => {
  usePageTitle('Settings', 'Manage user preferences and application settings')

  const { settings, loadSettings, updateSettings, resetSettings, isLoading, error, lastSyncedAt } = useSettingsStore()
  const addNotification = useNotificationStore((state) => state.addNotification)
  const [activeTab, setActiveTab] = useState<SettingsTab>(readTabFromUrl())
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)

  /** The tab and the URL stay in step, so the address is shareable. */
  const selectTab = (tab: SettingsTab) => {
    setActiveTab(tab)
    const url = new URL(window.location.href)
    url.searchParams.set('tab', tab)
    window.history.replaceState({}, '', url)
  }

  // Load settings on mount
  useEffect(() => {
    loadSettings()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Show error if exists
  useEffect(() => {
    if (error) {
      addNotification({
        type: 'error',
        title: 'Settings Error',
        message: error,
        duration: 5000
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [error])

  const handleSavePreferences = async () => {
    try {
      await updateSettings(settings)
      setHasUnsavedChanges(false)
      addNotification({
        type: 'success',
        title: 'Settings Saved',
        message: 'Your preferences have been saved to the database.',
        duration: 3000
      })
    } catch {
      // Error already handled by store
    }
  }

  const handleResetSettings = async () => {
    if (!confirm('Are you sure you want to reset all settings to defaults?')) {
      return
    }

    try {
      await resetSettings()
      addNotification({
        type: 'success',
        title: 'Settings Reset',
        message: 'All settings have been restored to defaults.',
        duration: 3000
      })
    } catch {
      // Error already handled by store
    }
  }

  const updateGeneralSetting = <K extends keyof Settings['general']>(
    key: K,
    value: Settings['general'][K]
  ) => {
    updateSettings({
      general: { ...settings.general, [key]: value }
    })
    setHasUnsavedChanges(true)
  }

  const updateAppearanceSetting = <K extends keyof Settings['appearance']>(
    key: K,
    value: Settings['appearance'][K]
  ) => {
    updateSettings({
      appearance: { ...settings.appearance, [key]: value }
    })
    setHasUnsavedChanges(true)
  }

  const updateNotificationSetting = <K extends keyof Settings['notifications']>(
    key: K,
    value: Settings['notifications'][K]
  ) => {
    updateSettings({
      notifications: { ...settings.notifications, [key]: value }
    })
    setHasUnsavedChanges(true)
  }

  if (isLoading) {
    return (
      <PageContainer>
        <PageBanner title="Settings" tooltip="Manage user preferences and application settings" />
        <div className="flex justify-center p-8">
          <span className="loading loading-spinner loading-lg"></span>
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer>
      {/* Page Header — standard pattern */}
      <PageBanner
        title="Settings"
        tooltip="Manage user preferences and application settings"
        action={<HelpButton context="settings" tooltipPosition="bottom" />}
      />

      {lastSyncedAt && (
        <div className="text-xs text-readout mb-4">
          Last synced: {lastSyncedAt.toLocaleTimeString()}
          {hasUnsavedChanges && <span className="ml-2 text-warning">● Unsaved changes</span>}
        </div>
      )}

      {/* Tabs */}
      <div className="tabs tabs-boxed mb-4">
        <a className={`tab ${activeTab === 'appearance' ? 'tab-active' : ''}`} onClick={() => selectTab('appearance')}>Appearance</a>
        <a className={`tab ${activeTab === 'general' ? 'tab-active' : ''}`} onClick={() => selectTab('general')}>General</a>
        <a className={`tab ${activeTab === 'notifications' ? 'tab-active' : ''}`} onClick={() => selectTab('notifications')}>Notifications</a>
        <a className={`tab ${activeTab === 'data' ? 'tab-active' : ''}`} onClick={() => selectTab('data')}>Data</a>
      </div>

      {/* Appearance Tab */}
      {activeTab === 'appearance' && settings.appearance && (
        <div className="card bg-base-100 shadow-xl mb-4">
          <div className="card-body">
            <h2 className="card-title">Appearance</h2>

            <ThemeSelector
              fontSize={settings.appearance.fontSize}
              onFontSizeChange={(v) => updateAppearanceSetting('fontSize', v)}
              compactMode={settings.appearance.compactMode}
              onCompactModeChange={(v) => updateAppearanceSetting('compactMode', v)}
              showAnimations={settings.appearance.showAnimations}
              onShowAnimationsChange={(v) => updateAppearanceSetting('showAnimations', v)}
              chatBubbleGhost={settings.appearance.chatBubbleGhost}
              onChatBubbleGhostChange={(v) => updateAppearanceSetting('chatBubbleGhost', v)}
              loudness={settings.appearance.loudness}
              onLoudnessChange={(v) => updateAppearanceSetting('loudness', v)}
              keepCommandBoxOpen={settings.appearance.keepCommandBoxOpen}
              onKeepCommandBoxOpenChange={(v) => updateAppearanceSetting('keepCommandBoxOpen', v)}
            />

            <div className="card-actions justify-end mt-2">
              <button className="btn btn-primary" onClick={handleSavePreferences} disabled={!hasUnsavedChanges}>
                Save Appearance
              </button>
            </div>
          </div>
        </div>
      )}

      {/* General Tab */}
      {activeTab === 'general' && settings.general && (
        <div className="card bg-base-100 shadow-xl mb-4">
          <div className="card-body">
            <h2 className="card-title">General Preferences</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="form-control w-full">
                <label className="label">
                  <span className="label-text font-medium">Language</span>
                </label>
                <select
                  className="select select-bordered w-full"
                  value={settings.general.language}
                  onChange={(e) => updateGeneralSetting('language', e.target.value as Language)}
                >
                  <option value="en">English</option>
                  <option value="es">Spanish</option>
                  <option value="fr">French</option>
                  <option value="de">German</option>
                </select>
              </div>

              <div className="form-control w-full">
                <label className="label">
                  <span className="label-text font-medium">Time Zone</span>
                </label>
                <select
                  className="select select-bordered w-full"
                  value={settings.general.timeZone}
                  onChange={(e) => updateGeneralSetting('timeZone', e.target.value as TimeZone)}
                >
                  <option value="UTC-5">UTC-5 (America/Chicago)</option>
                  <option value="UTC-8">UTC-8 (America/Los_Angeles)</option>
                  <option value="UTC-4">UTC-4 (America/New_York)</option>
                  <option value="UTC+0">UTC+0 (Europe/London)</option>
                </select>
              </div>
            </div>

            {/* Title Generation — MOVED to the Local Services page
                (2026-09-03, the Local Services arc): capability config
                lives with the capability, not in user preferences. */}
            <div className="divider text-sm text-readout">Title Generation</div>
            <p className="text-sm opacity-70 mb-2">
              The title-generation controls (model + auto-title) now live on the{' '}
              <Link to="/local-services" className="link link-primary">Local Services</Link> page —
              where the local providers and the capabilities they power are configured together.
            </p>

            {/* Macro Development Section */}
            <div className="divider text-sm text-readout">Macro Development</div>

            <div className="form-control">
              <label className="label cursor-pointer justify-start gap-3">
                <input
                  type="checkbox"
                  className="toggle toggle-primary"
                  checked={settings.general.showMacroIds}
                  onChange={(e) => updateGeneralSetting('showMacroIds', e.target.checked)}
                />
                <span className="label-text font-medium">Show macro IDs in tooltips</span>
              </label>
              <label className="label">
                <span className="label-text-alt text-readout">
                  Display macro set IDs (e.g., ID=29) in M-key and F-key tooltips. This provides a stable shared identifier for referencing macros across sessions.
                </span>
              </label>
            </div>

            <div className="card-actions justify-end">
              <button className="btn btn-primary" onClick={handleSavePreferences} disabled={!hasUnsavedChanges}>
                Save Preferences
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Notifications Tab */}
      {activeTab === 'notifications' && settings.notifications && (
        <div className="card bg-base-100 shadow-xl mb-4">
          <div className="card-body">
            <h2 className="card-title">Notifications</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="form-control">
                <label className="label cursor-pointer">
                  <span className="label-text font-medium">Email Notifications</span>
                  <input
                    type="checkbox"
                    className="toggle toggle-primary"
                    checked={settings.notifications.emailNotifications}
                    onChange={(e) => updateNotificationSetting('emailNotifications', e.target.checked)}
                  />
                </label>
              </div>

              <div className="form-control">
                <label className="label cursor-pointer">
                  <span className="label-text font-medium">Push Notifications</span>
                  <input
                    type="checkbox"
                    className="toggle toggle-primary"
                    checked={settings.notifications.pushNotifications}
                    onChange={(e) => updateNotificationSetting('pushNotifications', e.target.checked)}
                  />
                </label>
              </div>

              <div className="form-control">
                <label className="label cursor-pointer">
                  <span className="label-text font-medium">System Alerts</span>
                  <input
                    type="checkbox"
                    className="toggle toggle-primary"
                    checked={settings.notifications.systemAlerts}
                    onChange={(e) => updateNotificationSetting('systemAlerts', e.target.checked)}
                  />
                </label>
              </div>

              <div className="form-control w-full">
                <label className="label">
                  <span className="label-text font-medium">Notification Frequency</span>
                </label>
                <select
                  className="select select-bordered w-full"
                  value={settings.notifications.frequency}
                  onChange={(e) => updateNotificationSetting('frequency', e.target.value as NotificationFrequency)}
                >
                  <option value="realtime">Real-time</option>
                  <option value="5min">Every 5 minutes</option>
                  <option value="15min">Every 15 minutes</option>
                  <option value="hourly">Hourly</option>
                  <option value="daily">Daily</option>
                </select>
              </div>
            </div>

            <div className="card-actions justify-end">
              <button className="btn btn-primary" onClick={handleSavePreferences} disabled={!hasUnsavedChanges}>
                Save Notification Settings
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Data Tab */}
      {activeTab === 'data' && (
        <div className="space-y-4">
          {/* THE RUN WINDOWS — the Data tab is where the app's own data is decided. */}
          <RetentionCard />

          <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
              <h2 className="card-title">Export Settings</h2>
              <p className="text-sm opacity-70">Download your settings as JSON</p>
              <div className="card-actions justify-end">
                <button
                  className="btn btn-outline"
                  onClick={() => {
                    const dataStr = JSON.stringify(settings, null, 2)
                    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr)
                    const exportFileDefaultName = 'cogitate-settings.json'
                    const linkElement = document.createElement('a')
                    linkElement.setAttribute('href', dataUri)
                    linkElement.setAttribute('download', exportFileDefaultName)
                    linkElement.click()
                  }}
                >
                  Export JSON
                </button>
              </div>
            </div>
          </div>

          <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
              <h2 className="card-title">Import Settings</h2>
              <p className="text-sm opacity-70">Restore settings from a JSON file</p>
              <input
                type="file"
                accept=".json"
                className="file-input file-input-bordered w-full"
                onChange={async (e) => {
                  const file = e.target.files?.[0]
                  if (!file) return
                  try {
                    const text = await file.text()
                    const importedSettings = JSON.parse(text)
                    await updateSettings(importedSettings)
                    addNotification({
                      type: 'success',
                      title: 'Settings Imported',
                      message: 'Your settings have been imported successfully.',
                      duration: 3000
                    })
                    setHasUnsavedChanges(true)
                  } catch {
                    addNotification({
                      type: 'error',
                      title: 'Import Failed',
                      message: 'Failed to import settings. Please check the file format.',
                      duration: 5000
                    })
                  }
                }}
              />
            </div>
          </div>

          <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
              <h2 className="card-title text-error">Reset Settings</h2>
              <p className="text-sm opacity-70">Restore all settings to their default values</p>
              <div className="card-actions justify-end">
                <button className="btn btn-error" onClick={handleResetSettings}>
                  Reset to Defaults
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  )
}

export default Settings
