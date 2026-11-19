---
title: LogFilters
type: atlas-component
path: frontend/src/components/logs/LogFilters.tsx
confidence: high
updated: 2026-09-06
tags: [type/component, domain/atlas-ui]
---

# LogFilters

**Path**: `frontend/src/components/logs/LogFilters.tsx`
**Last Updated**: 2026-09-06

## Purpose

The filter-card BODY for the Logs page. It renders no card shell of its
own — the Logs page wraps it in a DaisyUI collapse (the "Filters"
expander, closed by default) — and it owns no data: everything arrives
via props from `Logs.tsx`. Layout is two working lines + pagination:

1. **Search + Time line** — the full-text search input (flex-1, debounced
   upstream) with a search-spinner and clear-search ✕, then a
   right-justified `shrink-0` cluster: `Time:` preset select (All Time /
   1h / 6h / 12h / 24h / 7d), the Advanced/Simple toggle (reveals the
   custom From/To datetime inputs), and a clear-time ✕ when a custom
   range is set.
2. **Levels + Sources line** — left: the level buttons (All Levels /
   Debug / Info / Warning / Error / Critical); right: the `Source:`
   component select, a 20px gap, then the file-type segmented
   **Both / Frontend / Backend**. Both groups carry `shrink-0` so the
   row wraps whole instead of the `btn-group` collapsing into a column.
3. **Pagination** — page-size selector + the `Pagination` component,
   with the "Showing X–Y of N logs" count.

## Selection conventions

- The selected level button = `btn-active btn-selected` (uniform
  action-blue fill; see the control-system design note).
- The segmented's selected state = the SAME `btn-selected` treatment
  for Both / Frontend / Backend — deliberately no per-source hues.
  The unselected segment buttons are plain `btn-outline`.
- Source-type value is still `'all' | 'frontend' | 'backend'`; the
  label for `'all'` is **Both**.
- The level filter applies client-side; search / time / source go
  server-side.

## Props Interface

Controlled component — all state arrives as props (`selectedLevel`,
`searchTerm`, `sourceType`, `selectedSource`, `availableSources`,
`fromTime` / `toTime` / `timePreset` / `showAdvancedTime`, pagination
state + handlers, and the level/source/search/time change callbacks).
It no longer takes `logsLoading` / `onRefresh` — the Refresh button
lives in the Logs page header.

## Styling notes

- Every control is theme-keyed (no hardcoded colors); the tooltip
  audit removed all native `title=` attributes — DaisyUI tooltips (or
  `aria-label`) everywhere.
- The Advanced toggle + clear ✕ controls are `btn-ghost` with tooltips;
  icon/text ✕ buttons carry `aria-label` + a wrapping tooltip span.
