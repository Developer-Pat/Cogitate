---
title: Notification Sounds — enabling audio alerts
type: dev-note
category: dev-notes
order: 10
confidence: high
created: 2026-08-30
updated: 2026-08-30
tags: [type/dev-notes, domain/assets, domain/messaging]
---

# Notification Sounds — enabling audio alerts

> What must be configured for the toasts to actually make sound, and
> where the pieces live. The app side is only half the story — the
> browser's autoplay policy is the other half, and it cannot be
> bypassed from the page.

## The in-app config (the app side)

| Setting | Home | Default |
|---|---|---|
| `audio_enabled` (the "Play a sound with toasts" toggle) | The Sounds page → the notification-sound card; the `notifications` UserSettings blob | off |
| `sound_id` (the fallback wav) | The same card; 5 curated wavs | `gentle-ping.wav` |
| `sound_success` / `sound_warning` / `sound_error` (the per-class wavs) | The same card's three per-class pickers | `end-of-run.wav` / `alert.wav` / `emergency.wav` |
| `sound_level` (the minimum class that pings) | The same card's Sound level picker | `warning` |
| `volume` (0-1) | The same card's Volume slider; applied at play | 1.0 |

The class filter: success (the run-complete bell), warning (the
alert), and error (the emergency) each play their own wav; the quiet
info stays silent. The preview buttons follow the slider for instant
audition.

## The browser side (the OTHER half)

The browser's **autoplay policy** blocks page audio until the user
has interacted with the site. Consequences:

- The **first** play after a page load is rejected until the first
  click anywhere on the page. The click is remembered per-origin —
  after one interaction, autoplay works thereafter.
- When a play is rejected, the toast stack shows the
  **"The browser blocked the sound"** banner — one click plays the
  alert immediately + unlocks the rest (the 2s sticky cycle resumes).
- The **permanent browser config**: the address-bar lock/speaker
  icon → Site settings → Sound → **Allow** for the origin — sound
  then plays with zero clicks, forever, and the banner never shows.

## The playback chain (where the code lives)

- `frontend/src/services/domain/soundsService.ts` — `soundFileUrl()`
  (the ONE resolver: `${API_BASE_URL}/api/v1/sounds/<name>/file` —
  never a static mount; the sound bytes ride the API).
- `frontend/src/components/NotificationContainer.tsx` — the play
  hooks (the class filter, the volume, the 2s sticky repeat, the
  blocked-sound banner).
- `frontend/src/hooks/useNotifyBridge.ts` — the sticky re-toast:
  the sticky toasts survive page reloads (the replay re-toasts them
  until the ✕ — the tombstone still suppresses).
- `backend/app/api/v1/sounds_router.py` — the file serving
  (`Cache-Control: no-cache`).
- `backend/app/domain/messaging/notifications_config.py` — the
  config store; `backend/app/domain/messaging/sounds.py` — the
  business rules.

## The known issues

- The browser's autoplay policy: the first play after a load is
  blocked until a click (or the site setting above).
- The wavs are served with `no-cache` — the browsers' media cache
  must never serve stale bytes after a seed regeneration.
- The sounds must flow through `soundFileUrl()` only — a raw
  `/sounds/` path returns the SPA's HTML and fails silently.

## The _27 UI re-homes (2026-08-31)

- The Sounds page is now the PURE CATALOG — the TTS/STT lives at
  /speech (the Speech page — the providers/voices/source + the
  test facility), the notification configs at /notifications-config
  (the Config + Events tabs).
- THE PER-CLASS NONE: the empty per-class value = the per-class
  silent (the backend accepts the empty; the container's play-hooks
  skip it — no fallback).
- THE EVENTS TABLE: the per-class sounds' ONE place — the
  class-rows' pickers + the data-driven system-rows (the
  message-store's distinct sources/kinds).
- The legacy sound_id (the plain Sound box) is RETIRED from the UI
  — it stays the backend's quiet fallback.
