/**
 * INGESTABLES — what a run covers, and what it will cost.
 *
 * The six ingestion roots are the unit a person thinks in: a checkbox each, the files counted, the
 * chunks and minutes ESTIMATED beside them, and one total. The estimate's rate is the last run's own
 * measurement (`/rag/ingest/estimate` names its source), so the number can never quietly drift from
 * reality without saying so.
 *
 * The destructive pair is deliberately two controls, not one: CLEAR empties the index, REBUILD is a
 * clear followed by a forced run. Both ask once, on a dialog with the counts on it.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNotifications } from '@/hooks/useNotifications'
import { ragService, type IngestEstimate, type IngestRequest } from '@/services/ragService'

interface IngestablesTabProps {
  /** The roots the app knows (from `/rag/status` → config.ingestion_dirs). */
  roots: string[]
  /** A job is running: starting another is refused, and Clear is unsafe. */
  running: boolean
  /** Called after a run is accepted, so the page can start polling. */
  onStarted: () => void
  /** Called after a destructive clear, so the health card refreshes. */
  onIndexChanged: () => void
}

const MODES: { id: IngestRequest['mode']; label: string; tip: string }[] = [
  {
    id: 'incremental',
    label: 'Incremental',
    tip: 'Only files that are new or changed since the last index — the normal choice',
  },
  { id: 'full', label: 'Full', tip: 'Re-read every selected file, fresh' },
  {
    id: 'force-reingest',
    label: 'Force re-ingest',
    tip: 'Ignore the index timestamps entirely — slowest, and it re-embeds everything',
  },
  {
    id: 'heal',
    label: 'Heal',
    tip: 'Repair only the documents the index disagrees with — a chunk that failed, or a chunker change',
  },
]

const formatMinutes = (minutes: number): string => {
  if (minutes <= 0) return '0 min'
  // 25 seconds is not "~0 min" — it reads as "nothing", which is the one thing a run never is.
  if (minutes < 1) return '<1 min'
  if (minutes < 60) return `~${Math.round(minutes)} min`
  const hours = Math.floor(minutes / 60)
  const rest = Math.round(minutes % 60)
  return rest === 0 ? `~${hours} h` : `~${hours} h ${rest} min`
}

