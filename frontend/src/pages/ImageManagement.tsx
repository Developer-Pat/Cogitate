/**
 * ImageManagement — application image assets (Utilities section).
 *
 * Grid of image assets with usage info (which agents reference
 * them), upload, delete (blocked when in use), import (zip) and
 * export (zip download). Images-only scope per the
 * asset-management roadmap Phase 1.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Image as ImageIcon } from 'lucide-react';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { usePageTitle } from '../hooks/usePageTitle';
import { PageBanner } from '../components/ui/PageBanner';
import { imageService, type ImageAsset } from '../services/domains/llm/imageService';
import { useNotificationStore } from '../stores/notificationStore';
import { HelpButton } from '../components/help';

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

export default function ImageManagement() {
  usePageTitle('Image Management', 'Application image assets — upload, browse, delete, import/export');

  const [images, setImages] = useState<ImageAsset[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [curatedFilter, setCuratedFilter] = useState<'all' | 'true' | 'false'>('all');
  const [sortBy, setSortBy] = useState<'filename' | 'size' | 'created_at' | 'mime'>('filename');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [page, setPage] = useState(1);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkModalOpen, setBulkModalOpen] = useState(false);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [bulkUploading, setBulkUploading] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [restoreModalOpen, setRestoreModalOpen] = useState(false);
  const [stripMeta, setStripMeta] = useState(true);
  const uploadRef = useRef<HTMLInputElement>(null);
  const importRef = useRef<HTMLInputElement>(null);
  const { addSuccess, addError } = useNotificationStore();

  const PAGE_SIZE = 50;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await imageService.listImages(page, PAGE_SIZE, curatedFilter, sortBy, sortDir);
      setImages(resp.images);
      setTotal(resp.total);
    } catch (err) {
      addError('Images', 'Failed to load images');
      console.error('ImageManagement load:', err);
    } finally {
      setLoading(false);
    }
  }, [page, curatedFilter, sortBy, sortDir, addError]);

  useEffect(() => { load(); }, [load]);

  const filtered = search.trim()
    ? images.filter((i) => i.filename.toLowerCase().includes(search.toLowerCase()))
    : images;

  const handleUpload = async (files: File[]) => {
    if (files.length === 0) return;
    setBulkUploading(true);
    try {
      const result = await imageService.uploadImagesBulk(files, stripMeta);
      const ok = result.total_added;
      const bad = result.total_errors;
      if (ok > 0) addSuccess('Images', `Uploaded ${ok} image${ok === 1 ? '' : 's'}${stripMeta ? ' (metadata stripped)' : ' (metadata kept)'}${bad > 0 ? `, ${bad} skipped` : ''}`);
      if (bad > 0) {
        const reasons = result.errors.map((e) => `${e.filename}: ${e.reason}`).join('; ');
        addError('Images', `${bad} file${bad === 1 ? '' : 's'} failed — ${reasons}`);
      }
      load();
    } catch (err) {
      addError('Images', 'Upload failed');
      console.error('ImageManagement upload:', err);
    } finally {
      setBulkUploading(false);
    }
  };

  const handleDelete = async (img: ImageAsset) => {
    if (!window.confirm(`Delete ${img.filename}? This cannot be undone.`)) return;
    setDeleting(img.filename);
    try {
      await imageService.deleteImage(img.filename);
      addSuccess('Images', `Deleted ${img.filename}`);
      load();
    } catch (err) {
      addError('Images', 'Delete failed — is it in use by an agent?');
      console.error('ImageManagement delete:', err);
    } finally {
      setDeleting(null);
    }
  };

  const toggleSort = (col: 'filename' | 'size' | 'created_at' | 'mime') => {
    // read current state from the closure — no side effects inside
    // state updaters (React may drop them; StrictMode double-invokes)
    if (sortBy === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(col);
      setSortDir('asc');
    }
    setPage(1);
    setSelectedIds(new Set());
  };

  const SortHeader = ({ col, children }: { col: 'filename' | 'size' | 'created_at' | 'mime'; children: React.ReactNode }) => (
    <th>
      <button
        type="button"
        className="btn btn-ghost btn-xs px-1 font-semibold normal-case tooltip tooltip-top"
        data-tip={`Sort by ${col}`}
        onClick={() => toggleSort(col)}
      >
        {children}
        {sortBy === col ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
      </button>
    </th>
  );

  const toggleSelect = (filename: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename);
      else next.add(filename);
      return next;
    });
  };

  const toggleSelectAll = () => {
    setSelectedIds((prev) => {
      const all = filtered.map((i) => i.filename);
      const allSelected = all.length > 0 && all.every((f) => prev.has(f));
      return allSelected ? new Set() : new Set(all);
    });
  };

  const handleBulkDelete = async () => {
    const ids = Array.from(selectedIds);
    setBulkDeleting(true);
    try {
      const result = await imageService.batchDelete(ids);
      const ok = result.total_deleted;
      const bad = result.total_failed;
      if (ok > 0) addSuccess('Images', `Deleted ${ok} image${ok === 1 ? '' : 's'}`);
      if (bad > 0) {
        const inUse = result.failed.filter((f) => f.reason.includes('in use'));
        const other = result.failed.filter((f) => !f.reason.includes('in use'));
        if (inUse.length > 0) addError('Images', `${inUse.length} in use by agents — unassign first`);
        if (other.length > 0) addError('Images', `${other.length} could not be deleted`);
        console.error('ImageManagement bulk delete failed:', result.failed);
      }
      setSelectedIds(new Set());
      setBulkModalOpen(false);
      load();
    } catch (err) {
      addError('Images', 'Bulk delete failed');
      console.error('ImageManagement bulk delete:', err);
    } finally {
      setBulkDeleting(false);
    }
  };

  const handleRestoreCurated = async () => {
    setRestoring(true);
    try {
      const result = await imageService.restoreCurated();
      const n = result.restored.length;
      addSuccess('Images', n > 0 ? `Restored ${n} curated image${n === 1 ? '' : 's'}` : 'Curated set already complete');
      setRestoreModalOpen(false);
      load();
    } catch (err) {
      addError('Images', 'Restore failed');
      console.error('ImageManagement restore:', err);
    } finally {
      setRestoring(false);
    }
  };

  const handleImport = async (file: File) => {
    try {
      const result = await imageService.importZip(file, stripMeta);
      const stripped = (result as unknown as { stripped_count?: number }).stripped_count ?? 0;
      addSuccess('Images', `Imported ${result.added_count} images${stripMeta && stripped > 0 ? ` (${stripped} metadata stripped)` : ''}${result.errors.length ? ` (${result.errors.length} errors)` : ''}`);
      load();
    } catch (err) {
      addError('Images', 'Import failed — not a valid zip?');
      console.error('ImageManagement import:', err);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const resp = await fetch('/api/v1/images/export', { method: 'POST' });
      if (!resp.ok) throw new Error(`export ${resp.status}`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'cogitate-images.zip';
      a.click();
      URL.revokeObjectURL(url);
      addSuccess('Images', `Exported ${total} images`);
    } catch (err) {
      addError('Images', 'Export failed');
      console.error('ImageManagement export:', err);
    } finally {
      setExporting(false);
    }
  };

  return (
    <ErrorBoundary>
      <div className="p-6 max-w-7xl mx-auto">
        <PageBanner
          title="Image Management"
          className="mb-8"
          tooltip="Application image assets — upload, browse, delete, import/export. Images in use by agents are protected from deletion."
          action={
            <div className="flex items-center gap-2">
              <input
                ref={uploadRef}
                type="file"
                accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml"
                multiple
                className="hidden"
                onChange={(e) => { const fs = e.target.files ? Array.from(e.target.files) : []; if (fs.length) handleUpload(fs); e.target.value = ''; }}
              />
              <input
                ref={importRef}
                type="file"
                accept=".zip"
                className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImport(f); e.target.value = ''; }}
              />
              <button className="btn btn-sm btn-transfer btn-outline tooltip tooltip-bottom" data-tip="Import a zip of images (bulk add)" onClick={() => importRef.current?.click()}>
                Import
              </button>
              <button className="btn btn-sm btn-transfer btn-outline tooltip tooltip-bottom" data-tip="Download all images as a zip" onClick={handleExport} disabled={exporting || total === 0}>
                {exporting ? 'Exporting…' : 'Export'}
              </button>
              <button className="btn btn-sm btn-primary tooltip tooltip-bottom" data-tip="Upload one or more images (Ctrl/Cmd+click to select many)" onClick={() => uploadRef.current?.click()} disabled={bulkUploading}>
                {bulkUploading ? 'Uploading…' : 'Upload'}
              </button>
              <label className="flex items-center gap-2 text-xs cursor-pointer select-none tooltip tooltip-bottom" data-tip="Remove hidden image details (camera info, generation workflow) on upload">
                <input
                  type="checkbox"
                  className="toggle toggle-primary toggle-sm"
                  checked={stripMeta}
                  onChange={(e) => setStripMeta(e.target.checked)}
                />
                Strip metadata
              </label>
              <button className="btn btn-sm btn-outline tooltip tooltip-bottom" data-tip="Re-copy the curated images that ship with the app (your uploads are untouched)" onClick={() => setRestoreModalOpen(true)} disabled={restoring}>
                {restoring ? 'Restoring…' : 'Restore curated'}
              </button>
              <HelpButton context="image-management" tooltipPosition="bottom" />
            </div>
          }
        />

        <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
          <div className="card-body gap-[var(--card-gap)]">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h2 className="card-title">Images</h2>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Search filename…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="input input-bordered input-sm w-56"
                />
                <select
                  className="select select-bordered select-sm tooltip tooltip-top"
                  value={curatedFilter}
                  onChange={(e) => { setCuratedFilter(e.target.value as 'all' | 'true' | 'false'); setPage(1); setSelectedIds(new Set()); }}
                  data-tip="Filter by curated status"
                >
                  <option value="all">All</option>
                  <option value="true">Curated</option>
                  <option value="false">Uploads</option>
                </select>
                <span className="text-sm text-readout">{total} total</span>
              </div>
            </div>

            {selectedIds.size > 0 && (
              <div className="flex items-center gap-3 py-2 px-3 bg-primary/10 rounded-lg">
                <span className="text-sm font-medium">{selectedIds.size} selected</span>
                <button
                  className="btn btn-xs btn-error"
                  onClick={() => setBulkModalOpen(true)}
                >
                  Delete selected
                </button>
                <button className="btn btn-xs btn-outline" onClick={() => setSelectedIds(new Set())}>
                  Clear
                </button>
              </div>
            )}

            {loading ? (
              <p className="text-sm text-readout">Loading images…</p>
            ) : filtered.length === 0 ? (
              <div className="text-center py-8 opacity-70">
                <div className="text-4xl mb-2 text-readout">
                  <ImageIcon className="h-10 w-10 mx-auto" />
                </div>
                <div>{total === 0 ? 'No images yet — upload one to get started.' : 'No images match the search.'}</div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="table table-zebra w-full">
                  <thead>
                    <tr>
                      <th className="w-8">
                        <div className="tooltip tooltip-bottom" data-tip="Select all shown">
                          <input
                            type="checkbox"
                            className="checkbox checkbox-sm checkbox-primary"
                            checked={filtered.length > 0 && filtered.every((i) => selectedIds.has(i.filename))}
                            onChange={toggleSelectAll}
                            aria-label="Select all shown"
                          />
                        </div>
                      </th>
                      <th>Preview</th>
                      <SortHeader col="filename">Filename</SortHeader>
                      <SortHeader col="size">Size</SortHeader>
                      <SortHeader col="mime">Type</SortHeader>
                      <th>Used By</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((img) => (
                      <tr key={img.filename} className={selectedIds.has(img.filename) ? 'bg-base-300/40' : ''}>
                        <td>
                          <input
                            type="checkbox"
                            className="checkbox checkbox-sm checkbox-primary"
                            checked={selectedIds.has(img.filename)}
                            onChange={() => toggleSelect(img.filename)}
                            aria-label={`Select ${img.filename}`}
                          />
                        </td>
                        <td>
                          <div className="w-12 h-12 bg-base-300/40 rounded-md overflow-hidden flex items-center justify-center">
                            <img src={img.url} alt={img.filename} className="max-h-full max-w-full object-contain" loading="lazy" />
                          </div>
                        </td>
                        <td className="font-mono text-xs">{img.filename}</td>
                        <td className="text-sm text-readout">{formatSize(img.size)}</td>
                        <td className="text-sm">
                          {img.mime.replace('image/', '')}
                          {img.is_curated && (
                            <span className="ml-1 badge badge-sm badge-primary badge-outline">curated</span>
                          )}
                        </td>
                        <td>
                          {img.used_by.length > 0 ? (
                            <span className="badge badge-sm badge-success badge-outline">agent {img.used_by.join(', ')}</span>
                          ) : (
                            <span className="badge badge-sm badge-ghost">unused</span>
                          )}
                        </td>
                        <td>
                          <div className="tooltip tooltip-left" data-tip="Delete image">
                            <button
                              className="btn btn-xs btn-ghost btn-error"
                              onClick={() => handleDelete(img)}
                              disabled={deleting === img.filename}
                              aria-label={`Delete ${img.filename}`}
                            >
                              {deleting === img.filename ? '…' : '✕'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {total > PAGE_SIZE && (
              <div className="flex items-center justify-between mt-2">
                <span className="text-sm text-readout">{total} images</span>
                <div className="join">
                  <div className="tooltip tooltip-top" data-tip="Previous page">
                    <button className="join-item btn btn-sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} aria-label="Previous page">«</button>
                  </div>
                  <span className="join-item btn btn-sm btn-active btn-selected no-animation">{page}</span>
                  <div className="tooltip tooltip-top" data-tip="Next page">
                    <button className="join-item btn btn-sm" disabled={page * PAGE_SIZE >= total} onClick={() => setPage((p) => p + 1)} aria-label="Next page">»</button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {restoreModalOpen && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]" onClick={() => setRestoreModalOpen(false)}>
            <div className="bg-base-200 rounded-lg shadow-xl w-[var(--dialog-width-lg)] max-w-[90vw] mx-4" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between px-6 pt-5 pb-3">
                <h3 className="font-bold text-lg">Restore curated images?</h3>
                <button className="btn btn-ghost btn-sm" onClick={() => setRestoreModalOpen(false)} aria-label="Close">✕</button>
              </div>
              <div className="px-6 pb-2 text-sm opacity-80">
                <p>Re-copies the curated images that ship with the app (assets/agent-images/) into the store.</p>
                <p className="mt-1">Your uploads are untouched. Existing files are not overwritten.</p>
              </div>
              <div className="flex justify-end gap-2 border-t border-base-300 px-6 py-4">
                <button className="btn btn-neutral btn-ghost btn-sm" onClick={() => setRestoreModalOpen(false)}>Cancel</button>
                <button className="btn btn-primary btn-sm" onClick={handleRestoreCurated} disabled={restoring}>
                  {restoring ? 'Restoring…' : 'Restore'}
                </button>
              </div>
            </div>
          </div>
        )}

        {bulkModalOpen && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]" onClick={() => setBulkModalOpen(false)}>
            <div className="bg-base-200 rounded-lg shadow-xl w-[var(--dialog-width-lg)] max-w-[90vw] mx-4" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between px-6 pt-5 pb-3">
                <h3 className="font-bold text-lg">Delete {selectedIds.size} images?</h3>
                <button className="btn btn-ghost btn-sm" onClick={() => setBulkModalOpen(false)} aria-label="Close">✕</button>
              </div>
              <div className="px-6 pb-2 text-sm opacity-80">
                <p>These images will be permanently removed from the store.</p>
                <p className="mt-1">Images in use by an agent are skipped (unassign them first).</p>
              </div>
              <div className="flex justify-end gap-2 border-t border-base-300 px-6 py-4">
                <button className="btn btn-neutral btn-ghost btn-sm" onClick={() => setBulkModalOpen(false)}>Cancel</button>
                <button className="btn btn-error btn-sm" onClick={handleBulkDelete} disabled={bulkDeleting}>
                  {bulkDeleting ? 'Deleting…' : `Delete ${selectedIds.size}`}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
}
