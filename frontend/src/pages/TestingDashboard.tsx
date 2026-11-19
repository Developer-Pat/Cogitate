/**
 * Testing — the user-testing page.
 *
 * THE USER-TESTING PAGE. **This replaced a SIMULATION.**
 *
 * The predecessor fetched nothing. `TestRunner.generateTestResults()` invented
 * test names, and its result was literally a coin flip
 * (`Math.random() > 0.1 ? 'passed' : 'failed'`) animated behind a progress bar.
 * Someone could run "tests" here, watch them pass, and believe the suite
 * healthy while nothing executed. A pass by accident is a lie, and a page that
 * shows one is worse than no page.
 *
 * So every number on this page now comes from a file. The catalog is DERIVED
 * from the test tree (descriptions from the module docstrings, clusters from the
 * paths, time classes from the dependencies), the reports are the runner's
 * own output read back from disk, and a RUN is the same `scripts/testing/
 * run_tests.py` a person starts from a terminal — started under the run lock,
 * followed through its own event file, and stopped with a group kill.
 *
 * SCOPE — USER SPACE. The sweeps and the full application suite are developer /
 * system-agent space. **This page owns nothing**: no report repository, no
 * rolling, no retention, no system-health monitoring. It is a workbench:
 * pick → run → look → save-or-send.
 *
 * WHAT IT STILL DOES NOT DO, said on the control rather than done quietly:
 * save the report and send it to Exa (Phase D) — the page's own exports. The
 * catalog check belongs in the sweep, not here.
 *
 * THE LIVE STATE LIVES HERE, not in the tab: a run's feed must survive a nav
 * within the page (switching to Runnable to read a row must not tear down the
 * stream of a run that takes half an hour), so the stream is opened once, by the
 * page, and the Run tab only renders it.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageContainer } from '../components/ui/PageContainer';
import { PageBanner } from '../components/ui/PageBanner';
import { HelpButton } from '../components/help';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { usePageTitle } from '../hooks/usePageTitle';
import { useRunStream } from '../hooks/useRunStream';
import { useNotificationStore } from '../stores/notificationStore';
import { CatalogTable } from '../components/features/testing/CatalogTable';
import { ReportsTable } from '../components/features/testing/ReportsTable';
import { TestDetailsModal } from '../components/features/testing/TestDetailsModal';
import { LiveRunPanel } from '../components/features/testing/LiveRunPanel';
import { DeleteRunModal } from '../components/features/testing/DeleteRunModal';
import { RetireRunsModal } from '../components/features/testing/RetireRunsModal';
import { SaveRunModal } from '../components/features/testing/SaveRunModal';
import { useTestingSavePreference } from '../stores/testingSavePreference';
import {
  testingService,
  type CatalogEntry,
  type CurrentRun,
  type RetireResult,
  type RunLockInfo,
  type RunSummary,
  type SavedRun,
  type TestTab,
} from '../services/domain/TestingService';
import { doneCount } from '../utils/runFeed';

type Tab = TestTab | 'reports' | 'live';

/**
 * The tabs, in dependency order — least dependent first.
 *
 * **The order is also the diagnosis**: the runnable ones come first, the
 * conditional ones next (with the condition shown), the parked ones last. Same
 * doctrine as the test tiers, one level up. Runs and Live sit at the end:
 * history beside the thing that is happening now.
 */
const TABS: { key: Tab; label: string; tooltip: string }[] = [
  {
    key: 'runnable',
    label: 'Runnable',
    tooltip: 'Tests with no external dependency — pure logic, the database, the filesystem, the app in-process',
  },
  {
    key: 'conditional',
    label: 'Conditional',
    tooltip: 'Tests that need a service, provider or LLM that may not be configured — they say what they need',
  },
  {
    key: 'quarantine',
    label: 'Quarantine',
    tooltip: 'Parked tests, kept visible rather than deleted',
  },
  {
    key: 'selftest',
    label: 'Self-test',
    tooltip: 'The page\'s own check — deliberately failing tests, so you can see a failure, a skip and a cancel working',
  },
  {
    key: 'reports',
    label: 'Runs',
    tooltip: 'Past test runs and what they actually said, including why anything was skipped',
  },
  {
    key: 'live',
    label: 'Live',
    tooltip: 'The run in progress: what it has done, what it found, and what it is saying right now',
  },
];

