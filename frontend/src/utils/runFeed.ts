/**
 * runFeed — the live run's state, folded from the runner's own event lines.
 *
 * THE USER-TESTING PAGE, Phase C2. A run's `events.jsonl` is a line per thing
 * that happened; this module turns that stream into the four things a person
 * looking at a running test suite actually wants:
 *
 *   1. HOW FAR IT IS — `done` against `total`, where the total is pytest's own
 *      collected count (`collect`). Never a percentage and never an ETA: a bar
 *      over an unknown duration is the mock this page replaced. Until the total
 *      arrives the count is shown as a count and no fraction is claimed.
 *   2. WHAT IT HAS FOUND — passed / failed / errors / skipped, counted from the
 *      stream as it arrives. pytest's own tally (`summary`) REPLACES these at the
 *      end, and the panel says which of the two it is showing.
 *   3. WHAT HAPPENED, LINE BY LINE — the per-test lines, capped in view. The cap
 *      DROPS OLD LINES AND COUNTS THEM, because a feed that silently forgets is
 *      the same lie as a feed that invents: the panel can say "showing the last
 *      200 of 1,284, the file holds them all".
 *   4. HOW IT ENDED — `finished`, `killed`, or `error`, in the words the stream
 *      itself used. A stream that stops without `run_end` is NOT "finished": it
 *      was killed, and calling those two the same is the kind of lie this page
 *      exists to avoid.
 *
 * Pure functions on purpose: this is the part of the live tab worth testing, and
 * it is testable without a browser, a socket or a backend.
 */

import type { RunEvent, TestOutcome } from '../services/domain/TestingService';

/** How a run is going, as far as the stream says. */
export type FeedState =
  | 'connecting'
  | 'running'
  | 'finished'
  | 'killed'
  | 'error';

export interface FeedLine {
  /** The test's node id — `tests/unit/x.py::test_y`. */
  nodeid: string;
  outcome: TestOutcome;
  /** pytest's reason, for a skip or a failure. The reason is the point. */
  reason?: string;
  /** Seconds, when the event carried one. */
  duration?: number;
}

export interface RunFeed {
  runId: string | null;
  state: FeedState;
  /** The runner's own envelope fields. */
  group: string | null;
  kind: string | null;
  started: string | null;
  /** How many FILES this run selected — the runner's count, not the page's. */
  files: number | null;
  /** pytest's collected total, once it has said so. `null` until then: the page
   *  shows no fraction rather than a guess. */
  total: number | null;
  /** Counted from the stream as it arrives. */
  counts: Record<TestOutcome, number>;
  /** pytest's own final tally, when the run reached one. */
  summary: Record<string, number> | null;
  /** The lines still in view, oldest first. */
  lines: FeedLine[];
  /** How many lines the cap has dropped. */
  dropped: number;
  /** Set when the run ended: the exit code and how long it took. */
  exit: number | null;
  elapsedS: number | null;
  /** The stream's own closing sentence, when it had one. */
  message: string | null;
}

/** How many per-test lines the feed keeps. The file holds every one. */
export const LINE_CAP = 200;

const OUTCOMES: TestOutcome[] = ['passed', 'failed', 'error', 'skipped'];

export function emptyFeed(runId: string | null = null): RunFeed {
  return {
    runId,
    state: 'connecting',
    group: null,
    kind: null,
    started: null,
    files: null,
    total: null,
    counts: { passed: 0, failed: 0, error: 0, skipped: 0 },
    summary: null,
    lines: [],
    dropped: 0,
    exit: null,
    elapsedS: null,
    message: null,
  };
}

/** Tests the stream has reported on — the numerator of "312 of 1,190". */
export function doneCount(feed: RunFeed): number {
  return OUTCOMES.reduce((n, o) => n + feed.counts[o], 0);
}

/**
 * Fold one event into the feed.
 *
 * Unknown event types are kept OUT of the counts and OUT of the lines but do not
 * reset anything: a frame this build cannot read is a gap in the reading, not a
 * reason to claim the run restarted.
 */
export function reduceRunEvent(feed: RunFeed, event: RunEvent): RunFeed {
  switch (event.t) {
    case 'run_start':
      return {
        ...feed,
        state: 'running',
        runId: event.id ?? feed.runId,
        group: event.group ?? null,
        kind: event.kind ?? null,
        started: event.started ?? null,
        files: typeof event.files === 'number' ? event.files : null,
      };

    case 'collect': {
      // The reducer takes the LARGEST report, matching the plugin: every xdist
      // worker collects the whole session, so a stream carrying several equal
      // totals must not be read as a growing run.
      const count = typeof event.count === 'number' ? event.count : null;
      if (count === null) return feed;
      return { ...feed, total: feed.total === null ? count : Math.max(feed.total, count) };
    }

    case 'test': {
      const outcome = OUTCOMES.includes(event.outcome) ? event.outcome : null;
      if (!event.nodeid || outcome === null) return feed;
      const line: FeedLine = {
        nodeid: event.nodeid,
        outcome,
        ...(event.reason !== undefined ? { reason: event.reason } : {}),
        ...(event.duration !== undefined ? { duration: event.duration } : {}),
      };
      const lines = [...feed.lines, line];
      // The cap drops the OLDEST and counts them, so the panel can be exact
      // about what it is not showing.
      const over = Math.max(0, lines.length - LINE_CAP);
      return {
        ...feed,
        counts: { ...feed.counts, [outcome]: feed.counts[outcome] + 1 },
        lines: over > 0 ? lines.slice(over) : lines,
        dropped: feed.dropped + over,
      };
    }

    case 'summary':
      return {
        ...feed,
        summary: event.counts ?? null,
        elapsedS: typeof event.duration_s === 'number' ? event.duration_s : feed.elapsedS,
      };

    case 'run_end':
      return {
        ...feed,
        state: 'finished',
        exit: typeof event.exit === 'number' ? event.exit : null,
        elapsedS: typeof event.elapsed_s === 'number' ? event.elapsed_s : feed.elapsedS,
        message: null,
      };

    case 'stream_end':
      // The stream closes itself for two very different reasons, and it SAYS
      // which: a run that finished, or one whose process is gone. Trusting the
      // sentence is the whole reason it was written.
      return {
        ...feed,
        state: feed.state === 'finished' ? 'finished' : 'killed',
        message: event.message ?? null,
      };

    case 'error':
      return { ...feed, state: 'error', message: event.message ?? null };

    default:
      // `session_start` carries the rootdir, which the page already knows, and
      // anything from a newer plugin is simply not read yet.
      return feed;
  }
}

/** Fold a batch — the stream delivers lines in order, sometimes several at once. */
export function reduceRunEvents(feed: RunFeed, events: RunEvent[]): RunFeed {
  return events.reduce(reduceRunEvent, feed);
}

/**
 * The counts to SHOW: pytest's own tally once the run has one, else the live
 * count. Which one it is has to be visible to the reader — see `countsAreFinal`.
 */
export function shownCounts(feed: RunFeed): Record<string, number> {
  if (feed.summary) return feed.summary;
  const out: Record<string, number> = {};
  for (const o of OUTCOMES) if (feed.counts[o] > 0) out[o] = feed.counts[o];
  return out;
}

/** True when the numbers on screen are pytest's final tally, not the live count. */
export function countsAreFinal(feed: RunFeed): boolean {
  return feed.summary !== null;
}
