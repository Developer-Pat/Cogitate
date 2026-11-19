---
title: ollamaCloudModelBrowser
type: atlas-service
path: backend/app/domain/providers/ollama_cloud_browser.py
confidence: high
updated: 2026-08-03
tags: [type/service, domain/atlas-ui]
---
# OllamaCloudModelBrowser

**Path**: `backend/app/domain/providers/ollama_cloud_browser.py`
**Type**: service (model discovery — Ollama Cloud)
**Status**: NEW (2026-08-03, Phase 2 of provider model curation roadmap)

## Purpose
Model browser for **Ollama Cloud** (hosted Ollama at `https://ollama.com`).
Fetches the model list from the native `/api/tags` endpoint, sending the
Bearer API key when one is set. Results cached in
`provider_model_cache` (1h TTL).

**No listing on ollama.com is auth-gated.** `/api/tags` answers 200 with no key at all, and so does
the OpenAI-compat `/v1/models` — measured: 200 to a deliberately fake key. Inference is the only
gated operation (`/api/chat` → 401 without one). A model list therefore proves only that the
endpoint is reachable: an `ollama_cloud` row's availability probe reads `/v1/models`, which is how a
dead key used to read as "connected" (the Test button now asks the gated path — see
`availability.probe_key_accepted`).

## Key differences from OllamaModelBrowser
- Base URL: `https://ollama.com` (not localhost:11434)
- Requires `api_key` (Bearer token from ollama.com account)
- `top_provider` = `ollama_cloud`
- Same model shape/transform (name, family, parameter size, quantization)

## Methods
- `browse_models(db, provider_id, api_key, base_url, filters)` — paginated
  browse (inherits filtering/sorting/pagination from ModelBrowserService)
- `_fetch_models(db, provider_id, base_url, api_key)` — cache-first fetch,
  then `GET {base_url}/api/tags` with `Authorization: Bearer <key>`

## Dependencies
- httpx, provider_model_cache_service, ModelBrowserService base

## Wiring
- `models_router.py`: `provider_type == "ollama_cloud"` → this browser
  (API key required — 400 if missing, unlike local ollama)
- `llm_factory.py`: `_create_ollama_cloud_client` — ChatOpenAI against
  `https://ollama.com/v1` (OpenAI-compatible), api_key + base_url
- `factory.py`: SUPPORTED_PROVIDERS entry (`ollama_cloud: cloud`)
- ProviderConfigModal.tsx: 'ollama_cloud' option added

## Related
- Roadmap: local/roadmaps/provider-model-curation-roadmap.md (Phase 2)
