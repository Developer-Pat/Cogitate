/**
 * ReportsTable — the test runs on disk, and what they actually said.
 *
 * THE USER-TESTING PAGE, Phase B.
 *
 * **The skips are the point.** A skipped test is EVIDENCE, not noise: "12 tests
 * are not running because Ollama is down" is something a person can act on,
 * where a bare count is not. So a skipped count is a button, and the reasons are
 * one click away.
 *
 * The page READS these runs; it does not own them. `data/test-runs/` is written
 * with the runner and the sweep, and there is no repository, rolling or
 * retention here — that is the user-space boundary.
 */

import React, { useState } from 'react';
import type { RunSummary, RunDetail } from '@/services/domain/TestingService';
import { testingService } from '@/services/domain/TestingService';
import { VERDICT_BADGE, verdictOf } from '@/utils/runVerdict';
import { readableProse } from '@/utils/pytestProse';
import type { RunDiff } from '@/services/domain/TestingService';

interface ReportsTableProps {
  reports: RunSummary[];
  isLoading?: boolean;
  /** Retire ONE run — the page owns the call, and the confirmation. */
  onDelete?: (run: RunSummary) => void;
  /** Keep a COPY of one run — the page owns the dialog, and the destination. */
  onSave?: (run: RunSummary) => void;
  /** The run in progress, if it is one of these rows: it cannot be deleted, and
   *  the control says so instead of failing on click. */
  runningRunId?: string | null;
  /** The runs ticked for a BATCH retire. The page owns the set — a table that
   *  kept its own selection would disagree with the count in the action bar. */
  selected?: Set<string>;
  onToggle?: (name: string) => void;
  onToggleAll?: () => void;
}

/** pytest's vocabulary, ordered by how much the user should care. */
const COUNT_ORDER = ['failed', 'error', 'errors', 'skipped', 'passed', 'warning', 'warnings'] as const;

const COUNT_STYLE: Record<string, string> = {
  failed: 'text-error font-semibold',
  error: 'text-error font-semibold',
  errors: 'text-error font-semibold',
  skipped: 'text-warning',
  passed: 'text-success',
  warning: 'text-base-content/50',
  warnings: 'text-base-content/50',
};

function summarise(counts: Record<string, number>): { word: string; n: number }[] {
  const out: { word: string; n: number }[] = [];
  for (const word of COUNT_ORDER) {
    if (counts[word] != null) out.push({ word, n: counts[word] });
  }
  // Anything pytest emitted that is not in the known vocabulary still shows —
  // silently dropping a count would hide exactly the number that matters.
  for (const [word, n] of Object.entries(counts)) {
    if (!COUNT_ORDER.includes(word as (typeof COUNT_ORDER)[number])) out.push({ word, n });
  }
  return out;
}

/** One list of the diff: what changed, and which tests. */
const DiffRow: React.FC<{ label: string; tone: string; items: string[] }> = ({
  label,
  tone,
  items,
}) => {
  if (items.length === 0) return null;
  return (
    <div>
      <span className={`${tone} font-semibold`}>
        {label} ({items.length})
      </span>
      <ul className="font-mono text-base-content/70">
        {items.slice(0, 12).map((test) => (
          <li key={test}>{test}</li>
        ))}
        {items.length > 12 && (
          <li className="text-base-content/50">
            …and {items.length - 12} more — the run's report.xml holds them all
          </li>
        )}
      </ul>
    </div>
  );
};

