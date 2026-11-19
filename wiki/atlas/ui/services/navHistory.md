---
title: navHistory
type: atlas-service
path: frontend/src/services/navHistory.ts
confidence: high
updated: 2026-09-15
tags: [type/service, domain/navigation, status/active]
---

# navHistory

**Path**: `frontend/src/services/navHistory.ts`

The shortcut list behind the Ask-Exa box: where you actually go, so the **mouse
path needs no typing**. localStorage under `cog-nav-history`, aggregated BY
destination (a repeat raises `count` instead of adding a row), most-used first
with recency as the tie-break, bounded to 40 entries.

## Exports

| Export | What it does |
|---|---|
| `recordNav(to, label, now?)` | one open = one count; an empty `to` is ignored (a tab app has no path to store) |
| `navHistory(limit?)` | the shortcuts, most-used first |
| `clearNavHistory()` | wipe it — the box's `Clear` control, confirmed through the toaster |

## The rule that matters
A **convenience, never a source of truth**: a corrupt or absent store degrades to
"no history" rather than throwing, because this runs in the header of every page
in the app.
