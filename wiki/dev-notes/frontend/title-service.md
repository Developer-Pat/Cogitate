---
title: Title Service
type: atlas-devnote
category: frontend
order: 1
confidence: high
updated: 2026-09-03
tags: [type/dev-notes, domain/frontend]
---

# Title Service

## Overview

The frontend title flow — a queued background job that asks the
backend (the **title capability**) to name a session. Backend:
`TitleService` (backend/app/domain/title/services.py) — resolution
and endpoints are documented in
[[dev-notes/api/title-capability|the title capability]].

## Key facts

- The frontend service (`frontend/src/services/domain/
  TitleService.ts`) dedupes per session: a second job for the same
  session while one is pending/in-flight is dropped.
- The model comes from the user's Title Generation preference in
  Settings — agent model, backend default, or a custom string —
  NOT a separate title-LLM config (the old `TITLE_LLM_*` env
  universe is retired).

## Frontend trigger points

`generateTitleInBackground(sessionId, content, model, userEnabled)`
queues the job with toasts on completion.

Two triggers in `useAgentInteraction.ts`:

1. **On session create (first message)**: when a fresh session gets
   its first assistant message, a title is generated in the
   background if the session still needs one (no title, or a
   "New Session" placeholder). A session that starts with "hello"
   yields an uninformative title — disable Auto-Title in Settings
   to rename deliberately instead.
2. **Manual regeneration**: the session rename action calls
   `generateTitleInBackground` with the conversation content.

The Sessions page's "Rename from the conversation" is a separate
path — `POST /api/v1/sessions/{id}/title`, which reads the FULL
conversation (see [[dev-notes/api/title-capability|the title
capability]]). One click = one rename (in-flight guard).

## SSE note

Title updates are applied through the session data (not a
dedicated SSE event) — the UI refreshes the session title from the
response.
