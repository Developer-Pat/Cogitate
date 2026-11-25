import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { usePageTitle } from '../hooks/usePageTitle';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { PageBanner } from '../components/ui/PageBanner';
import { ttsConfigService, type TtsVoice } from '../services/domain/ttsConfigService';
import { getSttConfig, updateSttConfig, transcribeAudio } from '../services/sttService';
import { ttsService } from '../services/ttsService';
import { useNotificationStore } from '../stores/notificationStore';
import { frontendLoggingService } from '../services/frontendLoggingService';

// THE SPEECH PAGE (2026-08-31, the _27 Phase-2 build — the
// Configuration-nav roadmap): the TTS/STT re-homed from the Sounds
// page. The voice/rate + the enabled toggle + the STT
// toggle + the TEST FACILITY (the round-trip self-diagnostic).
// 2026-09-04 (the chat-audio rework P1): the voice-source picker
// (browser vs the provider) is GONE — the browser path was ditched.
// 2026-10-03 (phase 6, G2-F4): the ENGINE picker is GONE too. Which
// engine speaks/hears is the `tts`/`stt` capability's answer, changed
// on /providers/capabilities — this page shows it and links there,
// and repairs a voice left over from a previous engine (see the load
// effect: the repair has to happen where the voice LIST is read).

