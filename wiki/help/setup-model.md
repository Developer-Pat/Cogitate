---
title: Setup — Default Model
category: setup-model
subtopic: Setup
order: 4
confidence: high
created: 2026-08-04
updated: 2026-11-20
tags: [domain/help]
---

# Setup — Default Model

The default provider + model is what answers when nothing else is chosen — chat, session titles,
summaries, workflows and memory all inherit it, so setting it once is the whole job.

## Set it

Open the **Provider Dashboard** and choose the default provider and model. The curated list (marked
✓ verified) is the human-reviewed shortlist, and a good place to start; any provider with a working
key shows its own catalog.

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

- [Setup — API Keys](/wiki/help/setup-keys) — the step before this one
- [Setup — Agents](/wiki/help/setup-agent) — what arrives once a model resolves
- [Setup — Overview](/wiki/help/setup-overview) — the verdict these steps move
