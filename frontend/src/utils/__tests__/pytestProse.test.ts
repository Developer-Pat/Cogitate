/**
 * pytestProse — pytest's console markup, removed for display.
 *
 * The case these tests encode: the user read the Self-test run's failure in the
 * page and asked what the `E` meant —
 *
 *     "this suite exists to be red E assert (2 + 2) == 5"
 *
 * It is pytest pointing at the error line. The page should not make a person
 * learn that to read a failure message, and the raw text still ships in the API
 * for anyone reading the XML or `report.md`, where the markers are correct.
 */

import { describe, expect, it } from 'vitest';
import { readableProse } from '../pytestProse';

describe('readableProse — pytest markers off, text intact', () => {
  it('drops the E marker but keeps the assertion', () => {
    expect(readableProse('E   assert (2 + 2) == 5')).toBe('assert (2 + 2) == 5');
  });

  it('drops the `>` marker of a long traceback', () => {
    expect(readableProse('>       assert 2 + 2 == 5')).toBe('assert 2 + 2 == 5');
  });

  it('keeps a real message whole, across lines', () => {
    const raw = [
      'E   AssertionError: deliberate failure — this suite exists to be red',
      'E   assert (2 + 2) == 5',
    ].join('\n');
    expect(readableProse(raw)).toBe(
      ['AssertionError: deliberate failure — this suite exists to be red',
       'assert (2 + 2) == 5'].join('\n'),
    );
  });

  it('drops pytest\'s section rules, which carry nothing but the rule', () => {
    const raw = [
      '___________________ test_a_failure ___________________',
      'E   AssertionError: nope',
    ].join('\n');
    expect(readableProse(raw)).toBe('AssertionError: nope');
  });

  it('leaves text that merely STARTS with those letters alone', () => {
    // `Error: connection refused` is a message, not a marker. A rule that
    // stripped a bare leading E would eat this line's first letter.
    expect(readableProse('Error: connection refused')).toBe('Error: connection refused');
    expect(readableProse('Each item must be unique')).toBe('Each item must be unique');
  });

  it('handles an empty or blank message without inventing one', () => {
    expect(readableProse('')).toBe('');
    expect(readableProse('   ')).toBe('');
  });

  it('keeps a message with no markers untouched', () => {
    const raw = 'assert 1 == 2';
    expect(readableProse(raw)).toBe(raw);
  });
});
