/**
 * EmptyShelfModal — emptying ONE shelf, and its confirm.
 *
 * The bulk form of the irreversible act: the per-entry Purge is the primary way
 * to remove something, and this is how a person says "I am done with all of
 * these". The dialog's job is to say what goes — the shelf, its directory, what
 * each entry holds — and then to offer the two things a person can do about it.
 *
 * BUTTONS, NOT TYPING. Emptying a shelf used to demand a phrase the SERVER
 * checked ("empty the databases trash"). The phrase is gone from the product: it
 * was the wrong sentence for the neighbouring case (removing ONE entry) and at
 * best a speed bump for this one, because a sentence read off the dialog in
 * front of you and typed back adds nothing to a decision already made. What
 * guards the act now is the act itself — an irreversible removal asked for
 * deliberately, in a dialog that names what it takes.
 *
 * A SHELF THAT CANNOT RESTORE SAYS SO, because "you can put them back
 * individually" is only true where a record exists — and on the reports, dbs and
 * misc shelves it does not.
 */

import React from 'react';
import TrashModal from './TrashModal';

interface EmptyShelfModalProps {
  /** The shelf's name, as its tab reads. */
  shelfLabel: string;
  /** Where the shelf lives, e.g. `trash/agents`. */
  directory: string;
  /** How many entries go, so the number is on screen before the act. */
  count: number;
  /** Whether the shelf's entries can be put back one at a time instead. */
  restorable: boolean;
  pending: boolean;
  /** A refusal from the server, verbatim (it is the shelf's own sentence). */
  error: string | null;
  onClose: () => void;
  onConfirm: () => void;
}

export const EmptyShelfModal: React.FC<EmptyShelfModalProps> = ({
  shelfLabel,
  directory,
  count,
  restorable,
  pending,
  error,
  onClose,
  onConfirm,
}) => (
  <TrashModal onClose={onClose} label={`Empty the ${shelfLabel} shelf`}>
    <h3 className="text-lg font-semibold mb-2 text-error">
      Permanently delete {count} {count === 1 ? 'entry' : 'entries'}?
    </h3>

    <p className="text-sm mb-3">
      This is the IRREVERSIBLE delete. Everything on the {shelfLabel} shelf is
      removed from <span className="font-mono">{directory}/</span>.{' '}
      <span className="font-semibold">Nothing can restore them.</span>
    </p>

    {restorable ? (
      <p className="text-sm mb-4">
        Restoring one at a time is still possible instead: close this and use
        Restore on the entries you want to keep.
      </p>
    ) : (
      <p className="text-sm mb-4">
        Nothing on this shelf can be restored — it keeps no record of where its
        entries came from. Removing them here is the only way off it.
      </p>
    )}

    {error && (
      <div className="alert alert-error text-sm py-2 mb-4" role="alert">
        <span>{error}</span>
      </div>
    )}

    <div className="flex justify-end gap-2">
      <button
        className="btn btn-sm btn-ghost"
        onClick={onClose}
        disabled={pending}
        aria-label="Close without emptying the shelf"
        title="Close without deleting anything"
      >
        Cancel
      </button>
      <span
        className="tooltip tooltip-left"
        data-tip={`Delete all ${count} on the ${shelfLabel} shelf — this cannot be undone`}
      >
        <button
          className="btn btn-sm btn-error"
          onClick={onConfirm}
          disabled={pending}
          aria-label={`Permanently delete everything on the ${shelfLabel} shelf`}
        >
          {pending ? 'Deleting…' : 'Delete permanently'}
        </button>
      </span>
    </div>
  </TrashModal>
);

export default EmptyShelfModal;
