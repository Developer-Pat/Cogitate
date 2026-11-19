/**
 * Trash Service — the trash page's client.
 *
 * ONE surface over every shelf. The page never names a shelf: the list comes
 * from `getShelves()`, which is the registry read out, so a new shelf appears on
 * the page the day it is registered rather than the day someone edits the
 * frontend.
 *
 * THE SHAPES ARE THE SERVER'S FIELDS, not a summary of them. `entries[].note` is
 * the shelf's OWN sentence about what an entry is (a trashed agent, residue, a
 * retired backup), and `restorable` is the row-vs-residue answer — both are
 * rendered as given. A page that re-derived either would be a second opinion
 * about a distinction only the shelf can make.
 *
 * MUTATIONS DO NOT RETRY (`retries: 0`). A restore and a purge both name the
 * entry they act on, and a retry would re-send a name that has already moved —
 * turning a success into a 404 the person cannot explain.
 */

import { apiClient } from '../apiClient';
import type { ApiResponse } from '@/types';

/** One shelf, as the tabs read it. `count` is read at this moment, never cached. */
export interface TrashShelf {
  key: string;
  label: string;
  count: number;
  /** True when this shelf has a way back at all (the agents and runs shelves do). */
  restorable: boolean;
  /** Where the shelf lives, relative to the installation — `trash/agents`. */
  directory: string;
}

/** One thing on a shelf. */
export interface TrashEntry {
  name: string;
  is_dir: boolean;
  size_bytes: number;
  /** When it was retired — the entry's own mtime, an observation, not a property. */
  retired_at: number;
  /** What is inside, for a directory; empty for a loose file. */
  files: string[];
  /** True only when a RECORD exists to put this entry back to. */
  restorable: boolean;
  /** Why it is not restorable, or what the entry is — the shelf's own words. */
  note: string;
}

export interface TrashListing {
  key: string;
  label: string;
  restorable: boolean;
  directory: string;
  count: number;
  entries: TrashEntry[];
}

/** A permanent removal of one entry. */
export interface PurgedEntry {
  purged: boolean;
  shelf: string;
  name: string;
}

/** What emptying a shelf did. */
export interface EmptiedShelf {
  emptied: boolean;
  /** The shelf key the server actually emptied. */
  domain: string;
  /** How many entries went — a count, not a claim. */
  deleted: number;
}

/**
 * What a restore answered.
 *
 * The SHELF owns the report's shape: an agent comes back with its id and
 * workspace key, a run with where it landed (and `renamed` when its name had
 * been taken since). The page shows the sentence the shelf would want read and
 * keeps the rest unexamined rather than inventing a common subset.
 */
export type RestoredEntry = { restored: boolean } & Record<string, unknown>;

export interface ITrashService {
  /** Every shelf with its count — the tabs, rendered from the registry. */
  getShelves(): Promise<ApiResponse<{ shelves: TrashShelf[] }>>;
  /** One shelf read out: what is on it and the phrase that empties it. */
  getShelf(key: string): Promise<ApiResponse<TrashListing>>;
  /** Put one entry back where it came from — the way off the shelf. */
  restore(key: string, name: string): Promise<ApiResponse<RestoredEntry>>;
  /** Remove ONE entry **permanently**. */
  purge(key: string, name: string): Promise<ApiResponse<PurgedEntry>>;
  /** Empty ONE shelf — every entry on it, permanently. */
  empty(key: string): Promise<ApiResponse<EmptiedShelf>>;
}

class TrashService implements ITrashService {
  // The full base path — the client does NOT auto-prefix (a bare '/trash' 404s
  // silently through the vite proxy and reads as an empty page).
  private readonly basePath = '/api/v1/trash';

  async getShelves(): Promise<ApiResponse<{ shelves: TrashShelf[] }>> {
    return await apiClient.get<{ shelves: TrashShelf[] }>(this.basePath);
  }

  async getShelf(key: string): Promise<ApiResponse<TrashListing>> {
    return await apiClient.get<TrashListing>(`${this.basePath}/${encodeURIComponent(key)}`);
  }

  /** Restore one entry. No retries: the entry is named, and it has already moved. */
  async restore(key: string, name: string): Promise<ApiResponse<RestoredEntry>> {
    return await apiClient.post<RestoredEntry>(
      `${this.basePath}/${encodeURIComponent(key)}/restore/${encodeURIComponent(name)}`,
      undefined,
      { retries: 0 },
    );
  }

  /**
   * Purge one entry — **PERMANENTLY**, and the caller says so.
   *
   * `confirm: true` is the server's intent flag: not a gate (any caller can send
   * it) but the difference between a request that decided and one that merely
   * arrived — a lost body or a defaulted script now FAILS instead of deleting.
   * The 404 the server answers when the entry is already gone is shown as it
   * arrives; it is not smoothed into a success. No retries: a second POST would
   * report "already gone" about the entry the first one removed.
   */
  async purge(key: string, name: string): Promise<ApiResponse<PurgedEntry>> {
    return await apiClient.post<PurgedEntry>(
      `${this.basePath}/${encodeURIComponent(key)}/purge/${encodeURIComponent(name)}`,
      { confirm: true },
      { retries: 0 },
    );
  }

  /**
   * Empty a shelf — **PERMANENTLY**, every entry on it, and the caller says so.
   *
   * No phrase: the confirmation is the dialog the person just answered, and a
   * sentence the server holds while the client retypes it is a speed bump rather
   * than a gate. The `confirm` flag is the cheap structural stop that remains —
   * see `purge` above for what it is and is not. No retries: a second POST would
   * empty a shelf that is already empty and report its zero as a failure.
   */
  async empty(key: string): Promise<ApiResponse<EmptiedShelf>> {
    return await apiClient.post<EmptiedShelf>(
      `${this.basePath}/${encodeURIComponent(key)}/empty`,
      { confirm: true },
      { retries: 0 },
    );
  }
}

export const trashService: ITrashService = new TrashService();

export default trashService;
