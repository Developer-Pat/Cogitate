/**
 * runVerdict — HOW A RUN ENDED, IN WORDS.
 *
 * `finished — exit 1` is a number, and the exit table is not something a person
 * reading a test page should need. What they are asking is "did anything fail?",
 * and the run's own counts answer that. So the words come from the counts, and
 * the raw code is kept in the result for the tooltip and the detail view.
 *
 * THE CODES ARE NOT UNIQUE, so EVIDENCE decides and the code only fills the gap.
 * The runner and pytest both use 2 and 4 for different things
 * (`scripts/testing/run_tests.py`):
 *
 *   0    clean, by every reading
 *   1    pytest ran a session and something failed or errored
 *   2    the RUNNER: nothing to run, or no such file.  PYTEST: interrupted
 *   4    the RUNNER: refused — the lock is held.       PYTEST: a usage error
 *   5    the runner could not load the run lock and refused to run
 *   130  interrupted — the cancel path
 *
 * To disambiguate, the caller supplies what the run itself said: whether its
 * record shows it started at all, and whether it ended without finishing. The
 * stored-run reader and the live feed both know those two facts, which is why one
 * function serves both — a second reading of the same codes is how two surfaces
 * come to disagree about what "1" means.
 *
 * Tones are the page's four states, not words: `clean`, `failed`, `stopped`, and
 * `unknown` for a run with no ending yet.
 */

export type VerdictTone = 'clean' | 'failed' | 'stopped' | 'unknown';

/** The tone, in the page's colours — ONE map, so the live badge and the run
 *  history cannot come to disagree about what a stopped run looks like. */
export const VERDICT_BADGE: Record<VerdictTone, string> = {
  clean: 'badge-success',
  failed: 'badge-error',
  stopped: 'badge-warning',
  unknown: 'badge-ghost',
};

export interface Verdict {
  /** The sentence to show. Never contains a bare code. */
  words: string;
  tone: VerdictTone;
  /** The raw ending code, for the tooltip and the detail view. Null when there
   *  was none — a run still going, or a folder a crash left behind. */
  code: number | null;
}

export interface VerdictInput {
  /** True once the run's own record shows it STARTED (`run_start`). A run
   *  refused by the lock leaves no folder, and a crash between the folder and
   *  the first event leaves an empty one — that is "did not start", not "failed". */
  started: boolean;
  /** The ending code, when there was one. */
  exit: number | null;
  /** Counts, from pytest's tally (live) or the JUnit XML (a stored run). Both
   *  vocabularies are accepted: pytest's summary says `errors`, the event stream
   *  says `error`. */
  counts?: Record<string, number> | null;
  /** True when the run ended WITHOUT finishing — the stream stopped without a
   *  `run_end`. */
  stopped?: boolean;
}

/** Any non-zero count of things that are not a pass. */
function failuresFrom(counts: Record<string, number> | null | undefined): {
  failed: number;
  errors: number;
} {
  return {
    failed: counts?.failed ?? 0,
    errors: (counts?.errors ?? 0) + (counts?.error ?? 0),
  };
}

/** "1 test failed" / "3 failed, 2 errors" — the counts, in pytest's words. */
function failurePhrase(failed: number, errors: number): string {
  const parts: string[] = [];
  if (failed > 0) parts.push(`${failed} failed`);
  if (errors > 0) parts.push(`${errors} error${errors === 1 ? '' : 's'}`);
  return parts.join(', ');
}

export function verdictOf({
  started,
  exit,
  counts = null,
  stopped = false,
}: VerdictInput): Verdict {
  const { failed, errors } = failuresFrom(counts);

  if (!started) {
    if (exit === null) {
      return { words: 'did not start', tone: 'unknown', code: null };
    }
    const why =
      exit === 4
        ? 'another run was already going'
        : exit === 2
          ? 'nothing matched'
          : exit === 5
            ? 'the runner could not start'
            : 'the runner stopped before it ran';
    return { words: `did not run — ${why}`, tone: 'stopped', code: exit };
  }

  if (exit === 130) {
    // The cancel path's own code: the runner exits 130 on an interrupt, so this
    // one IS knowable, and saying "cancelled" is the useful sentence.
    return { words: 'stopped — cancelled', tone: 'stopped', code: 130 };
  }

  if (stopped) {
    // No claim about WHO stopped it: a cancel and a crash look identical from
    // the stream, and the stream's own closing sentence is shown beside this.
    return { words: 'stopped — it did not finish', tone: 'stopped', code: exit };
  }

  if (exit === null) {
    // Started, no ending, and the stream has not said it stopped: still going.
    return { words: 'running', tone: 'unknown', code: null };
  }

  if (exit === 0) {
    return { words: 'all clear', tone: 'clean', code: 0 };
  }

  const phrase = failurePhrase(failed, errors);
  if (phrase) {
    return { words: phrase, tone: 'failed', code: exit };
  }

  // A non-zero end with no count to explain it. Say exactly that much — a
  // guessed "1 test failed" would be the page inventing a result.
  return { words: 'not clean', tone: 'failed', code: exit };
}
