/**
 * Trash — the ONE surface over every shelf.
 *
 * THE TRASH IS A DOMAIN, not a folder: five shelves (agents, test-runs, reports,
 * dbs, misc) behind one verb set, registered in one map on the server. This page
 * is that map's reader — the TABS ARE RENDERED FROM `GET /trash`, never
 * hand-listed, so a sixth shelf appears here the day it is registered rather than
 * the day someone edits this file.
 *
 * WHAT THE PAGE OWES A PERSON. A delete anywhere in this app is a MOVE, and the
 * standing rule is that what was moved stays VISIBLE: the page says what is on
 * each shelf, how big and how old it is, and — the distinction the whole domain
 * turns on — whether a RECORD exists to put an entry back (a trashed agent, a
 * retired run) or not (residue, a retired backup, a loose file nothing claims).
 * The shelf says that in its own words; the page renders the sentence rather than
 * paraphrasing it.
 *
 * THE TWO VERBS, HONESTLY LABELLED. **Restore** is offered only on a row a record
 * backs — a shelf with no way back is not shown a button that cannot work.
 * **Delete forever** is on every row, and it is the one gate this app cannot walk
 * back: a single entry takes its own NAME typed (the house's hard-delete
 * convention), and emptying a whole shelf takes the phrase the SERVER checks.
 *
 * WHAT IT DOES NOT DO: prune, roll, keep the last N, or empty anything global.
 * Emptying is domain-scoped on purpose — one control over a root that holds
 * database backups would claim more than it does.
 *
 * A tab is a VIEW, so the URL is the shelf (`?shelf=dbs`) and switching writes
 * with `replace`: Back leaves the page rather than walking the tabs visited. An
 * unknown value falls back to the default shelf rather than a dead grid.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PageContainer } from '../components/ui/PageContainer';
import { PageBanner } from '../components/ui/PageBanner';
import { HelpButton } from '../components/help';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { usePageTitle } from '../hooks/usePageTitle';
import { useDomainSync } from '../hooks/useDomainSync';
import { useNotificationStore } from '../stores/notificationStore';
import { TrashShelfTable, shelfShape } from '../components/features/trash/TrashShelfTable';
import { PurgeEntryModal } from '../components/features/trash/PurgeEntryModal';
import { EmptyShelfModal } from '../components/features/trash/EmptyShelfModal';
import {
  trashService,
  type RestoredEntry,
  type TrashEntry,
  type TrashListing,
  type TrashShelf,
} from '../services/domain/TrashService';

/**
 * The shelf a URL is asking for, or the default when it names nothing real.
 *
 * THE DEFAULT IS THE FIRST SHELF WITH SOMETHING ON IT: landing on an empty tab
 * while three shelves are full reads as "the trash is empty", which is the exact
 * misreading this page exists to prevent.
 */
function readShelf(raw: string | null, shelves: TrashShelf[] | null): string | null {
  if (!shelves || shelves.length === 0) return null;
  if (raw && shelves.some((s) => s.key === raw)) return raw;
  return (shelves.find((s) => s.count > 0) ?? shelves[0]).key;
}

/**
 * What a restore did, in the shelf's own terms.
 *
 * The shelves report different shapes (a run says where it landed and whether its
 * name had been taken; an agent says its name and workspace) and the page shows
 * what came back rather than inventing a common subset — a restore that was
 * renamed must not read as one that landed under the name asked for.
 */
function restoredSentence(name: string, answer: RestoredEntry): string {
  const landed = typeof answer.restored_to === 'string' ? answer.restored_to : '';
  if (answer.renamed === true) {
    return `Restored ${name} as ${landed.split('/').pop() || landed} — its name had been taken`;
  }
  return landed ? `Restored ${name} to ${landed}` : `Restored ${name}`;
}

