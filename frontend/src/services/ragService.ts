/**
 * RAG Ingest Service — Frontend API client for RAG documentation ingestion.
 *
 * Provides typed methods for index health monitoring, triggering ingestion
 * jobs, and polling job status.  All endpoints are under the
 * ``/api/v1/rag/*`` prefix.
 */

import { apiClient } from './apiClient';
import type { ApiResponse } from '../types';

// ─── Type Definitions ─────────────────────────────────────────────────────────

export interface RagHealthConfig {
  ingestion_dirs: string[];
  /** The `embeddings` capability's model, or null when the install has configured none. */
  embedding_model: string | null;
  /** The width the INDEX was created at, read from the index file — null when there is no index yet. */
  index_width?: number | null;
  /** What the stores IN THIS PROCESS were built with — what is actually embedding right now. */
  running_model?: string | null;
  running_address?: string | null;
  /**
   * The sentence to show when a saved model cannot fit the index — the width mismatch, which the
   * store reset (the capability write) cannot repair: only a re-ingest can. Null when they agree.
   */
  note?: string | null;
  /** The provider row's endpoint, or null when no row declares one (the app reports, never guesses). */
  ollama_base_url: string | null;
}

export interface RagStatusResponse {
  indexed_documents: number;
  total_chunks: number;
  last_indexed: string | null;
  database_path: string;
  database_size_bytes: number;
  config: RagHealthConfig;
}

export interface IngestRequest {
  mode: 'incremental' | 'full' | 'force-reingest';
  index_type?: 'docs' | 'code';
  /** The roots to walk; omitted means the app's own six. */
  dirs?: string[];
}

export interface IngestResponse {
  job_id: string;
  status: string;
  mode: string;
  started_at: string;
}

export interface IngestProgress {
  files_discovered: number;
  files_processed: number;
  files_failed: number;
  /** Chunks the INDEX holds from this run — moves when a document commits. */
  total_chunks: number;
  /** Chunks attempted so far — moves per chunk, which is what makes a card look alive. */
  chunks_done: number;
  /** The document being indexed right now. */
  current_file: string;
  elapsed_seconds: number;
}

export interface IngestResult {
  files_discovered: number;
  files_processed: number;
  files_failed: number;
  total_chunks: number;
  stale_removed: number;
  elapsed_seconds: number;
  /** Seconds per chunk THIS run measured — the rate the estimate prices with. */
  s_per_chunk: number | null;
}

export interface IngestEstimateRow {
  dir: string;
  files: number;
  bytes: number;
  chunks: number;
  minutes: number;
}

export interface IngestEstimate {
  dirs: IngestEstimateRow[];
  total: { files: number; bytes: number; chunks: number; minutes: number };
  /** The seconds-per-chunk the minutes are built on. */
  rate_s_per_chunk: number;
  /** 'last run' or a default — said out loud so a guess is never mistaken for a measurement. */
  rate_source: string;
  chars_per_chunk: number;
  estimated: true;
}

export interface IngestJobStatusResponse {
  job_id: string;
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  mode: string;
  /** The roots this run was given. */
  dirs: string[];
  /** The process doing the work. */
  pid: number | null;
  started_at: string;
  completed_at: string | null;
  error: string | null;
  progress: IngestProgress | null;
  result: IngestResult | null;
}

// ─── Service ──────────────────────────────────────────────────────────────────

export const ragService = {
  /**
   * Get RAG index health statistics.
   *
   * Queries the vector index for document count, chunk count, last indexed
   * timestamp, and database file size.  Also exposes the current
   * embedding/indexing configuration.
   */
  async getStatus(): Promise<ApiResponse<RagStatusResponse>> {
    return apiClient.get<RagStatusResponse>('/api/v1/rag/status');
  },

  /**
   * Trigger a RAG documentation ingestion job.
   *
   * Runs ingestion in the background.  Returns a ``job_id`` for polling
   * progress via ``getIngestJobStatus()``.
   *
   * @param mode  Ingestion mode:
   *   - ``incremental`` — only re-index modified files (default).
   *   - ``full`` — re-process all discovered files.
   *   - ``force-reingest`` — bypass incremental checks.
   * @param index_type  Which index to rebuild (default ``"docs"``).
   */
  async triggerIngest(
    mode: IngestRequest['mode'] = 'incremental',
    index_type: IngestRequest['index_type'] = 'docs',
    dirs?: string[],
  ): Promise<ApiResponse<IngestResponse>> {
    return apiClient.post<IngestResponse>('/api/v1/rag/ingest', {
      mode,
      index_type,
      ...(dirs && dirs.length > 0 ? { dirs } : {}),
    });
  },

  /** What a run over these roots would cost — counted files, estimated chunks and minutes. */
  async estimateIngest(dirs?: string[]): Promise<ApiResponse<IngestEstimate>> {
    return apiClient.post<IngestEstimate>('/api/v1/rag/ingest/estimate', {
      ...(dirs && dirs.length > 0 ? { dirs } : {}),
    });
  },

  /** Stop the running job (the child is signalled; the record follows). */
  async cancelIngest(): Promise<
    ApiResponse<{ cancelled: boolean; status: string; job_id?: string; message?: string }>
  > {
    return apiClient.post('/api/v1/rag/ingest/cancel', {});
  },

  /** Empty the index — every chunk and every vector. Refused while a job runs. */
  async clearIndex(): Promise<ApiResponse<{ cleared: boolean; documents: number; chunks: number }>> {
    return apiClient.post('/api/v1/rag/index/clear', {});
  },

  /**
   * Poll the current ingest job's status.
   *
   * Call every 2-3 seconds while the status is ``"running"`` to track
   * progress.  Once the status transitions to ``"completed"`` or
   * ``"failed"``, stop polling.
   *
   * Returns ``404`` if no ingest job has been started yet — the caller
   * should handle this case gracefully.
   */
  async getIngestJobStatus(): Promise<ApiResponse<IngestJobStatusResponse>> {
    return apiClient.get<IngestJobStatusResponse>(
      '/api/v1/rag/ingest/status',
    );
  },
};

export default ragService;
