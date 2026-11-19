/**
 * ProfileImagePicker — browse the image store (curated + uploads)
 * and pick a profile image. Replaces the bare URL field / upload-
 * only flow: the store is the single source of image truth.
 *
 * Modal, collection-style grid: curated images first (flagged),
 * then uploads. Selecting one sets the profile image URL.
 */

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { imageService, type ImageAsset } from '@/services/domains/llm/imageService';
import { frontendLoggingService } from '@/services/frontendLoggingService';

interface ProfileImagePickerProps {
  open: boolean;
  onClose: () => void;
  onSelect: (imageUrl: string) => void;
}

export default function ProfileImagePicker({ open, onClose, onSelect }: ProfileImagePickerProps) {
  const [images, setImages] = useState<ImageAsset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    imageService
      .listImages(1, 200)
      .then((resp) => setImages(resp.images))
      .catch((err) => {
        frontendLoggingService.error('ProfileImagePicker', 'Failed to load image store', err);
        setError('Could not load the image store. Try again later.');
      })
      .finally(() => setLoading(false));
  }, [open]);

  // Esc closes the picker (no accidental selection)
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  // Curated first, then uploads, then alphabetical
  const sorted = [...images].sort((a, b) => {
    if (a.is_curated && !b.is_curated) return -1;
    if (!a.is_curated && b.is_curated) return 1;
    return a.filename.localeCompare(b.filename);
  });

  const filtered = search.trim()
    ? sorted.filter((i) => i.filename.toLowerCase().includes(search.toLowerCase()))
    : sorted;

  return createPortal(
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]" onClick={onClose}>
      <div className="bg-base-200 rounded-lg shadow-xl w-[var(--dialog-width-lg)] max-w-[var(--dialog-width-full)] mx-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 pt-5">
          <div>
            <h3 className="font-bold text-lg">Choose an image</h3>
            <p className="text-sm text-readout mt-1">
              Browse the image store — curated images ship with the app; uploads are your own.
            </p>
          </div>
          <button className="btn btn-sm btn-ghost btn-circle" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="px-6 pt-3 flex items-center gap-3">
          <input
            type="text"
            placeholder="Search filename…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input input-bordered input-sm flex-1"
          />
          <button
            type="button"
            onClick={onClose}
            className="btn btn-ghost btn-sm text-error shrink-0"
          >
            Cancel
          </button>
        </div>

        <div className="px-6 py-4">
          {loading ? (
            <p className="text-sm text-readout text-center py-8">Loading images…</p>
          ) : error ? (
            <p className="text-sm text-error text-center py-8">{error}</p>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-readout text-center py-8">
              {images.length === 0 ? 'No images in the store yet — upload one from the Image Management page.' : 'No images match the search.'}
            </p>
          ) : (
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3">
              {filtered.map((img) => (
                <button
                  key={img.filename}
                  type="button"
                  onClick={() => onSelect(img.url)}
                  className="border rounded-lg p-2 text-left hover:border-primary hover:bg-base-200/50 transition-colors flex flex-col"
                  title={img.filename}
                >
                  <div className="aspect-square bg-base-300/40 rounded-md overflow-hidden flex items-center justify-center mb-1">
                    <img src={img.url} alt={img.filename} className="max-h-full max-w-full object-contain" loading="lazy" />
                  </div>
                  <div className="text-xs font-mono truncate" title={img.filename}>{img.filename}</div>
                  {img.is_curated && (
                    <span className="text-[10px] text-primary font-semibold uppercase">curated</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-base-300 px-6 py-4">
          <button className="btn btn-neutral btn-ghost btn-sm" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
