---
title: Speech
type: atlas-page
path: frontend/src/pages/SpeechPage.tsx
confidence: high
updated: 2026-10-03
tags: [type/page, domain/atlas-ui]
---

# Speech

**Component**: `frontend/src/pages/SpeechPage.tsx`
**Route**: `/speech` (icon `mic`, breadcrumb "Speech") — registered in
`frontend/src/config/routes.ts`; the sidebar's **Configuration** section (nav label "Speech", the
section's alphabetical order — the _28 re-home; the Sounds page
stays the Assets).
**Last Updated**: 2026-10-03

## Purpose

The **voice (TTS) + the hearing (STT)** — the speech layer's preferences,
re-homed from the Sounds page (the _27 Phase 2).

- The TTS card: the auto-voice toggle, the voice picker (the ENGINE's
  dynamic list — the selection auto-saves), the rate, the Save.
- **Which engine speaks is not a preference**: it is the `tts`
  capability's answer, shown in the card as a read-out with a link to
  `/providers/capabilities` — the one surface that changes it. A stored
  voice the current engine cannot speak is repaired on load, against the
  engine's own list and the `default` `GET /api/v1/tts/voices` publishes
  (the app's configured voice when the engine offers it, else its first).
- The STT card: the speech-to-text's enable toggle (the local whisper —
  the keyless faster-whisper via the subprocess bridge), and the `stt`
  capability's engine as a read-out with the same link.
- THE TEST FACILITY: the "Test the wiring" card — the round-trip
  self-diagnostic — the phrase's synthesized (PLAYED), transcribed
  by the whisper, and the "Wired ✓" badge + the heard text prove
  the whole pipeline (the user's ask).

## The backend

`/api/v1/tts/*` (the speak/voices/config) + `/api/v1/stt/*`
(the transcribe/config). `PUT /tts/config` and `PUT /stt/config` carry the
PREFERENCES only: a request naming `provider` is refused with the reason
and the replacement, because the engine's one home is the capability row.
The STT's provider shells out to the
system python3's `backend/data/stt/transcribe.py` (the venv's
3.14 gap — the edge-tts pattern).
