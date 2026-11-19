---
title: TTS / STT — the browser speech layer
type: dev-note
category: dev-notes
order: 11
confidence: high
created: 2026-08-30
updated: 2026-09-04
tags: [type/dev-notes, domain/messaging, domain/ui]
---

# TTS / STT — the browser speech layer

> The voicing direction: the BACKEND's TTS providers do the
> synthesis (piper offline / edge online); the frontend fetches the
> wav and plays it through ONE HTMLAudioElement. 2026-09-04 (the
> chat-audio rework): the browser's speechSynthesis path was
> DITCHED — it was broken (the user's call). The design roadmap
> lives in local/tts-audio/01-roadmap.md; the older study in
> local/tts-stt/01-study.md.

## What IS (built, 2026-09-04)

- **THE ONE TRANSPORT** (`frontend/src/services/ttsService.ts`):
  speak() -> `GET /api/v1/tts/speak?text=...` (the configured
  provider) -> the wav -> ONE HTMLAudioElement. NO speechSynthesis
  anywhere — no source switch, no OS-voice list, no fallback swap.
- **THE PLAYBACK STATE MACHINE (P2)**: the service OWNS the state —
  `idle | playing | paused` — with `subscribe()` for the
  components; `pause()` pauses the audio element IN PLACE (kept
  alive), `resume()` continues from the same spot (no re-fetch);
  `cancel()` is the full stop. `isSpeaking()` = the real audio
  state (the old speechSynthesis.speaking check lied — false while
  the wav played).
- **THE SPEAK CLUSTER (P3)**: the per-bubble controls render from
  the service state + the active speaking KEY (`speak(text, {key})`
  attaches the speech to its bubble): the ACTIVE bubble shows
  Pause⇄Resume + Stop (never a play); every other bubble shows
  Play (click = switch — the queue policy cancels the current).
  THE AUTO-READ keys to the bubble that received the reply — an
  auto-read shows the same controls (never unstoppable).
- **THE AUTO-VOICE**: when the config's `enabled` flag is on, the
  Exa page's finished responses read themselves aloud (the done
  handler -> ttsService). THE LIVE READ (P2): the config re-reads
  when the page gains focus/visibility (Speech and Exa are
  separate tabs — the mount-time read went stale).
- **THE FAILURE POLICY (P1)**: an API failure = no audio + a small
  VISIBLE 'Voice unavailable' notice (throttled 10s). An
  autoplay-policy play rejection stays SILENT (the browser's
  policy — not a failure to fall back from). A stop-cancel is NOT
  a failure.
- **The queue policy**: one voice at a time — a new speak cancels
  the current.
- **THE PROVIDER ENGINE** (`backend/app/domain/tts/`): the provider
  contract (voices + synthesize) + the config (the UserSettings
  "tts" blob: provider/voice/rate/enabled + the legacy source
  field — kept harmlessly, unused) + the registry (the ONE
  resolver — a MAP). **piper** (the private neural — the
  standalone binary + voice models in backend/data/piper/, the
  runtime gitignored) + **edge** (the ONLINE keyless — the
  Microsoft Edge neural voices via the edge-tts CLI — free, no
  key, the network's the only requirement). The provider flip
  auto-selects the voice.
- **THE CONFIG SURFACE**: the Speech page's "The voice (TTS)" card
  — the Auto-voice toggle + the PROVIDER picker (piper | edge) +
  the voice picker (the provider's dynamic /tts/voices) + the rate
  slider. The source switch is GONE (2026-09-04).
- **THE STT (unchanged)**: `domain/stt/` — the ONE `transcribe()`
  contract + the local keyless faster-whisper ("base"); the
  subprocess bridge (the venv is Python 3.14 — the provider shells
  out to the system python3's transcribe.py); `/api/v1/stt/*`; the
  round-trip harness (piper speaks -> the wav -> the whisper
  hears -> the WER).

## The known issues

- The auto-voice is blocked until the first page interaction (the
  autoplay policy) — the toggle's click (or a bubble's Play click)
  unlocks it.
- The queue is global to the page — switching pages mid-speech
  cancels the voice (the unmount cancel); cross-page handoff is
  deferred in the roadmap.
