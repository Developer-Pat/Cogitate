---
title: Not Found
type: atlas-page
path: frontend/src/pages/NotFound.tsx
confidence: high
updated: 2026-07-31
tags: [type/page, domain/atlas-ui]
---
# Not Found

**Component**: `frontend/src/pages/NotFound.tsx`
**Route**: `*` (catch-all) — registered in `frontend/src/config/routes.ts`
**Last Updated**: 2026-07-31

## Purpose

Renders the 404 "Page Not Found" screen for any URL that does not match a registered route. It is registered in `frontend/src/config/routes.ts` as the catch-all route (`path: '*'`, `requiresAuth: false`, `breadcrumb: '404'`) and lazy-loaded via `React.lazy` for code splitting. Because it is public (no auth required), it displays for any visitor, authenticated or not, whenever React Router falls through every other route.

## Key Features

- Full-viewport DaisyUI hero layout (`hero min-h-screen bg-base-200`) with centered content in a `max-w-md` column
- Large `404` display in `text-primary` followed by a "Page Not Found" heading and a short explanatory message
- Two recovery actions implemented as client-side `<Link>`s:
  - **Go Home** — primary button navigating to `/` (Dashboard)
  - **View Logs** — outline button navigating to `/logs` (Logs)
  - Both buttons are styled with theme CSS variables (`--button-radius`, `--button-padding`, `--button-transition`) for consistent theming
- Sets the browser tab title and meta description via `usePageTitle('Not Found', 'Page not found')`
- No authentication gate — the page must render even for logged-out users landing on dead URLs

## Components Used

| Component | Path | Purpose |
|---|---|---|
| `Link` | `react-router-dom` (external package) | Client-side navigation to the `/` and `/logs` recovery routes without a full page reload |

## Hooks Used

| Hook | Path | Purpose |
|---|---|---|
| `usePageTitle` | `frontend/src/hooks/usePageTitle.tsx` | Sets `document.title` to `formatPageTitle('Not Found')` on mount, renders a Helmet entry with the title and the "Page not found" meta description, and restores the previous document title on unmount |

## Data Flow

No external data flows into or out of this page. It is purely presentational:

- `usePageTitle` writes the title and meta description into the document head on mount (via `document.title` plus `react-helmet-async`) and restores the previous title on cleanup
- The page body is static JSX — the heading, copy, and links never change
- Clicking either link hands off to React Router, which performs client-side navigation to the target route

No fetching, transformation, or serialization of data occurs anywhere in this page.

## State Management

None. The page reads and writes no stores (no Zustand/Redux stores touched), holds no local component state, and subscribes to no context. Its only side effect is the document title/meta managed by `usePageTitle`.

## API Endpoints Called

None. The page makes no network requests — confirmed by source inspection: neither `NotFound.tsx` nor anything it imports (`usePageTitle`, `Link`) contains any `/api/v1` references or service usage.

## Related Pages

- [[Dashboard]] — destination of the "Go Home" link (`/`)
- [[Logs]] — destination of the "View Logs" link (`/logs`)
