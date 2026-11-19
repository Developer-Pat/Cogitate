/**
 * runVerdict — the words a run's ending gets, and the codes they come from.
 *
 * The point of these tests is the SECOND reading of a code: the runner and pytest
 * both exit 2 and 4, so a mapping that trusted the number alone would report a
 * refused start as "1 test failed". The evidence (did it start, was it stopped,
 * what did the counts say) has to win, and the code only fills the gap.
 */

import { describe, expect, it } from 'vitest';
import { verdictOf } from '../runVerdict';

describe('verdictOf — a run that started and finished', () => {
  it('reads a clean run as clean, and keeps the code for the tooltip', () => {
    const v = verdictOf({
      started: true,
      exit: 0,
      counts: { passed: 5, failed: 0, errors: 0, skipped: 1 },
    });
    expect(v.words).toBe('all clear');
    expect(v.tone).toBe('clean');
    expect(v.code).toBe(0);
  });

  it('says how many failed, rather than printing the code', () => {
    const v = verdictOf({
      started: true,
      exit: 1,
      counts: { passed: 2, failed: 1, errors: 1, skipped: 1 },
    });
    expect(v.words).toBe('1 failed, 1 error');
    expect(v.tone).toBe('failed');
    expect(v.code).toBe(1);
  });

  it('pluralises errors without pluralising failed', () => {
    // pytest's own tally says "errors"; the event stream says "error" — both are
    // accepted, because the page reads both into the same badge.
    expect(
      verdictOf({ started: true, exit: 1, counts: { failed: 3, errors: 2 } }).words,
    ).toBe('3 failed, 2 errors');
    expect(
      verdictOf({ started: true, exit: 1, counts: { failed: 0, error: 2 } }).words,
    ).toBe('2 errors');
  });

  it('does NOT invent a count when there is none to read', () => {
    // A run that failed and left no parseable tally: "not clean" is what is known.
    const v = verdictOf({ started: true, exit: 1, counts: null });
    expect(v.words).toBe('not clean');
    expect(v.tone).toBe('failed');
  });

  it('reads only SKIPS as clean — a skip is not a failure', () => {
    const v = verdictOf({
      started: true,
      exit: 0,
      counts: { passed: 8, skipped: 14 },
    });
    expect(v.words).toBe('all clear');
  });
});

describe('verdictOf — a run that did not finish', () => {
  it('names a cancel as a cancel: 130 is the interrupt path', () => {
    const v = verdictOf({ started: true, exit: 130, stopped: true });
    expect(v.words).toBe('stopped — cancelled');
    expect(v.tone).toBe('stopped');
  });

  it('claims no more than it knows when the stream just stopped', () => {
    // A stream without `run_end` cannot say whether a person cancelled it or the
    // process died, so the words do not guess.
    const v = verdictOf({ started: true, exit: null, stopped: true });
    expect(v.words).toBe('stopped — it did not finish');
    expect(v.code).toBeNull();
  });

  it('reads a run with no ending and no stop as still running', () => {
    const v = verdictOf({ started: true, exit: null });
    expect(v.words).toBe('running');
    expect(v.tone).toBe('unknown');
  });
});

describe('verdictOf — a run that never started (the code needs reading)', () => {
  it('reads 4 as the LOCK, not as pytest\'s usage error', () => {
    const v = verdictOf({ started: false, exit: 4, counts: null });
    expect(v.words).toBe('did not run — another run was already going');
    expect(v.tone).toBe('stopped');
  });

  it('reads 2 as nothing matched, not as an interrupted session', () => {
    const v = verdictOf({ started: false, exit: 2, counts: null });
    expect(v.words).toBe('did not run — nothing matched');
  });

  it('reads 5 as the runner refusing to start', () => {
    const v = verdictOf({ started: false, exit: 5 });
    expect(v.words).toBe('did not run — the runner could not start');
  });

  it('names an unknown non-zero code as the runner stopping, without a reason it made up', () => {
    const v = verdictOf({ started: false, exit: 200 });
    expect(v.words).toBe('did not run — the runner stopped before it ran');
    expect(v.code).toBe(200);
  });

  it('reads an empty folder as "did not start"', () => {
    const v = verdictOf({ started: false, exit: null });
    expect(v.words).toBe('did not start');
    expect(v.code).toBeNull();
  });
});
