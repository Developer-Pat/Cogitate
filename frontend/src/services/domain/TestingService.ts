/**
 * Testing Service — the user-testing page's client.
 *
 * THE USER-TESTING PAGE. It reads the catalog, the runs, and the run lock, and
 * it can FOLLOW a run in progress — but it does not START one: spawning and
 * cancel are Phase C1, and a method that looked like it ran tests but did not
 * would be the same lie the old page told.
 *
 * The predecessor at /testing-dashboard FABRICATED its results. Every value this
 * service returns comes from a real endpoint, and every endpoint reads real
 * files — including "a run is in progress", which is the runner's own lock file
 * rather than a timer this page made up.
 */

import { apiClient, API_BASE_URL } from '../apiClient';
import type { ApiResponse } from '@/types';

/** The time classes. Driven by DEPENDENCIES, never by a stopwatch reading. */
export type TimeClass = 'short' | 'medium' | 'variable';

/** Which tab an entry belongs on. `selftest` is the page's own exercise —
 *  deliberately red, run by name from its own tab, never in a group. */
export type TestTab = 'runnable' | 'conditional' | 'quarantine' | 'selftest';

export interface CatalogEntry {
  path: string;
  /** The path a RUN takes, as the runner wants it (`tests/unit/foo.py`) — sent
   *  back verbatim when this file is run, never assembled in the page. */
  run_path: string;
  filename: string;
  group: string;
  cluster: string;
  /** The module docstring's first line — derived, never hand-written. */
  description: string;
  test_count: number;
  time_class: TimeClass;
  tab: TestTab;
  /** Why it might not run, e.g. "needs a live LLM service". Null when runnable. */
  condition: string | null;
  /** A self-test file's own declared PASS CONDITION — read from the fixture
   *  itself, so a deliberately red tab cannot read as a broken app. "" for
   *  every file in the suite. */
  expectation: string;
  markers: string[];
}

export interface CatalogCluster {
  key: string;
  label: string;
  files: number;
  tests: number;
  time_class: TimeClass;
}

export interface TestCatalog {
  available: boolean;
  /** Why the catalog is empty, when it is. Null when it is not. */
  reason: string | null;
  totals: { files: number; tests: number; clusters: number };
  clusters: CatalogCluster[];
  tests: CatalogEntry[];
}

export interface RunSummary {
  /** The run's folder name — `<ts>`, and its identity everywhere. */
  name: string;
  timestamp: string;
  group: string;
  parallel: boolean;
  files: number;
  backend: string;
  counts: Record<string, number>;
  duration_s: number | null;
  elapsed: string;
  exit_code: number | null;
  /** True while the run has a `run_start` and no `run_end` yet. */
  running: boolean;
  /** True when the run's own SELECTION was the page's exercise — a deliberately
   *  red run, marked so history cannot read it as the suite failing. */
  self_test: boolean;
  failures: number;
  skips: number;
  parsed: boolean;
  mtime: number;
}

export interface RunDetail extends Omit<RunSummary, 'failures' | 'skips' | 'mtime'> {
  failures: { kind: string; where: string; why: string }[];
  skips: { where: string; reason: string }[];
  note: string | null;
}

/** Who holds the run lock — the runner's own record of a run in progress. */
export interface RunLockInfo {
  id: string;
  pid: number;
  pgid: number;
  started: string;
  /** "page" | "terminal" | "sweep" — WHO started the run, not a guess. */
  origin: string;
}

export interface CurrentRun {
  running: boolean;
  /** True when the lock's process is gone: debris from a crashed run. */
  stale: boolean;
  lock: RunLockInfo | null;
}

/** A test's outcome, in pytest's vocabulary. `error` is a setup/teardown
 *  failure: the test never reached a verdict, and calling that "failed" would
 *  blame the assertion. */
export type TestOutcome = 'passed' | 'failed' | 'error' | 'skipped';

