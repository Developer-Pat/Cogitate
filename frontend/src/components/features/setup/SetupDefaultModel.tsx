/**
 * The Default Model step on the Setup page (ruled 2026-11-22, option 2).
 *
 * This tab used to be a stub that sent the reader to the cloud-providers page's Default tab — a
 * tab that no longer exists, so the last step of setup pointed at nothing. The act lives here now:
 * pick the provider and the model, press Save once, and the whole install takes it (chat, title,
 * summary, workflow and memory chains are rewritten by the setup accept; this is the same
 * `PUT /providers/default` the CLI drives).
 *
 * Pending-until-saved on purpose: the readout above the button says whether what is on screen is
 * what is stored, so a selection that was never saved cannot be mistaken for the install's answer.
 */
import { useCallback, useEffect, useState } from 'react'
import { DefaultProviderConfig } from '../providers/DefaultProviderConfig'
import { useDefaultProvider } from '@/hooks/useDefaultProvider'
import { useNotificationStore } from '@/stores/notificationStore'

interface Pending {
  providerId: number
  providerName: string
  providerType: string
  model: string
}

export default function SetupDefaultModel({ onApplied }: { onApplied?: () => void }) {
  const { defaultProvider, loading, error, refreshDefaultProvider, setDefaultProvider } =
    useDefaultProvider()
  const addSuccess = useNotificationStore((s) => s.addSuccess)
  const addError = useNotificationStore((s) => s.addError)

  const [pending, setPending] = useState<Pending | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    void refreshDefaultProvider()
  }, [refreshDefaultProvider])

  const handleProviderChange = useCallback(
    (providerId: number, providerName: string, providerType: string) => {
      setPending((prev) => ({
        providerId,
        providerName,
        providerType,
        model: prev?.model || defaultProvider?.model_name || '',
      }))
    },
    [defaultProvider]
  )

  const handleModelChange = useCallback(
    (model: string) => {
      setPending((prev) =>
        prev
          ? { ...prev, model }
          : defaultProvider
            ? {
                providerId: defaultProvider.provider_id,
                providerName: defaultProvider.provider_name,
                providerType: defaultProvider.provider_type,
                model,
              }
            : null
      )
    },
    [defaultProvider]
  )

  const handleSave = useCallback(async () => {
    if (!pending?.providerId || !pending.model) return
    setSaving(true)
    const ok = await setDefaultProvider(pending.providerId, pending.model)
    setSaving(false)
    if (ok) {
      addSuccess('Default model saved', `${pending.model} via ${pending.providerName}`)
      setPending(null)
      onApplied?.()
    } else {
      addError('Default model not saved', 'The backend refused the change — see the readout for why.')
    }
  }, [pending, setDefaultProvider, addSuccess, addError, onApplied])

  // A selection EQUAL to the stored default is not a change: the selector fires its callbacks
  // once on mount, and that mount must not read as "you have unsaved edits".
  const changed =
    !!pending &&
    !!pending.model &&
    (pending.providerId !== defaultProvider?.provider_id ||
      pending.model !== defaultProvider?.model_name)

  return (
    <div className="bg-base-200 rounded-lg border border-base-300 p-5 space-y-4">
      <div>
        <h3 className="font-semibold text-base-content">Default Model</h3>
        <p className="text-sm text-readout">
          One provider and model the install falls back to when a piece of work names none — chat,
          session titles, summaries, workflow steps and memory all take it from here.
        </p>
      </div>

      {loading && !defaultProvider && (
        <p className="text-sm text-readout" aria-live="polite">
          Reading the current default…
        </p>
      )}

      {/* MOUNTED AFTER THE READ, and keyed by the stored provider: the selector loads its model
          list from the provider it is given at mount, so mounting it while the default is still
          loading left it fetching provider `0` and rendering "No models available". */}
      {!loading && (
        <DefaultProviderConfig
          key={defaultProvider?.provider_id ?? 'none'}
          currentProviderId={defaultProvider?.provider_id}
          currentProviderName={defaultProvider?.provider_name}
          currentProviderType={defaultProvider?.provider_type}
          currentModel={defaultProvider?.model_name}
          onProviderChange={handleProviderChange}
          onModelChange={handleModelChange}
        />
      )}

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-xs text-readout" aria-live="polite">
          {changed
            ? 'Not saved yet — press Save to make this the install’s default.'
            : defaultProvider
              ? `Stored: ${defaultProvider.model_name} via ${defaultProvider.provider_name}.`
              : 'No default is set.'}
        </p>
        <button
          onClick={() => void handleSave()}
          disabled={saving || !changed}
          className={`btn btn-sm rounded-[var(--button-radius)] ${changed ? 'btn-primary' : 'btn-disabled'}`}
          data-tip={
            changed ? 'Save this provider and model as the install-default' : 'Nothing has changed yet'
          }
        >
          {saving ? 'Saving…' : 'Save Default Model'}
        </button>
      </div>

      {error && (
        <p className="text-xs text-error" role="status">
          {error}
        </p>
      )}
    </div>
  )
}
