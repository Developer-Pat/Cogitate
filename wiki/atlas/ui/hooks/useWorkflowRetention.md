---
title: useWorkflowRetention
type: atlas-hook
path: frontend/src/hooks/useWorkflowRetention.ts
confidence: high
updated: 2026-10-07
tags: [type/hook, domain/atlas-ui]
---

# useWorkflowRetention

**Hook**: `frontend/src/hooks/useWorkflowRetention.ts`
**Used by**: [[atlas/ui/components/features/workflows/RetentionCard|RetentionCard]]

## Purpose

The retention card's data half: fetch the effective policy (plus the defaults behind it and what
the store holds), save a partial policy, preview a prune, apply one. Page → hook → service, the
house layering — the card renders, this hook owns the calls and the in-flight guard, the service
owns the transport.

Nothing here decides a window. The values come from the backend, which resolves them from the app
settings, so the surface cannot drift from the policy the maintenance job actually applies.

## Returns

`policy`, `defaults`, `stats`, `report` (the last preview or applied prune), `loading`, `busy`,
`error`, and the verbs `refresh`, `save(partial)`, `preview`, `prune`.

## Notes

- An in-flight guard is a **ref**, not state: it has to be readable in the same tick that starts
  the request, which a state update is not.
- A successful **apply** logs (counts and bytes) rather than toasting: the card's own readout
  refreshes, and the house rule is that a visible result is the confirmation.
- A FAILED apply returns `false` so the confirm dialog stays open with the reason on screen.

## Related

- [[atlas/ui/pages/Settings|Settings]]
- [[atlas/ui/services/domains/llm/workflowService|workflowService]]
