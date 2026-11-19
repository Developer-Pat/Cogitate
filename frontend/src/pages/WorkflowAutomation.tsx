/**
 * WorkflowAutomation — the triggered-execution model
 *
 * "Keep doing this thing": two activities on one page (tabs):
 *   🎛️ Triggers — control table (activate/deactivate/cron)
 *   📊 History  — per-trigger run history (collection pattern:
 *                 filter + pagination, since runs proliferate)
 *
 * The History tab uses the collection pattern (search/filter +
 * pagination) because every trigger fire = a row — a 5-min
 * trigger alone produces 288/day. The Triggers tab is a bounded
 * list and stays a normal page flow.
 */

import { useCallback, useMemo, useState } from 'react';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { usePageTitle } from '../hooks/usePageTitle';
import { useWorkflowAutomation } from '../hooks/useWorkflowAutomation';
import { PageBanner } from '../components/ui/PageBanner';
import TriggerManagement from '../components/features/workflows/TriggerManagement';
import ExaSchedulePanel from '../components/features/workflows/ExaSchedulePanel';
import { HelpButton } from '../components/help';
import type { AutomationRun } from '../hooks/useWorkflowAutomation';

type AutomationTab = 'triggers' | 'history';

const PAGE_SIZE = 20;

export default function WorkflowAutomation() {
  usePageTitle('Workflow Automation', 'Set up recurring workflow runs and monitor their history');

  const [tab, setTab] = useState<AutomationTab>('triggers');
  // a shared refresh key (2026-08-18): the Exa panel's done bumps it;
  // TriggerManagement reloads on change — the table shows the new cron
  const [refreshKey, setRefreshKey] = useState(0);
  const bumpRefresh = useCallback(() => setRefreshKey((k) => k + 1), []);
  const {
    triggers,
    selectedTrigger,
    runs,
    loadingRuns,
    selectTrigger: handleTriggerChange,
    refreshTriggers,
  } = useWorkflowAutomation();

  // ---- History tab: collection pattern state ----
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  const filteredRuns = useMemo(() => {
    let result = runs;
    if (statusFilter) {
      result = result.filter((r) => r.status === statusFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase().trim();
      result = result.filter(
        (r) => r.id.toLowerCase().includes(q) || r.templateId.toLowerCase().includes(q)
      );
    }
    return result;
  }, [runs, statusFilter, search]);

  const totalPages = Math.max(1, Math.ceil(filteredRuns.length / PAGE_SIZE));
  const pageRuns = filteredRuns.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // A degraded run is `completed` with something wrong inside it: the status badge stays the
  // execution outcome and the second axis rides BESIDE it, never encoded into one word.
  const statusBadge = (status: string, degraded?: boolean) => {
    const cls =
      status === 'completed' ? 'badge-success' :
      status === 'running' ? 'badge-warning' :
      status === 'failed' ? 'badge-error' :
      status === 'cancelled' ? 'badge-neutral' : 'badge-info';
    return (
      <span className="inline-flex items-center gap-1">
        <span className={`badge badge-sm ${cls}`}>{status}</span>
        {degraded && (
          <span
            className="badge badge-warning badge-sm tooltip tooltip-top"
            data-tip="A step failed and the run absorbed it — part of the result may be missing"
          >
            degraded
          </span>
        )}
      </span>
    );
  };

  const statusOptions = useMemo(() => {
    const set = new Set(runs.map((r) => r.status));
    return [...set].sort();
  }, [runs]);

  return (
    <ErrorBoundary>
      <div className="p-6 max-w-7xl mx-auto">
        <PageBanner
          title="Workflow Automation"
          className="mb-8"
          tooltip="Set up recurring workflow runs (scheduled or webhook triggers) and monitor their execution history over time."
          action={<HelpButton context="workflows" tooltipPosition="bottom" />}
        />

        {/* Tabs — the two activities of the triggered model */}
        <div role="tablist" className="tabs tabs-bordered tabs-lg mb-6">
          <a
            role="tab"
            className={`tab ${tab === 'triggers' ? 'tab-active' : ''}`}
            onClick={() => setTab('triggers')}
          >
            🎛️ Triggers
          </a>
          <a
            role="tab"
            className={`tab ${tab === 'history' ? 'tab-active' : ''}`}
            onClick={() => setTab('history')}
          >
            📊 History
            {runs.length > 0 && <span className="ml-1 badge badge-sm badge-ghost">{runs.length}</span>}
          </a>
        </div>

        {tab === 'triggers' ? (
          <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
            <div className="card-body gap-[var(--card-gap)]">
              <TriggerManagement refreshKey={refreshKey} onRefresh={refreshTriggers} />
              <ExaSchedulePanel onScheduled={() => { refreshTriggers(); bumpRefresh(); }} />
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Trigger selector */}
            <div className="lg:col-span-1">
              <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
                <div className="card-body gap-[var(--card-gap)]">
                  <h2 className="card-title">Triggers</h2>
                  {triggers.length === 0 ? (
                    <p className="text-sm text-readout">No triggers configured.</p>
                  ) : (
                    <div className="space-y-2">
                      {triggers.map((t) => (
                        <button
                          key={t.id}
                          onClick={() => { handleTriggerChange(t.id); setPage(1); }}
                          className={
                            'w-full rounded-md border px-3 py-2 text-left text-sm transition-colors ' +
                            (selectedTrigger === t.id
                              ? 'border-primary bg-primary/10'
                              : 'border-base-300 hover:bg-base-200/60')
                          }
                        >
                          <div className="font-medium">{t.name ?? t.id}</div>
                          <div className="text-xs text-readout">
                            {t.trigger_type} · {t.is_active ? 'Active' : 'Inactive'}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Run history — collection pattern (filter + pagination) */}
            <div className="lg:col-span-3">
              <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
                <div className="card-body gap-[var(--card-gap)]">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <h2 className="card-title">
                      Run History
                      {selectedTrigger && <span className="text-sm font-normal text-readout">— {selectedTrigger}</span>}
                    </h2>
                    {/* Filters (collection pattern) */}
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        placeholder="Search runs…"
                        value={search}
                        onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                        className="input input-bordered input-sm"
                      />
                      <select
                        value={statusFilter}
                        onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                        className="select select-bordered select-sm"
                      >
                        <option value="">All statuses</option>
                        {statusOptions.map((s) => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {!selectedTrigger ? (
                    <p className="text-sm text-readout">Select a trigger to see its run history.</p>
                  ) : loadingRuns ? (
                    <p className="text-sm text-readout">Loading runs…</p>
                  ) : filteredRuns.length === 0 ? (
                    <p className="text-sm text-readout">
                      {runs.length === 0
                        ? 'No runs for this trigger yet. Activate it and wait for the next fire.'
                        : 'No runs match the current filters.'}
                    </p>
                  ) : (
                    <>
                      <div className="overflow-x-auto">
                        <table className="table table-zebra w-full">
                          <thead>
                            <tr>
                              <th>Run ID</th>
                              <th>Workflow</th>
                              <th>Status</th>
                              <th>Started</th>
                              <th>Duration</th>
                            </tr>
                          </thead>
                          <tbody>
                            {pageRuns.map((run: AutomationRun) => (
                              <tr key={run.id}>
                                <td className="font-mono text-xs">{run.id}</td>
                                <td>{run.templateId}</td>
                                <td>{statusBadge(run.status, run.degraded)}</td>
                                <td>{run.startedAt ? new Date(run.startedAt).toLocaleString() : '—'}</td>
                                <td>{run.elapsed != null ? `${run.elapsed.toFixed(2)}s` : '—'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      {/* Pagination (collection pattern) */}
                      <div className="flex items-center justify-between mt-2">
                        <span className="text-sm text-readout">
                          {filteredRuns.length} run{filteredRuns.length !== 1 ? 's' : ''}
                        </span>
                        <div className="join">
                          <button
                            className="join-item btn btn-sm"
                            disabled={page <= 1}
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                          >
                            «
                          </button>
                          <span className="join-item btn btn-sm btn-ghost no-animation">
                            {page} / {totalPages}
                          </span>
                          <button
                            className="join-item btn btn-sm"
                            disabled={page >= totalPages}
                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                          >
                            »
                          </button>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
}
