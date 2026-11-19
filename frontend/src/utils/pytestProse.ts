/**
 * pytestProse — pytest's human-readable output, made readable.
 *
 * The reader serves a failure's `why` verbatim (the JUnit `message`, or the
 * element's text), and pytest writes that text for a CONSOLE: it prefixes
 * traceback lines with its own markers, so a person reading the page sees
 * `E assert (2 + 2) == 5` and reasonably asks what the `E` means. It means
 * nothing to a reader — it is pytest pointing at the error line, and pointing is
 * what the surrounding layout already does.
 *
 * So the markers are stripped WHERE THEY ARE DISPLAYED, and only there:
 *
 *   `E   <text>`   the error line — the exception or the assertion's own text
 *   `>   <text>`   the failing source line (`--tb=long`)
 *   `_____ name _____`   pytest's rule between sections: dropped whole, since
 *                        its only content is the separator
 *
 * The RAW string stays untouched in the API — the page's job is to present it,
 * and the evidence is still there for anyone reading the XML or `report.md`,
 * where the markers are meaningful and correct.
 *
 * Pure and tiny on purpose: this is display, and it is worth a test rather than
 * a regex inlined in a component.
 */

/** One line, without pytest's leading traceback marker. */
function withoutMarker(line: string): string {
  // `E` and `>` only when followed by spaces — `E   assert ...`. A line that
  // merely STARTS with those letters (a variable named `E`) is left alone.
  return line.replace(/^[E>]\s{1,3}/, '');
}

/** True for pytest's section rule: `____________________ test_name ______`. */
function isRule(line: string): boolean {
  return /^_{4,}.*_{4,}$/.test(line.trim());
}

export function readableProse(raw: string): string {
  if (!raw) return '';
  return raw
    .split('\n')
    .map((line) => line.trimEnd())
    .filter((line) => !isRule(line))
    .map(withoutMarker)
    .join('\n')
    .trim();
}
