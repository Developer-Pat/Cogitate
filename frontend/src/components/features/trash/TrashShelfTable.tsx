/**
 * TrashShelfTable — one shelf's entries, and the two verbs that are true of them.
 *
 * WHAT A ROW SAYS: the entry's name, what it holds, how big and how old it is,
 * and — where the shelf's own answers differ row to row — WHAT IT IS. Restore is
 * offered only on a row a RECORD backs; Delete forever is offered on every row,
 * because the irreversible act is always available to a person who asks for it.
 *
 * THE COLUMN-VARIANCE RULE, applied here rather than assumed either way: a column
 * that reads one value on every live row carries nothing, so the shelf's OWN
 * SENTENCE about its entries (`note`) is measured at render — on four shelves it
 * is one string repeated down the column, and on the agents shelf it differs
 * (a trashed agent against residue). Constant → hoisted into the card's blurb;
 * varying → a column. Either way the same sentence is on screen once.
 *
 * NO PRUNING, NO "keep the last N", nothing removed without a person asking for
 * that exact thing.
 */

import React from 'react';
import type { TrashEntry, TrashListing } from '@/services/domain/TrashService';
import { shelfShape } from './shelfShape';

interface TrashShelfTableProps {
  listing: TrashListing | null;
  isLoading: boolean;
  /** The entry whose Restore is in flight — that row says so, the others do not. */
  busyName: string | null;
  onRestore: (entry: TrashEntry) => void;
  onPurge: (entry: TrashEntry) => void;
}

/** Bytes, in the units a person reads them in. */
function sizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * What an entry holds, in the space a cell has.
 *
 * A folder of three files reads as its names; a retired backup holding fifteen
 * reads as a count, with the names on the title as a convenience. Nothing is
 * hidden behind the hover — the entry's NAME is the access path to knowing what
 * this is, and the count is the fact worth the space.
 */
function holds(entry: TrashEntry): string {
  if (entry.files.length === 0) return entry.is_dir ? 'empty' : '—';
  if (entry.files.length <= 3) return entry.files.join(', ');
  return `${entry.files.length} files`;
}

export const TrashShelfTable: React.FC<TrashShelfTableProps> = ({
  listing,
  isLoading,
  busyName,
  onRestore,
  onPurge,
}) => {
  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <span className="loading loading-spinner loading-lg" />
      </div>
    );
  }

  const entries = listing?.entries ?? [];

  if (entries.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-base-content/70">Nothing on this shelf.</p>
        <p
          className="text-sm text-base-content/60 w-full mx-auto"
          style={{ maxWidth: 'var(--content-measure)' }}
        >
          Nothing arrives here on its own: there is no retention rule and nothing
          is pruned automatically.
        </p>
      </div>
    );
  }

  // MEASURED, not assumed: one sentence repeated down a column carries nothing,
  // so a shelf whose entries all say the same thing hoists it to the blurb. The
  // measurement lives in `shelfShape` so the page's blurb and this table cannot
  // disagree about what is shared.
  const { sharedNote } = shelfShape(listing);

  return (
    <div className="overflow-x-auto">
      <table className="table table-sm">
        <thead>
          <tr>
            <th>Entry</th>
            <th>Holds</th>
            {sharedNote === null && <th>What it is</th>}
            <th className="w-24 text-right">Size</th>
            <th className="w-52">Retired</th>
            <th className="w-56"></th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.name} className="hover">
              <td className="font-mono text-xs">{entry.name}</td>
              <td className="text-xs text-base-content/60" title={entry.files.join('\n')}>
                {holds(entry)}
              </td>
              {sharedNote === null && (
                <td className="text-xs text-base-content/60">{entry.note}</td>
              )}
              <td className="text-xs text-right tabular-nums">
                {sizeLabel(entry.size_bytes)}
              </td>
              <td className="text-xs text-base-content/60">
                {new Date(entry.retired_at * 1000).toLocaleString()}
              </td>
              <td>
                <div className="flex justify-end gap-2">
                  {/* RESTORE, where a record exists to restore TO. Two levels of
                      refusal, and both are stated rather than shown as a dead
                      button: a shelf that never restores gets NO Restore at all
                      (a column of dead controls carries nothing — the blurb
                      already says why this shelf has no way back), and on a shelf
                      that does, an entry with no record keeps the button disabled
                      with the shelf's own sentence in the tooltip. */}
                  {listing?.restorable && (
                    <span
                      className="tooltip tooltip-left"
                      data-tip={
                        entry.restorable
                          ? `Put ${entry.name} back where it came from`
                          : entry.note || 'this entry has no record to restore it to'
                      }
                    >
                      <button
                        className="btn btn-xs btn-ghost"
                        onClick={() => onRestore(entry)}
                        disabled={!entry.restorable || busyName === entry.name}
                        aria-label={`Restore ${entry.name}`}
                      >
                        {busyName === entry.name ? 'Restoring…' : 'Restore'}
                      </button>
                    </span>
                  )}
                  <span
                    className="tooltip tooltip-left"
                    data-tip={`Remove ${entry.name} for good — nothing can restore it afterwards`}
                  >
                    <button
                      className="btn btn-xs btn-error btn-outline"
                      onClick={() => onPurge(entry)}
                      aria-label={`Delete ${entry.name} forever`}
                    >
                      Delete forever
                    </button>
                  </span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default TrashShelfTable;
