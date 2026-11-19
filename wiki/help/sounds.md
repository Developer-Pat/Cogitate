---
title: Sounds
category: sounds
subtopic: Overview
order: 1
confidence: high
created: 2026-08-29
updated: 2026-11-18
tags: [domain/help]
---

# Sounds

The notification-sound assets (the **wav-assets**): a small catalog of
WAV files the app can play when a toast fires.

## The catalog

- **Curated** — the sounds that ship with the app
  (`assets/notification-sounds/`, git-tracked): a gentle ping + a soft
  chime, self-synthesized (no external sources, no license files).
- **Uploads** — WAV files you add (validated `audio/wav`, max 2 MB,
  content-deduped). Upload as many as you like; nothing is
  overwritten.
- **Restore curated** — re-copies any missing curated sound back into
  the store (additive only; your uploads are untouched).

## The notification sound

The **selectable surface**: pick which sound the toasts play.

- **Play a sound with toasts** — the audio-ping toggle (off by
  default).
- **Sound** — the picker; the configured sound is marked **in use**
  and **cannot be deleted** (pick another first).
- **Save** — writes the choice to the notifications config.

The sound plays when a toast arrives (the class's own wav — the
**run-complete bell** for success, the **alert** for warning, the
**siren** for error) while the toggle is on; the quiet info stays
silent. The three per-class pickers set each class's sound (the
plain Sound picker is the fallback). The **Sound level** picker sets
the MINIMUM class that pings — "warning" by default (the alerts +
the emergencies; the run-complete bell is silent below the level).
The **Volume** slider sets the loudness (0-100%, saved with the
sound); the preview buttons follow the slider for instant audition.

The browser's **autoplay policy** blocks audio until the first click
on the page. When a play is blocked, a **"Sound blocked by the
browser"** banner appears above the toasts — one click enables the
audio alerts (and the sticky cycle resumes on its next tick).

## Exa's announcements

The **send_notification** tool (the Exa agent's surface) sends a
notification through the same chain: a toast + the center record +
the class sound. Exa announces completions, findings, and the
attention-critical cases (the sticky flag makes it stay + cycle).

The tool can carry a **link** (+ a label): the toast's action link
navigates the user there when clicked — Exa's "Talk to me" / "Urgent"
flavor brings the user to the Exa chat (`/exa`). Links are gated to
app routes + http(s) URLs.

## Sticky toasts

Some notifications are **sticky**: they stay on screen until you
dismiss them (the ✕), and while one is present the sound **cycles
every 2 seconds** until it's gone — the attention events that must
not be missed (the user away from the terminal scenario). The sticky
comes from the event itself (the workflow-abort/emergency class
publishers mark it); the sound + the volume follow the config as
usual. The sticky toasts **survive page reloads** — the ring replay
re-toasts them until the ✕.

## Mute notifications (the airplane-mode)

The **suppression** toggle: the toasts are hidden but every message
still lands in the message center (the queue + the counts persist —
the viewable-queue doctrine).

- **Mute for 30 seconds / 1 hour / until I restore** — the duration
  picker (30 seconds is the test-delay, not the hour!). The
  backend's timer restores the notifications at the end + announces
  it ("Notifications back on").
- **Restore now** — ends the mute early.
- While muted: the live countdown to the auto-restore.
