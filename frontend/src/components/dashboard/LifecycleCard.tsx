import { useCallback, useEffect, useState } from 'react'
import { lifecycleService, type LastShutdown } from '@/services/domains/system/lifecycleService'
import { useNotificationStore } from '@/stores/notificationStore'

/**
 * THE SHUTDOWN BUTTON + THE EXIT RECORD, on one surface (2026-09-15).
 *
 * The button PRODUCES the thing the card reports, so they belong together —
 * and putting them together makes an unclean exit VISIBLE instead of buried in
 * a log. That is the design's point, not the button.
 *
 * THE THING MOST EASILY GOT WRONG: when the app stops, the request that stopped
 * it dies with it, so the connection drops and no reply arrives. That is SUCCESS.
 * `lifecycleService` resolves with `dropped: true` for it, and this component
 * says "stopping…" — never an error toast, never a spinner left turning.
 */

/** The four outcomes, said plainly. `none` claims NOTHING — that is deliberate. */
const STATE_COPY: Record<
  LastShutdown['state'],
  { label: string; tone: string; tip: string }
> = {
  clean: {
    label: 'Clean exit',
    tone: 'text-success',
    tip: 'The last instance shut down completely and abandoned nothing.',
  },
  unclean: {
    label: 'Died mid-shutdown',
    tone: 'text-error',
    tip: 'The last instance began shutting down and never finished. Something was interrupted.',
  },
  running: {
    label: 'Died while running',
    tone: 'text-warning',
    tip: 'The last instance was up and never began to shut down — killed, crashed, or the machine went down.',
  },
  none: {
    label: 'No record',
    tone: 'text-readout',
    tip: 'No exit has been recorded. A first run and a wiped store look identical here, so this claims nothing.',
  },
}

export default function LifecycleCard() {
  const [last, setLast] = useState<LastShutdown | null>(null)
  const [busy, setBusy] = useState<false | 'stop' | 'restart'>(false)
  const [confirming, setConfirming] = useState<false | 'stop' | 'restart'>(false)
  const addNotification = useNotificationStore((s) => s.addNotification)

  const load = useCallback(async () => {
    try {
      const res = await lifecycleService.getLastShutdown()
      setLast(res.data ?? null)
    } catch {
      // A read failure must not present as "no record" — that would be the lie
      // this whole mechanism exists to prevent. Leave it null and say so.
      setLast(null)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const run = useCallback(
    async (action: 'stop' | 'restart') => {
      setConfirming(false)
      setBusy(action)
      const result = await lifecycleService[action === 'stop' ? 'stop' : 'restart']()
      // The connection dropping is the EXPECTED outcome. Say "stopping…", keep
      // the state honest, and do not clear `busy`: the page is about to go.
      addNotification({
        type: 'info',
        title: action === 'stop' ? 'Stopping Cogitate' : 'Restarting Cogitate',
        message: result.dropped
          ? 'The launcher is stopping the application. This page will stop responding.'
          : 'Request accepted — the launcher is handling it.',
      })
    },
    [addNotification],
  )

  const copy = last ? STATE_COPY[last.state] : null

  return (
    <div className="card bg-base-200 shadow-sm">
      <div className="card-body p-4">
        <h2 className="card-title text-sm">
          Application Lifecycle
          <span
            className="tooltip tooltip-top"
            data-tip="Stop or restart the app, and see how the last run ended"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-3.5 w-3.5 text-readout"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </span>
        </h2>

        {/* THE RECORD — how the LAST run ended */}
        <div className="mt-2">
          {copy ? (
            <>
              <div className="flex items-baseline gap-2">
                <span
                  className={`text-sm font-medium ${copy.tone}`}
                  title={copy.tip}
                >
                  Last exit: {copy.label}
                </span>
                {last?.record?.reason && (
                  <span className="text-xs text-readout font-mono">
                    {last.record.reason}
                  </span>
                )}
              </div>
              {last?.record?.abandoned && last.record.abandoned.length > 0 && (
                <p className="text-xs text-warning mt-1">
                  Abandoned: {last.record.abandoned.join(', ')}
                </p>
              )}
            </>
          ) : (
            <span className="text-sm text-readout" title="The record could not be read">
              Last exit: unavailable — the record could not be read
            </span>
          )}
        </div>

        {/* THE BUTTONS */}
        <div className="card-actions justify-end mt-3">
          <span className="tooltip tooltip-left" data-tip="Stop the backend and the frontend">
            <button
              type="button"
              className="btn btn-sm btn-outline btn-error"
              disabled={busy !== false}
              onClick={() => setConfirming('stop')}
            >
              {busy === 'stop' ? <span className="loading loading-spinner loading-xs" /> : 'Stop'}
            </button>
          </span>
          <span className="tooltip tooltip-left" data-tip="Restart both — usually what you want">
            <button
              type="button"
              className="btn btn-sm btn-outline btn-warning"
              disabled={busy !== false}
              onClick={() => setConfirming('restart')}
            >
              {busy === 'restart' ? <span className="loading loading-spinner loading-xs" /> : 'Restart'}
            </button>
          </span>
        </div>
      </div>

      {/* A PLAIN CONFIRM — a shutdown is recoverable, so this is NOT the
          typed-name gate reserved for irreversible deletes.

          THE HOUSE TEMPLATE, VERBATIM (wiki/dev-notes/frontend/modal-dialogs.md):
          NEVER the DaisyUI `modal-box` class. In this Tailwind v4 setup it
          renders 48px wide (and 8px with an arbitrary max-w-*), because DaisyUI 5
          sets max-width via descendant selectors that outrank Tailwind's utility.
          The note calls this the 4th/5th recurrence; it recurred again here
          because the template was not copied. Width var + p-6 — BOTH required. */}
      {confirming && (
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/50"
          onClick={() => setConfirming(false)}
        >
          <div
            className="bg-base-100 rounded-lg shadow-xl max-h-[90vh] overflow-y-auto p-6"
            style={{ width: 'min(var(--dialog-width-sm), 95vw)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="font-bold text-lg">
              {confirming === 'stop' ? 'Stop Cogitate?' : 'Restart Cogitate?'}
            </h3>
            <p className="py-3 text-sm">
              {confirming === 'stop'
                ? 'The backend and the frontend will both stop. You can start them again with ./cogitate.sh start.'
                : 'Both the backend and the frontend will restart. This page will stop responding briefly.'}
            </p>
            <p className="text-xs text-readout">
              The exit is recorded either way, so the next boot can say a human did this.
            </p>
            <div className="flex justify-end gap-2 mt-4">
              <button
                type="button"
                className="btn btn-sm btn-ghost"
                onClick={() => setConfirming(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className={`btn btn-sm ${confirming === 'stop' ? 'btn-error' : 'btn-warning'}`}
                onClick={() => confirming && run(confirming)}
              >
                {confirming === 'stop' ? 'Stop' : 'Restart'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
