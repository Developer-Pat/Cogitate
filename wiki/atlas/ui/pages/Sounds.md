---
title: Sounds
type: atlas-page
path: frontend/src/pages/SoundsManagement.tsx
confidence: high
updated: 2026-08-29
tags: [type/page, domain/atlas-ui]
---

# Sounds

**Component**: `frontend/src/pages/SoundsManagement.tsx`
**Route**: `/sounds` (protected, `requiresAuth: true`, icon `music`, breadcrumb "Sounds") — registered in `frontend/src/config/routes.ts` and linked from the sidebar navigation in `frontend/src/App.tsx` under the **Assets** section (nav label "Sounds")
**Last Updated**: 2026-08-31

## Purpose

The **notification-sound assets** (the wav-assets): the PURE CATALOG
(the _27 Phase 2/3 re-homes) — the upload/restore/preview/browse
surface, the images-store pattern applied to the toast sounds. The
TTS/STT config lives at `/speech`; the notification-sound config +
the mute at `/notifications-config`.

The store is the filesystem: `data/notification-sounds/` (gitignored;
the bytes are served through `GET /api/v1/sounds/{filename}/file` — a
static mount would collide with the SPA route). Two kinds appear:

- **Curated** — the sounds shipped in `assets/notification-sounds/`
  (self-synthesized WAVs, seeded additively at startup + restorable
  via the endpoint), flagged **curated**.
- **Uploads** — user WAVs (validated `audio/wav`, 2 MB cap,
  content-hash deduped), flagged by absence of the curated badge.

## The notification surfaces

The page's config cards bind the **notifications config**
(`GET/PUT /api/v1/notifications/config`, the UserSettings blob under
the `notifications` key):

- the **page tabs** (2026-08-30, the user's reorganize): Messages (the notification sound + the mute + the catalog) vs The voice (TTS)
- the **TTS card** — the Auto-voice toggle + the provider picker (piper | edge) + the voice picker (the provider's dynamic voices) + the rate + the source switch
- the **TTS card** (2026-08-30, the _25 P2): the Auto-voice toggle + the voice picker (the provider's dynamic voices) + the rate slider — the UserSettings "tts" blob; the auto-voice reads the Exa page's finished responses aloud when enabled
- the audio-ping toggle (`audio_enabled`) + the sound picker
  (`sound_id` — the FALLBACK) + the **per-class pickers**
  (`sound_success` -> the run-complete bell, `sound_warning` -> the
  alert, `sound_error` -> the emergency; the container plays the
  class's wav — success + warning + error ping, info stays silent)
  + the **volume** slider (`volume`, 0-1 — the HTMLAudio volume
  applied at play; the previews follow it) — the configured sound is
  flagged **in use** and the sounds router refuses to delete it (409)
- **the mute row** (`suppressed` + `mute_until`): the airplane-mode
  (the toasts muted, the center still records — the gate lives in
  the notificationStore's addNotification choke point) + the
  scheduled-mute (the backend's APScheduler restore job + the
  "Notifications back on" announcement; the startup heal covers a
  missed job) + the live countdown + the Restore now.

## Key Features

- The catalog table: play-preview (the Audio API, no libraries),
  filename/size/source columns, delete (curated + the configured
  sound protected), the All/Curated/Uploads filter.
- Upload (single/multi) + Restore curated (the additive doctrine).
- **The sticky toast + the repeat** — the notifications config's
  chain supports the sticky flag (the bus payloads carry it; the
  bridge passes it through the choke point): the toast stays until
  dismissed (no auto-remove) + the container cycles the sound every
  2s while it's present (the immediate play + the interval; the
  regular play hook defers to the repeat for the sticky toasts).
  Live-proven: the sticky toast survived past the 5s window with 7
  plays over ~8s; the ✕ stopped both instantly.
- **The toast play hook** — `NotificationContainer` plays the
  CLASS sound (the F4 mapping: success -> `sound_success`, warning
  -> `sound_warning`, error -> `sound_error`, fallback `sound_id`;
  info silent) while `audio_enabled` (one play per toast id; the
  browser's autoplay policy may mute the first play until a page
  interaction).
- **The mute-restore handling** — `useNotifyBridge` force-reloads
  the config + adds the "Notifications back on" announcement with
  the bypass flag (it shows even while the stale local config says
  suppressed).

## Data Flow

Sounds page / container → `soundsService` + `notificationConfigService`
→ the `/api/v1/sounds` + `/api/v1/notifications/config` endpoints →
the sounds store (filesystem) + the notifications config
(UserSettings). The delete guard reads the config's `sound_id`
(sync sqlite read — the `Paths.from_settings` shared_db, fixed
2026-08-29 for the double-slash URL form).

## Related

- [[help/sounds|Sounds help]] — the page help
- The notifications-upgrade (the airplane-mode + the scheduled-mute
  + the attention-worthy filtering) rides on the same config —
  tracked in the backlog
