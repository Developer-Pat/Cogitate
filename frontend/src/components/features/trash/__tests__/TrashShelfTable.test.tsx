/**
 * TrashShelfTable — the shelf's own answers, and the three places they can be
 * wrongly smoothed over.
 *
 * What is pinned here is not layout but HONESTY, because each of these is a way
 * the table could quietly say something untrue:
 *
 *  - **the column-variance rule** (`shelfShape`): the shelf's sentence about its
 *    entries is hoisted when every row says the same thing and kept as a column
 *    when they differ. The agents shelf is the case that matters — a trashed
 *    agent (restorable) beside residue (purge only) — and a table that showed one
 *    column of one repeated string, or that dropped the column on the shelf where
 *    it carries the distinction, would both be wrong in a way nothing else
 *    notices.
 *  - **no Restore on a shelf that never restores.** A column of disabled buttons
 *    reads as a broken app; the shelf's blurb already says there is no way back,
 *    so the control is absent rather than dead.
 *  - **every row offers Delete forever**, and each one's tooltip says what it
 *    does — the irreversible act is always reachable by a person who asks.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TrashShelfTable } from '../TrashShelfTable'
import { shelfShape } from '../shelfShape'
import type { TrashEntry, TrashListing } from '@/services/domain/TrashService'

const entry = (over: Partial<TrashEntry> = {}): TrashEntry => ({
  name: 'thing',
  is_dir: true,
  size_bytes: 1024,
  retired_at: 1_800_000_000,
  files: ['agent.json'],
  restorable: false,
  note: 'no record names this folder — residue, purge only',
  ...over,
})

const listing = (over: Partial<TrashListing> = {}): TrashListing => ({
  key: 'agents',
  label: 'Agents',
  restorable: true,
  directory: 'trash/agents',
  count: 1,
  entries: [entry()],
  ...over,
})

const noop = () => {}

describe('shelfShape — the column-variance rule', () => {
  it('hoists the sentence when every entry says the same thing', () => {
    const shape = shelfShape(listing({ entries: [entry(), entry({ name: 'other' })] }))
    expect(shape.sharedNote).toBe('no record names this folder — residue, purge only')
    expect(shape.mixedStates).toBe(false)
  })

  it('keeps the sentence per-row when the entries differ — the agents case', () => {
    const shape = shelfShape(
      listing({
        entries: [
          entry({ restorable: true, note: 'the agent “Bob” is trashed — restore it, or purge it for good' }),
          entry({ name: 'noid-6198c2' }),
        ],
      }),
    )
    expect(shape.sharedNote).toBeNull()
    expect(shape.mixedStates).toBe(true)
  })

  it('has nothing to hoist on an empty shelf', () => {
    expect(shelfShape(listing({ entries: [], count: 0 }))).toEqual({
      sharedNote: null,
      mixedStates: false,
    })
  })
})

describe('TrashShelfTable', () => {
  it('drops the "What it is" column when one sentence covers every row', () => {
    render(
      <TrashShelfTable
        listing={listing({ entries: [entry(), entry({ name: 'other' })] })}
        isLoading={false}
        busyName={null}
        onRestore={noop}
        onPurge={noop}
      />,
    )
    expect(screen.queryByText('What it is')).toBeNull()
  })

  it('shows the column when the rows disagree about what they are', () => {
    const restorable = entry({ restorable: true, note: 'the agent “Bob” is trashed' })
    render(
      <TrashShelfTable
        listing={listing({ entries: [restorable, entry({ name: 'noid-6198c2' })] })}
        isLoading={false}
        busyName={null}
        onRestore={noop}
        onPurge={noop}
      />,
    )
    expect(screen.getByText('What it is')).toBeTruthy()
    expect(screen.getByText('the agent “Bob” is trashed')).toBeTruthy()
  })

  it('offers no Restore at all on a shelf with no way back', () => {
    render(
      <TrashShelfTable
        listing={listing({ restorable: false, key: 'dbs', label: 'Databases' })}
        isLoading={false}
        busyName={null}
        onRestore={noop}
        onPurge={noop}
      />,
    )
    expect(screen.queryByLabelText('Restore thing')).toBeNull()
    // …but the irreversible verb is still there, and it says what it does.
    const del = screen.getByLabelText('Delete thing forever')
    expect(del.closest('span')?.getAttribute('data-tip')).toContain('nothing can restore it afterwards')
  })

  it('keeps Restore on a restorable shelf, disabled where no record backs the row — with the shelf’s reason', () => {
    render(
      <TrashShelfTable
        listing={listing({ entries: [entry({ restorable: false })] })}
        isLoading={false}
        busyName={null}
        onRestore={noop}
        onPurge={noop}
      />,
    )
    const restore = screen.getByLabelText('Restore thing') as HTMLButtonElement
    expect(restore.disabled).toBe(true)
    expect(restore.closest('span')?.getAttribute('data-tip')).toBe(
      'no record names this folder — residue, purge only',
    )
  })

  it('hands the row to the caller when Delete forever is pressed', () => {
    const onPurge = vi.fn()
    render(
      <TrashShelfTable
        listing={listing()}
        isLoading={false}
        busyName={null}
        onRestore={noop}
        onPurge={onPurge}
      />,
    )
    ;(screen.getByLabelText('Delete thing forever') as HTMLButtonElement).click()
    expect(onPurge).toHaveBeenCalledWith(expect.objectContaining({ name: 'thing' }))
  })
})
