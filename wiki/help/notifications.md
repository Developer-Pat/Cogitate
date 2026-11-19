---
title: Notifications Config
category: notifications
subtopic: Config
order: 1
confidence: high
created: 2026-08-31
updated: 2026-08-31
tags: [domain/help]
---

# Notifications Config

The notification-sound preferences + the temporary mute.

## The Config tab

The card's TOP-RIGHT holds the **Temporary Mute** widget (the blue
pill + the duration selector to its right: 30s / 1h / forever).
While muted: the badge + the countdown + the Restore. The muted
toasts are hidden but every message still lands in the message
center; the backend's timer restores at the end.

The card body:

- **Play a sound with toasts** — the audio-ping toggle (the
  attention-worthy classes only).
- **Sound level** — the minimum class that pings:
  info < success < warning < error (default warning — the
  run-complete bell is silent below it).
- **Volume** — the audio-ping's loudness (0-100%).
- **Save** — persists the preferences.

## The Events tab

The configurable events' table:

- The **class-rows** (Run complete / Alert / Emergency) carry the
  per-class sound pickers — THE one place for the per-class
  sounds; "(none — silent)" silences that class. The Info row is
  silent by design.
- The **system-rows** mirror the message-center's records (the
  distinct sources/kinds) — the new event kinds appear
  automatically.

## The header

The banner's right holds the Help button (this page).

## The per-class sounds

The three classes map to the curated wavs by default (the
run-complete bell / the alert / the emergency siren); the Events
table's rows choose each. An empty choice = the per-class silent.