const DetailPanel: React.FC<{ name: string }> = ({ name }) => {
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [diff, setDiff] = useState<RunDiff | null>(null);
  const [loading, setLoading] = useState(true);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      // THE DIFF COMES WITH THE DETAIL. "Why did this fail?" is the question a
      // failure raises, and what CHANGED is most of the answer — a second click to
      // ask for it would be one click too many.
      const [res, diffRes] = await Promise.all([
        testingService.getRun(name),
        testingService.getDiff(name),
      ]);
      if (cancelled) return;
      // The client RETURNS {error} — it does not throw. Read it, do not ignore.
      setDetail(res.error ? null : res.data ?? null);
      setDiff(diffRes.error ? null : diffRes.data ?? null);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [name]);

  if (loading) {
    return (
      <div className="p-4 text-center">
        <span className="loading loading-spinner loading-sm" />
      </div>
    );
  }
  if (!detail) {
    return <div className="p-4 text-sm text-error">Could not read this report.</div>;
  }

  return (
    <div className="p-4 bg-base-200/50 text-sm space-y-4">
      {detail.note && (
        <div className="text-xs text-warning">{detail.note}</div>
      )}

      {detail.failures.length > 0 && (
        <div>
          <div className="text-xs uppercase tracking-wide text-base-content/50 mb-1">
            Failures and errors ({detail.failures.length})
          </div>
          <ul className="space-y-1">
            {detail.failures.map((f, i) => (
              <li key={i}>
                <span className="badge badge-error badge-sm mr-2">{f.kind}</span>
                <span className="font-mono text-xs">{f.where}</span>
                {f.why && (
                  // THE MESSAGE, WITHOUT PYTEST'S MARKERS. The stored text is
                  // written for a console and carries `E ` / `> ` prefixes plus
                  // its own section rules ("this suite exists to be red E assert
                  // (2 + 2) == 5" is how a person reads that). The raw string
                  // stays in the API; the display is cleaned where it is shown.
                  <div className="text-xs text-base-content/60 ml-1 whitespace-pre-line">
                    {readableProse(f.why)}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {detail.skips.length > 0 && (
        <div>
          {/* The whole reason this page exists: a skip with its REASON. */}
          <div className="text-xs uppercase tracking-wide text-base-content/50 mb-1">
            Skipped — and why ({detail.skips.length})
          </div>
          <ul className="space-y-1">
            {detail.skips.map((s, i) => (
              <li key={i}>
                <span className="font-mono text-xs">{s.where}</span>
                <div className="text-xs text-warning">{s.reason}</div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {detail.failures.length === 0 && detail.skips.length === 0 && (
        <div className="text-base-content/60">No failures and no skips in this run.</div>
      )}

      {diff && (
        <div>
          <div className="text-xs uppercase tracking-wide text-base-content/50 mb-1">
            What changed
          </div>
          {diff.reason ? (
            // NO COMPARISON, SAID PLAINLY. An empty diff would read as "nothing
            // changed", which is a different fact.
            <div className="text-xs text-base-content/60">{diff.reason}</div>
          ) : (
            <div className="space-y-2 text-xs">
              <div className="text-base-content/60">
                against <span className="font-mono">{diff.baseline}</span> — the last green
                run of the same selection
              </div>
              <DiffRow
                label="Newly failing — passed there"
                tone="text-error"
                items={diff.newly_failing}
              />
              <DiffRow label="Fixed since then" tone="text-success" items={diff.fixed} />
              <DiffRow label="Added" tone="text-base-content/60" items={diff.added} />
              <DiffRow label="Gone" tone="text-base-content/60" items={diff.removed} />
              {diff.newly_failing.length === 0 &&
                diff.fixed.length === 0 &&
                diff.added.length === 0 &&
                diff.removed.length === 0 && (
                  <div className="text-base-content/60">
                    Nothing changed in this run's tests — the same ones passed and failed.
                  </div>
                )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export const ReportsTable: React.FC<ReportsTableProps> = ({
  reports,
  isLoading = false,
  onDelete,
  onSave,
  runningRunId = null,
  selected = new Set<string>(),
  onToggle,
  onToggleAll,
}) => {
  const [expanded, setExpanded] = useState<string | null>(null);
  const allSelected = reports.length > 0 && reports.every((r) => selected.has(r.name));

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <span className="loading loading-spinner loading-lg" />
      </div>
    );
  }

  if (reports.length === 0) {
    return (
      <div className="text-center py-12 text-base-content/60">
        <p>No test runs yet.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="table table-sm">
        <thead>
          <tr>
            <th className="w-10">
              {/* A disabled control cannot hold a tooltip, so the span wraps it —
                  the house rule from the tooltip doctrine. */}
              <span className="tooltip tooltip-bottom" data-tip="Select every run in this list">
                <input
                  type="checkbox"
                  className="checkbox checkbox-sm"
                  checked={allSelected}
                  onChange={() => onToggleAll?.()}
                  aria-label="Select every run"
                />
              </span>
            </th>
            <th>Run</th>
            <th className="w-24">Group</th>
            <th>Result</th>
            <th className="w-32 text-right">Verdict</th>
            <th className="w-20"></th>
          </tr>
        </thead>
        <tbody>
          {reports.map((r) => {
            const isOpen = expanded === r.name;
            // WAS THE RUN'S OWN RECORD ENOUGH TO DECIDE? `running` means it
            // started and has no ending yet; an exit code means it ended. Neither
            // one, with a folder on disk, is a run that died before it began.
            const started = r.running || r.exit_code !== null;
            const verdict = verdictOf({
              started,
              exit: r.exit_code,
              counts: r.counts,
              stopped: started && !r.running && r.exit_code === null,
            });
            return (
              <React.Fragment key={r.name}>
                <tr className={isOpen ? 'bg-base-200/40' : 'hover'}>
                  <td>
                    <span
                      className="tooltip tooltip-bottom"
                      data-tip={`Select ${r.name} for a batch retire`}
                    >
                      <input
                        type="checkbox"
                        className="checkbox checkbox-sm"
                        checked={selected.has(r.name)}
                        onChange={() => onToggle?.(r.name)}
                        aria-label={`Select ${r.name}`}
                      />
                    </span>
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs">{r.name}</span>
                      {r.self_test && (
                        // A DELIBERATELY RED RUN, marked. Without this a person
                        // scanning history reads the fixture's failure as the
                        // suite's — which is the one thing this page exists to
                        // prevent.
                        <span
                          className="badge badge-info badge-sm tooltip tooltip-right"
                          data-tip="The page's own check — this run was meant to fail"
                        >
                          self-test
                        </span>
                      )}
                    </div>
                    {r.duration_s != null && (
                      <div className="text-xs text-base-content/50">
                        {/* Labelled as an observation, NOT as a property — the
                            same number is different on another machine. */}
                        took {r.duration_s.toFixed(1)}s on this machine
                      </div>
                    )}
                  </td>
                  <td>
                    <span className="badge badge-ghost badge-sm">{r.group || '—'}</span>
                  </td>
                  <td>
                    {r.parsed ? (
                      <div className="flex flex-wrap gap-x-3 gap-y-1">
                        {summarise(r.counts).map(({ word, n }) => (
                          <span key={word} className={`text-sm ${COUNT_STYLE[word] ?? ''}`}>
                            {n} {word}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-sm text-warning">
                        no summary — truncated, in flight, or crashed early
                      </span>
                    )}
                  </td>
                  <td className="text-right">
                    {/* THE WORDS, NOT THE CODE. `1` is not an answer to "did
                        anything fail?" — the counts are, and the raw code stays
                        on the tooltip for whoever wants it. */}
                    <span
                      className={`badge badge-sm tooltip tooltip-left ${VERDICT_BADGE[verdict.tone]}`}
                      data-tip={
                        verdict.code === null
                          ? 'the runner reported no exit code'
                          : `exit code ${verdict.code} — the runner's own`
                      }
                    >
                      {verdict.words}
                    </span>
                  </td>
                  <td className="text-right">
                    <div className="flex justify-end gap-1">
                      <button
                        className="btn btn-xs btn-ghost tooltip tooltip-left"
                        data-tip={isOpen ? 'Hide this run\'s detail' : 'What this run said, and why anything was skipped'}
                        onClick={() => setExpanded(isOpen ? null : r.name)}
                        aria-label={isOpen ? 'Hide details' : 'Show details'}
                      >
                        {isOpen ? 'Hide' : 'View'}
                      </button>
                      {/* SAVE A COPY. Allowed for any run that has finished: the
                          copy is the point, and the run stays exactly where it is.
                          A run being written is refused for the same reason a
                          delete is — its files are mid-write. */}
                      <span
                        className="tooltip tooltip-left"
                        data-tip={
                          runningRunId === r.name
                            ? 'This run is in progress — its files are still being written'
                            : onSave
                              ? 'Save a copy of this run — the run itself stays here'
                              : 'Not wired'
                        }
                      >
                        <button
                          className="btn btn-xs btn-ghost"
                          onClick={() => onSave?.(r)}
                          disabled={!onSave || runningRunId === r.name}
                          aria-label={`Save run ${r.name}`}
                        >
                          Save
                        </button>
                      </span>
                      {/* The control is ALWAYS visible (never hover-hidden) and
                          DISABLED with its reason when the run cannot go — the
                          lock already knows, so the page does not have to fail
                          on click to say it. */}
                      <span
                        className="tooltip tooltip-left"
                        data-tip={
                          runningRunId === r.name
                            ? 'This run is in progress — it cannot be deleted while it is writing'
                            : onDelete
                              ? 'Delete this run — it moves to the trash rather than being erased'
                              : 'Not wired'
                        }
                      >
                        <button
                          className="btn btn-xs btn-ghost text-error"
                          onClick={() => onDelete?.(r)}
                          disabled={!onDelete || runningRunId === r.name}
                          aria-label={`Delete run ${r.name}`}
                        >
                          Delete
                        </button>
                      </span>
                    </div>
                  </td>
                </tr>
                {isOpen && (
                  <tr>
                    <td colSpan={6} className="p-0">
                      <DetailPanel name={r.name} />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default ReportsTable;