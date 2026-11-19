---
title: curatedModelsService
type: atlas-service
path: frontend/src/services/domains/providers/curatedModelsService.ts
confidence: high
updated: 2026-08-03
tags: [type/service, domain/atlas-ui]
---
# curatedModelsService

**Path**: `frontend/src/services/domains/providers/curatedModelsService.ts`
**Type**: service (API client — curated model list)
**Status**: NEW (2026-08-03, Phase 1 of provider model curation roadmap)

## Purpose
API client for the curated model list — the human-owned recommendation
layer backed by `curated_models` DB table and `/api/v1/curated-models`
endpoints. Distinct from model discovery (`provider_model_cache` +
modelBrowserService): discovery answers "what does the provider offer?",
curation answers "what should we recommend?".

## Methods
- `fetchCuratedModels(provider?)` — GET list, optional provider filter
- `addCuratedModel(model)` — POST new entry
- `updateCuratedModel(id, updates)` — PUT category/sort/active/etc.
- `removeCuratedModel(id)` — DELETE by DB row id
- `toCuratedModel(dto)` — maps API DTO (snake_case) to frontend
  CuratedModel shape; carries DB row id via `curatedRowId`

## Dependencies
- apiClient (HTTP)
- `frontend/src/config/curatedModels.ts` — seed/default data + CuratedModel
  type (config file now used as fallback, not source of truth)

## Related
- Backend: `backend/app/api/v1/curated_models_router.py`,
  `backend/app/domain/providers/curated_models_service.py`
- Consumer: ProfileDetail.tsx (Tier 2 model fetch — API first, config seed
  fallback)
- Roadmap: local/roadmaps/provider-model-curation-roadmap.md (Phase 1)
