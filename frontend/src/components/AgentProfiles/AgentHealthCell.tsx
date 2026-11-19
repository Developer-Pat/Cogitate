import { useState } from 'react'

import { cleanErrorMessage } from '@/utils/cleanErrorMessage'

/**
 * The provider-health cell — the surface the chat badge never had a home for.
 *
 * Same data the AgentSelector badge shows (`AgentHealth`, derived from
 * usage_logs), but here it is readable rather than a truncated tooltip: the
 * full last error, when it happened, and a copy button.
 *
 * Two deliberate choices:
 *  - The error is DISPLAYED cleaned and COPIED raw. litellm nests the same
 *    exception inside its own message, so the raw string repeats itself and
 *    reads as a wall; the cleaned form is for eyes, the raw is the evidence.
 *  - The trigger is ALWAYS VISIBLE (no hover-only affordance), and the flyout
 *    opens UP so a row near the table's foot does not push the panel off-screen.
 */

type ProfileHealth = {
  status: 'ok' | 'warn' | 'fail'
  consecutive_failures: number
  last_error?: string | null
  last_failure_at?: string | null
  failures_7d: number
}

interface AgentHealthCellProps {
  health?: ProfileHealth | null
  agentName?: string
  /**
   * The list-view form. The sidebar is ~320px and healthy is the NORM, so
   * spelling out "OK" on every row is noise that buries the exception. In
   * compact form a healthy agent gets a quiet dot (still visible, still
   * hoverable — nothing is hidden), and anything wrong gets the FULL badge.
   */
  compact?: boolean
}

export default function AgentHealthCell({ health, agentName, compact = false }: AgentHealthCellProps) {
  const [copied, setCopied] = useState(false)

  // No health on the response means nothing is known — say so rather than
  // implying the agent is fine.
  if (!health) {
    return <span className="text-xs text-readout">—</span>
  }

  const { status, failures_7d, last_error, last_failure_at } = health
  const clean = last_error ? cleanErrorMessage(last_error) : ''

  const badgeClass =
    status === 'fail' ? 'badge-error'
    : status === 'warn' ? 'badge-warning'
    : 'badge-ghost'

  const label =
    status === 'fail' ? 'Failing'
    : status === 'warn' ? 'Warnings'
    : 'OK'

  const summary = status === 'ok'
    ? `${agentName || 'This agent'}: no provider failures in the last 7 days`
    : `${failures_7d} failure${failures_7d === 1 ? '' : 's'} in the last 7 days`

  const copy = async () => {
    try {
      // The RAW string: the cleaned form is for reading, this is the evidence.
      await navigator.clipboard.writeText(last_error || '')
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  // In compact form the badge must actually BE compact: the sidebar's info
  // column is ~128px and "Warnings 4/7d" alone measured ~118px, which pushed
  // the row past the panel and clipped it. So compact shows the marker + the
  // count ("⚠4") and the words live in the tooltip; the flyout on click still
  // carries the full error. Non-compact (the table column) keeps the words,
  // where there is room for them.
  const compactBadge = (
    <div className={`badge ${badgeClass} badge-sm gap-1`} aria-label={`Provider health: ${label}, ${summary}`}>
      <span aria-hidden="true">⚠</span>
      <span>{failures_7d}</span>
    </div>
  )

  const badge = compact ? compactBadge : (
    <div className={`badge ${badgeClass} badge-sm gap-1`} aria-label={`Provider health: ${label}`}>
      {status !== 'ok' && <span aria-hidden="true">⚠</span>}
      <span>{label}</span>
      {status !== 'ok' && <span className="opacity-80">{failures_7d}/7d</span>}
    </div>
  )

  // Healthy and nothing to read.
  if (!last_error) {
    // In compact form a healthy agent is a small dot rather than the word
    // "OK" — the sidebar has ~320px and every row being fine is the norm.
    // It stays a VISIBLE marker (not hover-only), and its reason is on hover.
    if (compact && status === 'ok') {
      return (
        <div className="tooltip tooltip-top" data-tip={summary}>
          <span
            className="inline-block w-2 h-2 rounded-full bg-success shrink-0"
            role="img"
            aria-label="Provider health: OK"
          />
        </div>
      )
    }
    return (
      <div className="tooltip tooltip-top" data-tip={summary}>
        {badge}
      </div>
    )
  }

  return (
    <div className="dropdown dropdown-end dropdown-top">
      <div tabIndex={0} role="button" className="tooltip tooltip-top" data-tip="Show the last provider error">
        {badge}
      </div>
      <div
        tabIndex={0}
        className="dropdown-content menu bg-base-100 border border-base-300 rounded-box shadow-lg z-50 w-96 p-3"
      >
        <div className="text-xs font-medium mb-1">
          Last provider error
          {last_failure_at && (
            <span className="ml-2 font-normal text-readout">{last_failure_at}</span>
          )}
        </div>
        <pre className="text-[11px] whitespace-pre-wrap break-words max-h-40 overflow-y-auto bg-base-200 rounded p-2 mb-2">
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
      </div>
    </div>
  )
}
