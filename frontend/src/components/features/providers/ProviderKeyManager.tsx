/**
 * ProviderKeyManager — Keys tab for the Provider Dashboard.
 *
 * Phase 4 (mini-map item 8): single place to see/set/rotate/clear
 * provider API keys. Key source is surfaced per provider:
 *   env  — key comes from settings (.env); not editable here
 *   db   — key stored encrypted on the provider row; clearable
 *   none — no key; local providers (ollama) need none
 *
 * Backed by /api/v1/providers/managed/keys + PUT/DELETE
 * /managed/{id}/key (EncryptionService fix 2026-08-03 makes DB
 * storage first-class).
 */

import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '@/services/apiClient'
import { providerLocationOf } from '@/utils/providerLocation'
import { useNotificationStore } from '@/stores/notificationStore'
import { frontendLoggingService } from '@/services/frontendLoggingService'

interface KeyStatus {
  provider_id: number
  provider_name: string
  provider_type: string
  key_source: 'env' | 'db' | 'none'
  has_key: boolean
}

interface ProviderKeyManagerProps {
  loading?: boolean
  /** The class seam (2026-09-08, the A1 split): 'cloud' = hide the
   * keyless local rows on the cloud page. */
  location?: 'cloud' | 'local'
}

const SOURCE_LABEL: Record<string, { text: string; cls: string; hint: string }> = {
  env: { text: 'Env (.env)', cls: 'badge-info badge-outline', hint: 'Key comes from the .env file (gitignored)' },
  db: { text: 'Stored (DB)', cls: 'badge-success badge-outline', hint: 'Key stored encrypted on this provider' },
  none: { text: 'None', cls: 'badge-ghost', hint: 'No key — local providers need none' },
}

export default function ProviderKeyManager({ loading: _loading, location }: ProviderKeyManagerProps) {
  const [rows, setRows] = useState<KeyStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<KeyStatus | null>(null)
  const [keyInput, setKeyInput] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const resp = await apiClient.get<{ providers?: KeyStatus[] }>('/api/v1/providers/managed/keys')
      const all = resp.data?.providers ?? []
      // THE CLASS SEAM (2026-09-08, the A1 split): the local rows
      // are keyless by design — the cloud page filters them out
      // (the same derivation the backend uses).
      setRows(location ? all.filter((r) => providerLocationOf(r) === location) : all)
    } catch (err) {
      frontendLoggingService.error('ProviderKeyManager', 'Failed to load key status', err)
      useNotificationStore.getState().addError('Load Failed', 'Could not load provider key status')
    } finally {
      setLoading(false)
    }
  }, [location])

  useEffect(() => { load() }, [load])

  const handleSave = async () => {
    if (!editing) return
    if (!keyInput.trim()) {
      useNotificationStore.getState().addError('Missing Key', 'Enter an API key')
      return
    }
    setSaving(true)
    try {
      await apiClient.put(`/api/v1/providers/managed/${editing.provider_id}/key`, {
        api_key: keyInput.trim(),
      })
      useNotificationStore.getState().addSuccess(
        'Key Stored',
        `${editing.provider_name}: API key saved (encrypted at rest)`
      )
      setEditing(null)
      setKeyInput('')
      setShowKey(false)
      await load()
    } catch (err) {
      frontendLoggingService.error('ProviderKeyManager', 'Save failed', err)
      useNotificationStore.getState().addError(
        'Save Failed',
        err instanceof Error ? err.message : 'Could not store API key'
      )
    } finally {
      setSaving(false)
    }
  }

  const handleClear = async (row: KeyStatus) => {
    if (!window.confirm(`Clear the stored API key for "${row.provider_name}"? It will fall back to .env if configured.`)) return
    try {
      await apiClient.delete(`/api/v1/providers/managed/${row.provider_id}/key`)
      useNotificationStore.getState().addSuccess('Key Cleared', `${row.provider_name}: stored key removed`)
      await load()
    } catch (err) {
      frontendLoggingService.error('ProviderKeyManager', 'Clear failed', err)
      useNotificationStore.getState().addError(
        'Clear Failed',
        err instanceof Error ? err.message : 'Could not clear API key'
      )
    }
  }

  const sourceInfo = (s: string) => SOURCE_LABEL[s] ?? SOURCE_LABEL.none

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-base-content">Provider API Keys</h3>
        <p className="text-sm text-readout mt-0.5">
          Where each provider gets its API key. Keys stored here are encrypted at rest;
          .env keys are read from the (gitignored) .env file.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-10">
          <span className="loading loading-spinner loading-md text-primary" />
        </div>
      ) : (
        <div className="overflow-x-auto bg-base-200 rounded-lg border border-base-300">
          <table className="table table-sm">
            <thead>
              <tr className="text-readout">
                <th>Provider</th>
                <th>Type</th>
                <th>Key Source</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => {
                const info = sourceInfo(row.key_source)
                return (
                  <tr key={row.provider_id} className="hover:bg-base-300/50">
                    <td className="font-medium">{row.provider_name}</td>
                    <td className="font-mono text-xs text-readout">{row.provider_type}</td>
                    <td>
                      <span className="tooltip tooltip-top" data-tip={info.hint}>
                        <span className={`badge badge-sm ${info.cls}`}>
                          {info.text}
                        </span>
                      </span>
                    </td>
                    <td className="text-right whitespace-nowrap">
                      {row.key_source === 'none' && row.provider_type === 'ollama' ? (
                        <span className="text-xs text-readout">No key needed (local)</span>
                      ) : (
                        <>
                          <button
                            type="button"
                            onClick={() => { setEditing(row); setKeyInput(''); setShowKey(false) }}
                            className="btn btn-xs btn-outline"
                          >
                            {row.key_source === 'db' ? 'Rotate' : 'Set Key'}
                          </button>
                          {row.key_source === 'db' && (
                            <button
                              type="button"
                              onClick={() => handleClear(row)}
                              className="btn btn-xs btn-error btn-outline"
                            >
                              Clear
                            </button>
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Set/Rotate modal */}
      {editing && (
        <div
          className="fixed inset-0 z-[999] flex items-center justify-center p-4 bg-black/50"
          role="dialog"
          onClick={() => { if (!saving) setEditing(null) }}
        >
          <div
            className="bg-base-100 rounded-box max-w-md w-full shadow-xl"
            onClick={e => e.stopPropagation()}
          >
            <div className="p-5">
              <h3 className="text-lg font-semibold text-base-content mb-1">
                {editing.key_source === 'db' ? 'Rotate' : 'Set'} API Key — {editing.provider_name}
              </h3>
              <p className="text-sm text-readout mb-4">
                Stored encrypted at rest. {editing.key_source === 'env' && 'This provider currently uses a .env key — storing one here will take precedence.'}
              </p>
              <div className="form-control">
                <label className="label">
                  <span className="label-text font-semibold">API Key</span>
                </label>
                <div className="flex gap-2">
                  <input
                    type={showKey ? 'text' : 'password'}
                    value={keyInput}
                    onChange={e => setKeyInput(e.target.value)}
                    disabled={saving}
                    placeholder="sk-... or Bearer key"
                    className="input input-bordered input-sm flex-1 font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="btn btn-sm btn-outline"
                    tabIndex={-1}
                  >
                    {showKey ? 'Hide' : 'Show'}
                  </button>
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-5">
                <button
                  type="button"
                  onClick={() => setEditing(null)}
                  disabled={saving}
                  className="btn btn-neutral btn-ghost btn-sm"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className="btn btn-primary btn-sm"
                >
                  {saving ? 'Saving...' : editing.key_source === 'db' ? 'Rotate Key' : 'Store Key'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
