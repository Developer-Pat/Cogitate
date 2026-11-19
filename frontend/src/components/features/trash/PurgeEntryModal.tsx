/**
 * PurgeEntryModal — deleting ONE entry forever, and its confirm.
 *
 * THE IRREVERSIBLE ACT, ONE THING WIDE. Everywhere else in this app a delete is a
 * MOVE (a run goes to the trash, an agent's workspace goes to the trash); this is
 * the control that takes an entry off the trash for good, and nothing in the app
 * can put it back afterwards.
 *
 * BUTTONS, NOT TYPING. The dialog's job is to say what is about to be destroyed —
 * the entry by name, the directory it comes off, what it holds, and that nothing
 * can restore it — and then to offer the two things a person can do about it.
 * Asking someone to retype a name they can see on the row behind the dialog adds
 * no information to the decision: it is a speed bump, and on this surface the
 * shelf's phrase would be the WRONG sentence to demand for one file (`empty the
 * databases trash` to remove a single backup). The typed phrase survives where it
 * is checked by the SERVER, which is a gate rather than a gesture — see the
 * empty-shelf confirm.
 *
 * THE SHELF'S OWN SENTENCE IS SHOWN, not reworded: `entry.note` says what this is
 * (a trashed agent, residue, a retired backup), and on a shelf with a way back the
 * dialog points at Restore instead of presenting the destruction as the only
 * option.
 */

import React from 'react';
import TrashModal from './TrashModal';
import type { TrashEntry } from '@/services/domain/TrashService';

interface PurgeEntryModalProps {
  entry: TrashEntry;
  /** The shelf's name, as its tab reads — the dialog says where the entry lives. */
  shelfLabel: string;
  /** The shelf's own directory, e.g. `trash/agents`. */
  directory: string;
  /** Whether this shelf has a way back, so the copy can point at Restore or not. */
  shelfRestorable: boolean;
  pending: boolean;
  /** A refusal from the server, verbatim (it is the guard's own sentence). */
  error: string | null;
  onClose: () => void;
  onConfirm: () => void;
}

export const PurgeEntryModal: React.FC<PurgeEntryModalProps> = ({
  entry,
  shelfLabel,
  directory,
  shelfRestorable,
  pending,
  error,
  onClose,
  onConfirm,
}) => (
  <TrashModal onClose={onClose} label={`Delete ${entry.name} permanently`}>
    <h3 className="text-lg font-semibold mb-2 text-error">
      Delete <span className="font-mono">{entry.name}</span> forever?
    </h3>

    <p className="text-sm mb-3">
      This is the IRREVERSIBLE delete, and it takes the entry off the {shelfLabel}{' '}
      shelf: it is removed from <span className="font-mono">{directory}/</span>
      {entry.is_dir ? ' — everything it holds with it.' : ' — the file itself.'}{' '}
      <span className="font-semibold">Nothing can restore it.</span>
    </p>

    <p className="text-sm mb-4 text-base-content/70">{entry.note}</p>

    {shelfRestorable && (
      <p className="text-sm mb-4">
        Restoring is still possible instead: close this and use Restore on the
        entries you want to keep.
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
        aria-label={`Keep ${entry.name}`}
        title="Close without deleting anything"
      >
        Cancel
      </button>
      <span
        className="tooltip tooltip-left"
        data-tip={`Remove ${entry.name} from ${directory}/ for good — this cannot be undone`}
      >
        <button
          className="btn btn-sm btn-error"
          onClick={onConfirm}
          disabled={pending}
          aria-label={`Permanently delete ${entry.name}`}
        >
          {pending ? 'Deleting…' : 'Delete forever'}
        </button>
      </span>
    </div>
  </TrashModal>
);

export default PurgeEntryModal;
