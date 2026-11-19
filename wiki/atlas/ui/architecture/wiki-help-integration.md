---
title: Wiki & Help Integration
type: atlas-architecture
path: backend/app/api/v1/wiki/router.py + frontend/src/components/help/
confidence: high
updated: 2026-08-01
tags: [type/architecture, domain/atlas-ui]
---

# Wiki & Help Integration

**Path**: `backend/app/api/v1/wiki/router.py` + `frontend/src/components/help/`
**Type**: architecture

## Overview

The application embeds a full wiki viewer + contextual help system. The
backend serves the git-tracked `wiki/` directory (markdown + html) through a
small REST API; the frontend renders it with the wiki-style markdown viewer
(react-markdown + Mermaid) inside both the WikiViewer page and the
HelpModal drawer.

```mermaid
flowchart LR
    W[wiki/ dir - git tracked] --> R[backend wiki router]
    R -->|GET /api/v1/wiki| T[tree .md + .html]
    R -->|GET /api/v1/wiki/{path}| P[page content]
    R -->|GET /api/v1/wiki/help?context=| H[help page]
    T --> F[WikiViewer page]
    P --> F
    F --> V[wiki markdown renderer]
    H --> M[HelpModal drawer]
    M --> V
```

## API Surface

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/wiki/` | Wiki tree (markdown + html files, ordered) |
| GET | `/api/v1/wiki/{path:path}` | Page content — resolution: exact path → recursive name search → `.html` fallback |
| GET | `/api/v1/wiki/help?context=` | Help page for a context key (contextual help) |

### Path resolution semantics (backend)

1. **Exact path** under `wiki/` (directory traversal guarded)
2. **Recursive name search** — wikilinks may omit the directory prefix
   (stem match, not partial)
3. **`.html` fallback** — serve HTML files directly as raw content
4. Security: traversal attempts rejected; results confined to `WIKI_ROOT`

## Help System Contract

The HelpModal (626L) implements a full help experience:

### Trigger
- Global event listener on `open-help-modal` — any component dispatches
  `window.dispatchEvent(new CustomEvent('open-help-modal', { detail: { context } }))`
  to open the drawer with a context.

### Fetch
- `GET /api/v1/wiki/help?context=<key>` returns the help page for that
  context. `HelpButton` components (one per feature page) carry the context
  key.

### Rendering
- react-markdown + Mermaid (same renderer as the wiki viewer)
- history stack + back navigation (drawer maintains its own nav history)
- content updates per context as the user navigates

### HelpButton
`components/help/HelpButton.tsx` — the trigger component mounted on feature
pages (currently 6 pages carry it). Dispatches `open-help-modal` with the
page's context key.

## Context Keys

Help pages live in `wiki/help/*.md`. Each page is addressed by a context key
(the file stem). The wiki sidebar nav is collapsible with auto-expand to the
active page (contextual atlas root pattern).

## Data Flow

```mermaid
sequenceDiagram
    participant B as HelpButton
    participant M as HelpModal
    participant API as wiki API
    participant W as wiki/help/*.md

    B->>M: dispatch open-help-modal (context)
    M->>API: GET /api/v1/wiki/help?context=key
    API->>W: resolve wiki/help/key.md
    W-->>API: markdown
    API-->>M: page content
    M->>M: render (react-markdown + Mermaid)
    M->>M: push history; enable back nav
```

## Wiki Viewer Page

`pages/WikiViewer.tsx` hosts the full wiki experience:
- sidebar tree (collapsible sections, default-collapsed, auto-expand to
  active page, manual-toggle preservation)
- content pane (markdown renderer + Mermaid)
- used for both the main wiki (`/wiki`) and the UI Atlas

## Related

- `backend/app/api/v1/wiki/router.py` — the API (3 endpoints)
- `frontend/src/components/help/HelpModal.tsx` (626L) — drawer
- `frontend/src/components/help/HelpButton.tsx` — trigger
- `frontend/src/pages/WikiViewer.tsx` — full-page viewer
- `wiki/help/` — 11 help pages (markdown, git-tracked)
- `wiki/` — the wiki content root (git-tracked)