/**
 * One frame of a run's event stream.
 *
 * The frames are the RUNNER's own lines (`events.jsonl`), served verbatim over
 * SSE — this union is the client's reading of them, not a second protocol. Every
 * variant is something the runner or pytest actually wrote.
 *
 * There is deliberately NO catch-all variant: the wire is untrusted but the SHAPE
 * is known, so the unchecked step happens once, at the boundary in
 * `useRunStream`, where a frame whose `t` this build does not know is kept as an
 * `unknown` and the reducer ignores it. A union with a `{t: string}` member would
 * make every `case` below a cast.
 */
export type RunEvent =
  | { t: 'run_start'; id: string; kind: string; group: string; files: number; parallel: boolean; backend: string; pid: number; started: string; selection?: string[] }
  | { t: 'session_start'; rootdir: string }
  | { t: 'collect'; count: number; via: string }
  | { t: 'test'; nodeid: string; outcome: TestOutcome; duration?: number; reason?: string }
  | { t: 'summary'; counts: Record<string, number>; duration_s: number | null }
  | { t: 'run_end'; exit: number; elapsed_s: number }
  | { t: 'stream_end'; message: string }
  | { t: 'error'; message: string };

/** What to run — the same choices the terminal runner takes. */
export interface StartRunRequest {
  group?: string;
  /** The paths to run, as the CATALOG gives them (`run_path`) — never assembled
   *  here: the page sends back what it was handed. */
  files?: string[];
  parallel?: boolean;
  /** The run's name, so this page can watch it immediately. */
  run_id?: string;
}

/** The handle returned by a successful start — read from the runner's own lock. */
export interface StartedRun {
  run_id: string;
  pid: number;
  pgid: number;
  started: string;
  origin: string;
}

/** The answer to a cancel: what died, and whether anything survived. */
export interface CancelResult {
  cancelled: boolean;
  forced?: boolean;
  released_lock?: boolean;
  /** Anything still in the process group AFTER the kill, named rather than
   *  hidden — `[]` is the only good news and it is reported as such. */
  survivors?: number[];
  /** Why it was refused, when it was (a run the page did not start). */
  reason?: string;
  console?: string[];
}

/** The answer to a delete: where the run went. `delete` is a MOVE into the
 *  trash, so the folder can be recovered — the page says where. */
export interface DeletedRun extends RetiredRun {
  deleted: boolean;
}

/** One run that a retire moved — the same shape a single delete answers with. */
export interface RetiredRun {
  name: string;
  /** Relative to the project root, e.g. `trash/test-runs/20260101-000000`. */
  moved_to: string;
  contents: string[];
}

/**
 * What a BATCH retire did, per run.
 *
 * Every name the caller sent is answered for: `retired`, `refused` (a run in
 * progress, with the lock's own sentence) or `missing` (no such run). A batch
 * that reported a bare success would leave a person guessing which of nine went,
 * and one that stopped at the first refusal would be worse.
 */
export interface RetireResult {
  retired: RetiredRun[];
  refused: { name: string; reason: string }[];
  missing: string[];
}

/**
 * What CHANGED since the last green run of the SAME selection (the design's §8).
 *
 * `reason` is the important field: when there is nothing comparable on disk, the
 * answer SAYS SO rather than returning empty lists — "no baseline" and "nothing
 * changed" must not look alike.
 */
export interface RunDiff {
  run: string;
  /** The run's own selection fingerprint — empty for a run that recorded none. */
  fingerprint: string;
  /** The baseline's run name, when a comparable green run exists. */
  baseline: string | null;
  reason: string | null;
  added: string[];
  removed: string[];
  /** REGRESSIONS only — a test both runs ran, failing now and not before. */
  newly_failing: string[];
  fixed: string[];
  baseline_counts: Record<string, number>;
}

/** Where a Save put the copy. `saved_to` is relative inside the project, absolute
 *  outside it — because a person may save anywhere. */
