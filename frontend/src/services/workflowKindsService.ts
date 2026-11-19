/**
 * Workflow kinds service (Phase A).
 *
 * The kind registry is CODE-DEFINED (the source of truth for
 * behavior); these endpoints serve it. The DB catalog mirror joins
 * in Phase B when template rows carry kind_id.
 */

import { apiClient } from './apiClient';

export interface KindInput {
  name: string;
  type: string;
  description: string;
  default?: unknown;
  required: boolean;
}

export interface WorkflowKind {
  name: string;
  description: string;
  builder_key: string;
  product_type: string;
  inputs: KindInput[];
}

export interface KindListResponse {
  kinds: WorkflowKind[];
  total: number;
}

export async function fetchWorkflowKinds(
  params: { q?: string; product_type?: string } = {}
): Promise<WorkflowKind[]> {
  const qs = new URLSearchParams();
  if (params.q) qs.set('q', params.q);
  if (params.product_type) qs.set('product_type', params.product_type);
  const resp = await apiClient.get<KindListResponse>(
    `/api/v1/workflow-kinds${qs.toString() ? `?${qs.toString()}` : ''}`
  );
  return resp.data?.kinds ?? [];
}
