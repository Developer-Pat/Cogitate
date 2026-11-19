---
name: ask-before-destructive
description: "The destructive-ops protocol: never delete, clear, reset, or restart without explicit user confirmation. Use before ANY irreversible or system-affecting operation."
version: 1.0.0
author: Cogitate Team
tags: [cogitate, safety, destructive, protocol]
---

# Ask Before Destructive Operations

Deletion stays possible — but it is never automatic, and recovery
is explicit. This is the house rule for the external agent too.

## The protocol

1. **Classify the operation.** Destructive/irreversible: deleting
   products, clearing a monitor's dedup state, archiving agents,
   restarting the backend. Non-destructive: reading configs,
   listing triggers, verifying health.
2. **Ask before destructive.** State what will be affected and
   wait for explicit confirmation. The system's confirm modals
   are the human path — the agent asks the same way.
3. **Never auto-restore.** A deleted thing stays deleted until an
   explicit Restore action (the recoverable-delete pattern).
4. **Restart = destructive-ish.** It interrupts running work —
   confirm first unless the user explicitly asked for it.

## The exception

If the user's request IS the destructive operation ("delete
product X", "reset the monitor", "restart the backend", "delete
agent 45"), that is the explicit confirmation — perform it, then
VERIFY + report the verified outcome.

## The sanctioned tools (2026-08-19)

Agent retirement goes through the **delete-agent** tool (keyed —
the fix-mode grant gates it): it uses the SAME repository path as
the UI/API and VERIFIES by reading the row back. Never delete an
agent by editing the DB directly.

**The two tiers — know the difference:**
- **delete-agent with `hard: false`** (default) = DEACTIVATE: the
  agent is archived + recoverable. The undo is **restore-agent**
  (keyed, same grant). Deactivation without restore is a dead end
  — always offer the undo path.
- **delete-agent with `hard: true`** = PERMANENT SCRUB: the row +
  workspace + memory all go. IRREVERSIBLE. Only with explicit
  user confirmation, and never for an agent the user might want
  back.

**Reading the archived state:** **list-archived-agents** (READ,
no grant) shows the soft-deleted agents — check it before any
delete so you know what exists and what is recoverable.

## Common pitfalls

- Treating "delete the products" as a suggestion to be safe —
  no, the explicit request is the confirmation.
- Restarting the backend to 'help' without being asked.