export interface SavedRun {
  saved: boolean;
  name: string;
  saved_to: string;
  files: string[];
}

export interface ITestingService {
  getCatalog(): Promise<ApiResponse<TestCatalog>>;
  getRuns(limit?: number): Promise<ApiResponse<{ available: boolean; count: number; reports: RunSummary[] }>>;
  getRun(name: string): Promise<ApiResponse<RunDetail>>;
  getCurrentRun(): Promise<ApiResponse<CurrentRun>>;
  startRun(body: StartRunRequest): Promise<ApiResponse<StartedRun>>;
  cancelRun(runId: string): Promise<ApiResponse<CancelResult>>;
  deleteRun(runId: string): Promise<ApiResponse<DeletedRun>>;
  /** Retire several runs at once — the same move, answered for one by one. */
  retireRuns(names: string[]): Promise<ApiResponse<RetireResult>>;
  /** What changed since the last green run of the same selection. */
  getDiff(name: string): Promise<ApiResponse<RunDiff>>;
  /** Keep a COPY of a run, where the person says (empty = the server's default). */
  saveRun(name: string, destination?: string): Promise<ApiResponse<SavedRun>>;
  /** The URL an EventSource should open to follow a run's live event stream. */
  runEventsUrl(runId: string, opts?: { tail?: boolean }): string;
}

// LOOKING AT THE TRASH IS NOT THIS SERVICE'S. The shelf, its entries, the way
// back and the permanent removal are `services/domain/TrashService` — one client
// for every shelf, at `/api/v1/trash`. This page retires a run INTO the trash
// and links there to look at it.

class TestingService implements ITestingService {
  // The full base path — the client does NOT auto-prefix (a bare '/testing'
  // 404s silently through the vite proxy and reads as an empty page).
  private readonly basePath = '/api/v1/testing';

  /** The derived catalog: every test, its meaning, its dependencies, its condition. */
  async getCatalog(): Promise<ApiResponse<TestCatalog>> {
    return await apiClient.get<TestCatalog>(`${this.basePath}/catalog`);
  }

  /** The runs on disk, newest first. */
  async getRuns(
    limit = 50,
  ): Promise<ApiResponse<{ available: boolean; count: number; reports: RunSummary[] }>> {
    return await apiClient.get<{ available: boolean; count: number; reports: RunSummary[] }>(
      `${this.basePath}/runs`,
      { params: { limit } },
    );
  }

  /**
   * One run in full — its counts, its failures, and its skips WITH REASONS.
   *
   * The reasons are the point: "12 tests are not running because Ollama is down"
   * is something a person can act on, where a bare count is not.
   */
  async getRun(name: string): Promise<ApiResponse<RunDetail>> {
    return await apiClient.get<RunDetail>(`${this.basePath}/runs/${encodeURIComponent(name)}`);
  }

  /** Is a run in progress, and who started it. The lock's answer, never a guess. */
  async getCurrentRun(): Promise<ApiResponse<CurrentRun>> {
    return await apiClient.get<CurrentRun>(`${this.basePath}/runs/current`);
  }

  /**
   * Start a run — the SAME runner a person starts from a terminal.
   *
   * The caller NAMES the run (`run_id`) so it can watch it immediately rather
   * than polling for whichever folder appears. A refusal (409) arrives as an
   * error whose `message` is the LOCK's own sentence, naming who holds it — the
   * page shows that sentence rather than inventing a reason of its own.
   *
   * THE TIMEOUT IS LONGER THAN THE SERVER'S OWN PATIENCE, and that is not
   * tuning: the spawn waits for the runner to take its lock (up to 20s) before
   * answering, so the client's 10s default would abort a start that SUCCEEDED and
   * leave the page reporting a refusal for a run that is going. No retries either
   * — a start is not idempotent, and a second POST would collide with the lock
   * the first one just took.
   */
  async startRun(body: StartRunRequest): Promise<ApiResponse<StartedRun>> {
    return await apiClient.post<StartedRun>(`${this.basePath}/runs`, body, {
      timeout: 30000,
      retries: 0,
    });
  }

