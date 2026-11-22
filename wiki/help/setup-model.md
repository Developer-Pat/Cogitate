---
title: Setup — Default Model
category: setup-model
subtopic: Setup
order: 5
confidence: high
created: 2026-08-04
updated: 2026-11-21
tags: [domain/help]
---

# Setup — Default Model

The default provider + model is what answers when nothing else is chosen — chat, session titles,
summaries, workflows and memory all inherit it, so setting it once is the whole job.

## Set it

Choose the provider and the model **on this tab**, then press **Save Default Model** — until you do, the
readout says the selection is not saved yet. The list is that provider's own catalogue; if the install's
stored model is not in it, it is still offered and marked *(current)*, so a save cannot silently replace a
working model string. The curated list (marked ✓ verified) is the human-reviewed shortlist and a good place
to start — see **Curated Models**.

**Setting the default seeds the agents.** Bob and Lois arrive as soon as a chat model resolves —
immediately, without a restart. On an install where nothing answers chat yet, they wait: the seed
reports *deferred* with the reason and tries again on the next start.

## Choosing

- A model that is free or local costs nothing per message and is fine to try first.
- Anything set as default is also what an **Exa** activation offers as its own model (see
  **Exa Agent**), so one choice can configure both — and neither takes it without a press.

## If nothing resolves

The readiness check says *nothing answers chat yet*, and the **Agents** item stays blocked behind
it. That is the honest state: no model, no answer — nothing is guessed and no agent is seeded on a
model nobody chose.

## Related

- [Default Provider](/wiki/help/providers-default) — what reads this value, and what ignores it
- [Setup — API Keys](/wiki/help/setup-keys) — the step before this one
- [Setup — Agents](/wiki/help/setup-agent) — what arrives once a model resolves
- [Setup — Overview](/wiki/help/setup-overview) — the verdict these steps move
