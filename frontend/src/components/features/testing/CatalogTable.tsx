/**
 * CatalogTable — the test catalog, tick a row or open its details.
 *
 * THE USER-TESTING PAGE. The pattern is the Sessions page's:
 * a table, a view button, and a modal. Both selection modes exist because they
 * answer different questions — the PROFILE answers "what should I run?", and
 * ticking rows answers "I want these, specifically".
 *
 * TIME IS A DEPENDENCY CLASS, never a stopwatch reading. The column says
 * short/medium/variable because a duration measured on the dev box is a lie on
 * any other machine, and this box is old.
 */

import React from 'react';
import type { CatalogEntry, TimeClass, TestTab } from '@/services/domain/TestingService';

interface CatalogTableProps {
  entries: CatalogEntry[];
  selected: Set<string>;
  onToggle: (path: string) => void;
  onToggleAll: () => void;
  onView: (entry: CatalogEntry) => void;
  onRun: (entry: CatalogEntry) => void;
  /** Why a run cannot start right now — the LOCK's own sentence, or null.
   *  A disabled control always carries its reason (never a silent no-op). */
  runBlocked?: string | null;
  isLoading?: boolean;
}

/** The tier badge. Colour carries the dependency weight, the word carries the meaning. */
const TIER_BADGE: Record<TimeClass, string> = {
  short: 'badge-success',
  medium: 'badge-info',
  variable: 'badge-warning',
};

const TIER_SHORT: Record<TimeClass, string> = {
  short: 'short',
  medium: 'medium',
  variable: 'variable',
};

/** The last result we can honestly show for a row. */
const TAB_BADGE: Record<TestTab, string | null> = {
  runnable: null,
  conditional: 'badge-warning',
  quarantine: 'badge-ghost',
  // The page's own exercise: it is red on purpose, so it wears a badge rather
  // than the plain row the suite's own files get.
  selftest: 'badge-info',
};

export const CatalogTable: React.FC<CatalogTableProps> = ({
  entries,
  selected,
  onToggle,
  onToggleAll,
  onView,
  onRun,
  runBlocked = null,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <span className="loading loading-spinner loading-lg" />
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="text-center py-12 text-base-content/60">
        <p>Nothing here.</p>
      </div>
    );
  }

  const allSelected = entries.length > 0 && entries.every((e) => selected.has(e.path));

  return (
    <div className="overflow-x-auto">
      <table className="table table-sm">
        <thead>
          <tr>
            <th className="w-10">
              {/* A disabled control cannot hold a tooltip, so the span wraps it —
                  the house rule from the tooltip doctrine. */}
              <span className="tooltip tooltip-bottom" data-tip="Select every row in this view">
                <input
                  type="checkbox"
                  className="checkbox checkbox-sm"
                  checked={allSelected}
                  onChange={() => onToggleAll()}
                  aria-label="Select every row in this view"
                />
              </span>
            </th>
            <th className="w-full">Test</th>
            <th className="w-28">Tier</th>
            <th className="w-24 text-right">Tests</th>
            <th className="w-20"></th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.path} className="hover">
              <td>
                <span className="tooltip tooltip-bottom" data-tip={`Select ${entry.filename}`}>
                  <input
                    type="checkbox"
                    className="checkbox checkbox-sm"
                    checked={selected.has(entry.path)}
                    onChange={() => onToggle(entry.path)}
                    aria-label={`Select ${entry.filename}`}
                  />
                </span>
              </td>
              <td>
                <div className="font-medium">{entry.filename}</div>
                {/* The description is DERIVED from the module docstring — it
                    lives beside the test, so it cannot drift from it.
                    NOT `truncate`: with the table's auto layout it collapsed the
                    column to "The…" — the one piece of value-add on the row,
                    invisible. The prose is allowed to wrap; the column is given
                    a floor so it does not get squeezed by the numeric columns. */}
                <div className="text-xs text-base-content/60 whitespace-normal">
                  {entry.description || (
                    <span className="italic text-base-content/40">no docstring</span>
                  )}
                </div>
                {/* THE CONDITION, on the row. It is the most actionable thing
                    about a conditional test — a user should not have to open a
                    modal to learn WHICH service is missing. It names the
                    dependency ("needs local Ollama"), never "external". */}
                {entry.condition && (
                  <div className="text-xs text-warning mt-0.5">{entry.condition}</div>
                )}
              </td>
              <td>
                <span className={`badge badge-sm ${TIER_BADGE[entry.time_class]}`}>
                  {TIER_SHORT[entry.time_class]}
                </span>
                {TAB_BADGE[entry.tab] && (
                  <span className={`badge badge-sm ml-1 ${TAB_BADGE[entry.tab]}`}>
                    {entry.tab === 'conditional' ? 'cond' : 'quar'}
                  </span>
                )}
              </td>
              <td className="text-right tabular-nums text-base-content/70">
                {entry.test_count}
              </td>
              <td className="text-right">
                {/* Both controls ALWAYS visible — never hover-hidden. Run is WIRED
                    (C2): the same runner a terminal starts, under the lock. While
                    another run holds the lock the control is DISABLED with the
                    lock's own sentence rather than failing on click. */}
                <div className="flex justify-end gap-1">
                  <button
                    className="btn btn-xs btn-ghost tooltip tooltip-left"
                    data-tip={runBlocked ?? `Run just ${entry.filename}`}
                    onClick={() => onRun(entry)}
                    disabled={runBlocked !== null}
                    aria-label={
                      runBlocked ? `Run ${entry.filename} (blocked)` : `Run ${entry.filename}`
                    }
                  >
                    Run
                  </button>
                  <button
                    className="btn btn-xs btn-ghost tooltip tooltip-left"
                    data-tip="What this protects, and what it needs"
                    onClick={() => onView(entry)}
                    aria-label={`View details for ${entry.filename}`}
                  >
                    View
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default CatalogTable;