export const Trash: React.FC = () => {
  usePageTitle('Trash');

  const [searchParams, setSearchParams] = useSearchParams();
  const [shelves, setShelves] = useState<TrashShelf[] | null>(null);
  const [listing, setListing] = useState<TrashListing | null>(null);
  const [loadingShelves, setLoadingShelves] = useState(true);
  const [loadingShelf, setLoadingShelf] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** The entry whose Restore is in flight — that row says so, the others do not. */
  const [busyName, setBusyName] = useState<string | null>(null);
  const [purgeTarget, setPurgeTarget] = useState<TrashEntry | null>(null);
  const [purgePending, setPurgePending] = useState(false);
  const [purgeError, setPurgeError] = useState<string | null>(null);
  const [emptyOpen, setEmptyOpen] = useState(false);
  const [emptyPending, setEmptyPending] = useState(false);
  const [emptyError, setEmptyError] = useState<string | null>(null);

  const { addSuccess, addError } = useNotificationStore();

  const active = readShelf(searchParams.get('shelf'), shelves);
  const shelf = shelves?.find((s) => s.key === active) ?? null;
  // Only the listing for the shelf in view is rendered: switching tabs must not
  // show the previous shelf's entries under the new tab's name while it loads.
  const showing = listing && listing.key === active ? listing : null;
  const shape = shelfShape(showing);

  const loadShelves = useCallback(async () => {
    const res = await trashService.getShelves();
    setLoadingShelves(false);
    if (res.error || !res.data) {
      setError(
        `Could not read the shelves: ${res.error?.code ?? 'no answer'} — ${res.error?.message ?? ''}`,
      );
      return;
    }
    setShelves(res.data.shelves);
  }, []);

  const loadShelf = useCallback(async (key: string) => {
    setLoadingShelf(true);
    const res = await trashService.getShelf(key);
    setLoadingShelf(false);
    if (res.error || !res.data) {
      setError(
        `Could not read the ${key} shelf: ${res.error?.code ?? 'no answer'} — ${res.error?.message ?? ''}`,
      );
      return;
    }
    setListing(res.data);
  }, []);

  useEffect(() => {
    void loadShelves();
  }, [loadShelves]);

  useEffect(() => {
    if (!active) return;
    void loadShelf(active);
  }, [active, loadShelf]);

  // A STALE LINK IS CORRECTED IN THE URL, not just in the view: `?shelf=retired`
  // falls back to a real shelf, and leaving the URL claiming a surface that is
  // not on screen would make a reload or a copied link lie about where it goes.
  // A bare `/trash` is left alone — the default is written only when the URL has
  // already said something.
  const askedFor = searchParams.get('shelf');
  useEffect(() => {
    if (!active || askedFor === null || askedFor === active) return;
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set('shelf', active);
        return next;
      },
      { replace: true },
    );
  }, [active, askedFor, setSearchParams]);

  /**
   * Re-read everything a mutation could have moved: the counts on the tabs AND
   * the shelf in view. A restore or a purge changes both, and a page that
   * refreshed only one of them would show a badge that disagrees with its rows.
   */
  const reload = useCallback(async () => {
    await loadShelves();
    if (active) await loadShelf(active);
  }, [active, loadShelves, loadShelf]);

  // THE CROSS-WINDOW SYNC. A purge or an empty in ANOTHER tab must not leave this
  // one rendering a row that is gone, so the page hears the trash's own
  // announcements (`trash:<shelf>:<event>`) and re-reads. The ref keeps the
  // subscription stable while `reload` keeps its latest closure — the hook
  // re-subscribes when its callback identity changes, and switching shelves
  // changes `reload` on every click.
  const reloadRef = useRef(reload);
  reloadRef.current = reload;
  const onTrashEvent = useCallback(() => {
    void reloadRef.current();
  }, []);
  useDomainSync('trash', onTrashEvent);

  const setActive = (key: string) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set('shelf', key);
        return next;
      },
      { replace: true },
    );
  };

  // ── the two verbs ─────────────────────────────────────────────────────────

  const restore = async (entry: TrashEntry) => {
    if (!active) return;
    setBusyName(entry.name);
    const res = await trashService.restore(active, entry.name);
    setBusyName(null);
    if (res.error || !res.data) {
      addError(
        'Trash',
        `Could not restore ${entry.name}: ${res.error?.code ?? 'no answer'} — ${res.error?.message ?? ''}`,
      );
      return;
    }
    addSuccess('Trash', restoredSentence(entry.name, res.data));
    await reload();
  };

  const confirmPurge = async () => {
    if (!purgeTarget || !active) return;
    setPurgePending(true);
    setPurgeError(null);
    const res = await trashService.purge(active, purgeTarget.name);
    setPurgePending(false);
    if (res.error || !res.data) {
      // The server's own sentence — a 404 for an entry that is already gone, or
      // the shelf's refusal. The dialog stays open rather than vanishing on a
      // refusal the person has not read.
      setPurgeError(res.error ? `${res.error.code} — ${res.error.message}` : 'No answer');
      await reload();
      return;
    }
    const name = purgeTarget.name;
    setPurgeTarget(null);
    addSuccess('Trash', `Deleted ${name} — removed from ${shelf?.directory ?? 'the shelf'}/`);
    await reload();
  };

  const confirmEmpty = async () => {
    if (!showing) return;
    setEmptyPending(true);
    setEmptyError(null);
    const res = await trashService.empty(showing.key);
    setEmptyPending(false);
    if (res.error || !res.data) {
      // The refusal is the guard's own sentence — shown, not reworded.
      setEmptyError(res.error ? `${res.error.code} — ${res.error.message}` : 'No answer');
      await reload();
      return;
    }
    const answer = res.data;
    setEmptyOpen(false);
    addSuccess(
      'Trash',
      `${showing.label} shelf emptied — ${answer.deleted} permanently deleted`,
    );
    await reload();
  };

  return (
    <ErrorBoundary>
      <PageContainer>
        <PageBanner
          title="Trash"
          tooltip="Everything that was moved out of the way rather than erased — five shelves, and the way back off each"
          action={<HelpButton context="trash" />}
        />

        {/* ORIENTATION — what this page is for, in the page's own words. */}
        <p
          className="text-sm text-base-content/70 mb-4"
          style={{ maxWidth: 'var(--content-measure)' }}
        >
          A delete in this app is a move. A run you retire, a workspace you delete
          and the files nothing else claims all land here rather than being erased.
          Each shelf holds one kind of thing and is emptied on its own. Restore
          puts an entry back where it came from, wherever a record of that exists;
          Delete forever is the one action nothing can undo.
        </p>

        {error && (
          <div className="alert alert-error mb-4 text-sm py-2" role="alert">
            <span>{error}</span>
          </div>
        )}

        {loadingShelves && !shelves ? (
          <div className="flex justify-center py-12">
            <span className="loading loading-spinner loading-lg" />
          </div>
        ) : (
          <>
            {/* THE TABS COME FROM THE SERVER — the registry, read out. */}
            <div role="tablist" className="tabs tabs-boxed mb-4 w-fit flex-wrap">
              {(shelves ?? []).map((s) => (
                <button
                  key={s.key}
                  role="tab"
                  aria-selected={active === s.key}
                  className={`tab tooltip tooltip-bottom ${active === s.key ? 'tab-active' : ''}`}
                  onClick={() => setActive(s.key)}
                  data-tip={
                    `${s.label} — ${s.count} in ${s.directory}/. ` +
                    (s.restorable
                      ? 'Entries a record names can be put back.'
                      : 'Nothing here can be restored.')
                  }
                >
                  {s.label}
                  {/* The count sits ON the tab rather than in a headline above the
                      grid: it is the shelf's state, and it is read from the server
                      at this moment, never kept in step by hand. */}
                  <span className="ml-2 badge badge-sm">{s.count}</span>
                </button>
              ))}
            </div>

            {shelf && (
              <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)]">
                <div className="card-body gap-[var(--card-gap)]">
                  <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div>
                      <h2 className="card-title text-base">{shelf.label}</h2>
                      <p className="text-sm text-base-content/60">
                        {shelf.count} {shelf.count === 1 ? 'entry' : 'entries'} in{' '}
                        <span className="font-mono">{shelf.directory}/</span>
                      </p>
                    </div>
                    <span
                      className="tooltip tooltip-left"
                      data-tip={
                        shelf.count === 0
                          ? 'Nothing on this shelf to empty'
                          : `Permanently delete every entry on the ${shelf.label} shelf — this cannot be undone`
                      }
                    >
                      <button
                        className="btn btn-sm btn-error btn-outline"
                        onClick={() => {
                          setEmptyError(null);
                          setEmptyOpen(true);
                        }}
                        disabled={shelf.count === 0 || !showing}
                        aria-label={`Empty the ${shelf.label} shelf`}
                      >
                        Empty this shelf…
                      </button>
                    </span>
                  </div>

                  {/* THE SHELF'S OWN SENTENCE, once — shown here when every entry
                      says the same thing, and left to the rows when they differ. */}
                  {shape.sharedNote && (
                    <p className="text-sm text-base-content/60">{shape.sharedNote}</p>
                  )}

                  <TrashShelfTable
                    listing={showing}
                    isLoading={loadingShelf || showing === null}
                    busyName={busyName}
                    onRestore={(entry) => void restore(entry)}
                    onPurge={(entry) => {
                      setPurgeError(null);
                      setPurgeTarget(entry);
                    }}
                  />

                  {showing && showing.count > 0 && (
                    <p className="text-xs text-base-content/50">
                      {showing.restorable
                        ? 'Restoring moves an entry back where it came from and changes nothing else. '
                        : 'No entry on this shelf can be restored. '}
                      Deleting forever removes it from{' '}
                      <span className="font-mono">{showing.directory}/</span> and
                      nothing in this app can put it back.
                    </p>
                  )}
                </div>
              </div>
            )}
          </>
        )}

        {purgeTarget && shelf && showing && (
          <PurgeEntryModal
            entry={purgeTarget}
            shelfLabel={shelf.label}
            directory={showing.directory}
            shelfRestorable={showing.restorable}
            pending={purgePending}
            error={purgeError}
            onClose={() => {
              setPurgeTarget(null);
              setPurgeError(null);
            }}
            onConfirm={() => void confirmPurge()}
          />
        )}

        {emptyOpen && showing && (
          <EmptyShelfModal
            shelfLabel={showing.label}
            directory={showing.directory}
            count={showing.count}
            restorable={showing.restorable}
            pending={emptyPending}
            error={emptyError}
            onClose={() => {
              setEmptyOpen(false);
              setEmptyError(null);
            }}
            onConfirm={() => void confirmEmpty()}
          />
        )}
      </PageContainer>
    </ErrorBoundary>
  );
};

export default Trash;
