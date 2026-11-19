---
title: Adding a New Provider (howto)
type: atlas-devnote
category: configuration
order: 3
confidence: medium
updated: 2026-10-11
tags: [type/dev-notes, domain/configuration]
---

# Adding a New Provider (howto)

## Overview

Providers are wired in several places. A new provider needs a client
factory, a key slot, a provider row, and (optionally) curated models.

## Steps

1. **Settings field** — add `<provider>_api_key: str` to Settings
   (backend/app/core/config.py) + the env var in `.env`.
2. **The type's canonical endpoint** — add the vendor's published address to
   `PROVIDER_ENDPOINTS` in `domain/providers/provider_endpoints.py`, OR leave
   the type absent on purpose. Absence is an answer: `openai` and `anthropic`
   are deliberately out, because each name covers a hosted vendor AND any
   self-hosted OpenAI-compatible server, so no single address can be right and
   their rows must declare `base_url`. A row's `base_url` always wins; the
   registry answers only for a row that declares none, and
   `resolve_endpoint` LOGS that omission.
3. **Client factory** — add `_create_<provider>_client()` in
   llm_factory.py and wire it into `get_llm_from_config` dispatch. The adapter
   carries NO endpoint of its own: the dispatcher resolves the endpoint once
   and hands it over.
4. **Key plumbing** — add the env-var fallback branch to the key
   resolution sites (models_router._get_provider_api_key,
   management_router.get_provider_models) + EnvKeyStore's
   PROVIDER_ENV_VAR map (so the Keys tab can write it).
5. **Provider row** — the providers table holds the row; the Keys
   tab + status endpoints discover it via provider_type.
6. **Discovery** — add a discover_<provider>_models branch in
   discovery_service.py for catalog sync. A vendor-specific catalog reader may
   keep the vendor's OWN root as a named constant (`deepseek_client`,
   `groq_client`, `openrouter_client` do, with a note at the site): reading one
   vendor's published catalog is a definition, while choosing who answers a
   completion is a decision and resolves from the row.
7. **Curated models** — add entries via the Curated tab (DB) +
   frontend/src/config/curatedModels.ts seed fallback.

## Gotchas

- Provider `type` strings must match everywhere (provider_type in DB
  = settings field suffix = EnvKeyStore map key).
- **A row's `base_url` names the API root the app DIALS.** A type whose one
  host speaks BOTH an OpenAI-compatible API and a native one (`ollama_cloud`)
  carries its COMPAT root (`https://ollama.com/v1`); native consumers derive
  the bare host through `provider_endpoints.native_root` instead of pasting
  their path onto the compat root. A row carrying the wrong root is REPORTED
  (the provider test card, the capability read-out, the log at dispatch) and
  never rewritten — the row stays the user's.
- **The litellm handler decides which root it needs.** `domain/providers/litellm_route.py` is the ONE
  mapping: `litellm_model_string()` picks the handler — the row's TYPE decides it (the ollama family
  rides the tool-capable `ollama_chat`, the local llama.cpp row rides the `openai` adapter), the row
  NAME being the fallback for a caller with no type in hand — and `api_base_for()` derives the root
  that handler needs. The handlers compose differently: litellm's `ollama_chat` builds
  `{api_base}/api/chat` itself, while the `openai` prefix posts to
  `{api_base}/chat/completions`.
- The test endpoint (POST /managed/{id}/test) reads the key via
  env fallback; a 403 with a valid key often means network/VPN
  (see wiki/help/providers-reference.md — Groq quirk).
