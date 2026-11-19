---
title: Workflow Products
type: atlas-page
path: frontend/src/pages/WorkflowProducts.tsx
confidence: high
updated: 2026-08-10
tags: [type/page, domain/atlas-ui]
---

# Workflow Products

**Component**: `frontend/src/pages/WorkflowProducts.tsx`
**Route**: `/workflow-products` (protected, `requiresAuth: true`, icon `inbox`, breadcrumb "Workflow Products") — registered in `frontend/src/config/routes.ts` and linked from the sidebar navigation in `frontend/src/App.tsx` under the **Workflows** section (nav label "Products", alphabetical: Automation · Execution · Products · Templates)
**Last Update (fix 2026-08-13): both modals (report viewer + Clear) previously used the DaisyUI `modal-box` class inside a plain fixed overlay — `modal-box` defaults to `opacity: 0` unless revealed by a `.modal modal-open` wrapper, so the dark mask appeared with no box (the carried DaisyUI modal-box trap). Replaced with plain styled containers (rounded-2xl bg-base-100). Regression tests in WorkflowProducts.test.tsx assert no `modal-box` class.

## Purpose

The **display channel** of the workflow product distribution layer
— shows products (digests, alerts, reports) delivered by workflow
runs. Reads the display index (`data/monitor/products.json`) via
`GET /api/v1/workflows/products` — written by the
`DisplayDistributor` when a workflow delivers a product.

## Key Features

- **Collection pattern table** (products proliferate — a 5-min
  trigger = 288/day): Type badge (RSS Digest / Market Alert /
  Readiness Report / Exa Report — exa_report added 2026-08-13 with
  the Save-report feature, badge-info), Title, Workflow, Delivered, View actions
- **Search** (title or workflow) + **type filter** dropdown +
  **pagination** (pageSize 20) — the established WorkflowTable
  idiom
- **Report viewer modal**: View opens a modal rendering the
  product body with ReactMarkdown + remark-gfm +
  rehype-highlight (the WikiViewer pattern) — proper headings/
  lists/code vs raw text
- **Clear action** (stale-data reset, 2026-08-10): button appears
  when products exist; confirmation modal (the Session delete
  pattern — "cannot be undone") → `DELETE /api/v1/workflows/products`
  removes product files + the index (keeps monitor `state.json`)

## Components Used

| Component | Path | Purpose |
|---|---|---|
| `ErrorBoundary` | `frontend/src/components/ErrorBoundary.tsx` | Wraps the whole page |
| `PageBanner` | `frontend/src/components/ui/PageBanner.tsx` | Header + action slot (Refresh, Clear) |
| `ReactMarkdown` | `react-markdown` | Report rendering (remark-gfm, rehype-highlight) |

## Data Flow

1. **Mount**: `workflowService.getWorkflowProducts()` →
   `GET /api/v1/workflows/products?limit=50` → table state
2. **Filter/sort/paginate**: client-side `useMemo` (search,
   type filter, page slice) — the collection pattern
3. **View**: `setViewing(product)` opens the report modal with
   the product body rendered as markdown
4. **Clear**: confirmation modal → `workflowService.clearWorkflowProducts()`
   → `DELETE /api/v1/workflows/products` → empty state

## API Endpoints Called

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/workflows/products?limit=50` | List products (display index) |
| DELETE | `/api/v1/workflows/products` | Clear all product files + index |

## Related

- [[dev-notes/workflows/product-distribution|Workflow Product Distribution]] — the distribution layer
- [[atlas/api/routers/workflows|Workflows API]] — products + executions endpoints
- [[atlas/ui/pages/WorkflowAutomation|Workflow Automation]] — the triggered-execution sibling
