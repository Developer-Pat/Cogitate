---
title: WorkflowKinds
type: atlas-page
path: frontend/src/pages/WorkflowKinds.tsx
confidence: high
updated: 2026-10-07
tags: [type/page, domain/atlas-ui]
---

# WorkflowKinds

**Component**: `frontend/src/pages/WorkflowKinds.tsx`
**Route**: `/workflow-kinds` (protected, `requiresAuth: true`, icon `template`) — registered in
`frontend/src/config/routes.ts`; the sidebar's **Workflows** section in `App.tsx` (nav label
"Templates").

## Purpose

The canonical workflow process **shapes**. In this model a **template IS a kind**: the kind defines the
process, and a workflow is a configured instance of one. This page shows the kinds — **read-only**; the
configured instances live on [[atlas/ui/pages/WorkflowTemplates|WorkflowTemplates]].

## The list

One card per kind: the name, the product-type badge, the description, the inputs line, and the
`builder_key`.

- The badge maps `report` / `file` / `index` through `PRODUCT_LABELS`, falling back to the raw value —
  an unmapped type shows itself rather than rendering blank.
- **Inputs** render only when the kind declares any, each as `name (type, required)`, so a kind that
  takes nothing has no empty line.
- **`builder_key`** is shown in mono: the key that binds the kind to its builder.

## Filtering happens on the SERVER

The search box and the product-type select are both server-side filters — each change re-fetches:

```
fetchWorkflowKinds({ q, product_type })  →  GET /api/v1/workflow-kinds?q=…&product_type=…
```

with empty values omitted rather than sent blank. Debouncing is the caller's; the page passes the
current values.

## The focus contract (this page's half)

On mount the page calls `claimDeclaredPrimaryInput()` from `services/focusContract`. The search input
declares itself with `data-autofocus`, and **the declaration is a yield — somebody has to act on it**.
On a cold load (a lazy route, where nothing else owns the caret) that somebody is this page, so the
search box takes focus when the page arrives.

## States

| state | what renders |
|---|---|
| loading | a centered spinner |
| error | an inline `alert-error` — `Failed to load workflow kinds.` |
| empty | `No kinds match.` across the grid |
| loaded | the kind cards |

## State management

Local `useState` only: `kinds`, `loading`, `error`, `q`, `productType`. Each fetch carries a `cancelled`
flag so a superseded request cannot overwrite a newer result.

## Related pages

- [[atlas/ui/pages/WorkflowTemplates|WorkflowTemplates]] — the configured instances of these kinds
- [[atlas/ui/pages/WorkflowAutomation|WorkflowAutomation]]
- [[atlas/ui/pages/WorkflowExecution|WorkflowExecution]]
- [[atlas/api/routers/workflow-kinds|Workflow Kinds API]]
