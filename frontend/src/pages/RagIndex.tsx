import React, { useState, useEffect, useCallback, useRef } from 'react';
import { PageBanner } from '../components/ui/PageBanner';
import { PageContainer } from '../components/ui/PageContainer';
import { usePageTitle } from '../hooks/usePageTitle';
import { ragService } from '../services/ragService';
import { useNotifications } from '../hooks/useNotifications';

import type { RagStatusResponse, IngestJobStatusResponse } from '../services/ragService';

/**
 * RAG Index — the retrieval-augmented-generation index: health,
 * ingestion triggers, job status, and configuration.
 *
 * Extracted from the System Information page (2026-08-16, pre-push
 * Phase C): the RAG controls are the product-relevant part of that
 * page; the system-monitoring surface was removed.
 */

const RagIndex: React.FC = () => {
  usePageTitle('RAG Index', 'Manage the retrieval index and ingest jobs')

  const [ragStatus, setRagStatus] = useState<RagStatusResponse | null>(null);
  const [ragStatusLoading, setRagStatusLoading] = useState(false);
  const [ragStatusError, setRagStatusError] = useState<string | null>(null);
  const [ingestJobStatus, setIngestJobStatus] = useState<IngestJobStatusResponse | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [selectedMode, setSelectedMode] = useState<'incremental' | 'full' | 'force-reingest'>('incremental');
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const { notifySuccess, notifyError } = useNotifications();

  /** Fetch index health stats on mount. */
  const fetchRagStatus = useCallback(async () => {
    setRagStatusLoading(true);
    setRagStatusError(null);
    const res = await ragService.getStatus();
    if (res.error) {
      setRagStatusError(res.error.message);
    } else if (res.data) {
      setRagStatus(res.data);
    }
    setRagStatusLoading(false);
  }, []);

  /** Poll the ingest job status every 2.5 s while a job is running. */
  const startPolling = useCallback(() => {
    if (pollingRef.current) return;
    setIsPolling(true);
    pollingRef.current = setInterval(async () => {
      const res = await ragService.getIngestJobStatus();
      if (res.error) {
        if (res.status === 404) {
          setIngestJobStatus(null);
        }
        return;
      }
      if (res.data) {
        setIngestJobStatus(res.data);
        if (res.data.status !== 'running') {
          stopPolling();
        }
      }
    }, 2500);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    setIsPolling(false);
  }, []);

  // Fetch rag status + job status on mount (resume polling if running)
  useEffect(() => {
    fetchRagStatus();
    ragService.getIngestJobStatus().then((res) => {
      if (res.data) {
        setIngestJobStatus(res.data);
        if (res.data.status === 'running') {
          startPolling();
        }
      }
    });
    return () => {
      stopPolling();
    };
  }, [fetchRagStatus, startPolling, stopPolling]);

  /** Trigger a new ingest job. */
  const handleTriggerIngest = async () => {
    setIsTriggering(true);
    const res = await ragService.triggerIngest(selectedMode);
    if (res.error) {
      if (res.status === 409) {
        notifyError('Ingest Conflict', 'An ingest job is already running.');
      } else {
        notifyError('Ingest Failed', res.error.message);
      }
      setIsTriggering(false);
      return;
    }
    if (res.data) {
      setIngestJobStatus({
        job_id: res.data.job_id,
        status: 'running',
        mode: res.data.mode,
        started_at: res.data.started_at,
        completed_at: null,
        error: null,
        progress: null,
        result: null,
      });
      notifySuccess('Ingest Started', `Job ${res.data.job_id} — ${res.data.mode} mode`);
      startPolling();
    }
    setIsTriggering(false);
  };

  /** Format a byte count as a human-readable string. */
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  };

  return (
    <PageContainer>
      <PageBanner
        title="RAG Index"
        subtitle="Manage the retrieval index and ingest jobs"
      />
      <div className="space-y-6">
        {/* Index Health Card */}
        <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
          <div className="card-body gap-[var(--card-gap)]">
            <h2 className="card-title">📚 RAG Index Health</h2>

            {ragStatusLoading ? (
              <div className="flex items-center justify-center py-8">
                <span className="loading loading-spinner loading-lg"></span>
              </div>
            ) : ragStatusError ? (
              <div className="alert alert-error">
                <span>Failed to load RAG index health: {ragStatusError}</span>
              </div>
            ) : ragStatus ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-readout">Indexed Documents</span>
                    <span className="font-semibold text-lg">{ragStatus.indexed_documents}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-readout">Total Chunks</span>
                    <span className="font-semibold text-lg">{ragStatus.total_chunks}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-readout">Last Indexed</span>
                    <span className="font-medium">
                      {ragStatus.last_indexed
                        ? new Date(ragStatus.last_indexed).toLocaleString()
                        : 'Never'}
                    </span>
                  </div>
                </div>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-readout">Database Path</span>
                    <span className="font-mono text-xs truncate max-w-[200px]" title={ragStatus.database_path}>
                      {ragStatus.database_path || 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-readout">Database Size</span>
                    <span className="font-medium">{formatBytes(ragStatus.database_size_bytes)}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-readout">Embedding Model</span>
                    <span className="badge badge-outline">{ragStatus.config?.embedding_model || 'N/A'}</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-readout">
                No index data available. Trigger an ingestion to get started.
              </div>
            )}
          </div>
        </div>

        {/* Trigger Ingestion */}
        <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
          <div className="card-body gap-[var(--card-gap)]">
            <h2 className="card-title">⚡ Trigger Ingestion</h2>

            <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-end">
              <div className="form-control w-full sm:w-auto">
                <label className="label">
                  <span className="label-text">Mode</span>
                </label>
                <select
                  className="select select-bordered w-full sm:w-48"
                  value={selectedMode}
                  onChange={(e) => setSelectedMode(e.target.value as typeof selectedMode)}
                  disabled={isTriggering || isPolling}
                >
                  <option value="incremental">Incremental</option>
                  <option value="full">Full</option>
                  <option value="force-reingest">Force Re-ingest</option>
                </select>
              </div>

              <button
                onClick={handleTriggerIngest}
                disabled={isTriggering || isPolling}
                className="btn btn-primary rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
              >
                {isTriggering ? (
                  <>
                    <span className="loading loading-spinner loading-sm"></span>
                    Starting...
                  </>
                ) : (
                  <>Start Ingestion</>
                )}
              </button>

              {isPolling && (
                <div className="flex items-center gap-2 text-sm text-readout">
                  <span className="loading loading-spinner loading-xs"></span>
                  Polling for updates...
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Job Status Indicator */}
        <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
          <div className="card-body gap-[var(--card-gap)]">
            <h2 className="card-title">Ingest Job Status</h2>

            {!ingestJobStatus ? (
              <div className="text-center py-8 text-readout">
                No ingest job has been started yet.
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`badge badge-lg gap-2 ${
                      ingestJobStatus.status === 'running' ? 'badge-info' :
                      ingestJobStatus.status === 'completed' ? 'badge-success' :
                      'badge-error'
                    }`}>
                      {ingestJobStatus.status === 'running' && (
                        <span className="loading loading-spinner loading-xs"></span>
                      )}
                      {ingestJobStatus.status.toUpperCase()}
                    </span>
                    <span className="font-mono text-xs text-readout">{ingestJobStatus.job_id}</span>
                  </div>
                  <span className="text-sm text-readout">
                    Mode: <span className="badge badge-ghost badge-sm">{ingestJobStatus.mode}</span>
                  </span>
                </div>

                {ingestJobStatus.status === 'running' && ingestJobStatus.progress && (
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                      <div className="stat p-2 bg-base-200 rounded-box">
                        <div className="stat-title text-xs">Discovered</div>
                        <div className="stat-value text-lg">{ingestJobStatus.progress.files_discovered}</div>
                      </div>
                      <div className="stat p-2 bg-base-200 rounded-box">
                        <div className="stat-title text-xs">Processed</div>
                        <div className="stat-value text-lg">{ingestJobStatus.progress.files_processed}</div>
                      </div>
                      <div className="stat p-2 bg-base-200 rounded-box">
                        <div className="stat-title text-xs">Failed</div>
                        <div className="stat-value text-lg">{ingestJobStatus.progress.files_failed}</div>
                      </div>
                      <div className="stat p-2 bg-base-200 rounded-box">
                        <div className="stat-title text-xs">Chunks</div>
                        <div className="stat-value text-lg">{ingestJobStatus.progress.total_chunks}</div>
                      </div>
                    </div>
                    <div className="text-xs text-readout text-right">
                      Elapsed: {ingestJobStatus.progress.elapsed_seconds.toFixed(1)}s
                    </div>
                  </div>
                )}

                {ingestJobStatus.status === 'completed' && ingestJobStatus.result && (
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-sm">
                      <div className="stat p-2 bg-base-200 rounded-box">
                        <div className="stat-title text-xs">Discovered</div>
                        <div className="stat-value text-lg">{ingestJobStatus.result.files_discovered}</div>
                      </div>
                      <div className="stat p-2 bg-base-200 rounded-box">
                        <div className="stat-title text-xs">Processed</div>
                        <div className="stat-value text-lg">{ingestJobStatus.result.files_processed}</div>
                      </div>
                      <div className="stat p-2 bg-base-200 rounded-box">
                        <div className="stat-title text-xs">Failed</div>
                        <div className="stat-value text-lg">{ingestJobStatus.result.files_failed}</div>
                      </div>
                      <div className="stat p-2 bg-base-200 rounded-box">
                        <div className="stat-title text-xs">Chunks</div>
                        <div className="stat-value text-lg">{ingestJobStatus.result.total_chunks}</div>
                      </div>
                      <div className="stat p-2 bg-base-200 rounded-box">
                        <div className="stat-title text-xs">Stale Removed</div>
                        <div className="stat-value text-lg">{ingestJobStatus.result.stale_removed}</div>
                      </div>
                    </div>
                    <div className="text-xs text-readout text-right">
                      Completed in {ingestJobStatus.result.elapsed_seconds.toFixed(1)}s
                    </div>
                    {ingestJobStatus.completed_at && (
                      <div className="text-xs text-readout text-right">
                        Finished at: {new Date(ingestJobStatus.completed_at).toLocaleString()}
                      </div>
                    )}
                  </div>
                )}

                {ingestJobStatus.status === 'failed' && (
                  <div className="alert alert-error">
                    <div>
                      <div className="font-bold">Ingestion Failed</div>
                      <div className="text-sm">{ingestJobStatus.error || 'Unknown error'}</div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* WHAT A SAVE CANNOT FIX — the embedding-configuration ruling, options C then A (2026-10-12).
            The capability write resets the stores, so a saved model DOES reach the process on its next
            use; what it cannot fix is the INDEX's width, because an index keeps the width it was
            created at — a model of another width needs a re-ingest. The backend composes the sentence
            (`configuration_note`); this only shows it. */}
        {ragStatus?.config?.note && (
          <div className="alert alert-warning mb-4" role="status">
            <span className="text-sm">{ragStatus.config.note}</span>
          </div>
        )}

        {/* Configuration Display */}
        {ragStatus?.config && (
          <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
            <div className="card-body gap-[var(--card-gap)]">
              <h2 className="card-title">⚙️ Configuration</h2>
              <div className="space-y-3 text-sm">
                <div>
                  <span className="text-readout">Ingestion Directories</span>
                  <ul className="list-disc list-inside mt-1 space-y-1">
                    {ragStatus.config.ingestion_dirs.map((dir, i) => (
                      <li key={i} className="font-mono text-xs">{dir}</li>
                    ))}
                  </ul>
                </div>
                <div className="flex justify-between">
                  <span className="text-readout">Ollama Base URL</span>
                  <span className="font-mono text-xs">
                    {ragStatus.config.ollama_base_url || 'no provider row declares one'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-readout">Index Width</span>
                  <span className="font-mono text-xs">
                    {ragStatus.config.index_width
                      ? `${ragStatus.config.index_width} — what the index was built at`
                      : 'no index yet'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-readout">Running Model</span>
                  <span className="font-mono text-xs">
                    {ragStatus.config.running_model || 'nothing loaded in this process yet'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </PageContainer>
  );
};

export default RagIndex;
