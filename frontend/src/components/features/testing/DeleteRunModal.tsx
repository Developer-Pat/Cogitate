/**
 * DeleteRunModal — the confirmation for retiring ONE run.
 *
 * THE USER-TESTING PAGE, Phase C2. Deleting is the person's own action, one
 * folder at a time: no retention rule, no pruning, nothing automatic. The modal
 * says three things the action needs and nothing more:
 *
 *   - WHICH run (`name`), because a table row is not a name;
 *   - WHAT HAPPENS — it moves to `trash/test-runs/<name>`, so it can be recovered.
 *     Delete here is a MOVE, never an unlink, and saying so is the difference
 *     between a considered action and a gamble;
 *   - THAT A RUN IN PROGRESS CANNOT GO — the backend refuses it with the lock's
 *     own sentence, and the modal shows that sentence rather than a generic error.
 *
 * The markup is the dev-note template VERBATIM (wiki/dev-notes/frontend/
 * modal-dialogs.md): the fixed overlay with the width var and `p-6`, never
 * DaisyUI's `modal-box`, which renders 48px wide in this Tailwind v4 setup.
 */

import React from 'react';
import type { RunSummary } from '@/services/domain/TestingService';

interface DeleteRunModalProps {
  run: RunSummary;
  /** Set while the request is in flight — the button says so. */
  pending: boolean;
  /** The refusal, when there was one: the lock's own sentence, or the error. */
  error: string | null;
  onClose: () => void;
  onConfirm: () => void;
}

export const DeleteRunModal: React.FC<DeleteRunModalProps> = ({
  run,
  pending,
  error,
  onClose,
  onConfirm,
}) => (
  <div
    className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/50"
    onClick={() => onClose()}
  >
    <div
      className="bg-base-100 rounded-lg shadow-xl max-h-[90vh] overflow-y-auto p-6"
      style={{ width: 'min(var(--dialog-width-md), 95vw)' }}
      onClick={(e) => e.stopPropagation()}
    >
      <h3 className="text-lg font-semibold mb-2">Delete this run?</h3>

      <p className="text-sm text-base-content/70 mb-3">
        <span className="font-mono">{run.name}</span> — its report.md, report.xml and
        events.jsonl go together.
      </p>

      <p className="text-sm mb-4">
        It moves to <span className="font-mono">trash/test-runs/{run.name}</span> rather than
        being erased, so it can be recovered from disk. Nothing else is touched: the page has no
        retention rule and never deletes a run on its own.
      </p>

      {error && (
        <div className="alert alert-error text-sm py-2 mb-4" role="alert">
          <span>{error}</span>
        </div>
      )}

      <div className="flex justify-end gap-2">
        <button className="btn btn-sm btn-ghost" onClick={onClose} disabled={pending}>
          Keep it
        </button>
        <button
          className="btn btn-sm btn-error"
          onClick={onConfirm}
          disabled={pending}
          aria-label={`Delete run ${run.name}`}
        >
          {pending ? 'Deleting…' : 'Delete'}
        </button>
      </div>
    </div>
  </div>
);

export default DeleteRunModal;
