/**
 * `shelfShape` — what is true of the WHOLE shelf, and the one place that measures it.
 *
 * IT LIVES IN ITS OWN MODULE (2026-11-25). It was exported from `TrashShelfTable.tsx`,
 * which also exports the component, and `react-refresh` is right to object: a file that
 * exports both a component and a plain function cannot fast-refresh, because the module
 * has more than one thing to re-execute. The rule's fix is the structural one — one file
 * that shares constants or functions, another that renders — so the page's blurb and the
 * table both import the measurement from here.
 *
 * `sharedNote` is the shelf's own sentence when EVERY entry says the same thing, and null
 * when they differ — the caller shows it once in the blurb instead of a column of one
 * repeated string. `mixedStates` is the row-backed distinction showing up within a shelf
 * (the agents shelf: a trashed agent beside residue), which the blurb has to mention
 * because the rows no longer say it uniformly.
 */

import type { TrashListing } from '@/services/domain/TrashService';

export function shelfShape(listing: TrashListing | null): {
  sharedNote: string | null;
  mixedStates: boolean;
} {
  const entries = listing?.entries ?? [];
  const notes = new Set(entries.map((e) => e.note).filter(Boolean));
  return {
    sharedNote: entries.length > 0 && notes.size === 1 ? entries[0].note : null,
    mixedStates: new Set(entries.map((e) => e.restorable)).size > 1,
  };
}
