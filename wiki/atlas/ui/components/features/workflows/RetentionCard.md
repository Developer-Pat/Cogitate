---
title: RetentionCard
type: atlas-component
path: frontend/src/components/features/workflows/RetentionCard.tsx
confidence: high
updated: 2026-10-07
tags: [type/component, domain/atlas-ui]
---

# RetentionCard

**Component**: `frontend/src/components/features/workflows/RetentionCard.tsx`
**Used by**: [[atlas/ui/pages/Settings|Settings]] page (the **Data** tab — the app's own data)

## Purpose

The surface for the workflow-run retention WINDOWS. A run leaves three things behind — its row,
its debug snapshots inside that row, and its checkpoint journal — and every window that decides
what is kept is CONFIG, read from and written to the app settings through the backend. Nothing
about the policy is compiled in, so this card edits data rather than restating code.

It shows what the store HOLDS beside the windows that decide it (runs kept, snapshot MB, oldest
and newest run), because a number the reader cannot connect to a consequence is decoration. Each
window carries the shipped default next to it when the current value differs, so a reader can
tell a default from somebody's choice.

## Controls

| Control | Verb |
|---|---|
| four number fields (snapshots, runs, abandoned-after, prune hour) + **Save the windows** | writes the policy (validated server-side: a nonsense window is refused, not stored) |
| **Prune automatically** toggle | saves immediately — it is a switch, not a form field |
| **Preview** | a dry run: counts what a prune would remove, changes nothing |
| **Prune now** | previews fresh, then opens the confirm dialog |

## The destructive verb

The house procedure: a native `<dialog className="modal">` with the plain panel (NEVER DaisyUI's
`modal-box`), a confirm with BUTTONS and no typed phrase, the dialog naming what dies and what
cannot come back, the panel taking the caret one frame after `showModal()`, and a refusal that
KEEPS THE DIALOG OPEN with the server's own sentence. The apply request carries `confirm=true`;
the endpoint refuses an apply without it.

The preview is re-run on every "Prune now", so the numbers the dialog shows are the numbers the
confirm would act on.

## Data flow

`useWorkflowRetention` → `workflowService.getRetention / updateRetention / pruneRetention` →
`GET/PUT /api/v1/workflows/retention`, `POST /api/v1/workflows/retention/prune`.

## Related

- [[atlas/ui/hooks/useWorkflowRetention|useWorkflowRetention]]
- [[atlas/api/routers/workflows|Workflows API]] — the retention endpoints
- [[dev-notes/workflows/workflow-architecture|Workflow architecture]] — the policy's meaning
