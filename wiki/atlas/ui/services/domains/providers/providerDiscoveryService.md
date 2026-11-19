---
title: ProviderDiscoveryService
type: atlas-service
path: backend/app/domain/providers/discovery_service.py
confidence: high
updated: 2026-08-03
tags: [type/service, domain/atlas-ui]
---

# ProviderDiscoveryService

Per-provider model discovery for the provider catalog cache
(`provider_model_cache`). Each method fetches live models from the
provider API, transforms them into the unified cache shape, writes
them via `provider_model_cache_service.cache_models`, and falls back
to the expired cache on API error.

## Methods

| Method | Provider | Notes |
|---|---|---|
| `discover_openrouter_models` | openrouter | Bearer key required |
| `discover_ollama_models` | ollama | Local, no key; short TTL (1h) |
| `discover_deepseek_models` | deepseek | Key required |
| `discover_groq_models` | groq | Key required |
| `discover_ollama_cloud_models` | ollama_cloud | **Added 2026-08-03** — Bearer key, native `/api/tags` (same shape as local Ollama) with auth |

## `discover_ollama_cloud_models` (2026-08-03)

Added because the management router's discovery dispatch had NO
ollama_cloud branch (fell through to "not yet implemented" — the
default-provider model dropdown showed empty for Ollama Cloud even
though the browse router already supported it).

- `GET {base_url}/api/tags` with `Authorization: Bearer {api_key}`
- Transforms each `{name, details, size}` → cache row (id/name =
  model name, display_name = name before `:`, top_provider =
  `ollama_cloud`, pricing 0)
- Caches with 1h TTL; expired-cache fallback on API error
- Live-verified 2026-08-03: `/api/v1/providers/managed/5/models` →
  18 real models

## Callers

- `backend/app/api/v1/providers/management_router.py` —
  `get_provider_models` (default-provider model list). Gained the
  `ollama_cloud` env-key fallback (`settings.ollama_cloud_api_key`) +
  discovery branch on 2026-08-03 — the provider was listed as
  key-required but had no settings branch (always None).
- `backend/app/api/v1/providers/models_router.py` — the browse router
  (separate; its `_get_provider_api_key` also gained the branch).

## Related

- `wiki/atlas/ui/services/domains/providers/ollama_cloud_browser.md` —
  the browse-path browser (different entry point, same provider)
- `provider_model_cache` table — storage
