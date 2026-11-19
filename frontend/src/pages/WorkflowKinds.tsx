/**
 * Workflow Kinds page (Phase A).
 *
 * The canonical process shapes — the TEMPLATES of the agreed model
 * (template = kind). Read-only for Phase A; the configured
 * instances (Workflows) live on the Workflow Templates page until
 * Phase C splits the surfaces.
 */

import React, { useEffect, useState } from 'react';
import { PageBanner } from '../components/ui/PageBanner';
import { PageContainer } from '../components/ui/PageContainer';
import { usePageTitle } from '../hooks/usePageTitle';
import { fetchWorkflowKinds } from '../services/workflowKindsService';
import { claimDeclaredPrimaryInput } from '../services/focusContract';
import type { WorkflowKind } from '../services/workflowKindsService';

const PRODUCT_LABELS: Record<string, string> = {
  report: 'Report',
  file: 'File',
  index: 'Index',
};

const WorkflowKinds: React.FC = () => {
  usePageTitle('Templates', 'The canonical workflow process shapes — a template is a kind');
  const [kinds, setKinds] = useState<WorkflowKind[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState('');
  const [productType, setProductType] = useState('');

  /**
   * THE PAGE'S OWN HALF OF THE FOCUS CONTRACT (2026-09-19) — see
   * services/focusContract: the declaration is a YIELD, so somebody has to act on
   * it, and on a cold load (a lazy route) that somebody is this page.
   */
  useEffect(() => {
    claimDeclaredPrimaryInput();
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchWorkflowKinds({ q: q || undefined, product_type: productType || undefined })
      .then((data) => { if (!cancelled) setKinds(data); })
      .catch(() => { if (!cancelled) setError('Failed to load workflow kinds.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [q, productType]);

  return (
    <PageContainer>
      <PageBanner
        title="Templates"
        
        tooltip="The canonical workflow process shapes. A template (kind) defines the process; a Workflow is a configured instance of one."
      />

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <input
          data-autofocus
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search kinds…"
          className="input input-sm input-bordered max-w-xs"
          aria-label="Search kinds"
        />
        <select
          value={productType}
          onChange={(e) => setProductType(e.target.value)}
          className="select select-sm select-bordered"
          aria-label="Product type"
        >
          <option value="">All products</option>
          <option value="report">Report</option>
          <option value="file">File</option>
          <option value="index">Index</option>
        </select>
      </div>

      {error && <div className="alert alert-error mb-4"><span>{error}</span></div>}

      {loading ? (
        <div className="flex justify-center py-12">
          <span className="loading loading-spinner loading-lg"></span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {kinds.map((kind) => (
            <div key={kind.name} className="card bg-base-100 shadow-lg rounded-box p-5">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-bold text-lg">{kind.name}</h3>
                <span className="badge badge-sm badge-info badge-outline">
                  {PRODUCT_LABELS[kind.product_type] ?? kind.product_type}
                </span>
              </div>
              <p className="text-sm text-readout mb-3">{kind.description}</p>
              {kind.inputs.length > 0 && (
                <div className="text-xs opacity-70 mb-2">
                  <span className="font-medium">Inputs:</span>{' '}
                  {kind.inputs.map((i) => `${i.name} (${i.type}${i.required ? ', required' : ''})`).join(', ')}
                </div>
              )}
              <div className="text-xs opacity-50 font-mono">{kind.builder_key}</div>
            </div>
          ))}
          {!loading && kinds.length === 0 && (
            <div className="col-span-full text-center opacity-60 py-8">No kinds match.</div>
          )}
        </div>
      )}
    </PageContainer>
  );
};

export default WorkflowKinds;