/** The derived views. The NAMED, curated profiles come later — these are computed. */
const PROFILE_FAST = 'fast';
const PROFILES: { key: string; label: string; help: string }[] = [
  { key: PROFILE_FAST, label: 'Fast only', help: 'no I/O — the quickest signal' },
  { key: 'all', label: 'Everything', help: 'every test in this tab' },
  { key: 'medium', label: 'Needs the installation', help: 'database, filesystem or the app itself' },
];

/** How often the page asks the lock whether a run is going. It is one tiny read,
 *  and it is what lets the page notice a run started in a terminal. */
const CURRENT_POLL_MS = 10_000;

/** The name a page-started run gets. The runner accepts letters, digits, dot,
 *  dash and underscore, and the page watches this id rather than guessing which
 *  folder appeared.
 *
 *  THE SECONDS ARE NOT ENOUGH ON THEIR OWN. Two clicks in the same second — a
 *  double-click, or two windows — produced the SAME id, and the runner (rightly)
 *  refuses a name that is taken: the second attempt died at import and the page
 *  reported a 500 with the runner's console instead of "a run is already going".
 *  The suffix makes every id unique, so a duplicate start is refused by the LOCK
 *  for the honest reason. The click guard in `startRun` is the other half: the
 *  second click of a double-click should not send a request at all. */
function newRunId(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  const stamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`
    + `-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
  const unique = Math.random().toString(16).slice(2, 6);
  return `page-${stamp}-${unique}`;
}