export default function SpeechPage() {
  usePageTitle('Speech', 'The voice (TTS) + the hearing (STT) — the preferences, the voices, and the round-trip test facility');

  const { addSuccess, addError } = useNotificationStore();

  const [ttsEnabled, setTtsEnabled] = useState(false);
  const [ttsVoice, setTtsVoice] = useState('');
  const [ttsRate, setTtsRate] = useState(1.0);
  const [ttsVoices, setTtsVoices] = useState<TtsVoice[]>([]);
  const [ttsProvider, setTtsProvider] = useState('piper');
  // THE STICKY MODE (2026-08-31, the TTS P3 build): the sticky
  // alerts' voice — "siren" (the wav-loop) vs "spoken" (the
  // content read aloud once).
  const [stickyMode, setStickyMode] = useState<'siren' | 'spoken'>('siren');
  const [ttsSaving, setTtsSaving] = useState(false);

  const [sttEnabled, setSttEnabled] = useState(true);
  const [sttProvider, setSttProvider] = useState('whisper');
  const [sttSaving, setSttSaving] = useState(false);

  const [testPhrase, setTestPhrase] = useState(
    'The quick brown fox jumps over the lazy dog.',
  );
  const [testState, setTestState] = useState<'idle' | 'testing' | 'ok' | 'error'>('idle');
  const [testDetail, setTestDetail] = useState('');

  const handleRoundTripTest = async () => {
    const phrase = testPhrase.trim();
    if (!phrase) return;
    setTestState('testing');
    setTestDetail('');
    try {
      // THE LOOP: the TTS speaks -> the wav -> the STT hears.
      const blob = await ttsService.synthesize(phrase);
      // THE AUDIBLE (2026-08-31, the user's 'I hear nothing'): the
      // test must PLAY the spoken phrase — the wiring's proven AND
      // the user hears the voice (the button click is the gesture,
      // so the autoplay policy allows it).
      const audio = new Audio(URL.createObjectURL(blob));
      audio.play().catch(() => {
        /* the blocked-play stays silent — the policy's honest */
      });
      const file = new File([blob], 'roundtrip.wav', {
        type: blob.type || 'audio/wav',
      });
      const result = await transcribeAudio(file);
      setTestDetail(result.text);
      setTestState('ok');
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setTestDetail(message);
      setTestState('error');
      // THE VISIBLE + LOGGED RECORD (2026-09-04, the user's
      // no-toast/no-log finding): the card alone was the silent
      // surface — the failure now toasts AND rides the log funnel.
      useNotificationStore.getState().addError('Round-trip failed', message, 4000);
      frontendLoggingService.error('SpeechPage', 'Round-trip test failed', message);
    }
  };

  // THE TTS/STT CONFIG LOAD at mount.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [cfg, sttCfg] = await Promise.all([
          ttsConfigService.getConfig(),
          getSttConfig(),
        ]);
        if (cancelled) return;
        setSttEnabled(sttCfg.enabled);
        setSttProvider(sttCfg.provider);
        setTtsEnabled(cfg.enabled);
        setTtsRate(cfg.rate);
        setTtsProvider(cfg.provider);
        setStickyMode(cfg.sticky_mode ?? 'siren');
        // NO VOICE LIST WHILE SPEECH IS OFF (2026-11-25): the list costs an outbound
        // call — the edge engine asks Microsoft — and the backend refuses it while the
        // switch is off. An off install shows an empty picker rather than reaching out;
        // saving with the toggle on refetches it (handleSaveTtsConfig).
        if (!cfg.enabled) {
          setTtsVoice(cfg.voice);
          return;
        }
        const voiceOptions = await ttsConfigService.getVoices();
        if (cancelled) return;
        setTtsVoices(voiceOptions.voices);

        // THE STALE-VOICE REPAIR. WHICH engine speaks is chosen on /providers/capabilities, where
        // nothing knows about voices — so a voice left over from the PREVIOUS engine is repaired
        // here, against the list this engine actually offers. It is the rule the engine flip used to
        // apply on the way out (the app's default when the engine has it, else its first); without
        // it the next Speak fails on an unknown voice ("Unknown piper voice: …") and this page's
        // Voice select shows a value none of its options match.
        const speakable = voiceOptions.voices.some((v) => v.name === cfg.voice);
        if (!speakable && voiceOptions.default) {
          const repaired = await ttsConfigService.updateConfig({ voice: voiceOptions.default });
          if (cancelled) return;
          setTtsVoice(repaired.voice);
          useNotificationStore
            .getState()
            .addSuccess('TTS', `Voice — ${repaired.voice} (the previous one is not ${cfg.provider}'s)`);
        } else {
          setTtsVoice(cfg.voice);
        }
      } catch (err) {
        frontendLoggingService.error('SpeechPage', 'Failed to load the tts config', err);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSaveTtsConfig = async () => {
    setTtsSaving(true);
    try {
      const cfg = await ttsConfigService.updateConfig({
        enabled: ttsEnabled,
        voice: ttsVoice,
        rate: ttsRate,
        sticky_mode: stickyMode,
      });
      setTtsEnabled(cfg.enabled);
      setTtsProvider(cfg.provider);
      setTtsVoice(cfg.voice);
      setTtsRate(cfg.rate);
      const voiceOptions = await ttsConfigService.getVoices();
      setTtsVoices(voiceOptions.voices);
      addSuccess('TTS', `Voice config saved — ${cfg.voice}`);
    } catch (err) {
      addError('TTS', 'Failed to save the voice config');
      frontendLoggingService.error('SpeechPage', 'Failed to save the voice config', err);
    } finally {
      setTtsSaving(false);
    }
  };

  // THE INSTANT VOICE: the VOICE auto-saves on change.
  const handleTtsVoiceChange = async (voice: string) => {
    setTtsVoice(voice);
    try {
      const cfg = await ttsConfigService.updateConfig({ voice });
      setTtsVoice(cfg.voice);
      addSuccess('TTS', `Voice activated — ${cfg.voice}`);
    } catch (err) {
      addError('TTS', 'Failed to activate the voice');
      frontendLoggingService.error('SpeechPage', 'Failed to activate the voice', err);
    }
  };

  return (
    <ErrorBoundary>
      <div className="p-6 max-w-7xl mx-auto">
        <PageBanner
          title="Speech"
          className="mb-6"
          tooltip="The voice (TTS) + the hearing (STT) — the providers, the voices, and the round-trip test facility."
        />

        {/* THE TTS CARD */}
        <div className="card bg-base-100 shadow-md mb-4">
          <div className="card-body p-4">
            <h2 className="card-title text-sm">The voice (TTS)</h2>
            <p className="text-xs opacity-70">
              The responses read aloud — the Speak button on each answer, or the auto-voice
              when enabled. The engine speaking: <span className="font-mono">{ttsProvider}</span>
              {ttsProvider === 'piper' && ' — the private neural engine on this machine.'}
              {ttsProvider === 'edge' && ' — the online neural, free, no key.'}
            </p>
            <p className="text-xs opacity-70">
              Which engine speaks is the <span className="font-mono">tts</span> capability&apos;s
              answer —{' '}
              <Link to="/providers/capabilities" className="link link-primary">
                change it on Capabilities
              </Link>
              .
            </p>
            <div className="flex flex-wrap items-center gap-4 mt-2">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  className="toggle toggle-primary toggle-sm"
                  checked={ttsEnabled}
                  onChange={(e) => setTtsEnabled(e.target.checked)}
                />
                Auto-voice new responses
              </label>
              <label className="tooltip tooltip-top flex items-center gap-2 text-sm" data-tip="The voice this engine speaks in — the picker lists what the engine actually offers">
                Voice
                <select
                  className="select select-sm select-bordered"
                  value={ttsVoice}
                  onChange={(e) => handleTtsVoiceChange(e.target.value)}
                >
                  {ttsVoices.length === 0 && <option value="">(no voices available)</option>}
                  {ttsVoices.map((v) => (
                    <option key={v.name} value={v.name}>
                      {v.name}
                    </option>
                  ))}
                </select>
              </label>
              <div
                className="tooltip tooltip-top flex items-center gap-3 text-sm"
                data-tip="The sticky alerts' voice mode — the siren-loop (the current) vs the content read aloud once by the TTS"
              >
                Sticky alerts
                <label className="flex items-center gap-1 cursor-pointer">
                  <input
                    type="radio"
                    name="tts-sticky-mode"
                    className="radio radio-primary radio-xs"
                    checked={stickyMode === 'siren'}
                    onChange={() => setStickyMode('siren')}
                  />
                  Siren (the loop)
                </label>
                <label className="flex items-center gap-1 cursor-pointer">
                  <input
                    type="radio"
                    name="tts-sticky-mode"
                    className="radio radio-primary radio-xs"
                    checked={stickyMode === 'spoken'}
                    onChange={() => setStickyMode('spoken')}
                  />
                  Read aloud (once)
                </label>
              </div>
              <label
                className="tooltip tooltip-top flex items-center gap-2 text-sm"
                data-tip="The speaking speed (0.5x - 2x)"
              >
                Rate
                <input
                  type="range"
                  min={0.5}
                  max={2}
                  step={0.1}
                  value={ttsRate}
                  className="range range-primary range-xs w-32"
                  onChange={(e) => setTtsRate(Number(e.target.value))}
                />
                <span className="text-xs font-mono w-9">{ttsRate.toFixed(1)}x</span>
              </label>
              <button
                className="btn btn-primary btn-sm"
                onClick={handleSaveTtsConfig}
                disabled={ttsSaving}
              >
                {ttsSaving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>

        {/* THE HEARING (STT) CARD */}
        <div className="card bg-base-100 shadow-md mb-4">
          <div className="card-body p-4">
            <h2 className="card-title text-sm">The hearing (STT)</h2>
            <p className="text-xs opacity-70">
              The speech-to-text — the audio becomes text. The engine hearing:{' '}
              <span className="font-mono">{sttProvider}</span>
              {sttProvider === 'whisper' && ' — the private, keyless whisper model on this machine.'}
            </p>
            <p className="text-xs opacity-70">
              Which engine transcribes is the <span className="font-mono">stt</span> capability&apos;s
              answer —{' '}
              <Link to="/providers/capabilities" className="link link-primary">
                change it on Capabilities
              </Link>
              .
            </p>
            <div className="flex flex-wrap items-center gap-4 mt-2">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  className="toggle toggle-primary toggle-sm"
                  checked={sttEnabled}
                  onChange={async (e) => {
                    const next = e.target.checked;
                    setSttEnabled(next);
                    setSttSaving(true);
                    try {
                      await updateSttConfig({ enabled: next });
                    } finally {
                      setSttSaving(false);
                    }
                  }}
                />
                Enable speech-to-text
              </label>
              <span className="text-xs opacity-60">
                {sttSaving ? 'Saving…' : 'The whisper hears the wavs — the TTS→STT round-trip harness'}
              </span>
            </div>
          </div>
        </div>

        {/* THE TEST FACILITY */}
        <div className="card bg-base-100 shadow-md mb-4 border border-primary/20">
          <div className="card-body p-4">
            <h2 className="card-title text-sm">Test the wiring</h2>
            <p className="text-xs opacity-70">
              The round-trip: the piper speaks the phrase, the whisper hears it, and the
              result tells you the whole speech pipeline is wired correctly.
            </p>
            <div className="flex flex-wrap items-center gap-3 mt-2">
              <input
                type="text"
                className="input input-sm input-bordered w-80"
                value={testPhrase}
                onChange={(e) => setTestPhrase(e.target.value)}
                placeholder="The phrase to speak and hear"
                aria-label="Round-trip test phrase"
              />
              <button
                className="btn btn-primary btn-sm"
                onClick={handleRoundTripTest}
                disabled={testState === 'testing' || !testPhrase.trim()}
              >
                {testState === 'testing' ? 'Speaking…' : 'Test the round-trip'}
              </button>
              {testState === 'ok' && (
                <span className="badge badge-success gap-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Wired ✓
                </span>
              )}
              {testState === 'error' && <span className="badge badge-error">Failed — see below</span>}
              {testState === 'testing' && <span className="loading loading-spinner loading-xs" />}
            </div>
            {testState === 'ok' && (
              <p className="text-xs mt-2">
                Heard back: <span className="font-mono">{testDetail}</span>
              </p>
            )}
            {testState === 'error' && (
              <p className="text-xs text-error mt-2">
                The round-trip failed: <span className="font-mono">{testDetail}</span>
              </p>
            )}
          </div>
        </div>
      </div>
    </ErrorBoundary>
  );
}
