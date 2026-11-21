---
title: Setup — Agents
category: setup-agent
subtopic: Setup
order: 5
confidence: high
created: 2026-08-04
updated: 2026-11-20
tags: [domain/help]
---

# Setup — Agents

Two reporters — **Bob** and **Lois** — ship with the install and are seeded by it. They are what this
install carries out of the box: the character ships, the use is yours.

## When they arrive

The seed runs on the moment a **chat model resolves** — no separate step, and no restart. Until then
the Agents item on the Overview is *blocked*, not failing: there is nothing for you to do but set the
model.

Each agent gets its own workspace under `agents/<key>/` (persona, an empty state, and its skills), its
toolkits, and its face. Their memory starts empty **by design** — facts and beats form from your own
use.

## Adding more

- **Agent Profiles** is where agents are created, edited and cloned.
- Any agent can be put behind a **workflow** to run on a schedule; nothing schedules the reporters on
  its own.
- The desk as a *team* — journal, shared role skills, an editor — is the next layer, not this
  release.

Each agent takes its service from this install's answer to "what answers chat". No model is written
into a package, so a different key or another machine re-decides it.

## Related

- [Setup — Default Model](/wiki/help/setup-model) — the step that seeds them
- [Agent Profiles](/wiki/help/agent-profiles) — creating, editing and cloning agents
- [Exa Agent](/wiki/help/exa-agent) — the external agent, activated separately