export const TestingDashboard: React.FC = () => {
  usePageTitle('Testing');

  const [tab, setTab] = useState<Tab>('runnable');
  // THE FIRST CLICK IS NOT A TWO-MINUTE WAIT: the fast tier is the default, so
  // Run runs the quickest signal unless the person asks for more.
  const [profile, setProfile] = useState<string>(PROFILE_FAST);
  const [entries, setEntries] = useState<CatalogEntry[]>([]);
  const [totals, setTotals] = useState<{ files: number; tests: number; clusters: number } | null>(null);
  const [catalogReason, setCatalogReason] = useState<string | null>(null);
  const [reports, setReports] = useState<RunSummary[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [viewing, setViewing] = useState<CatalogEntry | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ── the run in progress: the LOCK's answer, never this page's guess ──
  const [current, setCurrent] = useState<CurrentRun | null>(null);
  const [liveRunId, setLiveRunId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  /** The refusal, verbatim — the lock's own sentence when it is a 409. */
  const [runRefused, setRunRefused] = useState<string | null>(null);
  /** A start whose ANSWER got lost, when the lock proves the run is going anyway. */
  const [runNotice, setRunNotice] = useState<string | null>(null);
  const [cancelPending, setCancelPending] = useState(false);
  /** What the cancel had to say, and how loudly. A run that had already ended is
   *  NOT a warning: Cancel was simply clicked after the end. */
  const [cancelNote, setCancelNote] = useState<string | null>(null);
  const [cancelTone, setCancelTone] = useState<'ok' | 'warn' | 'plain'>('plain');
  const [deleteTarget, setDeleteTarget] = useState<RunSummary | null>(null);
  const [deletePending, setDeletePending] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  /** A start attempt is in flight — a REF, because two clicks in one tick both
   *  read the state version as `false`. */
  const startInFlight = useRef(false);

  // ── retiring runs, and the trash they go to ───────────────────────────────
  /** The runs TICKED in the Runs list. The page owns the set, so the action
   *  bar's count and the table's checkboxes cannot disagree about it. */
  const [tickedRuns, setTickedRuns] = useState<Set<string>>(new Set());
  /** The confirmation, holding RESOLVED records rather than names: the list has
   *  to show which of them are self-test runs. */
  const [retireTargets, setRetireTargets] = useState<RunSummary[] | null>(null);
  const [retirePending, setRetirePending] = useState(false);
  const [retireResult, setRetireResult] = useState<RetireResult | null>(null);
  const [retireError, setRetireError] = useState<string | null>(null);
  /** What has been retired is NOT read here any more: the shelf, its entries and
   *  the way back off it live at /trash, one surface for all five shelves. This
   *  page retires a run and points there. */
  /** The run being saved, and where the copy went. One destination is remembered
   *  (the design's "chosen once"), so the common case is two clicks. */
  const [saveTarget, setSaveTarget] = useState<RunSummary | null>(null);
  const [savePending, setSavePending] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedResult, setSavedResult] = useState<SavedRun | null>(null);
  const { saveDestination, setSaveDestination } = useTestingSavePreference();
  const { feed, status: streamStatus } = useRunStream(liveRunId);
  const { addSuccess } = useNotificationStore();
  const lock = current?.lock ?? null;
  const running = current?.running === true;
  /** The run the lock names — the one and only run this page must not double-start. */
  const runningRunId = running && lock ? lock.id : null;
  /** True when the page started the run it is watching: the only case Cancel is
   *  offered (a terminal run is watched, not stopped). */
  const canCancel = lock !== null && lock.id === liveRunId && lock.origin === 'page';

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    const [cat, reps] = await Promise.all([
      testingService.getCatalog(),
      testingService.getRuns(50),
    ]);

    // The client RETURNS {error} — it does not throw. Reading res.data blindly
    // is this project's most-repeated silent-failure pattern, so the error is
    // checked and surfaced rather than swallowed.
    if (cat.error) {
      setError(`Could not load the test catalog: ${cat.error.code} — ${cat.error.message}`);
    } else if (cat.data) {
      setEntries(cat.data.tests);
      setTotals(cat.data.totals);
      setCatalogReason(cat.data.available ? null : cat.data.reason);
    }

    if (reps.error) {
      // The reports failing must not hide the catalog — they are independent.
      setError((e) => e ?? `Could not load the reports: ${reps.error!.code}`);
    } else if (reps.data) {
      setReports(reps.data.reports);
    }

    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // ── saving: keep a copy, where the person says ────────────────────────────

  /** Open the save dialog for one run. */
  const openSave = (run: RunSummary) => {
    setSavedResult(null);
    setSaveError(null);
    setSaveTarget(run);
  };

  const confirmSave = async () => {
    if (!saveTarget) return;
    setSavePending(true);
    setSaveError(null);
    const res = await testingService.saveRun(saveTarget.name, saveDestination);
    setSavePending(false);
    if (res.error || !res.data) {
      // The server's own sentence: the lock's, or "already saved at …". The page
      // does not reword a refusal, and it does not close the dialog on one.
      setSaveError(res.error ? `${res.error.code} — ${res.error.message}` : 'No answer');
      return;
    }
    // The destination is REMEMBERED only once it has worked: a typo is not worth
    // remembering, and the next save would inherit it.
    if (saveDestination.trim() !== '') setSaveDestination(saveDestination.trim());
    setSavedResult(res.data);
    addSuccess('Testing', `Saved to ${res.data.saved_to}`);
  };

  // ── retiring: tick, then confirm ──────────────────────────────────────────
  const toggleRun = (name: string) => {
    setTickedRuns((current) => {
      const next = new Set(current);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const toggleAllRuns = () => {
    setTickedRuns((current) =>
      current.size === reports.length
        ? new Set<string>()
        : new Set(reports.map((r) => r.name)),
    );
  };

  /** QUICK-SELECTS ONLY TICK. They never retire anything: the person still sees
   *  the list and still presses the one button that moves runs. */
  const tickSelfTestRuns = () =>
    setTickedRuns(new Set(reports.filter((r) => r.self_test).map((r) => r.name)));

  /** The deliberately red runs are the ones worth pointing at: they are the
   *  fixture's, and they are the ones nobody reads history for. */
  const tickNotCleanRuns = () =>
    setTickedRuns(
      new Set(
        reports
          .filter((r) => !r.running && r.exit_code !== null && r.exit_code !== 0)
          .map((r) => r.name),
      ),
    );

  const openRetire = () => {
    const targets = reports.filter((r) => tickedRuns.has(r.name));
    if (targets.length === 0) return;
    setRetireResult(null);
    setRetireError(null);
    setRetireTargets(targets);
  };

  const confirmRetire = async () => {
    if (!retireTargets) return;
    setRetirePending(true);
    setRetireError(null);
    const res = await testingService.retireRuns(retireTargets.map((r) => r.name));
    setRetirePending(false);
    if (res.error || !res.data) {
      setRetireError(res.error ? `${res.error.code} — ${res.error.message}` : 'No answer');
      return;
    }
    const answer = res.data;
    setRetireResult(answer);
    setTickedRuns(new Set());
    await load();
    if (answer.retired.length > 0) {
      addSuccess(
        'Testing',
        `Retired ${answer.retired.length} run${answer.retired.length === 1 ? '' : 's'} — in the trash; Restore from the Trash page`,
      );
    }
  };

  /** Ask the lock. This is also how the page NOTICES a run started elsewhere. */
  const refreshCurrent = useCallback(async () => {
    const res = await testingService.getCurrentRun();
    if (res.error || !res.data) return;      // a failed poll must not clear the state
    setCurrent(res.data);
    // A run in progress that the page is not already watching becomes the thing
    // the Live tab shows — including one a person started in a terminal.
    if (res.data.running && res.data.lock) {
      setLiveRunId((id) => id ?? res.data!.lock!.id);
    }
  }, []);

  useEffect(() => {
    void refreshCurrent();
    const timer = window.setInterval(() => void refreshCurrent(), CURRENT_POLL_MS);
    return () => window.clearInterval(timer);
  }, [refreshCurrent]);

  /** When a watched run ends, the runs list is stale — the run just landed in it. */
  const endedRef = useRef<string | null>(null);
  useEffect(() => {
    if (feed.state !== 'finished' && feed.state !== 'killed') return;
    if (!liveRunId || endedRef.current === liveRunId) return;
    endedRef.current = liveRunId;
    void refreshCurrent();
    void load();
  }, [feed.state, liveRunId, refreshCurrent, load]);

  /** The rows for the active tab, then the active derived view. */
  const visible = useMemo(() => {
    if (tab === 'reports' || tab === 'live') return [];
    let rows = entries.filter((e) => e.tab === tab);
    // The profile is a TIER VIEW of the suite — a way to narrow it down. The
    // self-test set is not part of the suite and is never narrowed: filtering it
    // by tier would hide the slow test whose whole job is to be cancelled.
    if (tab === 'selftest') return rows;
    if (profile === PROFILE_FAST) rows = rows.filter((e) => e.time_class === 'short');
    else if (profile === 'medium') rows = rows.filter((e) => e.time_class !== 'short');
    return rows;
  }, [entries, tab, profile]);

  const conditionalCount = useMemo(
    () => entries.filter((e) => e.tab === 'conditional').length,
    [entries],
  );

  const quarantineCount = useMemo(
    () => entries.filter((e) => e.tab === 'quarantine').length,
    [entries],
  );

  const tabLabel = TABS.find((t) => t.key === tab)?.label ?? '';
  const profileLabel = PROFILES.find((p) => p.key === profile)?.label ?? '';

  /**
   * WHAT RUN RUNS. The ticked rows when there are any — that is the person
   * saying "these, specifically" — and otherwise everything the current tab and
   * profile are showing. Either way the control names the count, so nobody has
   * to guess what a click will start.
   */
  const runSet = useMemo(() => {
    if (selected.size > 0) return entries.filter((e) => selected.has(e.path));
    return visible;
  }, [entries, selected, visible]);

  const runFiles = useMemo(() => runSet.map((e) => e.run_path), [runSet]);
  const runTests = useMemo(() => runSet.reduce((n, e) => n + e.test_count, 0), [runSet]);

  const runLabel = selected.size > 0
    ? `Run ${runFiles.length} selected`
    : `Run ${runFiles.length} in ${tabLabel}`;

  /** The self-test's own PASS CONDITION, read out of the fixture by the API.
   *  The page keeps no copy of it: a pass condition copied into the frontend is
   *  a number that drifts the moment the fixture changes. */
  const selftestExpectation = useMemo(
    () => entries.find((e) => e.tab === 'selftest')?.expectation ?? '',
    [entries],
  );

  /** CLEAR THE RESULT — not the run. The watched run leaves the view (its stream
   *  closes with it) and the start messages go with it. **Nothing on disk
   *  changes**: the run stays in Runs as the record, and Delete is the control
   *  that removes it — which is why this needs no confirmation.
   *
   *  The confirmation is a TOAST, per this app's convention: the panel's job is
   *  to show a run, and "cleared" is news rather than a state to leave standing
   *  in its place. */
  const clearResult = () => {
    const wasWatching = liveRunId;
    setLiveRunId(null);
    setRunRefused(null);
    setRunNotice(null);
    if (wasWatching) {
      addSuccess('Testing', 'Result cleared — the run itself is still in Runs');
    }
  };

  const selectionSummary = {
    files: runFiles.length,
    tests: runTests,
    label: selected.size > 0
      ? `the ${runFiles.length} ticked files`
      : `the ${profileLabel} view of ${tabLabel}`,
  };

  /** Why Run is unavailable — the lock's own sentence when a run holds it. */
  const runBlocked = running
    ? `a run is in progress: ${lock ? `${lock.id} (started ${lock.started}, origin ${lock.origin})` : 'unknown'}`
    : runFiles.length === 0
      ? 'nothing to run — this view is empty'
      : starting
        ? 'a run is starting — the runner takes its lock before the page lets go'
        : null;

  const toggle = (path: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const toggleAll = () => {
    setSelected((prev) => {
      const all = visible.every((e) => prev.has(e.path));
      const next = new Set(prev);
      for (const e of visible) {
        if (all) next.delete(e.path);
        else next.add(e.path);
      }
      return next;
    });
  };

  /**
   * Start a run — the runner, under the lock, with the id the page will watch.
   *
   * A refusal is SHOWN, not smoothed over: the 409 carries the lock's own
   * sentence naming the run that holds it, and the Live tab offers to watch that
   * run instead (the second-click rule: refuse, then offer the watch).
   *
   * WHEN THE REQUEST ITSELF FAILS, the lock decides what to say. The runner takes
   * its lock on the server, whether or not the answer reaches this page, so a
   * dropped request can mean "it never started" OR "it started and you did not
   * hear about it". Reading the lock separates them — reporting "not started"
   * about a run that is going would be the same class of lie the old page told.
   */
  const startRun = async (files: string[]) => {
    if (files.length === 0) return;
    // THE CLICK GUARD IS SYNCHRONOUS ON PURPOSE. `starting` is state, and two
    // clicks in one tick both read it as `false` — a double-click on Run sent TWO
    // starts. A ref is set before the first await, so the second click is dropped
    // here rather than raced at the server.
    if (startInFlight.current) return;
    startInFlight.current = true;
    setStarting(true);
    setRunRefused(null);
    setRunNotice(null);
    setCancelNote(null);
    setNotice(null);

    try {
      const runId = newRunId();
      const res = await testingService.startRun({ files, run_id: runId });

      if (res.error) {
        const held = (await testingService.getCurrentRun()).data?.lock ?? null;
        if (held?.id === runId) {
          // It IS going: the lock names the id this page asked for.
          setLiveRunId(runId);
          setTab('live');
          setRunNotice(
            `The start did not answer (${res.error.message}), but the run is going — `
            + 'the lock names it. Watching it live.',
          );
        } else {
          setRunRefused(res.error.message);
          await refreshCurrent();
        }
        return;
      }

      setLiveRunId(runId);
      setTab('live');
      await refreshCurrent();
    } finally {
      startInFlight.current = false;
      setStarting(false);
    }
  };

  const cancelRun = async () => {
    if (!liveRunId) return;
    setCancelPending(true);
    setCancelNote(null);
    const res = await testingService.cancelRun(liveRunId);
    setCancelPending(false);

    if (res.error) {
      // Same discipline as the start: the KILL runs on the server, so a request
      // that did not come back is not evidence the run survived. The lock is.
      const held = (await testingService.getCurrentRun()).data?.lock ?? null;
      if (held && held.id === liveRunId) {
        setCancelTone('warn');
        setCancelNote(`Could not cancel: ${res.error.message} — the run still holds the lock.`);
      } else {
        setCancelTone('plain');
        setCancelNote(
          `The cancel request did not answer (${res.error.message}), but the run is no `
          + 'longer in progress — the lock is released.',
        );
      }
      await refreshCurrent();
      await load();
      return;
    }
    const result = res.data;
    if (!result) return;
    if (!result.cancelled) {
      // Two very different refusals arrive the same way, and the LOCK tells them
      // apart. A run that has already finished is not a warning: Cancel was simply
      // clicked after the end. A run still held by someone else IS one.
      const held = (await testingService.getCurrentRun()).data?.lock ?? null;
      if (held && held.id === liveRunId) {
        setCancelTone('warn');
        setCancelNote(result.reason ?? 'the run was not cancelled');
      } else {
        setCancelTone('plain');
        setCancelNote('The run had already finished when Cancel was clicked — nothing to stop.');
      }
      await refreshCurrent();
      await load();
      return;
    }
    const survivors = result.survivors ?? [];
    setCancelTone(survivors.length > 0 ? 'warn' : 'ok');
    setCancelNote(
      survivors.length > 0
        ? `Stopped${result.forced ? ' (forced — it ignored the first signal)' : ''}, but these `
          + `processes are still there: ${survivors.join(', ')}`
        : `Stopped${result.forced ? ' (forced — it ignored the first signal)' : ''}. `
          + `${result.released_lock ? 'The run lock is released.' : 'The lock is still held.'} `
          + 'No processes were left behind.',
    );
    await refreshCurrent();
    await load();
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeletePending(true);
    setDeleteError(null);
    const res = await testingService.deleteRun(deleteTarget.name);
    setDeletePending(false);

    if (res.error) {
      // The 409 (a run in progress) and the 404 arrive here with their own words.
      setDeleteError(res.error.message);
      return;
    }
    setNotice(
      `Deleted ${res.data?.name ?? deleteTarget.name} — it moved to `
      + `${res.data?.moved_to ?? 'the trash'}, so it can be recovered from Trash.`,
    );
    setDeleteTarget(null);
    await load();
  };

  return (
    <ErrorBoundary>
      <PageContainer>
        <PageBanner
          title="Testing"
          tooltip="Run tests, read what they protect, and see what the last runs actually said"
          action={<HelpButton context="testing" />}
        />

        {/* ── the state, stated plainly ── */}
        {totals && (
          <div className="mb-4 text-sm text-base-content/70">
            {totals.files} test files · {totals.tests} tests · {totals.clusters} clusters
            {/* The conditional count is called out because it is the actionable
                one: it is the number of tests NOT running for want of a service. */}
            {conditionalCount > 0 && (
              <span className="ml-2 text-warning">
                · {conditionalCount} need something that may not be running
              </span>
            )}
          </div>
        )}

        {catalogReason && (
          <div className="alert alert-info mb-4 text-sm py-2">
            <span>No catalog — {catalogReason}</span>
          </div>
        )}

        {notice && (
          <div className="alert alert-success mb-4 text-sm py-2" role="status">
            <span>{notice}</span>
          </div>
        )}

        {error && (
          <div className="alert alert-error mb-4 text-sm py-2" role="alert">
            <span>{error}</span>
          </div>
        )}

        {/* ── the tabs ── */}
        <div role="tablist" className="tabs tabs-boxed mb-4 w-fit">
          {TABS.map((t) => (
            <button
              key={t.key}
              role="tab"
              className={`tab tooltip tooltip-bottom ${tab === t.key ? 'tab-active' : ''}`}
              onClick={() => setTab(t.key)}
              data-tip={t.tooltip}
            >
              {t.label}
              {/* The LIVE tab carries the run's count while it goes — the state
                  sits ON the element rather than in a headline above the grid. */}
              {t.key === 'live' && running && (
                <span className="ml-2 badge badge-sm badge-info">{doneCount(feed)}</span>
              )}
              {t.key !== 'live' && (
                <span className="ml-2 badge badge-sm">{countFor(t.key, { reports, entries, conditionalCount, quarantineCount })}</span>
              )}
            </button>
          ))}
        </div>

        {tab === 'reports' ? (
          <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)]">
            <div className="card-body gap-[var(--card-gap)]">
              <h2 className="card-title text-base">Test runs</h2>
              <p className="text-sm text-base-content/60 -mt-2">
                Read from the reports the runner wrote. The page does not own them —
                it reads them, and retires one only when a person says so.
              </p>

              {/* ── retiring: TICK first, then confirm. The quick-selects only
                  tick — the person still sees the list and still presses the one
                  button that moves runs. ── */}
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className="tooltip tooltip-top"
                  data-tip={
                    tickedRuns.size === 0
                      ? 'Tick runs below to retire them together'
                      : 'Move every ticked run to the trash — after showing you the list'
                  }
                >
                  <button
                    className="btn btn-sm btn-error btn-outline"
                    onClick={openRetire}
                    disabled={tickedRuns.size === 0}
                  >
                    {tickedRuns.size === 0 ? 'Retire selected' : `Retire ${tickedRuns.size} selected`}
                  </button>
                </span>
                <button className="btn btn-sm btn-ghost" onClick={tickSelfTestRuns}>
                  Select self-test runs
                </button>
                <button className="btn btn-sm btn-ghost" onClick={tickNotCleanRuns}>
                  Select runs that did not pass
                </button>
                {/* THE WAY TO THE TRASH. Retiring a run moves it onto a shelf this
                    page no longer renders: the shelf, its entries and the way back
                    off it are ONE surface covering all five shelves, at /trash. A
                    link rather than a second copy of that view. */}
                <span
                  className="tooltip tooltip-top"
                  data-tip="What has been retired, and how to put any of it back"
                >
                  <Link to="/trash?shelf=test-runs" className="btn btn-sm btn-ghost">
                    Trash
                  </Link>
                </span>
                {tickedRuns.size > 0 && (
                  <button className="btn btn-sm btn-ghost" onClick={() => setTickedRuns(new Set())}>
                    Clear ticks
                  </button>
                )}
                <span className="text-xs text-base-content/60 ml-auto">
                  {tickedRuns.size === 0
                    ? `${reports.length} runs here — tick any to retire them together`
                    : `${tickedRuns.size} ticked`}
                </span>
              </div>

              <ReportsTable
                reports={reports}
                isLoading={loading}
                onDelete={setDeleteTarget}
                onSave={openSave}
                runningRunId={runningRunId}
                selected={tickedRuns}
                onToggle={toggleRun}
                onToggleAll={toggleAllRuns}
              />
            </div>
          </div>
        ) : tab === 'live' ? (
          <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)]">
            <div className="card-body gap-[var(--card-gap)]">
              <h2 className="card-title text-base">Live run</h2>
              <LiveRunPanel
                feed={feed}
                status={streamStatus}
                runId={liveRunId}
                lock={lock}
                selection={selectionSummary}
                canCancel={canCancel}
                cancelPending={cancelPending}
                cancelNote={cancelNote}
                cancelTone={cancelTone}
                onCancel={() => void cancelRun()}
                onClear={clearResult}
              />
              {/* THE SECOND CLICK: refused, then offered the watch. */}
              <StartOutcome
                refused={runRefused}
                notice={runNotice}
                lock={lock}
                onWatch={() => setLiveRunId(lock ? lock.id : null)}
              />
            </div>
          </div>
        ) : (
          <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)]">
            <div className="card-body gap-[var(--card-gap)]">
              {/* ── the action bar ── */}
              <div className="flex flex-wrap items-center gap-3">
                {/* The profile narrows a TIER VIEW of the suite. The self-test
                    tab is a fixed set of files, so the control would do nothing
                    there — and a control that does nothing is worse than one
                    that is absent. */}
                {tab !== 'selftest' && (
                  <label className="flex items-center gap-2 text-sm">
                    <span className="text-base-content/70">Profile</span>
                    <span
                      className="tooltip tooltip-bottom"
                      data-tip="A named selection. These are derived for now — the curated profiles come next."
                    >
                      <select
                        className="select select-sm select-bordered"
                        value={profile}
                        onChange={(e) => setProfile(e.target.value)}
                        aria-label="Choose a test profile"
                      >
                        {PROFILES.map((p) => (
                          <option key={p.key} value={p.key}>
                            {p.label}
                          </option>
                        ))}
                      </select>
                    </span>
                  </label>
                )}

                {/* THE RUN CONTROL, wired to the same runner a terminal starts.
                    While a run holds the lock it is DISABLED and names the run —
                    the lock's sentence, not a guess. */}
                <span className="tooltip tooltip-top" data-tip={runBlocked ?? `Run ${runFiles.length} test files (${runTests} test functions)`}>
                  <button
                    className="btn btn-sm btn-primary"
                    onClick={() => void startRun(runFiles)}
                    disabled={runBlocked !== null || starting}
                    aria-label={runLabel}
                  >
                    {starting ? 'Starting…' : runLabel}
                  </button>
                </span>

                {selected.size > 0 ? (
                  <span className="text-sm text-base-content/70">
                    {selected.size} ticked — Run takes those
                  </span>
                ) : (
                  <span className="text-sm text-base-content/60">
                    nothing ticked — Run takes everything this view shows
                  </span>
                )}

                {/* The trailing controls sit in ONE group, so adding one does not
                    move the others. */}
                <div className="ml-auto flex items-center gap-2">
                  {running && (
                    <button className="btn btn-sm btn-ghost" onClick={() => setTab('live')}>
                      Watch it live
                    </button>
                  )}

                  {/* CLEARS THE VIEW, NOT THE RUN. The label says exactly what it
                      does; the tooltip says the rest. */}
                  {liveRunId !== null && !running && (
                    <span
                      className="tooltip tooltip-left"
                      data-tip="Stop showing this result. The run itself stays in Runs — nothing is deleted."
                    >
                      <button className="btn btn-sm btn-ghost" onClick={clearResult}>
                        Clear result
                      </button>
                    </span>
                  )}

                  {selected.size > 0 && !running && (
                    <button className="btn btn-sm btn-ghost" onClick={() => setSelected(new Set())}>
                      Clear ticks
                    </button>
                  )}
                </div>
              </div>

              <StartOutcome
                refused={runRefused}
                notice={runNotice}
                lock={lock}
                onWatch={() => setTab('live')}
              />

              <CatalogTable
                entries={visible}
                selected={selected}
                onToggle={toggle}
                onToggleAll={toggleAll}
                onView={setViewing}
                onRun={(entry) => void startRun([entry.run_path])}
                runBlocked={runBlocked}
                isLoading={loading}
              />

              {tab === 'conditional' && visible.length > 0 && (
                <p className="text-xs text-base-content/50">
                  These do not run unless their dependency is available. They skip
                  visibly, with the reason — a skip is evidence, not noise.
                </p>
              )}
              {tab === 'quarantine' && visible.length > 0 && (
                <p className="text-xs text-base-content/50">
                  Parked rather than deleted — nothing is abandoned silently.
                </p>
              )}
              {tab === 'selftest' && selftestExpectation && (
                <p className="text-xs text-base-content/60">
                  This is the page's own check, and it is meant to fail. A correct
                  run: {selftestExpectation}.
                </p>
              )}
            </div>
          </div>
        )}

        {viewing && (
          <TestDetailsModal entry={viewing} onClose={() => setViewing(null)} />
        )}

        {deleteTarget && (
          <DeleteRunModal
            run={deleteTarget}
            pending={deletePending}
            error={deleteError}
            onClose={() => {
              setDeleteTarget(null);
              setDeleteError(null);
            }}
            onConfirm={() => void confirmDelete()}
          />
        )}
        {retireTargets && (
          <RetireRunsModal
            runs={retireTargets}
            pending={retirePending}
            result={retireResult}
            error={retireError}
            onClose={() => {
              setRetireTargets(null);
              setRetireResult(null);
              setRetireError(null);
            }}
            onConfirm={() => void confirmRetire()}
          />
        )}

        {saveTarget && (
          <SaveRunModal
            run={saveTarget}
            destination={saveDestination}
            pending={savePending}
            error={saveError}
            saved={savedResult}
            onDestination={setSaveDestination}
            onClose={() => {
              setSaveTarget(null);
              setSavedResult(null);
              setSaveError(null);
            }}
            onConfirm={() => void confirmSave()}
          />
        )}
      </PageContainer>
    </ErrorBoundary>
  );
};

