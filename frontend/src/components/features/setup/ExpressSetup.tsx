/**
 * ExpressSetup — one model, one key, one press.
 *
 * The ruling this exists for (2026-11-21): a fresh install should not be a configuration puzzle.
 * Pick one strong model from a packaged list, paste its key if it needs one, press once — that
 * model becomes the install's model, and chat, titles, summaries, workflows, memory, Bob and Lois
 * all follow from it.
 *
 * The list is the `setup_picks` table (loaded from `express_setup.json` at every start); whether a
 * pick APPLIES is computed server-side from `.env`, never assumed here. Nothing in this component
 * decides what a pick needs — it renders what the endpoint says.
 */

import { useCallback, useEffect, useState } from 'react'
import { apiClient } from '@/services/apiClient'
import { useNotificationStore } from '@/stores/notificationStore'
import { frontendLoggingService } from '@/services/frontendLoggingService'

interface ExpressPick {
  key: string
  label: string
  provider_name: string
  provider_type: string
  model_id: string
  tier: string
  why: string | null
  needs_kind: 'key' | 'local' | 'none'
  needs_env: string | null
  needs_url: string | null
  state: 'ready' | 'needs-key' | 'unavailable'
  detail: string
  verified_on: string | null
  verified_how: string | null
}

interface ExpressSetupProps {
  /** Called after a successful apply so the page can re-read the verdict. */
  onApplied?: (ready: boolean) => void
}

export default function ExpressSetup({ onApplied }: ExpressSetupProps) {
  const [picks, setPicks] = useState<ExpressPick[] | null>(null)
  const [selected, setSelected] = useState<string>('')
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [applying, setApplying] = useState(false)
  const [result, setResult] = useState<{ log: string[]; ready: boolean } | null>(null)
  const [failed, setFailed] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const resp = await apiClient.get<{ picks: ExpressPick[] }>('/api/v1/setup/express')
      const list = resp.data?.picks ?? []
      setPicks(list)
      // The default selection is the first pick that APPLIES here; nothing applicable falls back
      // to the first row, so the page always explains something rather than showing an empty form.
      setSelected((current) => current || (list.find((p) => p.state === 'ready') ?? list[0])?.key || '')
    } catch (err) {
      frontendLoggingService.error('ExpressSetup', 'Failed to load the express picks', err)
      setFailed('The express list could not be read — the backend did not answer.')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const pick = picks?.find((p) => p.key === selected) ?? null
  const needsKeyNow = pick?.state === 'needs-key' && !apiKey.trim()
  const canApply = Boolean(pick) && pick?.state !== 'unavailable' && !needsKeyNow && !applying

  const apply = async () => {
    if (!pick) return
    setApplying(true)
    setFailed(null)
    setResult(null)
    try {
      const body = apiKey.trim() ? { api_key: apiKey.trim() } : {}
      const resp = await apiClient.post(`/api/v1/setup/express/${pick.key}/apply`, body)
      const data = resp.data as { log: string[]; readiness?: { ready?: boolean } }
      const ready = Boolean(data.readiness?.ready)
      setResult({ log: data.log ?? [], ready })
      setApiKey('')
      useNotificationStore
        .getState()
        .addSuccess('Model set', ready ? `${pick.label} is answering this install` : `${pick.label} is set — see the readiness items`)
      await load()
      onApplied?.(ready)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not apply this model'
      setFailed(message)
      useNotificationStore.getState().addError('Express setup failed', message)
      frontendLoggingService.error('ExpressSetup', 'Apply failed', err)
    } finally {
      setApplying(false)
    }
  }

  if (!picks) {
    return (
      <div className="flex items-center justify-center py-10">
        <span className="loading loading-spinner loading-md text-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="bg-base-200 rounded-lg border border-base-300 p-5 space-y-4">
        <div>
          <label className="block text-sm font-medium text-label mb-2" htmlFor="express-pick">
            What should answer here?
          </label>
          <select
            id="express-pick"
            value={selected}
            onChange={(e) => { setSelected(e.target.value); setResult(null); setFailed(null); setApiKey('') }}
            disabled={applying}
            data-tip="A model we have picked and tested — you can change it later"
            className="tooltip tooltip-bottom select select-bordered w-full"
          >
            {picks.map((p) => (
              <option key={p.key} value={p.key}>
                {p.label} · {p.provider_name}/{p.model_id} ({p.tier})
              </option>
            ))}
          </select>
        </div>

        {pick && (
          <div className="space-y-2 text-sm">
            {pick.why && <p className="text-base-content">{pick.why}</p>}
            <p className="text-readout">
              <span className="font-medium">{pick.provider_name}</span> ·{' '}
              <code className="font-mono text-xs bg-base-300 px-1 rounded">{pick.model_id}</code>
            </p>
            <p className={pick.state === 'ready' ? 'text-success' : 'text-warning'}>{pick.detail}</p>
            <p className="text-xs text-readout">
              {pick.verified_on
                ? `Verified ${pick.verified_on}${pick.verified_how ? ` — ${pick.verified_how}` : ''}`
                : `Not yet driven end to end${pick.verified_how ? ` — ${pick.verified_how}` : ''}. You can still use it.`}
            </p>
          </div>
        )}

        {pick?.state === 'needs-key' && (
          <div className="form-control">
            <label className="label py-0">
              <span className="label-text font-semibold">
                {pick.needs_env}
                {pick.needs_url && (
                  <>
                    {' '}
                    —{' '}
                    <a
                      href={pick.needs_url}
                      target="_blank"
                      rel="noreferrer"
                      className="link link-primary"
                    >
                      get one here
                    </a>
                  </>
                )}
              </span>
            </label>
            <div className="flex gap-2 mt-1">
              <input
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                disabled={applying}
                placeholder="paste the key"
                aria-label={`${pick.needs_env} value`}
                className="input input-bordered input-sm flex-1 font-mono"
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                data-tip={showKey ? 'Hide the key' : 'Show the key'}
                className="tooltip tooltip-top btn btn-sm btn-outline"
                tabIndex={-1}
              >
                {showKey ? 'Hide' : 'Show'}
              </button>
            </div>
            <p className="text-xs text-readout mt-1">
              Stored in this install&apos;s .env (gitignored) — never written to the database.
            </p>
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => void apply()}
            disabled={!canApply}
            data-tip={
              pick?.state === 'unavailable'
                ? 'This pick cannot be used here'
                : needsKeyNow
                  ? 'Paste the key first'
                  : 'Make this the install’s model, for chat and every system function'
            }
            className={`tooltip tooltip-top btn btn-primary btn-sm rounded-[var(--button-radius)] ${
              canApply ? '' : 'btn-disabled'
            }`}
          >
            {applying ? (
              <>
                <span className="loading loading-spinner loading-xs" /> Setting it…
              </>
            ) : (
              'Use this model'
            )}
          </button>
          <a href="/providers/cloud?tab=default" className="link link-primary text-sm">
            or configure a provider and model yourself
          </a>
        </div>

        {failed && (
          <div className="p-2 bg-error/10 border border-error/20 rounded text-xs text-error">
            ⚠️ {failed}
          </div>
        )}

        {result && (
          <div className="p-3 bg-success/10 border border-success/30 rounded text-sm space-y-1">
            <p className="font-medium text-success">
              {result.ready ? 'This install is ready.' : 'Applied — the readiness items below say the rest.'}
            </p>
            <ul className="text-xs text-readout list-disc list-inside">
              {result.log.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
