/**
 * The live run feed's fold — the part of the Run tab that can be wrong quietly.
 *
 * C2's rules that these tests pin, one per describe:
 *   - the total comes from pytest (`collect`) and a repeated delivery of the same
 *     total is NOT a growing run;
 *   - the per-test cap drops the oldest AND counts them;
 *   - pytest's final tally replaces the live count (and the panel can tell);
 *   - a stream that stops without an end event is KILLED, never "finished";
 *   - a frame this build cannot read is ignored, not counted and not fatal.
 */

import { describe, it, expect } from 'vitest';
import {
  LINE_CAP,
  countsAreFinal,
  doneCount,
  emptyFeed,
  reduceRunEvent,
  reduceRunEvents,
  shownCounts,
} from '../runFeed';
import type { RunEvent } from '@/services/domain/TestingService';

const start = (over: Partial<Extract<RunEvent, { t: 'run_start' }>> = {}): RunEvent => ({
  t: 'run_start',
  id: 'page-20260101-000000',
  kind: 'pytest',
  group: 'files',
  files: 2,
  parallel: false,
  backend: 'healthy',
  pid: 4242,
  started: '2026-01-01T00:00:00',
  ...over,
});

const testEvent = (nodeid: string, outcome: Extract<RunEvent, { t: 'test' }>['outcome'],
              reason?: string): RunEvent => ({
  t: 'test', nodeid, outcome, ...(reason !== undefined ? { reason } : {}),
});

describe('the run envelope', () => {
  it('a run_start says what is running and how many files', () => {
    const feed = reduceRunEvent(emptyFeed(), start());
    expect(feed.state).toBe('running');
    expect(feed.runId).toBe('page-20260101-000000');
    expect(feed.files).toBe(2);
    expect(feed.group).toBe('files');
  });

  it('the total is pytest\'s, and equal reports do not grow it', () => {
    // Every xdist worker collects the whole session, so the stream can carry the
    // same total many times. Reading that as progress would be a lie.
    const feed = reduceRunEvents(
      emptyFeed(),
      [{ t: 'collect', count: 26, via: 'xdist' }, { t: 'collect', count: 26, via: 'xdist' }],
    );
    expect(feed.total).toBe(26);
  });

  it('a LARGER report supersedes a smaller one', () => {
    const feed = reduceRunEvents(
      emptyFeed(),
      [{ t: 'collect', count: 5, via: 'xdist' }, { t: 'collect', count: 26, via: 'xdist' }],
    );
    expect(feed.total).toBe(26);
  });

  it('no total yet means no fraction — total stays null', () => {
    const feed = reduceRunEvent(emptyFeed(), start());
    expect(feed.total).toBeNull();
    expect(doneCount(feed)).toBe(0);
  });
});

describe('the counts', () => {
  it('counts each outcome as it arrives', () => {
    const feed = reduceRunEvents(emptyFeed(), [
      start(),
      testEvent('t.py::a', 'passed'),
      testEvent('t.py::b', 'passed'),
      testEvent('t.py::c', 'failed', 'AssertionError'),
      testEvent('t.py::d', 'skipped', 'needs Ollama'),
      testEvent('t.py::e', 'error', 'fixture blew up'),
    ]);
    expect(feed.counts).toEqual({ passed: 2, failed: 1, error: 1, skipped: 1 });
    expect(doneCount(feed)).toBe(5);
  });

  it('keeps pytest\'s final tally separate from the live count, and says which', () => {
    const live = reduceRunEvents(emptyFeed(), [testEvent('t.py::a', 'passed')]);
    expect(live.counts.passed).toBe(1);
    expect(live.summary).toBeNull();
    expect(countsAreFinal(live)).toBe(false);

    const finished = reduceRunEvent(live, { t: 'summary', counts: { passed: 2, failed: 1 }, duration_s: 12.5 });
    // The live count saw one test; pytest's tally is the authoritative end state,
    // and `shownCounts` switches to it — the panel labels which is on screen.
    expect(finished.counts.passed).toBe(1);
    expect(countsAreFinal(finished)).toBe(true);
    expect(shownCounts(finished)).toEqual({ passed: 2, failed: 1 });
    expect(finished.elapsedS).toBe(12.5);
  });

  it('a skip keeps its REASON — the reason is the point', () => {
    const feed = reduceRunEvent(emptyFeed(), testEvent('t.py::d', 'skipped', 'needs Ollama'));
    expect(feed.lines[0].reason).toBe('needs Ollama');
  });
});

describe('the line cap', () => {
  it('keeps the newest lines and COUNTS the dropped ones', () => {
    const events: RunEvent[] = [];
    const total = LINE_CAP + 25;
    for (let i = 0; i < total; i++) events.push(testEvent(`t.py::test_${i}`, 'passed'));
    const feed = reduceRunEvents(emptyFeed(), events);

    expect(feed.lines).toHaveLength(LINE_CAP);
    expect(feed.dropped).toBe(25);
    // The oldest went, the newest stayed: the cap drops from the FRONT.
    expect(feed.lines[feed.lines.length - 1].nodeid).toBe(`t.py::test_${total - 1}`);
    expect(feed.lines[0].nodeid).toBe(`t.py::test_25`);
    // Nothing is lost from the counts — the cap is a view, not the record.
    expect(doneCount(feed)).toBe(total);
  });
});

describe('how it ended', () => {
  it('run_end finishes it, with the exit code and the duration', () => {
    const feed = reduceRunEvents(emptyFeed(), [
      start(),
      { t: 'run_end', exit: 1, elapsed_s: 19.4 },
    ]);
    expect(feed.state).toBe('finished');
    expect(feed.exit).toBe(1);
    expect(feed.elapsedS).toBe(19.4);
  });

  it('a stream that stops WITHOUT an end event was KILLED, not finished', () => {
    const feed = reduceRunEvents(emptyFeed(), [
      start(),
      { t: 'stream_end', message: 'the run is no longer in progress and its stream stopped without an end event (it was killed)' },
    ]);
    expect(feed.state).toBe('killed');
    expect(feed.message).toContain('killed');
  });

  it('the stream\'s own sentence is kept when it says the run FINISHED', () => {
    const feed = reduceRunEvents(emptyFeed(), [
      start(),
      { t: 'run_end', exit: 0, elapsed_s: 3 },
      { t: 'stream_end', message: 'the run has finished — nothing more will be written' },
    ]);
    expect(feed.state).toBe('finished');
  });

  it('an error frame is an error, and carries its message', () => {
    const feed = reduceRunEvent(emptyFeed('nope'),
      { t: 'error', message: 'this run has no events file' });
    expect(feed.state).toBe('error');
    expect(feed.message).toContain('no events file');
  });
});

describe('frames this build cannot read', () => {
  it('an unknown event type changes nothing at all', () => {
    const before = reduceRunEvents(emptyFeed(), [start(), testEvent('t.py::a', 'passed')]);
    const unknown = { t: 'some_future_event', whatever: 7 } as unknown as RunEvent;
    expect(reduceRunEvent(before, unknown)).toEqual(before);
  });

  it('a test frame with no nodeid or an unknown outcome is not counted', () => {
    const before = emptyFeed();
    expect(reduceRunEvent(before, { t: 'test', nodeid: '', outcome: 'passed' })).toEqual(before);
    expect(
      reduceRunEvent(before, { t: 'test', nodeid: 't.py::a', outcome: 'exploded' } as unknown as RunEvent),
    ).toEqual(before);
  });
});