/**
 * The two things a start attempt can have to say, in one place so the Run tab and
 * the catalog tab cannot drift apart:
 *
 *   - a REFUSAL, verbatim from the lock (which names the run that holds it), with
 *     the offer to watch that run instead — refuse, then offer the watch;
 *   - a LOST ANSWER that the lock proved wrong: the request did not come back, but
 *     the run IS going, and saying "not started" would be false.
 */
const StartOutcome: React.FC<{
  refused: string | null;
  notice: string | null;
  lock: RunLockInfo | null;
  onWatch: () => void;
}> = ({ refused, notice, lock, onWatch }) => (
  <>
    {refused && (
      <div className="alert alert-warning text-sm py-2" role="alert">
        <span className="flex-1">
          Not started — {refused}
          {lock && (
            <>
              {' '}
              <button className="btn btn-xs btn-ghost" onClick={onWatch}>
                Watch that run
              </button>
            </>
          )}
        </span>
      </div>
    )}
    {notice && (
      <div className="alert alert-info text-sm py-2" role="status">
        <span>{notice}</span>
      </div>
    )}
  </>
);

/** The tab badges. Pulled out so the live tab's count can come from the feed
 *  instead of from a list this page already has. */
function countFor(
  t: Tab,
  data: {
    reports: RunSummary[];
    entries: CatalogEntry[];
    conditionalCount: number;
    quarantineCount: number;
  },
): number {
  if (t === 'reports') return data.reports.length;
  if (t === 'conditional') return data.conditionalCount;
  if (t === 'quarantine') return data.quarantineCount;
  // The self-test set is its OWN set of files. Without this line it fell through
  // to the runnable count and the tab read 178 — the whole suite's number on a
  // tab that holds one file.
  if (t === 'selftest') return data.entries.filter((e) => e.tab === 'selftest').length;
  return data.entries.filter((e) => e.tab === 'runnable').length;
}

export default TestingDashboard;
