import type { Profile } from '@/services/domain/ProfileService'

/**
 * The CURRENT-availability badge — "can this agent run RIGHT NOW?" (phase 6, G5-F2's agent half).
 *
 * Deliberately NOT the same badge as `AgentHealthCell`, and the copy keeps the two questions
 * apart: that one is HISTORICAL (`usage_logs` — "Failing", "3 failures in the last 7 days"), this
 * one is CURRENT ("cannot run now"). An agent can be failing lately and still run, or configure
 * perfectly and still be pointed at a service that is down — ONE badge for both would have to lie
 * about one of them.
 *
 * Blank by design when nothing was checked (`available` is null, never false): "we do not know" is
 * not a problem to report. In the sidebar's compact form only the EXCEPTION is drawn — a healthy
 * row already carries the health marker, and a second marker on every row is noise that buries the
 * one that matters.
 */

interface AgentServiceBadgeProps {
  availability?: Profile['service_availability']
  agentName?: string
  compact?: boolean
}

const STATE_COPY: Record<string, string> = {
  available: 'can run now',
  'down-by-occupancy': 'cannot run now — another local server owns the GPU (a swap-away, not a fault)',
  down: 'cannot run now — its service is not answering',
  unconfigured: 'cannot run now — its service is not configured',
  unknown: 'not checked',
  disabled: 'cannot run now — the chat capability is switched off',
}

export default function AgentServiceBadge({
  availability,
  agentName,
  compact = false,
}: AgentServiceBadgeProps) {
  // Nothing was read at all, or the read said nothing was checked: say nothing.
  if (!availability || availability.available === null) return null

  const { available, reason, checked_at, provider, model } = availability
  const service = [provider, model].filter(Boolean).join('/')
  const who = agentName || 'This agent'
  const state = STATE_COPY[availability.state] || (available ? 'can run now' : 'cannot run now')

  // A row that can run is the norm — the sidebar draws only the exception.
  if (compact && available) return null

  const summary = available
    ? `${who}: ${state}${service ? ` — ${service}` : ''}.`
    : `${who}: ${state}.${reason ? ` ${reason}.` : ''}`
  // The compact form has no room for a second line, so the check time rides INSIDE its tooltip —
  // the staleness window belongs to the copy wherever the copy is.
  const tip = checked_at ? `${summary} Checked ${checked_at}.` : summary

  if (compact) {
    return (
      <div className="tooltip tooltip-top" data-tip={tip}>
        <div className="badge badge-error badge-sm gap-1" aria-label={`Service availability: ${tip}`}>
          <span aria-hidden="true">⛔</span>
          <span>Cannot run</span>
        </div>
      </div>
    )
  }

  return (
    <div
      className="flex-1 min-w-0 card bg-base-200 border border-base-300 p-2"
      aria-label="Service availability"
    >
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-semibold">Service availability</span>
        <div className={`badge ${available ? 'badge-success' : 'badge-error'} badge-sm`}>
          {available ? 'Can run' : 'Cannot run'}
        </div>
        {service && <span className="text-xs text-readout">{service}</span>}
      </div>

      <div className="text-xs text-readout mt-1">{summary}</div>
      {checked_at && <div className="text-[11px] text-readout mt-1">Checked {checked_at}</div>}
    </div>
  )
}
