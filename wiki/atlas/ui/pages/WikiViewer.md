---
title: Wiki Viewer
type: atlas-page
path: frontend/src/pages/WikiViewer.tsx
confidence: high
updated: 2026-10-12
tags: [type/page, domain/atlas-ui]
---
# Wiki Viewer

**Component**: `frontend/src/pages/WikiViewer.tsx`
**Route**: `/wiki` and `/wiki/{path}` (wiki tree + page rendering)
**Last Updated**: 2026-07-31

## Purpose
Renders the project wiki: sidebar tree of all wiki files/directories, markdown page content (with wikilinks, GFM, Mermaid diagrams), and HTML diagram files in iframes.

## Key Features
- **WikiSidebar**: recursive tree from `GET /api/v1/wiki` (directories expanded, active page highlighted)
- **Markdown rendering**: ReactMarkdown + remark-gfm; wikilinks `[[page-name]]` converted to `/wiki/{name}` links (Link component); external links open in new tab
- **Frontmatter display**: confidence badge (high/medium/low), tags, updated date
- **HTML diagrams**: served as text/html -> rendered in sandboxed iframe
- **Breadcrumb** navigation; browser back/forward via popstate handler
- Loading / error states (404 'Page not found', generic error)

## Components Used
| Component | Path | Purpose |
|-----------|------|---------|
| WikiSidebar | inline in page | Wiki tree navigation |
| ReactMarkdown | react-markdown (lib) | Markdown -> HTML |
| remarkGfm | remark-gfm (lib) | GitHub-flavored markdown |
| Link | react-router-dom | Internal navigation |

## Hooks Used
| Hook | Path | Purpose |
|------|------|---------|
| useLocation | react-router-dom | Current wiki path |
| useNavigate | react-router-dom | Breadcrumb navigation |

## Data Flow
- **Tree**: `fetch('/api/v1/wiki')` on MOUNT AND ON EVERY NAVIGATION (`currentPath` dependency) -> `{ tree: [...] }` -> sidebar state. Re-read per navigation because the corpus changes under a mounted view: a page added, moved or removed otherwise left the sidebar holding paths that 404 on click. The swap is in the background, and the sidebar's collapse state is local, so opened folders survive it.
- **Page**: `fetch('/api/v1/wiki/{path}')` -> WikiPage { path, title, content, frontmatter, children } OR HTML content (served as text/html for diagram files)
- Path resolution: `location.pathname.replace(/^\/wiki\/?/, '') || 'index'`
- Wiki pages include help pages (`wiki/help/*.md`) and the UI Atlas (`wiki/atlas/ui/*`); the help-context API (`/api/v1/wiki/help?context=`) is separate (used by HelpModal)

## State Management
- Local state: tree, page, htmlContent, loading, error

## API Endpoints Called
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/wiki` | Full wiki tree |
| GET | `/api/v1/wiki/{path}` | Page content (markdown or HTML) |

## Related Pages
- HelpModal (components/help) — right-drawer help using `GET /api/v1/wiki/help?context=`
- UI Atlas — developer docs rendered here