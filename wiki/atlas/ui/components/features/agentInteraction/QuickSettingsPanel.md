---
title: QuickSettingsPanel (REMOVED)
type: atlas-component
path: frontend/src/components/features/agentInteraction/QuickSettingsPanel.tsx (DELETED)
confidence: high
updated: 2026-09-25
tags: [type/component, domain/atlas-ui]
---
# QuickSettingsPanel — REMOVED

**Path**: `frontend/src/components/features/agentInteraction/QuickSettingsPanel.tsx` — **DELETED**.
No file exists at that path; this is a removal record, kept so the links that named it still resolve.

## What it was

A per-session settings strip: it edited the ACTIVE session's generation overrides (temperature,
top-p, `max_tokens`, model override, system-prompt override), loaded them through
`runtimeConfigService`, and wrote them back with a **Save Settings** button gated on a dirty flag.

## Why it is gone

Two reasons, both structural rather than cosmetic:

- **It could not render.** Its only mount was a commented-out block in `SessionManager` — the
  Settings tab that held it had already been removed and the slot given to the History tab — so the
  component was unreachable code.
- **It wrote values nobody chose.** Its `defaults` object carried `temperature: 0.7, top_p: 0.9`,
  and a session override OUTRANKS an agent's own declaration: opening the panel and pressing Save
  put that pair on the session. The budget half of the same defect was fixed first (the panel's
  prefilled `max_tokens: 2000`), and the sampling half went with the component.

Deleted together with its barrel export in `features/agentInteraction/index.ts`, the commented mount
block in `SessionManager`, and `runtimeConfigService` (its only caller).

## Where the surface lives now

The session-override feature is **API-only**. Its routes are unchanged and live:
`GET/POST/PUT/DELETE /api/v1/runtime-config` plus the per-session reset. Nothing is lost to an
external caller — the app simply has no UI for it, and a UI that returns has to express "no override
for this field" as an EMPTY control rather than a prefilled pair.
