/**
 * RetentionCard — the workflow-run windows, on the Settings page's Data tab.
 *
 * THE WINDOWS ARE CONFIG, and this is the surface for them: every value here is read from and
 * written to the app settings through the backend, so nothing about the policy is compiled in.
 * The card shows what the store HOLDS next to the windows that decide it, because a number the
 * reader cannot connect to a consequence is decoration.
 *
 * The destructive verb follows the house procedure: a native `<dialog className="modal">` with the
 * plain panel (NEVER DaisyUI's `modal-box`), a confirm with BUTTONS and no typed phrase, the
 * dialog naming what dies and what cannot come back, and a refusal that KEEPS IT OPEN with the
 * server's own sentence. The panel takes the caret (`tabIndex={-1}`) one frame after `showModal()`.
 */

import { useEffect, useRef, useState } from 'react'

import { useWorkflowRetention } from '@/hooks/useWorkflowRetention'
import type { RetentionPolicy } from '@/types/workflows'

interface RetentionCardProps {
  /** A `--dialog-width-*` value; the house confirmations use `md`. */
  dialogWidth?: string
}

/** A window field: the label, the shipped default beside it when it differs, and its tip. */
const WindowField: React.FC<{
  label: string
  tip: string
  value: number
  defaultValue?: number
  min?: number
  max?: number
  disabled?: boolean
  onChange: (value: number) => void
}> = ({ label, tip, value, defaultValue, min, max, disabled, onChange }) => (
  <div className="form-control w-full">
    <label className="label">
      <span className="label-text font-medium">{label}</span>
      {defaultValue !== undefined && defaultValue !== value && (
        <span className="label-text-alt text-readout" data-tip={`Shipped default: ${defaultValue}`}>
          default {defaultValue}
        </span>
      )}
    </label>
    <input
      type="number"
      className="input input-bordered w-full tooltip tooltip-top"
      data-tip={tip}
      value={value}
      min={min}
      max={max}
      disabled={disabled}
      onChange={(e) => onChange(Number(e.target.value))}
    />
  </div>
)

function megabytes(bytes: number): string {
  return (bytes / 1e6).toFixed(2)
}

function day(iso: string | null): string {
  if (!iso) return '—'
  const at = new Date(iso)
  return Number.isNaN(at.getTime()) ? '—' : at.toLocaleDateString()
}

