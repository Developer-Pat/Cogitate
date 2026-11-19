---
title: NewUserTips (REMOVED)
type: atlas-component
path: frontend/src/components/NewUserTips.tsx (DELETED 2026-08-02)
confidence: high
updated: 2026-08-02
tags: [type/component, domain/atlas-ui]
---
# NewUserTips (REMOVED)

**Path**: `frontend/src/components/NewUserTips.tsx` — **DELETED 2026-08-02**
**Type**: component (onboarding tips — removed)

## Purpose
Former onboarding-tips component: fired toaster notifications on first
visit to each route, gated by the `showNewUserTips` setting (default
false). Was already `@deprecated` — tips predated the help system.

## What happened
- **Removed 2026-08-02** (user decision: tips were annoying; removal
  plan had been scheduled in the 🗑️ Deprecated todo section)
- Component file deleted; mount removed from App.tsx
- `showNewUserTips` setting removed from types/settings.ts (field + zod
  schema + default), settingsStore.ts (both defaults), and the Settings
  page onboarding toggle
- No tests referenced it
- **Note**: this was the last remaining reference to the legacy assistant
  name in frontend/src — its removal completes the zero-ref cleanup

## Related
- settingsStore.ts / types/settings.ts — setting removed
- wiki/help/ — the help system that superseded the tips
