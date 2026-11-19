/**
 * LiveRunPanel — the Run tab: what a running test suite is doing, right now.
 *
 * THE USER-TESTING PAGE, Phase C2 — the part a person actually looks at while
 * waiting. It renders the fold of the run's own event stream (`utils/runFeed`)
 * and nothing else: every number here was written by the runner or by pytest.
 *
 * FOUR DECISIONS ARE BAKED IN, each one a rule from the design:
 *
 * 1. **COUNTED, NEVER PERCENTAGE-ED.** Counts against pytest's own collected
 *    total ("312 of 1,190"), and NO bar, NO percentage and NO ETA — a progress bar
 *    over an unknown duration is the animation this page replaced. Until the
 *    total arrives the number is shown as a count and no fraction is claimed.
 *    The collected total is a fact about THIS run (the plugin reports it), not a
 *    sum this page does over the test tree — a file with parametrized tests
 *    expands into more cases than it has `def test_` lines, so the page's own
 *    arithmetic would be wrong in exactly the runs that matter most.
 *
 * 2. **THE COUNTS SAY WHICH COUNT THEY ARE.** pytest's final tally and the page's
 *    running count are different things and the panel labels the one on screen;
 *    silently swapping one for the other is how a number becomes a claim.
 *
 * 3. **WATCH-ONLY WHEN IT IS NOT OURS.** A run started in a terminal or by the
 *    sweep is shown live — the lock names who started it — with no Cancel button.
 *    Cancel appears only for a run this page started. Stopping someone else's run
 *    is a deliberate act, not the side effect of a button.
 *
 * 4. **THE CAP IS STATED.** The per-test lines are capped in view and the panel
 *    says how many it is not showing; the run's own `events.jsonl` holds them all.
 *    A feed that quietly forgets is a feed that lies by omission.
 */

import React from 'react';
import type { RunLockInfo } from '@/services/domain/TestingService';
import {
  countsAreFinal,
  doneCount,
  shownCounts,
  type FeedLine,
  type RunFeed,
} from '@/utils/runFeed';
import type { StreamStatus } from '@/hooks/useRunStream';
import { VERDICT_BADGE, verdictOf } from '@/utils/runVerdict';

interface LiveRunPanelProps {
  feed: RunFeed;
  status: StreamStatus;
  /** The run being watched — the lock's id, or the one this page just started. */
  runId: string | null;
  /** The lock, when a run holds it: who started it, and since when. */
  lock: RunLockInfo | null;
  /** What the Run control would start, for the idle state to state. */
  selection: { files: number; tests: number; label: string };
  /** True when this page started the run — the only case Cancel is offered. */
  canCancel: boolean;
  cancelPending: boolean;
  /** The cancel's own result, including any name-worthy survivors. */
  cancelNote: string | null;
  /** How loudly to say it: a stop that worked is `ok`, survivors or a refusal by
   *  someone else's run is `warn`, and "it had already finished" is `plain`. */
  cancelTone: 'ok' | 'warn' | 'plain';
  onCancel: () => void;
  /** Clear the RESULT from view. The run itself is untouched — it stays in Runs,
   *  where Delete is the control that removes it. */
  onClear: () => void;
}

/** pytest's vocabulary in the page's colours, ordered by how much it matters. */
const COUNT_STYLE: Record<string, string> = {
  failed: 'text-error font-semibold',
  error: 'text-error font-semibold',
  errors: 'text-error font-semibold',
  skipped: 'text-warning',
  passed: 'text-success',
  xfailed: 'text-warning',
  xpassed: 'text-warning',
};

const OUTCOME_STYLE: Record<string, string> = {
  passed: 'text-success',
  failed: 'text-error',
  error: 'text-error',
  skipped: 'text-warning',
};

const COUNT_ORDER = ['failed', 'error', 'errors', 'skipped', 'xfailed', 'xpassed', 'passed'];

function orderedCounts(counts: Record<string, number>): { word: string; n: number }[] {
  const out: { word: string; n: number }[] = [];
  for (const word of COUNT_ORDER) {
    if (counts[word] != null && counts[word] > 0) out.push({ word, n: counts[word] });
  }
  // Anything pytest emitted outside the known vocabulary still shows: a count
  // that is dropped is the one that mattered.
  for (const [word, n] of Object.entries(counts)) {
    if (!COUNT_ORDER.includes(word) && n > 0) out.push({ word, n });
  }
  return out;
}

/** The wall-clock time the run started, in the READER's timezone.
 *
 *  The runner stamps `started` in UTC (`…T00:28:17+00:00`), and slicing that
 *  string shows 00:28 to someone whose clock says 19:28 — a time that is not
 *  wrong so much as unreadable. `Date` parses it and the reader's own locale
 *  formats it; an unparseable stamp falls back to the raw tail rather than
 *  disappearing. */
