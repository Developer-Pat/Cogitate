---
title: Dev Notes — Application Lifecycle
type: atlas-index
path: wiki/dev-notes/lifecycle
confidence: medium
updated: 2026-09-17
tags: [type/index, domain/lifecycle]
---

# Application Lifecycle — Dev Notes

Everything with a **phase**: what the application does when it starts, what it
does on its own while running, and how it stops.

## How this section is organised

By **when it happens**, not by topic — so a new fact has an obvious home:

| phase | page | answers |
|---|---|---|
| **Launching** | [[dev-notes/lifecycle/starting|Starting]] | the launcher, the ports it binds, and the two frontend builds |
| **Boot** | [[dev-notes/lifecycle/startup|Startup]] | what runs, in what order, before the app serves |
| **Running** | [[dev-notes/lifecycle/background-work|Background Work]] | what runs without anyone asking, and how to turn it off |
| **Stopping** | [[dev-notes/lifecycle/shutdown|Shutdown]] | the drain, the bound, and the record of how it ended |
| **After** | — (in the Shutdown page) | what the next boot reads and reports |

## Inventory

- [[dev-notes/lifecycle/starting|Starting — the launcher, the ports, and the two builds]]
- [[dev-notes/lifecycle/startup|Startup — the boot sequence]]
- [[dev-notes/lifecycle/background-work|Background Work — what runs unasked]]
- [[dev-notes/lifecycle/shutdown|Shutdown — the contract]]

## The one rule for this section

**A page here must say how to check it is still true.** Lifecycle facts drift
quietly: a doc that lists one recurring loop fewer than the code does fails
silently and forever, and nothing notices. So each page carries the command or
log line that reveals the current truth, and the reader is expected to run it.

That is the same rule the rest of the project runs on — *a claim that nothing
checks drifts away from the code* (see
[[dev-notes/lessons-learned/checkable-claims|Checkable Claims]]).
