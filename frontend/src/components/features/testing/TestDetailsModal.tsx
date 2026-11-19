/**
 * TestDetailsModal — what a user needs to know about one test, without reading
 * the code.
 *
 * THE USER-TESTING PAGE. Ordered by usefulness:
 *   1. THE CONDITION — why it might not run ("needs a live LLM service")
 *   2. the last result and when
 *   3. WHAT IT PROTECTS — the description, derived from the module docstring
 *   4. the tier — short / medium / variable
 *   5. where it lives
 *
 * MARKUP: the verbatim template from
 * `wiki/dev-notes/frontend/modal-dialogs.md`. NEVER `modal-box` — it renders at
 * 48px in this Tailwind v4 setup, and the width classes do nothing. The width
 * var AND `p-6` are BOTH required; the var without padding clips at the edges.
 * This trap has recurred six times, so the template is copied rather than
 * remembered.
 *
 * VERIFY after any change: open it and measure
 * `getBoundingClientRect().width` — lg is 800. If it says 48, the wrong pattern
 * was used.
 */

import React from 'react';
import type { CatalogEntry, TimeClass, TestTab } from '@/services/domain/TestingService';

interface TestDetailsModalProps {
  entry: CatalogEntry;
  /** The last result for this file, when one is known. */
  lastResult?: { status: 'passed' | 'failed' | 'skipped'; when: string; note?: string } | null;
  onClose: () => void;
}

/** The class names are the user-facing words; the values are the derivation's. */
const TIME_CLASS_LABEL: Record<TimeClass, string> = {
  short: 'Short — no I/O, pure logic',
  medium: 'Medium — local I/O (database, filesystem, the app itself)',
  // NOT a stopwatch reading. A duration measured on one machine is a lie on
  // another, and the dev box is old.
  variable: 'Variable — depends on an external service, so the network dominates',
};

const TAB_LABEL: Record<TestTab, string> = {
  runnable: 'Runnable',
  conditional: 'Conditional',
  quarantine: 'Quarantine',
  selftest: 'Self-test',
};

const Row: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="mb-3">
    <div className="text-xs uppercase tracking-wide text-base-content/50 mb-1">{label}</div>
    <div className="text-sm">{children}</div>
  </div>
);

export const TestDetailsModal: React.FC<TestDetailsModalProps> = ({ entry, lastResult, onClose }) => {
  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/50"
      onClick={() => onClose()}
    >
      <div
        className="bg-base-100 rounded-lg shadow-xl max-h-[90vh] overflow-y-auto p-6"
        style={{ width: 'min(var(--dialog-width-lg), 95vw)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── the title ── */}
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="min-w-0">
            <h3 className="text-lg font-semibold break-words">{entry.filename}</h3>
            <div className="text-xs text-base-content/60 mt-1 break-all">{entry.path}</div>
          </div>
          <button
            className="btn btn-sm btn-ghost tooltip tooltip-left"
            data-tip="Close"
            onClick={() => onClose()}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* ── 1. THE CONDITION — first, because it decides whether it runs ── */}
        {entry.condition && (
          <div className="alert alert-warning text-sm mb-4 py-2" role="status">
            <span>{entry.condition}</span>
          </div>
        )}

        {/* ── 2. what it protects — the derived description ── */}
        <div className="mb-4">
          <div className="text-xs uppercase tracking-wide text-base-content/50 mb-1">
            What it protects
          </div>
          <p className="text-sm">
            {entry.description || (
              <span className="text-base-content/50 italic">
                No description — this file has no module docstring, which is where the
                catalog reads it from.
              </span>
            )}
          </p>
        </div>

        <Row label="Last result">
          {lastResult ? (
            <span>
              <span
                className={
                  lastResult.status === 'passed'
                    ? 'text-success'
                    : lastResult.status === 'failed'
                      ? 'text-error'
                      : 'text-warning'
                }
              >
                {lastResult.status}
              </span>
              {', '}
              {lastResult.when}
              {lastResult.note ? ` — ${lastResult.note}` : ''}
            </span>
          ) : (
            <span className="text-base-content/50">has not run</span>
          )}
        </Row>

        <Row label="Time class">
          {TIME_CLASS_LABEL[entry.time_class]}
          {/* No number here on purpose: a measured duration belongs to the
              machine it was measured on. */}
        </Row>

        <Row label="Where it sits">
          {TAB_LABEL[entry.tab]}
          {entry.cluster ? ` · ${entry.cluster}` : ''} · {entry.test_count}{' '}
          {entry.test_count === 1 ? 'test' : 'tests'}
        </Row>

        {entry.markers.length > 0 && (
          <Row label="Markers">
            <div className="flex flex-wrap gap-1">
              {entry.markers.map((m) => (
                <span key={m} className="badge badge-ghost badge-sm">
                  {m}
                </span>
              ))}
            </div>
          </Row>
        )}

        <div className="flex justify-end mt-6">
          <button className="btn btn-sm" onClick={() => onClose()}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default TestDetailsModal;
