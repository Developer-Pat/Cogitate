---
title: Default Provider
category: providers-default
subtopic: Provider Management
order: 1
confidence: high
created: 2026-09-29
tags: [domain/help]
---

# Default Provider

The Default tab sets the one provider + model the system falls back to when a
piece of work does not name its own.

## What it is used by

- The **title service** (session and chat titles).
- **Post and workflow steps** that need a model but were not given one.
- The **model factory**, as the base configuration for a request that names no
  provider.

Agents that were given their own provider or model ignore it — those are set in
agent setup. **Exa keeps its own provider** (Exa Config), and the vision model
has its own setting, so neither reads this value.

## Setting it

- **Provider** — pick which configured provider the default model runs on.
- **Model** — searchable: type to filter that provider's catalog (the list comes
  from the cached model sync). Pick the model you want as the system default.
- **Save Configuration** — persists the pair. Changes are held as *pending*
  until you save, so the readout above the button tells you whether what is on
  screen is what is stored.
- With no default set, the block offers **Initialize Default (Ollama)** to seed
  a local one.

## Tips

- The default shows in agent setup as the starting point; each agent can
  override it.
- A provider needs a working API key (stored key or `.env`) before it can serve
  models — the **Overview** tab can test a provider's connection.
- Providers carry a **Priority** for fallback ordering (lower = first). See
  [Provider Reference & Quirks](providers-reference.md) for per-provider setup
  gotchas.
