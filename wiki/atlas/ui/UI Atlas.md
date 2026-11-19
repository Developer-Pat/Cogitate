---
title: UI Atlas
type: atlas-index
path: frontend/src + backend/app
confidence: high
updated: 2026-11-18
tags: [type/index, domain/atlas-ui]
---

# UI Atlas — Developer Documentation

The UI Atlas is the developer-facing documentation for the Cogitate
frontend: the pages, components, hooks, services, and stores that
make up the application, plus architecture notes on how they fit
together. The section links below show each area and its pages.

## Sections

- **[[atlas/ui/pages|Pages]]** (29) — top-level page components (AgentInteraction, ExaChat, Dashboard, Logs, ...)
- **[[atlas/ui/components|Components]]** (189) — reusable components by feature area
- **[[atlas/ui/hooks|Hooks]]** (39) — custom React hooks
- **[[atlas/ui/services|Services]]** (67) — API and domain services
- **[[atlas/ui/stores|Stores]]** (16) — Zustand stores
- **[[atlas/ui/architecture|Architecture]]** (8) — deep-dive architecture docs with Mermaid diagrams

## How to read this atlas

1. **Start with the architecture docs** — [[atlas/ui/architecture/frontend-overview|Frontend Overview]]
   gives the component tree and data flow; [[atlas/ui/architecture/api-layers|Backend API Layers]]
   maps the ~48 routers.
2. **Drill into pages** — each page doc shows what the page composes.
3. **Follow the layers** — page → component → hook → service → store →
   apiClient → backend. Each doc links its consumers/dependencies.
4. **Check the sidebar** — every directory has a collapsible index (drill
   down, don't wade).

## Conventions

- Frontmatter: `title`, `type` (`atlas-page` / `atlas-component` /
  `atlas-hook` / `atlas-service` / `atlas-store` / `atlas-architecture` /
  `atlas-index`), `path` (real source path), `confidence`, `updated`
- All docs reference **real files and endpoints** — verified by the
  gate checks (no references to removed features)
- Wikilinks are wiki-root-relative: `[[atlas/ui/pages/Dashboard]]`
- Mermaid diagrams render in the wiki viewer
- Removed/obsolete code is documented as **removal records** (title
  marked REMOVED, path notes deletion)

## Maintenance

- **Gate check**: `scripts/core/check_atlas_validation.py` verifies frontmatter, stale names
  (removal records exempt), wikilink resolution, codebase sync and mermaid fence balance. It
  runs in the sweep and in the flat-tree gates.
- Rebuild on demand (periodic/on-demand, not per-session)

## Known gaps / candidates

- `services/domain/AgentListService.ts` — zero frontend consumers
  (obsolete candidate)
- `services/domain/TitleGenerationService.ts` — obsolete (superseded by
  TitleService)
- `services/metaTopicsService.ts` + `services/macroBackupService.ts` —
  zero consumers (bypassed/removal candidates)
- `components/features/monitoring/` — 5-of-6 simulated (only
  ConnectionStatus is real)
- `components/features/testing/` — fully client-side simulated
- ProviderConfig — zero consumers + redaction markers in source
- See [[atlas/ui/UI Atlas|master index]]'s sibling sections
  "🔍 Review — UI Atlas Phase 2 Findings" for the full list
