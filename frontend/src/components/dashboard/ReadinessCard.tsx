import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, Hourglass, RefreshCw } from 'lucide-react'
import { readinessService, type ReadinessItem, type ReadinessReport } from '@/services/readinessService'

/**
 * THE LANDING PAGE'S ONE VERDICT (2026-11-20).
 *
 * A fresh install that could not answer a single message looked completely healthy here:
 * the Dashboard had no readiness signal at all, so the only way to discover the app was
 * unconfigured was to open Setup yourself. This card is that signal, and its button is the
 * door to the page that fixes it.
 *
 * The state sits ON the card — one headline, red when something is owed — rather than a
 * badge above a grid. Blocked items are listed but never phrased as an instruction: the
 * user cannot act on "pick a profile" while no profile can exist yet.
 */

const ICONS = { unmet: AlertTriangle, blocked: Hourglass, ok: CheckCircle2, optional: Hourglass } as const

function tone(state: ReadinessItem['state']): string {
  if (state === 'unmet') return 'text-error'
  if (state === 'blocked') return 'text-warning'
  if (state === 'ok') return 'text-success'
  return 'text-readout'
}

export default function ReadinessCard() {
  const [report, setReport] = useState<ReadinessReport | null>(null)
  const [failed, setFailed] = useState(false)

  const load = useCallback(async () => {
    try {
      setReport(await readinessService.get())
      setFailed(false)
    } catch {
      // A read failure must not present as "ready" — that is the lie this card exists to stop.
      setFailed(true)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const owed = report?.items.filter((i) => i.counted && i.state !== 'ok') ?? []

  return (
    <div className="card bg-base-200 shadow-sm">
      <div className="card-body p-4 gap-3">
        <h2 className="card-title text-sm">
          System
          <span
            className="tooltip tooltip-top"
            data-tip="Whether this install can answer yet, and what is still owed"
          >
            <AlertTriangle className="h-3.5 w-3.5 text-readout" aria-hidden="true" />
          </span>
          <button
            type="button"
            onClick={() => void load()}
            className="btn btn-ghost btn-xs ml-auto"
            data-tip="Measure the checks again"
            aria-label="Re-check system readiness"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </h2>

        {failed && (
          <div className="text-warning text-sm">
            <p className="font-medium">Readiness unknown</p>
            <p className="text-readout">
              The backend did not answer the setup check. This says nothing about whether the
              install works — re-check, or read the logs.
            </p>
          </div>
        )}

        {!failed && !report && <p className="text-sm text-readout">Checking…</p>}

        {!failed && report && report.ready && (
          <div className="text-sm">
            <p className="font-medium text-success flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              Ready — a model answers and agents are installed
            </p>
          </div>
        )}

        {!failed && report && !report.ready && (
          <div className="text-sm space-y-2">
            <p className="font-medium text-error flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" aria-hidden="true" />
              Not configured — {report.remaining}{' '}
              {report.remaining === 1 ? 'thing' : 'things'} left
            </p>
            <ul className="space-y-1.5">
              {owed.map((item) => {
                const Icon = ICONS[item.state]
                return (
                  <li key={item.key} className="flex items-start gap-2">
                    <Icon className={`h-4 w-4 mt-0.5 shrink-0 ${tone(item.state)}`} aria-hidden="true" />
                    <div>
                      <Link to={item.href} className="link link-hover font-medium text-base-content">
                        {item.label}
                      </Link>
                      <p className="text-readout">{item.detail}</p>
                    </div>
                  </li>
                )
              })}
            </ul>
          </div>
        )}

        <div className="card-actions justify-end">
          <Link
            to="/setup"
            className={`btn btn-sm ${report && !report.ready ? 'btn-primary' : 'btn-ghost'}`}
            data-tip="The Setup page takes these in order"
          >
            {report && !report.ready ? 'Open Setup' : 'Review setup'}
          </Link>
        </div>
      </div>
    </div>
  )
}