function startedAt(stamp: string): string {
  const when = new Date(stamp);
  if (Number.isNaN(when.getTime())) return stamp.slice(11, 19);
  return when.toLocaleTimeString();
}

const LineRow: React.FC<{ line: FeedLine }> = ({ line }) => {
  // The file part is what a person scans for; the test name follows it.
  const [where, test] = line.nodeid.split('::');
  return (
    <div className="flex items-baseline gap-2 py-0.5">
      <span className={`w-16 shrink-0 text-xs ${OUTCOME_STYLE[line.outcome] ?? ''}`}>
        {line.outcome}
      </span>
      <span className="font-mono text-xs break-all">
        <span className="text-base-content/60">{where}</span>
        {test && <span className="text-base-content/90">::{test}</span>}
      </span>
      {line.reason && (
        // The reason is the point: "needs Ollama" is actionable where "skipped" is not.
        <span className="text-xs text-warning/90 break-all">{line.reason}</span>
      )}
    </div>
  );
};

export const LiveRunPanel: React.FC<LiveRunPanelProps> = ({
  feed,
  status,
  runId,
  lock,
  selection,
  canCancel,
  cancelPending,
  cancelNote,
  cancelTone,
  onCancel,
  onClear,
}) => {
  const counts = shownCounts(feed);
  const rows = orderedCounts(counts);
  const final = countsAreFinal(feed);
  const done = doneCount(feed);
  const total = feed.total;
  const startedByOther = lock !== null && lock.origin !== 'page';
  const isVitest = feed.kind === 'vitest';

  // ── nothing to watch ──────────────────────────────────────────────────────
  if (!runId) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3 text-center">
        <p className="text-base-content/70">Nothing is running.</p>
        {/* THE WIDTH IS AN EXPLICIT STYLE, not `max-w-md`.
            In this Tailwind v4 setup `max-w-md` resolves to **16px**, `max-w-lg` to
            **24px**, `max-w-xl` to `none` (measured on the live page: the
            `--container-*` tokens are empty) — the same broken-token family as the
            48px `modal-box`. A block child of an `items-center` column flex is sized
            by its max-width, so the sentence came out ONE WORD PER LINE.
            `w-full` alone is not enough: the broken max-width still caps it. */}
        <p className="text-sm text-base-content/60 w-full" style={{ maxWidth: 'var(--content-measure)' }}>
          {selection.files > 0 ? (
            <>
              Run starts {selection.label} —{' '}
              <span className="tabular-nums">{selection.files}</span> test files (
              <span className="tabular-nums">{selection.tests}</span> tests) under the run lock,
              then this tab follows it live. A run already going — from a terminal, or from the
              sweep — shows up here on its own.
            </>
          ) : (
            <>
              {/* The Live tab has no rows of its own, so its selection is empty:
                  naming it ("Run starts … 0 test files") said nothing and read as
                  a fault. Say what to DO instead. */}
              Start one from Runnable, Conditional or Self-test, or watch one that is already
              going — a run from a terminal or from the sweep shows up here on its own.
            </>
          )}
        </p>
      </div>
    );
  }

  // ── how it ended, in words ──
  // The badge said `finished — exit 1`, which is a number most people cannot
  // read. The verdict comes from the run's own counts ("1 failed"), and the raw
  // code stays on the tooltip for whoever wants it. `started` is false only while
  // the page is still connecting: a run that is being watched HAS started.
  const verdict = verdictOf({
    started: feed.state === 'running' || feed.state === 'finished' || feed.state === 'killed',
    exit: feed.exit,
    counts: shownCounts(feed),
    // A stream that stopped without `run_end` cannot say who stopped it, so the
    // words claim no more than "it did not finish" — the stream's own closing
    // sentence is shown beside this.
    stopped: feed.state === 'killed',
  });
  const stateBadge =
    feed.state === 'running'
      ? { cls: 'badge-info', text: 'running' }
      : feed.state === 'finished' || feed.state === 'killed'
        ? { cls: VERDICT_BADGE[verdict.tone], text: verdict.words }
        : feed.state === 'error'
          ? { cls: 'badge-warning', text: 'the feed stopped' }
          : { cls: 'badge-ghost', text: 'connecting' };
  /** The run is over — its result is what is on screen. */
  const ended =
    feed.state === 'finished' || feed.state === 'killed' || feed.state === 'error';

  return (
    <div className="space-y-4">
      {/* ── who is running, and since when ── */}
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={`badge badge-sm tooltip tooltip-bottom ${stateBadge.cls}`}
          data-tip={
            verdict.code === null
              ? 'the runner reported no exit code'
              : `exit code ${verdict.code} — the runner's own`
          }
        >
          {stateBadge.text}
        </span>

        <span className="font-mono text-xs text-base-content/70">{runId}</span>

        {feed.group && <span className="badge badge-ghost badge-sm">{feed.group}</span>}
        {feed.files != null && (
          <span className="text-xs text-base-content/60">
            <span className="tabular-nums">{feed.files}</span> files
          </span>
        )}
        {feed.started && (
          <span className="text-xs text-base-content/60">
            started {startedAt(feed.started)}
          </span>
        )}
        {startedByOther && lock && (
          // WATCH-ONLY, and it says so — with the lock's own fact, not a guess.
          <span className="text-xs text-warning">
            started outside this page ({lock.origin}, pid {lock.pid}) — watching, not stopping
          </span>
        )}
        {/* A run that has ended leaves its result on screen, and this is how a
            person clears it for the next one. It clears the VIEW: the run stays
            in Runs as the record, which is what the tooltip says. */}
        {status === 'error' && (
          <span className="text-xs text-warning">stream interrupted — reconnecting</span>
        )}

        {/* THE RUN'S OWN ACTION, in ONE slot on the right: Cancel while it is
            going, Clear result once it has ended. Two `ml-auto` items in one flex
            row fight over the space and the second one lands mid-row — which is
            exactly how the clear button came to sit in the middle, reading as
            stray text.

            And NO permanent note about who may cancel: a run started elsewhere
            already says so above, and a finished run needs no explanation for a
            stop button that is absent. */}
        <div className="ml-auto flex items-center gap-2">
          {ended && (
            <button
              className="btn btn-sm btn-outline tooltip tooltip-left"
              data-tip="Stop showing this result. The run itself stays in Runs — nothing is deleted."
              onClick={onClear}
            >
              Clear result
            </button>
          )}
          {canCancel && (
            <button
              className="btn btn-sm btn-error btn-outline"
              onClick={onCancel}
              disabled={cancelPending || feed.state !== 'running'}
              aria-label="Stop this run"
              title="Stop this run — the whole process group, then verified"
            >
              {cancelPending ? 'Stopping…' : 'Cancel'}
            </button>
          )}
        </div>
      </div>

      {cancelNote && (
        <div
          className={`text-sm py-2 ${
            cancelTone === 'warn'
              ? 'alert alert-warning'
              : cancelTone === 'ok'
                ? 'alert alert-success'
                : 'text-base-content/70'
          }`}
        >
          <span>{cancelNote}</span>
        </div>
      )}

      {/* ── the counts ── */}
      <div>
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <span className="text-2xl tabular-nums">
            {done}
            {total != null && (
              <>
                <span className="text-base-content/40"> of </span>
                <span>{total}</span>
              </>
            )}
          </span>
          {rows.map(({ word, n }) => (
            <span key={word} className={`text-sm tabular-nums ${COUNT_STYLE[word] ?? ''}`}>
              {n} {word}
            </span>
          ))}
          {rows.length === 0 && feed.state === 'running' && (
            <span className="text-sm text-base-content/60">nothing has finished yet</span>
          )}
        </div>
        <div className="text-xs text-base-content/50 mt-1">
          {final ? (
            <>pytest's own tally, from the run's summary</>
          ) : (
            <>
              counted from the stream as it arrives
              {total == null && ' — the collected total arrives when pytest has collected'}
            </>
          )}
          {feed.elapsedS != null && (
            <> · took {feed.elapsedS.toFixed(1)}s on this machine</>
          )}
        </div>
      </div>

      {/* ── how it ended, in the stream's own words ── */}
      {feed.message && (
        <div className={`text-sm ${feed.state === 'killed' ? 'text-warning' : 'text-base-content/70'}`}>
          {feed.message}
        </div>
      )}

      {/* ── the ui (vitest) group's honest gap ── */}
      {isVitest && feed.lines.length === 0 && (
        <div className="alert alert-info text-sm py-2">
          <span>
            This group reports an envelope only — its per-test lines come from pytest's own
            reporter, and vitest has no equivalent wired up yet. The counts above are real;
            the line-by-line feed is not available for it.
          </span>
        </div>
      )}

      {/* ── the lines ── */}
      {feed.lines.length > 0 && (
        <div className="border border-base-300 rounded-[var(--card-radius)] max-h-96 overflow-y-auto p-2 bg-base-100">
          {feed.lines.map((line, i) => (
            <LineRow key={`${line.nodeid}-${i}`} line={line} />
          ))}
        </div>
      )}

      {feed.dropped > 0 && (
        <p className="text-xs text-base-content/50">
          Showing the last {feed.lines.length} of {done} lines — the run keeps every one of them
          in its own events file.
        </p>
      )}

      {feed.state === 'running' && feed.lines.length === 0 && !isVitest && (
        <p className="text-xs text-base-content/50">
          Collected, running — the first result will appear here as soon as one test finishes.
        </p>
      )}
    </div>
  );
};

export default LiveRunPanel;
