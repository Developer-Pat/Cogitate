import { useState } from 'react'
import type { Profile } from '@/services/domain/ProfileService'
import { cleanErrorMessage } from '@/utils/cleanErrorMessage'

/**
 * The provider-health widget for the Basic Info tab.
 *
 * Deliberately NOT the compact badge the sidebar uses: there is room here, so
 * the last error is readable in place rather than hidden behind a click. The
 * point of the surface is to SEE why an agent is failing.
 *
 * BLANK BY DESIGN when there is no health to report. A profile that has not
 * been saved (or has never run) has no usage_logs behind it, and inventing a
 * cheerful green badge for "we know nothing" would be a lie about state.
 *
 * Display cleaned / copy raw, same rule as the table cell: litellm nests the
 * same exception into its own message, so the stored string repeats itself and
 * reads as a wall. The panel shows it once; Copy hands over the original.
 */

interface ProfileHealthWidgetProps {
  health?: Profile['health'] | null
}

export default function ProfileHealthWidget({ health }: ProfileHealthWidgetProps) {
  const [copied, setCopied] = useState(false)

  // No health to report — say nothing at all.
  if (!health) return null

  const { status, failures_7d, last_error, last_failure_at } = health
  const clean = last_error ? cleanErrorMessage(last_error) : ''

  const badgeClass =
    status === 'fail' ? 'badge-error'
    : status === 'warn' ? 'badge-warning'
    : 'badge-success'

  const label =
    status === 'fail' ? 'Failing'
    : status === 'warn' ? 'Warnings'
    : 'Healthy'

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(last_error || '')
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div
      className="flex-1 min-w-0 card bg-base-200 border border-base-300 p-2"
      aria-label="Provider health"
    >
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-semibold">Provider health</span>
        <div className={`badge ${badgeClass} badge-sm`}>{label}</div>
        <span className="text-xs text-readout">
          {failures_7d} failure{failures_7d === 1 ? '' : 's'} in the last 7 days
        </span>
      </div>

      {last_error ? (
        <>
          {last_failure_at && (
            <div className="text-[11px] text-readout mt-1">Last failure {last_failure_at}</div>
          )}
          <pre className="text-[11px] whitespace-pre-wrap break-words max-h-20 overflow-y-auto bg-base-100 rounded p-2 mt-1 mb-1">
            {clean}
          </pre>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn btn-xs"
              onClick={copy}
              data-tip="Copy the full raw error"
            >
              {copied ? 'Copied' : 'Copy error'}
            </button>
            {copied && <span className="text-xs text-success">Copied to clipboard</span>}
          </div>
        </>
      ) : (
        <div className="text-xs text-readout mt-1">
          No provider failures in the last 7 days.
        </div>
      )}
    </div>
  )
}
