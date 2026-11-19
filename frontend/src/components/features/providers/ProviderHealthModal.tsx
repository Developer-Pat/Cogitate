/**
 * ProviderHealthModal — one provider's LIVE check, in the house modal shell.
 *
 * WHAT THIS REPLACES: the Health TAB, whose grid was fed no health data at all (`healthData` was
 * never passed to `ProviderHealthDashboard`, so every card read `unknown` / `Latency: N/A`), and the
 * row's `Test` action, which reported the same call as a toast. One call, one surface now.
 *
 * THE CALL: `POST /api/v1/providers/config/{id}/test` — the provider's OWN `base_url` and key,
 * probing its `/models` endpoint — the same service the rest of the page uses, so the check has no
 * request path of its own. It runs on open and on demand; the modal is a REPORT, so a provider the
 * check cannot reach says so in its own words rather than throwing.
 *
 * Presenting the result mirrors the sibling page's probe readout (`pages/LocalProviders.tsx`) so the
 * two provider pages speak one vocabulary: a status badge, the latency in ms, the model count.
 */
import React, { useCallback, useEffect, useState } from 'react'
import ProviderModal from './ProviderModal'
import providerConfigService from '@/services/domains/providers/providerConfigService'
import type { ProviderConfig } from '@/types/providers'

interface ProviderHealthModalProps {
  provider: ProviderConfig
  onClose: () => void
}

/** The four fields the check actually returns; the type carries more than the endpoint sends. */
interface CheckResult {
  status: string
  message: string
  latency_ms?: number
  models_available?: number
}

/** The statuses the endpoint returns, spelled for a person. An unknown one prints AS IS. */
const STATUS_LABEL: Record<string, string> = {
  connected: 'Connected',
  not_configured: 'Not configured',
  unreachable: 'Unreachable',
  error: 'Failed',
  unknown_provider: 'Unknown provider type',
}

const statusBadgeClass = (status: string): string => {
  if (status === 'connected') return 'badge-success'
  if (status === 'unreachable' || status === 'error') return 'badge-error'
  return 'badge-warning'
}

const ProviderHealthModal: React.FC<ProviderHealthModalProps> = ({ provider, onClose }) => {
  const [result, setResult] = useState<CheckResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)

  const runCheck = useCallback(async () => {
    setChecking(true)
    setError(null)
    try {
      const response = await providerConfigService.testProvider(provider.id)
      setResult(response)
    } catch (err) {
      // The request itself failed (the app, not the provider) — report it rather than swallow it.
      setError(err instanceof Error ? err.message : 'The check could not be run')
    } finally {
      setChecking(false)
    }
  }, [provider.id])

  // Run on open: opening the modal IS the request to check.
  useEffect(() => {
    void runCheck()
  }, [runCheck])

  const name = provider.display_name || provider.name

  return (
    <ProviderModal onClose={onClose} label={`Provider health — ${name}`} width="var(--dialog-width-md)">
      <div className="flex items-start justify-between gap-4 mb-4 pb-4 border-b border-base-300">
        <div>
          <h3 className="text-xl font-semibold text-base-content">Health</h3>
          <p className="text-sm text-readout mt-1">
            {name}
            {provider.base_url ? <span className="opacity-70"> · probes {provider.base_url}/models</span> : ' · probes the provider’s default endpoint'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn btn-sm btn-ghost" onClick={() => void runCheck()} disabled={checking}>
            {checking ? 'Checking…' : 'Check again'}
          </button>
          <button className="btn btn-sm btn-ghost" onClick={onClose} aria-label="Close">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <div role="status" aria-live="polite">
        {checking && !result ? (
          <div className="flex items-center gap-2 text-sm text-readout py-4">
            <span className="loading loading-spinner loading-sm"></span>
            Checking {name}…
          </div>
        ) : error ? (
          <div className="p-3 bg-error/10 border border-error/20 rounded text-sm text-error">{error}</div>
        ) : result ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className={`badge badge-outline badge-sm ${statusBadgeClass(result.status)}`}>
                {STATUS_LABEL[result.status] ?? result.status}
              </span>
              {checking && <span className="loading loading-spinner loading-xs"></span>}
            </div>

            {result.message && <p className="text-sm text-base-content">{result.message}</p>}

            {(result.latency_ms !== undefined || result.models_available !== undefined) && (
              <dl className="text-sm space-y-1">
                {result.latency_ms !== undefined && (
                  <div className="flex justify-between">
                    <dt className="text-readout">Latency</dt>
                    <dd className="font-medium">{Math.round(result.latency_ms)}ms</dd>
                  </div>
                )}
                {result.models_available !== undefined && (
                  <div className="flex justify-between">
                    <dt className="text-readout">Models available</dt>
                    <dd className="font-medium">{result.models_available}</dd>
                  </div>
                )}
              </dl>
            )}
          </div>
        ) : null}
      </div>
    </ProviderModal>
  )
}

export default ProviderHealthModal
