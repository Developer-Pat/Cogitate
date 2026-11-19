/**
 * SaveRunModal — keeping a copy of a run, where the person says.
 *
 * THE DESIGN'S §8 SAVE, and it is deliberately explicit: the person SEES what is
 * about to happen and where it goes. Two facts do the work:
 *
 *   - it is a COPY — the run stays in Runs, so saving is never a second way to
 *     lose one;
 *   - the destination is a path on THIS machine, because all of the file I/O is
 *     the server's. The page never writes a file itself.
 *
 * The destination is remembered (one choice, made once — the design says so), and
 * an EMPTY destination is meaningful: the server's own default. The dialog says
 * that in words rather than showing a blank field the person has to interpret.
 *
 * Markup: the dev-note template VERBATIM
 * (`wiki/dev-notes/frontend/modal-dialogs.md`) — overlay + width var + `p-6`,
 * never `modal-box`, never `max-w-*`.
 */

import React from 'react';
import type { RunSummary, SavedRun } from '@/services/domain/TestingService';

interface SaveRunModalProps {
  run: RunSummary;
  /** The remembered destination. Empty string = the server's default. */
  destination: string;
  pending: boolean;
  /** The refusal, verbatim — the lock's sentence, or "already saved at …". */
  error: string | null;
  /** Where it went, once it has. */
  saved: SavedRun | null;
  onDestination: (value: string) => void;
  onClose: () => void;
  onConfirm: () => void;
}

export const SaveRunModal: React.FC<SaveRunModalProps> = ({
  run,
  destination,
  pending,
  error,
  saved,
  onDestination,
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
      <h3 className="text-lg font-semibold mb-2">Save this run?</h3>

      <p className="text-sm text-base-content/70 mb-3">
        <span className="font-mono">{run.name}</span> — its report.md, report.xml and
        events.jsonl are copied together.
      </p>

      {saved ? (
        <>
          <p className="text-sm mb-2">
            Saved to <span className="font-mono font-semibold">{saved.saved_to}</span>
          </p>
          <p className="text-xs text-base-content/60 mb-4">
            The run is still in Runs — this is a copy, and the page keeps nothing here.
          </p>
          <div className="flex justify-end">
            <button className="btn btn-sm btn-primary" onClick={onClose}>
              Close
            </button>
          </div>
        </>
      ) : (
        <>
          <label className="block text-sm mb-1" htmlFor="save-destination">
            Where to put it
          </label>
          <input
            id="save-destination"
            type="text"
            className="input input-bordered input-sm w-full mb-2 font-mono"
            value={destination}
            onChange={(e) => onDestination(e.target.value)}
            placeholder="the page's default folder"
            aria-label="Destination folder for the saved run"
          />
          <p className="text-xs text-base-content/60 mb-4">
            Leave it empty to use the page's own default. A folder is created for this
            run inside it, and an existing copy of this run is never overwritten.
          </p>

          {error && (
            <div className="alert alert-error text-sm py-2 mb-4" role="alert">
              <span>{error}</span>
            </div>
          )}

          <div className="flex justify-end gap-2">
            <button className="btn btn-sm btn-ghost" onClick={onClose} disabled={pending}>
              Cancel
            </button>
            <button
              className="btn btn-sm btn-primary"
              onClick={onConfirm}
              disabled={pending}
              aria-label={`Save run ${run.name}`}
            >
              {pending ? 'Saving…' : 'Save'}
            </button>
          </div>
        </>
      )}
    </div>
  </div>
);

export default SaveRunModal;