const RetentionCard: React.FC<RetentionCardProps> = ({ dialogWidth = 'var(--dialog-width-md)' }) => {
  const { policy, defaults, stats, report, loading, busy, error, save, preview, prune } =
    useWorkflowRetention()

  const [draft, setDraft] = useState<RetentionPolicy | null>(null)
  const [confirming, setConfirming] = useState(false)

  const dialogRef = useRef<HTMLDialogElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  // The draft follows the server's answer, so a save (or another window's change) is reflected.
  useEffect(() => {
    setDraft(policy)
  }, [policy])

  // THE CARET — the browser's own focus step lands on a control that may disable itself and drop
  // the caret to `body`; the PANEL takes it one frame after the dialog opens.
  useEffect(() => {
    if (!confirming) return
    const el = dialogRef.current
    if (el && !el.open) el.showModal()
    requestAnimationFrame(() => panelRef.current?.focus())
  }, [confirming])

  if (loading && !policy) {
    return (
      <div className="card bg-base-100 shadow-xl">
        <div className="card-body">
          <h2 className="card-title">Workflow runs</h2>
          <span className="loading loading-spinner loading-sm" />
        </div>
      </div>
    )
  }

  if (!policy || !draft) return null

  const dirty = JSON.stringify(draft) !== JSON.stringify(policy)
  const applyWindows = () => void save(draft)

  const askToPrune = async () => {
    // A FRESH preview every time the question is asked: the dialog's numbers must be the ones the
    // confirm would act on, never a stale reading of a policy that has since moved.
    await preview()
    setConfirming(true)
  }

  const confirmPrune = async () => {
    const applied = await prune()
    if (applied) setConfirming(false)
  }

  return (
    <div className="card bg-base-100 shadow-xl">
      <div className="card-body">
        <h2 className="card-title">Workflow runs</h2>
        <p className="text-sm opacity-70">
          A run leaves three things behind: its row, its debug snapshots and its checkpoint journal.
          These windows decide what is kept — they live in your settings, not in the code.
        </p>

        {/* WHAT THE STORE HOLDS — the state sits on the numbers themselves. */}
        <dl className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm mt-2">
          <div>
            <dt className="opacity-70">Runs kept</dt>
            <dd className="font-mono">{stats?.rows ?? '—'}</dd>
          </div>
          <div>
            <dt className="opacity-70">Debug snapshots</dt>
            <dd className="font-mono">{stats ? megabytes(stats.snapshot_bytes) : '—'} MB</dd>
          </div>
          <div>
            <dt className="opacity-70">Oldest run</dt>
            <dd className="font-mono">{day(stats?.oldest ?? null)}</dd>
          </div>
          <div>
            <dt className="opacity-70">Newest run</dt>
            <dd className="font-mono">{day(stats?.newest ?? null)}</dd>
          </div>
        </dl>

        {/* THE WINDOWS */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-2">
          <WindowField
            label="Debug snapshots (days)"
            tip="How long a run's per-node snapshots are kept. The row stays; only this detail goes."
            value={draft.snapshot_days}
            defaultValue={defaults?.snapshot_days}
            min={1}
            disabled={busy}
            onChange={(v) => setDraft({ ...draft, snapshot_days: v })}
          />
          <WindowField
            label="Runs (days)"
            tip="How long a run's row is kept — with its checkpoint journal, which goes at the same time."
            value={draft.run_days}
            defaultValue={defaults?.run_days}
            min={1}
            disabled={busy}
            onChange={(v) => setDraft({ ...draft, run_days: v })}
          />
          <WindowField
            label="Abandoned after (hours)"
            tip="A run still marked 'started' this long is not running — it is marked abandoned."
            value={draft.abandoned_hours}
            defaultValue={defaults?.abandoned_hours}
            min={1}
            disabled={busy}
            onChange={(v) => setDraft({ ...draft, abandoned_hours: v })}
          />
          <WindowField
            label="Prune at (hour, UTC)"
            tip="The hour the scheduled prune runs at, when it is switched on."
            value={draft.schedule_hour}
            defaultValue={defaults?.schedule_hour}
            min={0}
            max={23}
            disabled={busy}
            onChange={(v) => setDraft({ ...draft, schedule_hour: v })}
          />
        </div>

        {/* THE SWITCH — its own act, so it saves immediately and needs no Save press. */}
        <label className="label cursor-pointer justify-start gap-3 mt-2">
          <input
            type="checkbox"
            className="toggle toggle-primary tooltip tooltip-top"
            data-tip="Prune automatically at the hour above. Off means nothing is removed unless you ask."
            checked={draft.enabled}
            disabled={busy}
            onChange={(e) => void save({ enabled: e.target.checked })}
          />
          <span className="label-text font-medium">Prune automatically</span>
        </label>

        <div className="card-actions justify-end mt-2">
          <span className="tooltip tooltip-top" data-tip="Save the four windows above.">
            <button className="btn btn-primary btn-sm" onClick={applyWindows} disabled={!dirty || busy}>
              Save the windows
            </button>
          </span>
          <span className="tooltip tooltip-top" data-tip="Count what a prune would remove. Changes nothing.">
            <button className="btn btn-ghost btn-sm" onClick={() => void preview()} disabled={busy}>
              Preview
            </button>
          </span>
          <span
            className="tooltip tooltip-top"
            data-tip="Preview, then remove the runs past these windows. This cannot be undone."
          >
            <button className="btn btn-error btn-sm" onClick={() => void askToPrune()} disabled={busy}>
              Prune now
            </button>
          </span>
        </div>

        {/* THE PREVIEW'S NUMBERS — the cost, before the decision. */}
        {report && (
          <div className="mt-2 text-sm" data-testid="retention-report">
            <p className="text-readout">
              {report.dry_run ? 'A prune would remove' : 'Removed'}: {report.rows_pruned} run(s),{' '}
              {report.threads_pruned} checkpoint journal(s), {report.snapshots_stripped} snapshot
              blob(s) ({megabytes(report.snapshot_bytes_freed)} MB), and mark{' '}
              {report.abandoned_marked} abandoned run(s).
            </p>
            {report.errors.length > 0 && (
              <p className="text-error">Errors: {report.errors.join('; ')}</p>
            )}
          </div>
        )}

        {error && !confirming && <p className="text-sm text-error">{error}</p>}
      </div>

      {confirming && report && (
        <dialog
          ref={dialogRef}
          className="modal"
          aria-label="Apply the retention windows"
          onClick={(e) => {
            if (e.target === dialogRef.current) setConfirming(false)
          }}
        >
          <div
            ref={panelRef}
            tabIndex={-1}
            className="bg-base-100 rounded-lg shadow-xl max-h-[90vh] overflow-y-auto p-6 focus:outline-none"
            style={{ width: `min(${dialogWidth}, 95vw)` }}
          >
            <h3 className="text-lg font-medium">Prune the runs past these windows?</h3>
            <p className="text-sm mt-2">
              {report.rows_pruned} run row(s) and their checkpoint journals (
              {report.threads_pruned}) are removed from the run history, and{' '}
              {report.snapshots_stripped} snapshot blob(s) ({megabytes(report.snapshot_bytes_freed)}{' '}
              MB) are dropped from rows that stay.
            </p>
            <p className="text-sm mt-2 opacity-70">
              This cannot be undone: the runs, their journals and the snapshots are gone. Preview
              numbers come from the policy as it stands now.
            </p>
            {error && <p className="text-sm text-error mt-2">{error}</p>}
            <div className="flex justify-end gap-2 mt-4">
              <button className="btn btn-ghost btn-sm" onClick={() => setConfirming(false)} disabled={busy}>
                Cancel
              </button>
              <span
                className="tooltip tooltip-top"
                data-tip="Remove them. There is no restore for a pruned run."
              >
                <button className="btn btn-error btn-sm" onClick={() => void confirmPrune()} disabled={busy}>
                  Prune permanently
                </button>
              </span>
            </div>
          </div>
        </dialog>
      )}
    </div>
  )
}

export default RetentionCard
