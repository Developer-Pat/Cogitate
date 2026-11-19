import { useEffect, useMemo, useState } from 'react';
import { usePageTitle } from '../hooks/usePageTitle';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { PageBanner } from '../components/ui/PageBanner';
import { soundsService, type SoundAsset } from '../services/domain/soundsService';
import { useNotificationConfigStore } from '../stores/notificationConfigStore';
import { useNotificationStore } from '../stores/notificationStore';
import { HelpButton } from '../components/help';
import { useMessageStore } from '../stores/messageStore';

// THE NOTIFICATIONS CONFIG PAGE (2026-08-31, the _27 Phase-3 build —
// the Configuration-nav roadmap): the config HALF of the Sounds page
// re-homed — the notification-sound config (the per-class pickers +
// the level + the volume) + the mute (the airplane-mode). The Sounds
// page keeps only the wav catalog.

export default function NotificationsConfigPage() {
  usePageTitle('Notifications', 'The notification-sound config + the mute — the per-class sounds, the level, the volume');

  const { config, load: loadConfig, update: updateConfig } = useNotificationConfigStore();
  const { addSuccess, addError } = useNotificationStore();

  // THE EVENTS TABLE (2026-08-31, the _27 Phase-3.5 build — the
  // user's events-table ask, shape 1): the catalog of the
  // configurable events. The class-rows ride the per-class config;
  // the SYSTEM-ROWS are DATA-DRIVEN — the message-store's distinct
  // (source, type) pairs (the records are the truth, the table's
  // the mirror; the new kinds appear as new rows automatically).
  // THE STABLE SELECTOR (2026-08-31, the getSnapshot crash): the
  // zustand selector must return a CACHED value — a fresh array
  // every snapshot is the infinite-loop error. The selector returns
  // the messages reference; the pairs derive via the useMemo.
  const messages = useMessageStore((s) => s.messages)
  const messagePairs = useMemo(() => {
    const seen = new Set<string>()
    const pairs: Array<{ source: string; type: string }> = []
    for (const m of messages) {
      const key = `${m.source}|${m.type}`
      if (!seen.has(key)) {
        seen.add(key)
        pairs.push({ source: m.source, type: m.type })
      }
    }
    return pairs
  }, [messages])

  // THE CLASS LABELS (the events' names for the class-rows).
  const CLASS_EVENTS: Array<{ key: 'success' | 'warning' | 'error' | 'info'; name: string; hint: string }> = [
    { key: 'success', name: 'Run complete', hint: 'The bell when a workflow terminates' },
    { key: 'warning', name: 'Alert', hint: 'The alert when a workflow aborts' },
    { key: 'error', name: 'Emergency', hint: 'The siren for the emergency class' },
    { key: 'info', name: 'Info (the chatter)', hint: 'The quiet class — silent by design' },
  ]

  const classSound = (key: string): string =>
    key === 'success' ? soundSuccess : key === 'warning' ? soundWarning : key === 'error' ? soundError : ''

  const [sounds, setSounds] = useState<SoundAsset[]>([]);
  const [audioEnabled, setAudioEnabled] = useState(false);
  const [savingConfig, setSavingConfig] = useState(false);
  const [volume, setVolume] = useState(1);
  const [soundLevel, setSoundLevel] = useState<'info' | 'success' | 'warning' | 'error'>('warning');
  const [soundSuccess, setSoundSuccess] = useState('');
  const [soundWarning, setSoundWarning] = useState('');
  const [soundError, setSoundError] = useState('');
  const [muteDuration, setMuteDuration] = useState<'30s' | '1h' | 'forever'>('1h');
  const [muting, setMuting] = useState(false);
  const [nowTick, setNowTick] = useState(Date.now());
  // THE PAGE TABS (2026-08-31, the user's ask): Config (the
  // notification-sound + the mute) vs Events (the events table).
  const [pageTab, setPageTab] = useState<'config' | 'events'>('config');

  const PAGE_SIZE = 100;

  const loadSounds = async () => {
    try {
      const resp = await soundsService.listSounds(1, PAGE_SIZE, 'all');
      setSounds(resp.sounds);
    } catch (err) {
      console.error('NotificationsConfigPage sounds:', err);
    }
  };

  useEffect(() => {
    loadConfig();
    loadSounds();
  }, [loadConfig]);

  useEffect(() => {
    if (config) {
      setAudioEnabled(config.audio_enabled);
      setVolume(config.volume ?? 1);
      setSoundLevel(config.sound_level ?? 'warning');
      setSoundSuccess(config.sound_success);
      setSoundWarning(config.sound_warning);
      setSoundError(config.sound_error);
    }
  }, [config]);

  // THE COUNTDOWN TICKER (the scheduled-mute): while muted with an
  // end, tick once a second so the resume countdown stays live.
  useEffect(() => {
    if (config?.suppressed !== true) return;
    const t = window.setInterval(() => setNowTick(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [config?.suppressed]);

  const muted = config?.suppressed === true;
  const muteEnds = config?.mute_until ?? null;
  const remainingMs = muteEnds ? Math.max(0, muteEnds * 1000 - nowTick) : null;

  const fmtRemaining = (ms: number) => {
    const s = Math.floor(ms / 1000);
    const m = Math.floor(s / 60);
    const h = Math.floor(m / 60);
    if (h > 0) return `${h}:${String(m % 60).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
    return `${m}:${String(s % 60).padStart(2, '0')}`;
  };

  const handleMute = async () => {
    const secs = muteDuration === '30s' ? 30 : muteDuration === '1h' ? 3600 : null;
    const label = muteDuration === '30s' ? '30 seconds' : muteDuration === '1h' ? '1 hour' : 'indefinitely';
    addSuccess('Notifications', `Muted ${label} — the message center keeps recording`);
    setMuting(true);
    try {
      await updateConfig({ suppressed: true, mute_until: secs ? Date.now() / 1000 + secs : null });
    } catch (err) {
      addError('Notifications', 'Failed to mute');
      console.error('NotificationsConfigPage mute:', err);
    } finally {
      setMuting(false);
    }
  };

  const handleRestoreNow = async () => {
    setMuting(true);
    try {
      await updateConfig({ suppressed: false });
      addSuccess('Notifications', 'Notifications back on');
    } catch (err) {
      addError('Notifications', 'Failed to restore');
      console.error('NotificationsConfigPage restore:', err);
    } finally {
      setMuting(false);
    }
  };

  const handleSaveConfig = async () => {
    setSavingConfig(true);
    try {
      await updateConfig({
        audio_enabled: audioEnabled,
        volume,
        sound_success: soundSuccess,
        sound_warning: soundWarning,
        sound_error: soundError,
        sound_level: soundLevel,
      });
      addSuccess('Notifications', 'Notification sound updated');
    } catch (err) {
      addError('Notifications', 'Failed to update the notification sound');
      console.error('NotificationsConfigPage save:', err);
    } finally {
      setSavingConfig(false);
    }
  };

  return (
    <ErrorBoundary>
      <div className="p-6 max-w-7xl mx-auto">
        <PageBanner
          title="Notifications"
          className="mb-6"
          tooltip="The notification-sound config (the per-class sounds, the level, the volume) + the mute (the airplane-mode)."
          action={<HelpButton context="notifications" tooltipPosition="bottom" />}
        />

        {/* THE PAGE TABS (2026-08-31, the user's ask) */}
        <div className="tabs tabs-box mb-4">
          <button
            className={`tab ${pageTab === 'config' ? 'tab-active' : ''}`}
            onClick={() => setPageTab('config')}
          >
            Config
          </button>
          <button
            className={`tab ${pageTab === 'events' ? 'tab-active' : ''}`}
            onClick={() => setPageTab('events')}
          >
            Events
          </button>
        </div>

        {pageTab === 'config' && (
        <>
        {/* THE NOTIFICATION-SOUND CONFIG — the card's top-right
            holds the TEMPORARY MUTE widget (2026-08-31, the user's
            ask: the text button + the duration selector to its
            right, the red). */}
        <div className="card bg-base-100 shadow-md mb-4">
          <div className="card-body p-4">
            <div className="flex items-center justify-between gap-3 mb-1">
              <h2 className="card-title text-sm">The notification sound</h2>
              {!muted ? (
                <div className="flex items-center gap-2">
                  <div className="tooltip tooltip-top" data-tip="Temporary Mute — the toasts hidden, the center keeps recording">
                  <button
                    type="button"
                    className="pill-button pill-button--warning"
                    onClick={handleMute}
                    disabled={muting}
                  >
                    {muting ? <span className="loading loading-spinner loading-xs" /> : 'Temporary Mute'}
                  </button>
                  </div>
                  <select
                    className="select select-sm select-bordered"
                    value={muteDuration}
                    onChange={(e) => setMuteDuration(e.target.value as '30s' | '1h' | 'forever')}
                    aria-label="Mute duration"
                  >
                    <option value="30s">30s</option>
                    <option value="1h">1h</option>
                    <option value="forever">∞</option>
                  </select>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <span className="badge badge-error badge-outline badge-sm">muted</span>
                  {remainingMs !== null && (
                    <span className="text-sm font-mono">{fmtRemaining(remainingMs)}</span>
                  )}
                  <button
                    type="button"
                    className="btn btn-sm btn-primary"
                    onClick={handleRestoreNow}
                    disabled={muting}
                  >
                    Restore
                  </button>
                </div>
              )}
            </div>
            <p className="text-xs opacity-70">
              Played when a toast fires (off by default — the audio-ping option).
            </p>
            <div className="flex flex-wrap items-center gap-4 mt-2">
              <div className="tooltip tooltip-top" data-tip="The audio-ping when a toast fires — the attention-worthy classes only">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    className="toggle toggle-primary toggle-sm"
                    checked={audioEnabled}
                    onChange={(e) => setAudioEnabled(e.target.checked)}
                  />
                  Play a sound with toasts
                </label>
              </div>
            </div>
            {/* THE PER-CLASS SOUNDS (2026-08-31, the ONE-place fix):
                the trio's home is the EVENTS table's rows — this
                card holds only the general sound + the level +
                the volume. */}
            <div className="flex flex-wrap items-center gap-4 mt-2">
              <div
                className="tooltip tooltip-top"
                data-tip="The sound LEVEL — the minimum class that pings (the run-complete bell is silent below the warning level)"
              >
              <label
                className="flex items-center gap-2 text-sm"
              >
                Sound level
                <select
                  className="select select-sm select-bordered"
                  value={soundLevel}
                  onChange={(e) => setSoundLevel(e.target.value as 'info' | 'success' | 'warning' | 'error')}
                >
                  <option value="error">error (the emergencies only)</option>
                  <option value="warning">warning (the alerts + the emergencies)</option>
                  <option value="success">success (the run-completes too)</option>
                  <option value="info">info (everything)</option>
                </select>
              </label>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-4 mt-2">
              <div className="tooltip tooltip-top" data-tip="The audio-ping's loudness (0-100%)">
              <label className="flex items-center gap-2 text-sm">
                Volume
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={Math.round(volume * 100)}
                  className="range range-primary range-xs w-32"
                  onChange={(e) => setVolume(Number(e.target.value) / 100)}
                />
                <span className="text-xs font-mono w-9">{Math.round(volume * 100)}%</span>
              </label>
              </div>
              <button
                className="btn btn-primary btn-sm"
                onClick={handleSaveConfig}
                disabled={savingConfig || sounds.length === 0}
              >
                {savingConfig ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>

        </>
        )}
        {pageTab === 'events' && (
        <>
        {/* THE EVENTS TABLE (2026-08-31, the _27 Phase-3.5 build):
            the catalog of the configurable notification events. The
            class-rows carry the pickers (the per-class config); the
            system-rows are the data-driven mirror of the message-
            center's records. */}
        <div className="card bg-base-100 shadow-md mb-4">
          <div className="card-body p-4">
            <h2 className="card-title text-sm">The events</h2>
            <p className="text-xs opacity-70">
              The configurable notification events — the class-rows ride the per-class
              sounds; the system-rows mirror the message-center's records (the new
              event kinds appear here automatically).
            </p>
            <div className="overflow-x-auto mt-2">
              <table className="table table-sm">
                <thead>
                  <tr>
                    <th>Event</th>
                    <th>Class</th>
                    <th>Sound</th>
                  </tr>
                </thead>
                <tbody>
                  {CLASS_EVENTS.map((ev) => (
                    <tr key={ev.key}>
                      <td>
                        <span className="font-medium">{ev.name}</span>
                        <div className="text-xs opacity-60">{ev.hint}</div>
                      </td>
                      <td>
                        <span className={`badge badge-sm ${ev.key === 'error' ? 'badge-error badge-outline' : ev.key === 'warning' ? 'badge-warning badge-outline' : ev.key === 'success' ? 'badge-success badge-outline' : 'badge-ghost'}`}>
                          {ev.key}
                        </span>
                      </td>
                      <td>
                        {ev.key === 'info' ? (
                          <span className="text-xs opacity-60">silent</span>
                        ) : (
                          <select
                            className="select select-xs select-bordered"
                            value={classSound(ev.key)}
                            onChange={(e) => {
                              const v = e.target.value
                              if (ev.key === 'success') setSoundSuccess(v)
                              else if (ev.key === 'warning') setSoundWarning(v)
                              else setSoundError(v)
                            }}
                            aria-label={`${ev.name} sound`}
                          >
                            <option value="">(none — silent)</option>
                            {sounds.map((s) => (
                              <option key={s.filename} value={s.filename}>
                                {s.filename}
                              </option>
                            ))}
                          </select>
                        )}
                      </td>
                    </tr>
                  ))}
                  {messagePairs.map((pair) => (
                    <tr key={`${pair.source}|${pair.type}`} className="opacity-80">
                      <td>
                        <span className="font-medium">{pair.source}</span>
                        <div className="text-xs opacity-60">{pair.type} — the message-center's record</div>
                      </td>
                      <td>
                        <span className={`badge badge-sm ${pair.type === 'error' ? 'badge-error badge-outline' : pair.type === 'warning' ? 'badge-warning badge-outline' : pair.type === 'success' ? 'badge-success badge-outline' : 'badge-ghost'}`}>
                          {pair.type}
                        </span>
                      </td>
                      <td className="text-xs opacity-60">
                        {pair.type === 'info' ? 'silent' : (classSound(pair.type) || '(none — silent)')}
                      </td>
                    </tr>
                  ))}
                  {messagePairs.length === 0 && (
                    <tr>
                      <td colSpan={3} className="text-xs opacity-60">
                        No system messages yet — the recorded events appear here.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
        </>
        )}
      </div>
    </ErrorBoundary>
  );
}
