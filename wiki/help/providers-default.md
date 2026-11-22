---
title: Default Provider
category: providers-default
subtopic: Provider Management
order: 1
confidence: high
created: 2026-09-29
updated: 2026-11-22
tags: [domain/help]
---

# Default Provider

**Setup → Default Model** (`/setup?tab=model`) sets the one provider and model the system falls back to
when a piece of work does not name its own. There is ONE default, not one per surface: the same value the
provider rows mark as default and that `PUT /providers/default` writes.

## What it is used by

- The **title service** (session and chat titles).
- **Post and workflow steps** that need a model but were not given one.
- The **model factory**, as the base configuration for a request that names no provider.

Agents that were given their own provider or model ignore it — those are set in agent setup. **Exa keeps
its own provider** (Exa Config), and the vision model has its own setting, so neither reads this value.

## Setting it

- **Provider** — which configured provider the default model runs on. The current default is marked.
- **Model** — that provider's catalogue, searchable by name (the list comes from the cached model sync).
  If the stored model is not in the catalogue it is still offered, marked *(current)* — saving cannot
  silently swap a working model string for a different one.
- **Save Default Model** — persists the pair. Until you press it the readout says the selection is not
  saved yet, so a choice you did not save cannot be mistaken for the install's answer. Setting the default
  seeds the shipped agents immediately.

## Tips

- The default shows in agent setup as the starting point; each agent can override it.
- A provider needs a working API key (stored key or `.env`) before it can serve models — the
  **Overview** tab on Cloud Providers can test a provider's connection.
- Providers carry a **Priority** for fallback ordering (lower = first). See
  [Provider Reference & Quirks](/wiki/help/providers-reference) for per-provider setup gotchas.

## Related

- [Setup — Default Model](/wiki/help/setup-model) — the setup step, and what arrives once it resolves
- [Provider API Keys](/wiki/help/providers-keys) — what makes a model usable
