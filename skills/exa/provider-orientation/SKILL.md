---
name: provider-orientation
description: "The provider surfaces of Cogitate — ORIENTATION ONLY (2026-08-21): there are TWO provider surfaces, and the api-surface skill does NOT cover providers. Read this BEFORE working with providers; discover the endpoints yourself and document what you used."
version: 1.0.0
author: Cogitate Team
tags: [cogitate, providers, orientation, discovery]
---

# Provider Orientation (NOT a solution guide)

This skill orients you — it deliberately does NOT walk you through
the task. The exercise is for YOU to discover the provider surface,
handle errors, and document what you learn.

## The two surfaces (the system design you must know)

1. **Provider configs** — the live connection configs (CRUD under
   `/api/v1/providers`, plus health under `/completion`). Machine
   discovery: `/providers/{id}/models/browse` fetches the live model
   lists from each provider (cached).

2. **The CURATED list** — the `curated_models` table. This is
   HUMAN-OWNED: the models this system actually recommends, shown
   when configuring an agent. The DB is the source of truth. It is
   deliberately SEPARATE from machine discovery — adding a provider
   config does NOT add it to the curated list.

## Your task pattern

- Explore the API surface (the routes, the payloads) BEFORE reading
  source files — the API is the extension point.
- The `cogitate-api-surface` skill does NOT cover providers yet —
  treat this as an invitation: note the endpoints and shapes you
  used, and what you learned, so the skill can absorb them after
  your run.
- Verify your work (read back what you wrote) and report the
  VERIFIED state — not just what you intended.
