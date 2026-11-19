/**
 * Curated Models Service
 *
 * API client for the curated model list (human-owned recommendations).
 * Backed by the /api/v1/curated-models endpoints; the curatedModels.ts
 * config file provides seed/default data for first-load fallback.
 */

import { apiClient } from '@/services/apiClient'
import type { ApiResponse } from '@/types'
import type { CuratedModel } from '@/config/curatedModels'

/**
 * Curated model as returned by the API (snake_case fields).
 */
export interface CuratedModelDTO {
  id: number
  model_id: string
  model_name: string
  provider: string
  category: string | null
  description: string | null
  context_length: number | null
  is_free: boolean | null
  verified: boolean
  is_active: boolean
  thinking: string
  location: string
  created_at: string | null
  updated_at: string | null
}

/**
 * Convert a CuratedModelDTO (API) to the frontend CuratedModel shape.
 */
export function toCuratedModel(dto: CuratedModelDTO): CuratedModel {
  return {
    // Frontend CuratedModel.id is the MODEL ID (matches provider model ids),
    // not the DB row id. The DB row id is carried separately for updates.
    id: dto.model_id,
    name: dto.model_name,
    provider: dto.provider,
    category: (dto.category ?? undefined) as CuratedModel['category'],
    description: dto.description ?? undefined,
    contextLength: dto.context_length ?? undefined,
    isFree: dto.is_free,
    verified: dto.verified,
    thinking: dto.thinking as CuratedModel['thinking'],
    location: dto.location as CuratedModel['location'],
    // Row id from the curated_models table (for update/delete calls).
    // The CuratedModel interface doesn't declare it; access via cast.
    curatedRowId: dto.id,
  } as CuratedModel & { curatedRowId: number }
}

/**
 * Fetch curated models from the API, optionally filtered by provider.
 */
export async function fetchCuratedModels(
  provider?: string,
): Promise<CuratedModel[]> {
  const query = provider ? `?provider=${encodeURIComponent(provider)}` : ''
  const resp = await apiClient.get<ApiResponse<CuratedModelDTO[]>>(
    `/api/v1/curated-models${query}`,
  )
  const data = resp.data?.data ?? (resp.data as unknown as CuratedModelDTO[])
  return (data ?? []).map(toCuratedModel)
}

/**
 * Add a model to the curated list.
 */
export async function addCuratedModel(
  model: Omit<CuratedModel, 'id'> & { id?: string },
): Promise<CuratedModel> {
  const resp = await apiClient.post<ApiResponse<CuratedModelDTO>>(
    '/api/v1/curated-models',
    {
      provider: model.provider,
      model_id: model.id,
      model_name: model.name,
      // THE DESCRIPTOR IS OPTIONAL: nobody chose one, so nothing is sent and the row stores
      // "not described" rather than a word a layer below invented (see `thinking` below).
      ...(model.category ? { category: model.category } : {}),
      description: model.description ?? null,
      context_length: model.contextLength ?? null,
      // THE COST IS NOT SENT (Phase 4): the API derives it from the provider's own cached
      // pricing as the row is created, and it REFUSES a request that states it — so a
      // payload carrying `is_free` would be a 422, not a harmless extra field.
      // `location` is sent explicitly — a default that reaches the row on purpose.
      // `thinking` is NOT sent when nobody chose a level: the API then derives it from
      // the provider's own claim, which beats this form inventing 'none' for a driver
      // that cannot be told not to think.
      ...(model.thinking ? { thinking: model.thinking } : {}),
      location: model.location ?? 'cloud',
    },
  )
  const dto = resp.data?.data ?? (resp.data as unknown as CuratedModelDTO)
  return toCuratedModel(dto)
}

/**
 * Update a curated model entry.
 */
export async function updateCuratedModel(
  id: number,
  updates: Partial<{
    model_name: string
    category: string | null
    description: string | null
    context_length: number | null
    is_active: boolean
    thinking: string
    location: string
  }>,
): Promise<CuratedModel> {
  const resp = await apiClient.put<ApiResponse<CuratedModelDTO>>(
    `/api/v1/curated-models/${id}`,
    updates,
  )
  const dto = resp.data?.data ?? (resp.data as unknown as CuratedModelDTO)
  return toCuratedModel(dto)
}

/**
 * Remove a model from the curated list.
 */
export async function removeCuratedModel(id: number): Promise<void> {
  await apiClient.delete(`/api/v1/curated-models/${id}`)
}

/**
 * What verifying one curated row against its provider found, and what it did.
 *
 * The endpoint returns this FLAT (no `{data: …}` envelope), which is why this shape is
 * declared here rather than imported from the generated types.
 */
export interface CuratedWindowVerification {
  curated_id: number
  provider: string
  model_id: string
  curated: number | null            // what the row said before
  discovered: number | null         // what the provider's own list says
  window: number | null             // what the row says now
  verified: boolean                 // does the row agree with a claim we stand behind?
  mismatch: boolean                 // did the two numbers disagree?
  stale: boolean                    // is the provider's claim past its TTL?
  age_hours: number | null
  refreshed: boolean                // did we ask the provider again during this check?
  thinking_curated: string          // the row's level BEFORE this check
  thinking_provider: string | null  // the provider's own words, when it exposes any
  max_completion: number | null     // the provider's own output cap, when it states one
  note: string
  thinking_adopted: string | null   // the level the row carries AFTER (null = unchanged)
}

/**
 * Verify ONE row's window against the provider's own catalog claim.
 *
 * `refresh` is the only question this asks: ask the provider for its list again before
 * comparing, or read the claim our discovery fetch already recorded — which may be
 * dated, and the response's `stale` / `age_hours` say so rather than passing it off as
 * fresh.
 *
 * The row ADOPTS the provider's number and its reasoning claim; a disagreement comes
 * back as `mismatch`, reported rather than hidden. A refresh that cannot run is a note,
 * not a failure: the check still reports what it read.
 */
export async function verifyCuratedModelWindow(
  rowId: number,
  refresh = false,
): Promise<CuratedWindowVerification> {
  const resp = await apiClient.post<CuratedWindowVerification>(
    `/api/v1/curated-models/${rowId}/verify-window`,
    { refresh },
  )
  if (resp.error || !resp.data) {
    throw new Error(resp.error?.message ?? 'The check could not run')
  }
  return resp.data
}
