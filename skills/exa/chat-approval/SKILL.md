---
name: chat-approval
description: "The chat-authorization protocol (2026-08-21): when you propose an edit during a chat, the user sees an Allow edit / Deny card with the diff — your edit applies ONLY if they allow it. Use whenever you intend to write or patch a file in a chat session."
version: 1.0.0
author: Cogitate Team
tags: [cogitate, approval, permission, edits, chat]
---

# Chat Authorization (per-edit approval)

Cogitate's permission model has three tiers. In a chat session you
are on the tier the user selected on the Exa Agent page:

| Tier | What happens when you propose an edit |
|---|---|
| **Chat approval** (default) | the user sees an **Allow edit / Deny card with the diff** — the edit applies only if they click Allow (60s window; unanswered = denied) |
| Fix mode | edits inside the workspace auto-approve (the scoped grant) |
| **YOLO** | edits anywhere auto-approve — NO card (the secret-file guard still protects .env/.ssh/.git; the user can stop you with the chat Stop button; every action is still audited) |

The tier is in the session's MODE directive — read it before editing.
Under YOLO, still work in tight, verifiable steps and report every
change: unrestricted is not unsupervised.

## The protocol

1. **Propose the edit normally** — use write_file / patch with the
   full old/new content. The system intercepts it and shows the
   user the diff.
2. **WAIT for the decision.** The approval card has a 60-second
   window. Do NOT retry, do NOT work around it (no terminal
   bypass — the gate is deliberate).
3. **If allowed** — the edit applies once; continue + verify.
4. **If denied** — the edit is rejected; keep working read-only.
   Explain the change you proposed; the user can re-approve or
   grant fix mode for the whole task.
5. **Ask first when unsure.** A denied edit is not a failure —
   it is the user deciding granularly. That granularity is the
   feature.

## What to do when denied

- Report the denial honestly ("the edit was not approved").
- Offer the alternative: apply it yourself (the user pastes), or
  the user grants fix mode for the broad tier.

## The security contract

- The approval is request-bound: only the matching pending request
  resolves; stale responses are dropped.
- The diff is visible BEFORE the decision — the user never
  approves blind.
- Every decision is recorded in the verification store.