export default function IngestablesTab({
  roots,
  running,
  onStarted,
  onIndexChanged,
}: IngestablesTabProps) {
  const { notifySuccess, notifyError } = useNotifications()
  const [selected, setSelected] = useState<string[]>(roots)
  const [mode, setMode] = useState<IngestRequest['mode']>('incremental')
  const [estimate, setEstimate] = useState<IngestEstimate | null>(null)
  const [estimateError, setEstimateError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const clearDialog = useRef<HTMLDialogElement>(null)

  // Roots arrive with the status read; select them all until the person says otherwise.
  useEffect(() => {
    setSelected((current) => (current.length === 0 ? roots : current))
  }, [roots])

  const loadEstimate = useCallback(async (dirs: string[]) => {
    if (dirs.length === 0) {
      setEstimate(null)
      return
    }
    const res = await ragService.estimateIngest(dirs)
    if (res.data) {
      setEstimate(res.data)
      setEstimateError(null)
    } else {
      setEstimate(null)
      setEstimateError(res.error?.message ?? 'Could not price this run')
    }
  }, [])

  useEffect(() => {
    void loadEstimate(selected)
  }, [selected, loadEstimate])

  const toggleRoot = (root: string) => {
    setSelected((current) =>
      current.includes(root) ? current.filter((r) => r !== root) : [...current, root],
    )
  }

  const start = async () => {
    if (selected.length === 0) return
    setBusy(true)
    try {
      const res = await ragService.triggerIngest(mode, 'docs', selected)
      if (res.data) {
        notifySuccess('Ingest Started', `Job ${res.data.job_id} — ${res.data.mode}`)
        onStarted()
      } else {
        notifyError('Ingest Refused', res.error?.message ?? 'The run was not accepted')
      }
    } finally {
      setBusy(false)
    }
  }

  const clear = async () => {
    clearDialog.current?.close()
    setBusy(true)
    try {
      const res = await ragService.clearIndex()
      if (res.data) {
        notifySuccess(
          'Index Cleared',
          `${res.data.chunks} chunk(s) from ${res.data.documents} document(s) removed`,
        )
        onIndexChanged()
      } else {
        notifyError('Clear Refused', res.error?.message ?? 'The index was not cleared')
      }
    } finally {
      setBusy(false)
    }
  }

  const rowFor = (root: string) => estimate?.dirs.find((row) => row.dir === root)

  return (
    <div className="space-y-6">
      <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
        <div className="card-body gap-[var(--card-gap)]">
          <h2 className="card-title">📥 What to ingest</h2>
          <p className="text-sm text-readout">
            Each root is a directory of documentation. The counts are read from disk; the chunks and
            minutes are estimates.
          </p>

          <div className="overflow-x-auto">
            <table className="table table-sm">
              <thead>
                <tr>
                  <th className="w-10">
                    <span className="sr-only">Include</span>
                  </th>
                  <th>Root</th>
                  <th className="text-right">Files</th>
                  <th className="text-right">Chunks (est.)</th>
                  <th className="text-right">Time (est.)</th>
                </tr>
              </thead>
              <tbody>
                {roots.map((root) => {
                  const row = rowFor(root)
                  const isOn = selected.includes(root)
                  return (
                    <tr key={root} className={isOn ? '' : 'opacity-60'}>
                      <td>
                        <input
                          type="checkbox"
                          className="checkbox checkbox-sm"
                          checked={isOn}
                          onChange={() => toggleRoot(root)}
                          aria-label={`Include ${root}`}
                          data-tip={isOn ? 'Included in the run' : 'Excluded from the run'}
                        />
                      </td>
                      <td className="font-mono text-xs">{root}</td>
                      <td className="text-right font-semibold">{row ? row.files : '—'}</td>
                      <td className="text-right">{row ? row.chunks : '—'}</td>
                      <td className="text-right">{row ? formatMinutes(row.minutes) : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
              <tfoot>
                <tr>
                  <th></th>
                  <th>
                    {selected.length} of {roots.length} roots
                  </th>
                  <th className="text-right">{estimate ? estimate.total.files : '—'}</th>
                  <th className="text-right">{estimate ? estimate.total.chunks : '—'}</th>
                  <th className="text-right">
                    {estimate ? formatMinutes(estimate.total.minutes) : '—'}
                  </th>
                </tr>
              </tfoot>
            </table>
          </div>

          {estimate && (
            <p className="text-xs text-readout">
              Estimate: {estimate.chars_per_chunk} characters a chunk, at{' '}
              <strong>{estimate.rate_s_per_chunk.toFixed(1)} s a chunk</strong> ({estimate.rate_source}).
            </p>
          )}
          {estimateError && <div className="alert alert-warning text-sm">{estimateError}</div>}
        </div>
      </div>

      <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
        <div className="card-body gap-[var(--card-gap)]">
          <h2 className="card-title">▶️ Run</h2>

          <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-end">
            <label className="form-control w-full sm:w-64">
              <span className="label-text mb-1">Mode</span>
              <select
                className="select select-bordered"
                value={mode}
                onChange={(e) => setMode(e.target.value as IngestRequest['mode'])}
                aria-label="Ingestion mode"
              >
                {MODES.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </label>

            <button
              className="btn btn-primary"
              onClick={() => void start()}
              disabled={busy || running || selected.length === 0}
              data-tip={
                running
                  ? 'A job is already running — cancel it on the Index tab first'
                  : selected.length === 0
                    ? 'Select at least one root'
                    : `Index ${selected.length} root(s) — ${estimate ? formatMinutes(estimate.total.minutes) : 'estimating'}`
              }
            >
              {busy ? <span className="loading loading-spinner loading-xs"></span> : 'Start ingestion'}
            </button>

            <span className="text-sm text-readout">
              {running ? 'A job is running.' : MODES.find((m) => m.id === mode)?.tip}
            </span>
          </div>
        </div>
      </div>

      <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
        <div className="card-body gap-[var(--card-gap)]">
          <h2 className="card-title">🧨 The destructive half</h2>
          <p className="text-sm text-readout">
            Clear empties the index — every chunk and every vector. The documents on disk are
            untouched; the next run rebuilds from them.
          </p>
          <div>
            <button
              className="btn btn-error btn-outline"
              onClick={() => clearDialog.current?.showModal()}
              disabled={busy || running}
              data-tip={running ? 'Cancel the running job before clearing' : 'Empty the index'}
            >
              Clear the index
            </button>
          </div>
        </div>
      </div>

      <dialog ref={clearDialog} className="modal">
        <div className="modal-box">
          <h3 className="font-bold text-lg">Clear the index?</h3>
          <p className="py-4">
            This removes{' '}
            <strong>{estimate ? estimate.total.chunks : 'every'}</strong> chunk(s) from the vector
            index. Nothing on disk is deleted, and the next run rebuilds it.
          </p>
          <div className="modal-action">
            <button className="btn" onClick={() => clearDialog.current?.close()}>
              Cancel
            </button>
            <button className="btn btn-error" onClick={() => void clear()}>
              Clear
            </button>
          </div>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button>close</button>
        </form>
      </dialog>
    </div>
  )
}