  /**
   * Stop the run — the whole process group, killed and verified.
   *
   * A run this page did not start comes back `cancelled: false` with a reason:
   * a terminal run is watched, not stopped.
   *
   * The kill is TERM, wait, KILL, reap, verify — up to ~16s of real work on the
   * server — so it gets its own long timeout for the same reason the start does:
   * an abort here would report "could not cancel" about a run that has already
   * died, which is the worst answer of the three.
   */
  async cancelRun(runId: string): Promise<ApiResponse<CancelResult>> {
    return await apiClient.post<CancelResult>(
      `${this.basePath}/runs/${encodeURIComponent(runId)}/cancel`,
      undefined,
      { timeout: 30000, retries: 0 },
    );
  }

  /**
   * Retire one run — moved into the trash, so it can be recovered.
   *
   * A run in progress is refused (409) with the lock's sentence: the folder
   * cannot go while something is writing to it.
   */
  async deleteRun(runId: string): Promise<ApiResponse<DeletedRun>> {
    return await apiClient.delete<DeletedRun>(
      `${this.basePath}/runs/${encodeURIComponent(runId)}`,
    );
  }

  /**
   * Retire SEVERAL runs — one move each, and the answer names every one.
   *
   * `refused` carries the lock's own sentence for a run in progress and `missing`
   * holds a name that was never a run; the caller shows all three lists rather
   * than a count, because a batch that says "done" while one of nine was refused
   * is an answer nobody can act on. No retries: a retry would re-send names that
   * have already moved, and "missing" would read as an error.
   */
  async retireRuns(names: string[]): Promise<ApiResponse<RetireResult>> {
    return await apiClient.post<RetireResult>(
      `${this.basePath}/runs/retire`,
      { runs: names },
      { retries: 0 },
    );
  }

  /**
   * What CHANGED since the last green run of the SAME selection.
   *
   * The page shows this rather than inventing a verdict of its own: when nothing
   * comparable is on disk the answer carries a `reason` and empty lists, which is
   * a different thing from "nothing changed".
   */
  async getDiff(name: string): Promise<ApiResponse<RunDiff>> {
    return await apiClient.get<RunDiff>(
      `${this.basePath}/runs/${encodeURIComponent(name)}/diff`,
    );
  }

  /**
   * SAVE a copy of a run, where the person says.
   *
   * An empty `destination` means the server's own default (the locator's), so the
   * common case sends nothing to interpret. The PATIENCE is the start's, not the
   * client's default: a big run's XML is megabytes, and a copy that succeeded must
   * not be reported as failed because the client gave up at ten seconds. No
   * retries — a second save of the same run is refused by name, so a retry would
   * turn a success into an "already saved" error.
   */
  async saveRun(name: string, destination?: string): Promise<ApiResponse<SavedRun>> {
    const trimmed = (destination ?? '').trim();
    return await apiClient.post<SavedRun>(
      `${this.basePath}/runs/${encodeURIComponent(name)}/save`,
      { destination: trimmed === '' ? null : trimmed },
      { timeout: 30000, retries: 0 },
    );
  }

  /** The SSE URL for a run's events. `tail` skips the replay of what already happened. */
  runEventsUrl(runId: string, opts: { tail?: boolean } = {}): string {
    // Same base as every other SSE consumer (`sseClient`, `messagingFeed`) —
    // window.location.origin when no explicit API host is configured.
    const tail = opts.tail ? '?tail=true' : '';
    return `${API_BASE_URL}${this.basePath}/runs/${encodeURIComponent(runId)}/events${tail}`;
  }
}

export const testingService: ITestingService = new TestingService();

export default testingService;
