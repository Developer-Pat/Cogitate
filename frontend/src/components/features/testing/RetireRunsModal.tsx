/**
 * RetireRunsModal — the confirmation for retiring SEVERAL runs at once.
 *
 * THE SAME MOVE AS A SINGLE DELETE, listed. A person retiring nine runs needs to
 * see the nine: a count is not a name, and "9 runs" could include the one they
 * wanted to keep. So the list is shown in full (scrollable when long), the
 * DESTINATION is named, and the recoverable half is stated.
 *
 * IT IS ALSO THE OUTCOME. The batch answers for every run — retired, refused (a
 * run in progress, with the lock's own sentence) or missing — and the answer
 * appears HERE rather than as a toast nobody can read in three seconds. A
 * refusal that scrolls past is a person believing nine runs went when eight did.
 *
 * Markup: the dev-note template VERBATIM
 * (`wiki/dev-notes/frontend/modal-dialogs.md`) — the fixed overlay with the width
 * var and `p-6`, never DaisyUI's `modal-box` (which renders 48px wide here), and
 * never a `max-w-*` class (which resolves to 16px — measured).
 */

import React from 'react';
import type { RunSummary, RetireResult } from '@/services/domain/TestingService';

interface RetireRunsModalProps {
  /** The runs about to move — the ticks, resolved to their records. */
  runs: RunSummary[];
  pending: boolean;
  /** The batch's own answer, once it has one. Each run is listed by name. */
  result: RetireResult | null;
  /** A failure of the REQUEST itself (not a refusal by the run lock). */
  error: string | null;
  onClose: () => void;
  onConfirm: () => void;
}

export const RetireRunsModal: React.FC<RetireRunsModalProps> = ({
  runs,
  pending,
  result,
  error,
  onClose,
  onConfirm,
}) => {
  const done = result !== null;
  const count = runs.length;

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
        <h3 className="text-lg font-semibold mb-2">
          {done
            ? `Retired ${result.retired.length} of ${count}`
            : `Retire ${count} run${count === 1 ? '' : 's'}?`}
        </h3>

        {done ? (
          <>
            <p className="text-sm mb-4">
              They are in <span className="font-mono">trash/test-runs/</span> — recoverable
              from the Trash tab, one at a time. Nothing else was touched.
            </p>

            {result.retired.length > 0 && (
              <div className="mb-4">
                <div className="text-xs uppercase tracking-wide text-base-content/50 mb-1">
                  Moved ({result.retired.length})
                </div>
                <ul className="text-xs font-mono space-y-0.5">
                  {result.retired.map((r) => (
                    <li key={r.name}>{r.name}</li>
                  ))}
                </ul>
              </div>
            )}

            {result.refused.length > 0 && (
              <div className="mb-4">
                <div className="text-xs uppercase tracking-wide text-warning mb-1">
                  Refused ({result.refused.length}) — they stayed where they were
                </div>
                <ul className="text-xs space-y-1">
                  {result.refused.map((r) => (
                    <li key={r.name}>
                      <span className="font-mono">{r.name}</span>
                      <div className="text-base-content/60">{r.reason}</div>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.missing.length > 0 && (
              <div className="mb-4">
                <div className="text-xs uppercase tracking-wide text-base-content/50 mb-1">
                  Not found ({result.missing.length})
                </div>
                <ul className="text-xs font-mono space-y-0.5">
                  {result.missing.map((name) => (
                    <li key={name}>{name}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex justify-end">
              <button className="btn btn-sm btn-primary" onClick={onClose}>
                Close
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="text-sm text-base-content/70 mb-3">
              These go to <span className="font-mono">trash/test-runs/</span> together —
              one folder each, with their report.md, report.xml and events.jsonl intact.
            </p>

            <ul className="text-xs font-mono space-y-0.5 mb-4 max-h-64 overflow-y-auto rounded-lg bg-base-200/50 p-3">
              {runs.map((r) => (
                <li key={r.name} className="flex items-center gap-2">
                  <span>{r.name}</span>
                  {r.self_test && <span className="badge badge-info badge-xs">self-test</span>}
                </li>
              ))}
            </ul>

            <p className="text-sm mb-4">
              Deleting here is a MOVE, not an erasure: nothing is pruned automatically
              and the page has no retention rule. Any run in progress is refused, and
              the answer will name it.
            </p>

            {error && (
              <div className="alert alert-error text-sm py-2 mb-4" role="alert">
                <span>{error}</span>
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button className="btn btn-sm btn-ghost" onClick={onClose} disabled={pending}>
                Keep them
              </button>
              <button
                className="btn btn-sm btn-error"
                onClick={onConfirm}
                disabled={pending}
                aria-label={`Retire ${count} runs`}
              >
                {pending ? 'Retiring…' : `Retire ${count}`}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default RetireRunsModal;
