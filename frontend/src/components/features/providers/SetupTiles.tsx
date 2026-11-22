/**
 * The setup TILES at the top of the cloud-providers page (ruled 2026-11-22, option 2).
 *
 * The acts themselves live on the Setup page — one implementation each — so this page's job is to
 * show where the install stands and hand the reader the door. Every tile IS a readiness item: the
 * same measured payload the Dashboard's verdict card renders, never a second grade assembled here.
 *
 * The house rules this follows: state sits ON the element it describes (one badge per tile, no
 * headline restating them); a state of `ok` is the norm and reads quietly while a DEFECT is the
 * thing that stands out; `blocked` says "waiting on …" rather than giving an instruction for a step
 * the user cannot take yet; `optional` is never counted.
 */
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { readinessService, type ReadinessItem, type ReadinessState } from '@/services/readinessService'

/** The badge a state wears. `ok` is quiet — the defect is what the page is for. */
const STATE_BADGE: Record<ReadinessState, { className: string; word: string; tip: string }> = {
  ok: { className: 'badge-success badge-sm', word: 'ready', tip: 'This step is done.' },
  unmet: { className: 'badge-warning badge-sm', word: 'to do', tip: 'This step needs you.' },
  blocked: {
    className: 'badge-ghost badge-sm',
    word: 'waiting',
    tip: 'Waiting on an earlier step — nothing to do here yet.',
  },
  optional: {
    className: 'badge-ghost badge-sm',
    word: 'optional',
    tip: 'Not required to answer; switch it on when you want it.',
  },
}

function SetupTile({ item }: { item: ReadinessItem }) {
  const badge = STATE_BADGE[item.state] ?? STATE_BADGE.unmet
  return (
    <Link
      to={item.href}
      data-tip={badge.tip}
      aria-label={`${item.label} — ${badge.word}. ${item.detail}`}
      className="card bg-base-100 border border-base-300 rounded-[var(--card-radius)] p-3 hover:border-primary transition-colors duration-[var(--button-transition)]"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold">{item.label}</span>
        <span className={`badge ${badge.className}`}>{badge.word}</span>
      </div>
      <p className="text-[11px] text-readout mt-1 leading-snug">{item.detail}</p>
    </Link>
  )
}

export default function SetupTiles() {
  const [items, setItems] = useState<ReadinessItem[] | null>(null)

  const load = useCallback(async () => {
    try {
      const report = await readinessService.get()
      setItems(report.items)
    } catch {
      // A page that cannot read the verdict says nothing rather than inventing one.
      setItems(null)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (!items) return null

  return (
    <section className="mb-4" aria-label="Setup status">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-[var(--card-gap)]">
        {items.map((item) => (
          <SetupTile key={item.key} item={item} />
        ))}
      </div>
    </section>
  )
}
