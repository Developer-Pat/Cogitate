---
title: ProductViewer
type: atlas-page
path: frontend/src/pages/ProductViewer.tsx
confidence: high
updated: 2026-10-07
tags: [type/page, domain/atlas-ui]
---

# ProductViewer

**Component**: `frontend/src/pages/ProductViewer.tsx`
**Route**: `/products/:path` (protected, icon `document`) — registered in
`frontend/src/config/routes.ts`. **No nav entry and no breadcrumb**: it is an addressable route,
reached from the products list or from any link, which is the point of it existing.

## Purpose

The full-page READ surface for a workflow product — a report that outgrows the modal on the products
page gets a page of its own, addressable so it can be linked and bookmarked. The body is rendered by
the same `ReportViewer` the modal uses; only the container differs.

## How the route param resolves

The `:path` segment is a **filename**, not a stored path:

1. `workflowService.getWorkflowProducts(200)` → `GET /api/v1/workflows/products?limit=200` — the whole
   display index;
2. the param is URL-decoded and matched against the LAST segment of each product's `path`
   (`p.path.split('/').pop()`).

So there is no per-product fetch behind this route: the index is loaded and searched client-side, and a
product beyond the 200-row window of that index reads as not found.

## States

| state | what renders |
|---|---|
| loading | a centered spinner in the page container |
| not found | a card — `Report not found`, the reason (`It may have been cleared or the link is stale.`) and **Back to Products** |
| loaded | a `PageBanner` titled with the product's `title` and subtitled `<product_type> · from <source_template> · <created_at, local>`, then the body in a card via `ReportViewer` |

A failed load (rather than an empty index) raises a toast — `Report` / `Failed to load the report` —
and lands on the same not-found card, so a broken read is never a blank page.

## State management

Plain `useState` (`product`, `loading`, `notFound`) with a `cancelled` flag guarding every async
`setState`, so navigating away mid-load cannot write into an unmounted component. The success path and
the not-found path are separate booleans rather than an inferred one.

## Related pages

- [[atlas/ui/pages/WorkflowProducts|WorkflowProducts]] — the list that links here
- [[atlas/ui/pages/WorkflowExecution|WorkflowExecution]] — the run a product comes out of
- [[atlas/api/routers/workflows|Workflows API]] — the products index
