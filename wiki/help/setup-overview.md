---
title: Setup Overview
category: setup-overview
subtopic: Setup
order: 1
confidence: high
created: 2026-08-04
updated: 2026-11-20
tags: [domain/help]
---

# Setup — Overview

The Overview tab is the install's **readiness verdict**: the facts that decide whether anything can
answer, measured once in the backend. `./cogitate.sh verify` prints the same verdict from a terminal —
one check, the same number.

## The order

| Item | What it means |
|---|---|
| **Provider + key** | A provider row with a key, or a local model server on this machine. |
| **Chat model** | The default provider + model. Title, summary, workflow and memory inherit it. |
| **Agents** | Bob and Lois — seeded the moment a chat model resolves. |
| **Exa runtime (optional)** | Reported and never counted: activating Exa is a decision, not a requirement. |

Each item's icon and sentence come from the backend. **Red** means you have to act. **Amber** means
it is waiting on an earlier step — there is nothing to do on it yet, and the copy does not ask you
to. **Dim** means optional.

**Click an item to go where it is fixed.** The checklist is a set of doors, not a set of tabs.

## What this page does not do

It changes nothing: no key is written, no model is probed, no agent is seeded by looking at it. It
reads one verdict and shows it.

The full path — clone, install, start, verify — is the **Installing Cogitate** topic. Providers are
managed in full on the **Provider Dashboard**.

## Related

- [Installing Cogitate](/wiki/help/setup-install) — the whole path, and the two decisions it leaves to you
- [Setup — API Keys](/wiki/help/setup-keys) · [Setup — Default Model](/wiki/help/setup-model) ·
  [Setup — Agents](/wiki/help/setup-agent) — the three steps, in order
- [Providers](/wiki/help/providers-overview) — the Provider Dashboard's own help
