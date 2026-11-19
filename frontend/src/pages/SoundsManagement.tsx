import { useCallback, useEffect, useRef, useState } from 'react';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { usePageTitle } from '../hooks/usePageTitle';
import { PageBanner } from '../components/ui/PageBanner';
import { HelpButton } from '../components/help';
import { soundsService, type SoundAsset } from '../services/domain/soundsService';
import { useNotificationStore } from '../stores/notificationStore';

const PAGE_SIZE = 50;

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Sounds — the notification-sound assets (Assets section).
 *
 * The wav-assets catalog (the images-store pattern): upload / browse /
 * delete / restore-curated + the play-preview, and the notification-
 * sound picker (the selectable/configurable surface): the audio-ping
 * toggle + the selected sound -> the notifications config.
 */
export function SoundsManagement() {
  usePageTitle('Sounds', 'Notification-sound assets — upload, browse, preview, and pick the toast sound.');
  const { addSuccess, addError } = useNotificationStore();

  const [sounds, setSounds] = useState<SoundAsset[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [curatedFilter, setCuratedFilter] = useState<'all' | 'true' | 'false'>('all');
  const [deleting, setDeleting] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(false);
  const [restoreModalOpen, setRestoreModalOpen] = useState(false);
  const [uploading, setUploading] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const playingRef = useRef<HTMLAudioElement | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await soundsService.listSounds(1, PAGE_SIZE, curatedFilter);
      setSounds(resp.sounds);
      setTotal(resp.total);
    } catch (err) {
      addError('Sounds', 'Failed to load sounds');
      console.error('SoundsManagement load:', err);
    } finally {
      setLoading(false);
    }
  }, [curatedFilter, addError]);

  useEffect(() => {
    load();
  }, [load]);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      for (const f of Array.from(files)) {
        if (!f.name.toLowerCase().endsWith('.wav')) {
          addError('Sounds', `${f.name}: WAV files only`);
          continue;
        }
        await soundsService.uploadSound(f);
        addSuccess('Sounds', `Uploaded ${f.name}`);
      }
      load();
    } catch (err) {
      addError('Sounds', 'Upload failed');
      console.error('SoundsManagement upload:', err);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (s: SoundAsset) => {
    setDeleting(s.filename);
    try {
      await soundsService.deleteSound(s.filename);
      addSuccess('Sounds', `Deleted ${s.filename}`);
      load();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      addError('Sounds', typeof detail === 'string' ? detail : `Delete failed: ${s.filename}`);
    } finally {
      setDeleting(null);
    }
  };

  const handleRestoreCurated = async () => {
    setRestoring(true);
    try {
      const r = await soundsService.restoreCurated();
      addSuccess(
        'Sounds',
        r.restored.length > 0 ? `Restored ${r.restored.length} curated sound${r.restored.length === 1 ? '' : 's'}` : 'All curated sounds present'
      );
      setRestoreModalOpen(false);
      load();
    } catch (err) {
      addError('Sounds', 'Restore failed');
      console.error('SoundsManagement restore:', err);
    } finally {
      setRestoring(false);
    }
  };

  const handlePlay = (s: SoundAsset) => {
    if (playingRef.current) playingRef.current.pause();
    const audio = new Audio(s.url);
    // THE CATALOG PREVIEW (2026-08-31, the Phase-3 split): the
    // volume config lives on the Notifications page now — the
    // catalog's audition plays at the full volume.
    audio.volume = 1;
    playingRef.current = audio;
    audio.play().catch(() => {
      // the autoplay policy can block the first play — the user's
      // interaction (the click) usually unlocks it; stay silent
    });
  };


  return (
    <ErrorBoundary>
      <div className="p-6 max-w-7xl mx-auto">
        <PageBanner
          title="Sounds"
          className="mb-6"
          tooltip="Notification-sound assets — upload, browse, preview, and pick the sound the toasts play. The configured notification sound is protected from deletion."
          action={
            <div className="flex items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept=".wav,audio/wav"
                multiple
                className="hidden"
                onChange={(e) => handleUpload(e.target.files)}
              />
              <button className="btn btn-sm btn-outline tooltip tooltip-bottom" data-tip="Re-copy the curated sounds that ship with the app" onClick={() => setRestoreModalOpen(true)}>
                Restore curated
              </button>
              <button className="btn btn-sm btn-primary tooltip tooltip-bottom" data-tip="Upload one or more WAV files" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
                {uploading ? 'Uploading…' : 'Upload WAV'}
              </button>
              <HelpButton context="sounds" tooltipPosition="bottom" />
            </div>
          }
        />

        <div className="card bg-base-100 shadow-md">
          <div className="card-body p-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="card-title text-sm">
                The catalog
                {total > 0 && <span className="badge badge-ghost badge-sm">{total}</span>}
              </h2>
              <div className="join join-sm">
                <button
                  className={`join-item btn btn-sm ${curatedFilter === 'all' ? 'btn-active btn-selected' : 'btn-outline'}`}
                  onClick={() => setCuratedFilter('all')}
                >
                  All
                </button>
                <button
                  className={`join-item btn btn-sm ${curatedFilter === 'true' ? 'btn-active btn-selected' : 'btn-outline'}`}
                  onClick={() => setCuratedFilter('true')}
                >
                  Curated
                </button>
                <button
                  className={`join-item btn btn-sm ${curatedFilter === 'false' ? 'btn-active btn-selected' : 'btn-outline'}`}
                  onClick={() => setCuratedFilter('false')}
                >
                  Uploads
                </button>
              </div>
            </div>

            {loading ? (
              <div className="text-sm opacity-70 py-4">Loading…</div>
            ) : sounds.length === 0 ? (
              <div className="text-sm opacity-70 py-4">
                No sounds yet — the curated set ships with the app (restore it) or upload a WAV.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="table table-sm">
                  <thead>
                    <tr>
                      <th>Play</th>
                      <th>Filename</th>
                      <th>Size</th>
                      <th>Source</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sounds.map((s) => (
                      <tr key={s.filename}>
                        <td>
                          <button
                            className="btn btn-xs btn-ghost tooltip tooltip-top"
                            data-tip={`Preview ${s.filename}`}
                            onClick={() => handlePlay(s)}
                          >
                            ▶
                          </button>
                        </td>
                        <td className="font-mono text-xs" title={s.filename}>
                          {s.filename}
                        </td>
                        <td className="text-sm text-readout">{formatSize(s.size)}</td>
                        <td>
                          {s.is_curated && (
                            <span className="mr-1 badge badge-sm badge-primary badge-outline" title="Ships with the app (assets/notification-sounds/)">
                              curated
                            </span>
                          )}
                          {s.is_configured && (
                            <span className="badge badge-sm badge-success badge-outline" title="The configured notification sound">
                              in use
                            </span>
                          )}
                        </td>
                        <td>
                          <button
                            className="btn btn-xs btn-ghost btn-error"
                            onClick={() => handleDelete(s)}
                            disabled={deleting === s.filename}
                          >
                            {deleting === s.filename ? '…' : '✕'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {restoreModalOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]"
          onClick={() => setRestoreModalOpen(false)}
        >
          <div
            className="bg-base-200 rounded-lg shadow-xl w-[var(--dialog-width-lg)] max-w-[90vw] mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 pt-5 pb-3">
              <h3 className="font-bold text-lg">Restore curated sounds?</h3>
              <button className="btn btn-ghost btn-sm" onClick={() => setRestoreModalOpen(false)}>
                ✕
              </button>
            </div>
            <div className="px-6 pb-2 text-sm opacity-80">
              <p>
                Re-copies the curated sounds that ship with the app (assets/notification-sounds/) into
                the store.
              </p>
              <p className="mt-1">Your uploads are untouched. Existing files are not overwritten.</p>
            </div>
            <div className="flex justify-end gap-2 border-t border-base-300 px-6 py-4">
              <button className="btn btn-neutral btn-ghost btn-sm" onClick={() => setRestoreModalOpen(false)}>
                Cancel
              </button>
              <button className="btn btn-primary btn-sm" onClick={handleRestoreCurated} disabled={restoring}>
                {restoring ? 'Restoring…' : 'Restore'}
              </button>
            </div>
          </div>
        </div>
      )}
    </ErrorBoundary>
  );
}

export default SoundsManagement;
