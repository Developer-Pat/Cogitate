import { Link } from 'react-router-dom';
/**
 * WorkflowProducts — the display surface for workflow products.
 *
 * Collection pattern: scrollable table with search + type filter +
 * pagination (products proliferate — a 5-min trigger = 288/day).
 * Report viewer: click a row to render the product body as
 * markdown (ReactMarkdown + remark-gfm + rehype-highlight).
 *
 * Part of the workflow product distribution layer: products are
 * packaged (WorkflowProduct) and delivered through distributors —
 * file + display. This page is the display channel.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import ReportViewer from '../components/ReportViewer';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { usePageTitle } from '../hooks/usePageTitle';
import { PageBanner } from '../components/ui/PageBanner';
import { Package } from 'lucide-react';
import { workflowService } from '../services/domains/llm/workflowService';
import { useNotificationStore } from '../stores/notificationStore';
import { useWorkflowToastPreference } from '../stores/workflowToastPreference';
import type { WorkflowProductInfo } from '../types/workflows';

const PAGE_SIZE = 20;

const TYPE_BADGES: Record<string, string> = {
  rss_digest: 'badge-primary badge-outline',
  market_alert: 'badge-secondary badge-outline',
  readiness_report: 'badge-accent badge-outline',
  exa_report: 'badge-info badge-outline',
};

const TYPE_LABELS: Record<string, string> = {
  rss_digest: 'RSS Digest',
  market_alert: 'Market Alert',
  readiness_report: 'Readiness Report',
  exa_report: 'Exa Report',
};

export default function WorkflowProducts() {
  usePageTitle('Workflow Products', 'Products delivered by workflow runs — digests, alerts, reports');

  const [products, setProducts] = useState<WorkflowProductInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [page, setPage] = useState(1);
  const [viewing, setViewing] = useState<WorkflowProductInfo | null>(null);
  const [confirmingClear, setConfirmingClear] = useState(false);
  const [clearing, setClearing] = useState(false);
  // Phase G (2026-08-17): selection + the delete confirm
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // Phase G sort (2026-08-17): clickable columns — key + direction
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const { addError, addSuccess } = useNotificationStore();
  const toastsEnabled = useWorkflowToastPreference((s) => s.toastsEnabled);
  const toggleToasts = useWorkflowToastPreference((s) => s.toggleToasts);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await workflowService.getWorkflowProducts();
      setProducts((resp.data as WorkflowProductsResponse)?.products ?? []);
    } catch (err) {
      addError('Products', 'Failed to load workflow products');
      console.error('WorkflowProducts load:', err);
    } finally {
      setLoading(false);
    }
  }, [addError]);

  useEffect(() => { load(); }, [load]);

  // Phase G (2026-08-17): AUTO-RELOAD — new products appear without
  // a manual refresh (the user's catch: "I had to do a manual
  // refresh to see new products"). A silent poll keeps the list
  // fresh; failures stay quiet (polling must never spam errors).
  useEffect(() => {
    const id = setInterval(() => {
      workflowService.getWorkflowProducts().then((resp) => {
        setProducts((resp.data as WorkflowProductsResponse)?.products ?? []);
      }).catch(() => { /* silent */ });
    }, 15000);
    return () => clearInterval(id);
  }, []);

  const handleClear = async () => {
    setClearing(true);
    try {
      const resp = await workflowService.clearWorkflowProducts();
      setProducts([]);
      setConfirmingClear(false);
      addSuccess('Products', `Cleared ${(resp.data as { cleared?: number })?.cleared ?? 0} product files`);
    } catch (err) {
      addError('Products', 'Failed to clear products');
      console.error('WorkflowProducts clear:', err);
    } finally {
      setClearing(false);
    }
  };

  // The row identity = created_at (the collision fix, 2026-08-18:
  // the basename collided for same-day same-type products — e.g. 15
  // 'readiness_report-2026-08-15.md' entries — so selecting one row
  // selected them all. created_at is unique per index entry.)
  const rowId = (p: WorkflowProductInfo) => p.created_at;

  const toggleSelected = (b: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(b)) next.delete(b); else next.add(b);
      return next;
    });
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      let removed = 0;
      for (const b of selected) {
        const resp = await workflowService.deleteWorkflowProduct(b);
        if (resp.data) removed += 1;
      }
      addSuccess('Products', `Deleted ${removed} product${removed !== 1 ? 's' : ''}`);
      setSelected(new Set());
      setConfirmingDelete(false);
      await load();
    } catch (err) {
      addError('Products', 'Failed to delete the selected products');
      console.error('WorkflowProducts delete:', err);
    } finally {
      setDeleting(false);
    }
  };

  const types = useMemo(() => {
    const set = new Set(products.map((p) => p.product_type));
    return [...set].sort();
  }, [products]);

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const sortIcon = (key: string) => sortKey === key ? (sortDir === 'asc' ? '↑' : '↓') : '↕';

  const filtered = useMemo(() => {
    let result = products;
    if (typeFilter) result = result.filter((p) => p.product_type === typeFilter);
    if (search.trim()) {
      const q = search.toLowerCase().trim();
      result = result.filter(
        (p) => p.title.toLowerCase().includes(q)
          || p.source_template.toLowerCase().includes(q)
      );
    }
    // the column sort (Phase G, 2026-08-17) — applies before pagination
    if (sortKey) {
      const dir = sortDir === 'asc' ? 1 : -1;
      result = [...result].sort((a, b) => {
        const av = sortKey === 'delivered' ? a.created_at : String(a[sortKey as keyof WorkflowProductInfo] ?? '');
        const bv = sortKey === 'delivered' ? b.created_at : String(b[sortKey as keyof WorkflowProductInfo] ?? '');
        return av.localeCompare(bv) * dir;
      });
    }
    return result;
  }, [products, typeFilter, search, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageRows = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const pageSelected = pageRows.filter((p) => selected.has(rowId(p))).length;
  const allPageSelected = pageRows.length > 0 && pageSelected === pageRows.length;

  const togglePage = () => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allPageSelected) {
        for (const p of pageRows) next.delete(rowId(p));
      } else {
        for (const p of pageRows) next.add(rowId(p));
      }
      return next;
    });
  };

  // The type badge: known types show their short label; unknown
  // types show the raw slug TRUNCATED (long slugs break the daisyUI
  // badge — the 2026-08-17 fix) with the full value in the tooltip.
  const typeBadge = (t: string) => {
    const label = TYPE_LABELS[t] ?? t;
    const isKnown = t in TYPE_LABELS;
    if (isKnown) {
      return <span className={`badge badge-sm ${TYPE_BADGES[t] ?? 'badge-ghost'}`}>{label}</span>;
    }
    // unknown types: truncated + the full slug in a DaisyUI tooltip
    return (
      <div className="tooltip tooltip-top" data-tip={t}>
        <span
          className={`badge badge-sm ${TYPE_BADGES[t] ?? 'badge-ghost'}`}
          style={{ maxWidth: '10rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'inline-block', verticalAlign: 'middle' }}
        >
          {label}
        </span>
      </div>
    );
  };

  return (
    <ErrorBoundary>
      <div className="p-6 max-w-7xl mx-auto">
        <PageBanner
          title="Workflow Products"
          className="mb-8"
          tooltip="Digests, alerts and reports delivered by workflow runs — the display channel of the distribution layer."
          action={
            <div className="flex items-center gap-2">
              <div className="tooltip" data-tip={toastsEnabled ? 'Delivery toasts are ON — new products pop a toast with a link' : 'Delivery toasts are OFF — new products still appear in the list, no toast'}>
                <label className="flex items-center gap-2 cursor-pointer">
                  <span className="text-xs text-readout">Toasts</span>
                  <input
                    type="checkbox"
                    className="toggle toggle-sm toggle-primary"
                    checked={toastsEnabled}
                    onChange={toggleToasts}
                  />
                </label>
              </div>
              {selected.size > 0 && (
                <button
                  className="btn btn-sm btn-error"
                  onClick={() => setConfirmingDelete(true)}
                  disabled={deleting}
                >
                  Delete selected ({selected.size})
                </button>
              )}
              {products.length > 0 && (
                <button
                  className="btn btn-sm btn-outline btn-error"
                  onClick={() => setConfirmingClear(true)}
                >
                  Clear
                </button>
              )}
              <button
                className="btn btn-sm btn-outline"
                onClick={load}
                disabled={loading}
              >
                {loading ? 'Loading…' : 'Refresh'}
              </button>
            </div>
          }
        />

        <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
          <div className="card-body gap-[var(--card-gap)]">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h2 className="card-title">Recent Products</h2>
              <span className="text-sm text-readout">{filtered.length} shown · {products.length} delivered</span>
            </div>

            {/* Filters (collection pattern) */}
            <div className="flex items-center gap-2 flex-wrap">
              <input
                type="text"
                placeholder="Search title or workflow…"
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                className="input input-bordered input-sm w-64"
              />
              <select
                value={typeFilter}
                onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
                className="select select-bordered select-sm"
              >
                <option value="">All types</option>
                {types.map((t) => (
                  <option key={t} value={t}>{TYPE_LABELS[t] ?? t}</option>
                ))}
              </select>
            </div>

            {loading ? (
              <p className="text-sm text-readout">Loading products…</p>
            ) : filtered.length === 0 ? (
              <div className="text-center py-8 opacity-70">
                <div className="text-4xl mb-2 text-readout">
                  <Package className="h-10 w-10 mx-auto" />
                </div>
                <div>
                  {products.length === 0
                    ? 'No products yet — run a monitor workflow (e.g. readiness-check) to deliver one.'
                    : 'No products match the current filters.'}
                </div>
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="table table-zebra w-full">
                    <thead>
                      <tr>
                        <th className="w-10">
                          <div className="tooltip tooltip-right" data-tip="Select all on this page">
                            <input
                              type="checkbox"
                              className="checkbox checkbox-sm checkbox-primary"
                              checked={allPageSelected}
                              onChange={togglePage}
                            />
                          </div>
                        </th>
                        {(['product_type', 'title', 'source_template'] as const).map((key) => (
                          <th
                            key={key}
                            className="cursor-pointer select-none hover:bg-base-content/10"
                            onClick={() => handleSort(key)}
                          >
                            {key === 'product_type' ? 'Type' : key === 'title' ? 'Title' : 'Workflow'} {sortIcon(key)}
                          </th>
                        ))}
                        <th
                          className="cursor-pointer select-none hover:bg-base-content/10"
                          onClick={() => handleSort('delivered')}
                        >
                          Delivered {sortIcon('delivered')}
                        </th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pageRows.map((p, i) => {
                        const b = rowId(p);
                        return (
                        <tr key={`${p.created_at}-${i}`} className={selected.has(b) ? 'bg-base-200' : ''}>
                          <td>
                            <input
                              type="checkbox"
                              className="checkbox checkbox-sm checkbox-primary"
                              checked={selected.has(b)}
                              onChange={() => toggleSelected(b)}
                            />
                          </td>
                          <td>{typeBadge(p.product_type)}</td>
                          <td className="font-medium">{p.title}</td>
                          <td className="font-mono text-xs">{p.source_template}</td>
                          <td className="text-sm text-readout">{new Date(p.created_at).toLocaleString()}</td>
                          <td>
                            <button
                              className="btn btn-xs btn-outline"
                              onClick={() => setViewing(p)}
                            >
                              View
                            </button>
                          </td>
                        </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Pagination (collection pattern) */}
                <div className="flex items-center justify-between mt-2">
                  <span className="text-sm text-readout">
                    {filtered.length} product{filtered.length !== 1 ? 's' : ''}
                  </span>
                  <div className="join">
                    <div className="tooltip tooltip-top" data-tip="Previous page">
                      <button
                        className="join-item btn btn-sm"
                        disabled={page <= 1}
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        aria-label="Previous page"
                      >
                        «
                      </button>
                    </div>
                    <span className="join-item btn btn-sm btn-ghost no-animation">
                      {page} / {totalPages}
                    </span>
                    <div className="tooltip tooltip-top" data-tip="Next page">
                      <button
                        className="join-item btn btn-sm"
                        disabled={page >= totalPages}
                        onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                        aria-label="Next page"
                      >
                        »
                      </button>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Clear confirmation modal (the Session delete pattern) */}
      {confirmingClear && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/50" onClick={() => !clearing && setConfirmingClear(false)}>
          <div
            className="bg-base-200 rounded-lg shadow-xl max-h-[90vh] overflow-y-auto p-6"
            style={{ width: 'min(var(--dialog-width-md), 95vw)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="font-bold text-lg">Clear all products?</h3>
            <p className="py-4 text-readout">
              This deletes <strong>{products.length} product file{products.length !== 1 ? 's' : ''}</strong>{' '}
              (digests, alerts, reports) and the display index. Monitor dedup state is kept. This action cannot be undone.
            </p>
            <div className="modal-action">
              <button
                className="btn btn-neutral btn-ghost"
                onClick={() => setConfirmingClear(false)}
                disabled={clearing}
              >
                Cancel
              </button>
              <button
                className="btn btn-error"
                onClick={handleClear}
                disabled={clearing}
              >
                {clearing ? 'Clearing…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete-selected confirm modal — the DEV-NOTE working pattern
          (2026-08-18 second fix: the DaisyUI modal-box rendered at
          48px in this Tailwind v4 setup — measured. The documented
          pattern is the plain styled container + the --dialog-width
          CSS vars, per modal-dialogs.md) */}
      {confirmingDelete && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/50" onClick={() => !deleting && setConfirmingDelete(false)}>
          <div
            className="bg-base-200 rounded-lg shadow-xl max-h-[90vh] overflow-y-auto p-6"
            style={{ width: 'min(var(--dialog-width-md), 95vw)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="font-bold text-lg">Delete {selected.size} product{selected.size !== 1 ? 's' : ''}?</h3>
            <p className="py-4 text-readout">
              This removes the selected product{selected.size !== 1 ? 's' : ''} — the report
              file{selected.size !== 1 ? 's' : ''} and the display index entr{selected.size !== 1 ? 'ies' : 'y'}.
              This action cannot be undone.
            </p>
            <div className="modal-action">
              <button
                className="btn btn-neutral btn-ghost"
                onClick={() => setConfirmingDelete(false)}
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                className="btn btn-error"
                onClick={handleDelete}
                disabled={deleting}
              >
                {deleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Report viewer modal */}
      {viewing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setViewing(null)}>
          <div
            className="w-full max-w-3xl max-h-[80vh] flex flex-col overflow-hidden rounded-2xl bg-base-100 text-base-content shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="font-bold text-lg">{viewing.title}</h3>
                <p className="text-xs text-readout">
                  {TYPE_LABELS[viewing.product_type] ?? viewing.product_type} · from{' '}
                  <span className="font-mono">{viewing.source_template}</span> ·{' '}
                  {new Date(viewing.created_at).toLocaleString()}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {viewing.path && (
                  <div className="tooltip tooltip-left" data-tip="Open the report in the full-page viewer">
                    <Link
                      to={`/products/${encodeURIComponent(viewing.path.split('/').pop() ?? viewing.path)}`}
                      className="btn btn-sm btn-primary"
                      onClick={() => setViewing(null)}
                    >
                      Open full view
                    </Link>
                  </div>
                )}
                <button className="btn btn-sm btn-ghost" onClick={() => setViewing(null)} aria-label="Close">✕</button>
              </div>
            </div>
            <div className="overflow-y-auto flex-1">
              <ReportViewer body={viewing.body ?? ''} />
            </div>
          </div>
        </div>
      )}
    </ErrorBoundary>
  );
}

interface WorkflowProductsResponse {
  products: WorkflowProductInfo[];
  total: number;
}
