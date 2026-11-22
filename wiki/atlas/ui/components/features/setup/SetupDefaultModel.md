---
title: SetupDefaultModel
type: atlas-component
path: frontend/src/components/features/setup/SetupDefaultModel.tsx
confidence: high
updated: 2026-11-22
tags: [type/component, domain/atlas-ui]
---

# SetupDefaultModel

The Setup page's **Default Model** step: choose the provider and model the install falls back to, save
once, done. It replaced a stub that merely linked to the cloud-providers page's Default tab — a tab that
no longer exists, so the last step of setup opened a page with nothing on it.

## How it saves

`PUT /api/v1/providers/default` with `{provider_id, model}` — the same call the old dashboard tab and the
CLI drive. The model is written to the row's `config.default_model`, which is what the title service,
summaries, workflow steps and memory read.

## Pending until saved

The selection is local state and the readout says so: *"Not saved yet — press Save…"* until it differs
from the stored default, *"Stored: <model> via <provider>."* otherwise. The Save button is disabled when the
selection equals what is stored, because the selector fires its change callbacks once on MOUNT and that
mount must not read as unsaved edits.

## Two mounted-order rules it pays for

- **The selector mounts after the first read** (`!loading`) and is keyed by the stored provider id. It
  loads its model list from the provider it is handed at mount; mounting it while the default was still
  loading left it fetching provider `0` and rendering *No models available*.
- **The stored model is always an option.** The catalogue may not list it (`deepseek-v4-flash` against a
  list carrying `deepseek-flash`), and a `<select>` with no matching option renders blank — which would let
  the first Save silently replace a working model string. `DefaultProviderConfig` offers it, marked
  *(current)*.

## Related

- [[atlas/ui/pages/SetupPage|SetupPage]] — hosts it on the Default Model tab.
- [[atlas/ui/components/features/providers/DefaultProviderConfig|DefaultProviderConfig]] — the selector.
