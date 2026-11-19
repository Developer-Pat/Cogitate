---
title: Notifications Config
type: atlas-page
path: frontend/src/pages/NotificationsConfigPage.tsx
confidence: high
updated: 2026-08-31
tags: [type/page, domain/atlas-ui]
---

# Notifications Config

**Component**: `frontend/src/pages/NotificationsConfigPage.tsx`
**Route**: `/notifications-config` (icon `bell`, breadcrumb
"Notifications") — registered in `frontend/src/config/routes.ts`; the
sidebar's **Configuration** section (the _28 re-home — the
alphabetical order).
**Last Updated**: 2026-08-31

## Purpose

The **notification-sound config + the mute** — re-homed from the
Sounds page (the _27 Phase 3). Two tabs:

- **Config**: the card's top-right TEMPORARY MUTE (the blue pill +
  the duration selector; the muted badge/countdown/Restore); the
  audio-ping toggle, the sound LEVEL (the minimum class that
  pings), the volume, the Save. The legacy Sound box (the sound_id
  fallback) is retired from the UI — the Events table is the one
  sounds' home.
- **Events**: the configurable events' table — the class-rows
  (Run complete / Alert / Emergency — the per-class sound pickers,
  THE one place; "(none — silent)" silences a class) + the
  DATA-DRIVEN system-rows (the message-store's distinct
  sources/kinds — the records are the truth, the table's the
  mirror; the new kinds appear automatically).

## The config surface

The UserSettings "notifications" blob: {suppressed, audio_enabled,
sound_id, mute_until, volume, sound_success, sound_warning,
sound_error, sound_level}. The EMPTY per-class value = the per-class
silent (the backend accepts it; the container skips the play).
