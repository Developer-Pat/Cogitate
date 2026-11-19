import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { PageBanner } from '../components/ui/PageBanner';
import { PageContainer } from '../components/ui/PageContainer';
import { usePageTitle } from '../hooks/usePageTitle';
import { workflowService } from '../services/domains/llm/workflowService';
import { useNotificationStore } from '../stores/notificationStore';
import ReportViewer from '../components/ReportViewer';
import type { WorkflowProductInfo } from '../types/workflows';

/**
 * The full-page report viewer — the READ surface for reports that
 * outgrow the Workflow Products modal (the report-viewer
 * mini-map, 2026-08-17). Addressable route: /products/:path.
 */
const ProductViewer: React.FC = () => {
  usePageTitle('Report', 'Full-page report viewer');
  const { path: pathParam } = useParams<{ path: string }>();
  const [product, setProduct] = useState<WorkflowProductInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const { addError } = useNotificationStore();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const resp = await workflowService.getWorkflowProducts(200);
        const items = (resp.data as { products: WorkflowProductInfo[] })?.products ?? [];
        // match by the path segment (decode the route param)
        const target = decodeURIComponent(pathParam ?? '');
        const found = items.find((p) => (p.path ?? '').split('/').pop() === target);
        if (!cancelled) {
          if (found) {
            setProduct(found);
          } else {
            setNotFound(true);
          }
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          addError('Report', 'Failed to load the report');
          setNotFound(true);
          setLoading(false);
        }
      }
    })();
    return () => { cancelled = true; };
  }, [pathParam, addError]);

  if (loading) {
    return (
      <PageContainer>
        <div className="flex justify-center py-16"><span className="loading loading-spinner loading-lg"></span></div>
      </PageContainer>
    );
  }

  if (notFound || !product) {
    return (
      <PageContainer>
        <div className="card bg-base-100 p-8 text-center">
          <h2 className="font-bold text-lg">Report not found</h2>
          <p className="text-sm text-readout mt-2">It may have been cleared or the link is stale.</p>
          <Link to="/workflow-products" className="btn btn-primary btn-sm mt-4">Back to Products</Link>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <PageBanner title={product.title} subtitle={`${product.product_type} · from ${product.source_template} · ${new Date(product.created_at).toLocaleString()}`} />
      <div className="flex justify-end mb-4">
        <Link to="/workflow-products" className="btn btn-neutral btn-ghost btn-sm">Back to Products</Link>
      </div>
      <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
        <div className="card-body gap-[var(--card-gap)]">
          <ReportViewer body={product.body ?? ''} />
        </div>
      </div>
    </PageContainer>
  );
};

export default ProductViewer;
