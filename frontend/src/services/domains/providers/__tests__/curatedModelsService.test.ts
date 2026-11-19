import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  fetchCuratedModels,
  addCuratedModel,
  updateCuratedModel,
  removeCuratedModel,
  verifyCuratedModelWindow,
  toCuratedModel,
  type CuratedModelDTO,
} from '../curatedModelsService'

// Mock apiClient
vi.mock('@/services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

import { apiClient } from '@/services/apiClient'

const mockGet = apiClient.get as ReturnType<typeof vi.fn>
const mockPost = apiClient.post as ReturnType<typeof vi.fn>
const mockPut = apiClient.put as ReturnType<typeof vi.fn>
const mockDelete = apiClient.delete as ReturnType<typeof vi.fn>

const dto: CuratedModelDTO = {
  id: 42,
  model_id: 'test/model-1',
  model_name: 'Test Model 1',
  provider: 'openrouter',
  category: 'chat',
  description: 'A test model',
  context_length: 128000,
  is_free: true,
    verified: true,
  is_active: true,
  thinking: 'none',
  location: 'cloud',
  created_at: '2026-08-03T10:00:00',
  updated_at: '2026-08-03T10:00:00',
}

describe('curatedModelsService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('toCuratedModel', () => {
    it('maps DTO to CuratedModel shape', () => {
      const model = toCuratedModel(dto)
      expect(model.id).toBe('test/model-1')
      expect(model.name).toBe('Test Model 1')
      expect(model.provider).toBe('openrouter')
      expect(model.category).toBe('chat')
      expect(model.contextLength).toBe(128000)
      expect(model.isFree).toBe(true)
      expect(model.thinking).toBe('none')
      expect(model.location).toBe('cloud')
      expect((model as unknown as { curatedRowId: number }).curatedRowId).toBe(42)
    })

    it('maps a NULL cost to null — the provider prices this model nowhere', () => {
      // Three states reach the UI (Phase 4): free, paid, and "nobody has priced it". The
      // last must not arrive as `false`, which would render as a paid model.
      const model = toCuratedModel({ ...dto, is_free: null })
      expect(model.isFree).toBeNull()
    })

    it('maps a NULL category to undefined — "not described", not an empty string', () => {
      // The API stores nothing for a row nobody described; the frontend's shape says so with
      // absence. An empty string would be a value nobody chose, and the API refuses one.
      const model = toCuratedModel({ ...dto, category: null })
      expect(model.category).toBeUndefined()
    })
  })

  describe('fetchCuratedModels', () => {
    it('fetches all curated models without provider filter', async () => {
      mockGet.mockResolvedValue({ data: { data: [dto] } })
      const models = await fetchCuratedModels()
      expect(mockGet).toHaveBeenCalledWith('/api/v1/curated-models')
      expect(models).toHaveLength(1)
      expect(models[0].id).toBe('test/model-1')
    })

    it('passes provider query param when provided', async () => {
      mockGet.mockResolvedValue({ data: { data: [] } })
      await fetchCuratedModels('ollama')
      expect(mockGet).toHaveBeenCalledWith('/api/v1/curated-models?provider=ollama')
    })

    it('handles bare-array responses (non-wrapped)', async () => {
      mockGet.mockResolvedValue({ data: [dto] })
      const models = await fetchCuratedModels()
      expect(models).toHaveLength(1)
    })

    it('returns empty array when API returns no data', async () => {
      mockGet.mockResolvedValue({ data: { data: [] } })
      const models = await fetchCuratedModels()
      expect(models).toEqual([])
    })
  })

  describe('addCuratedModel', () => {
    it('posts model and returns mapped result', async () => {
      mockPost.mockResolvedValue({ data: { data: dto } })
      const model = await addCuratedModel({
        id: 'test/model-1',
        name: 'Test Model 1',
        provider: 'openrouter',
        category: 'chat',
      })
      expect(mockPost).toHaveBeenCalledWith('/api/v1/curated-models', {
        provider: 'openrouter',
        model_id: 'test/model-1',
        model_name: 'Test Model 1',
        category: 'chat',
        description: null,
        context_length: null,
        // NO `featured` key: the app stopped featuring models (the arc's Phase 3), and the
        // API REFUSES a request that still carries it.
        // NO `is_free` key either: the cost is DERIVED from the provider's cached pricing
        // (Phase 4) and a request stating it is a 422, not a harmless extra field.
        // NO `thinking` key: nobody chose a level, so the API derives it from the
        // provider's own claim rather than the form inventing 'none'.
        location: 'cloud',
      })
      expect(model.id).toBe('test/model-1')
    })

    it('omits the category when nobody chose one — the descriptor is optional', async () => {
      mockPost.mockResolvedValue({ data: { data: { ...dto, category: null } } })
      await addCuratedModel({
        id: 'test/no-descriptor',
        name: 'No Descriptor',
        provider: 'openrouter',
      })

      const body = mockPost.mock.calls[0][1] as Record<string, unknown>
      // NO `category` KEY AT ALL: omitting it is what makes the row read "not described", and
      // an empty string would be a value nobody chose — which the API refuses.
      expect('category' in body).toBe(false)
    })

    it('omits thinking when nobody chose a level, but sends a chosen one', async () => {
      mockPost.mockResolvedValue({ data: { data: dto } })
      await addCuratedModel({
        id: 'test/derived',
        name: 'Derived',
        provider: 'openrouter',
        category: 'chat',
      })
      const omitted = mockPost.mock.calls[0][1] as Record<string, unknown>
      expect('thinking' in omitted).toBe(false)
      expect(omitted.location).toBe('cloud')

      await addCuratedModel({
        id: 'test/stated',
        name: 'Stated',
        provider: 'openrouter',
        category: 'chat',
        thinking: 'mandatory',
      })
      const stated = mockPost.mock.calls[1][1] as Record<string, unknown>
      expect(stated.thinking).toBe('mandatory')
    })

    it('sends the capability dimensions when they are set', async () => {
      mockPost.mockResolvedValue({ data: { data: { ...dto, thinking: 'mandatory' } } })
      await addCuratedModel({
        id: 'test/thinks',
        name: 'Thinks',
        provider: 'openrouter',
        category: 'reasoning',
        thinking: 'mandatory',
        location: 'local',
      })
      expect(mockPost).toHaveBeenCalledWith(
        '/api/v1/curated-models',
        expect.objectContaining({ thinking: 'mandatory', location: 'local' }),
      )
    })
  })

  describe('updateCuratedModel', () => {
    it('puts updates and returns mapped result', async () => {
      mockPut.mockResolvedValue({
        data: { data: { ...dto, category: 'code', description: 'a coder now' } },
      })
      const model = await updateCuratedModel(42, { category: 'code', description: 'a coder now' })
      expect(mockPut).toHaveBeenCalledWith('/api/v1/curated-models/42', {
        category: 'code',
        description: 'a coder now',
      })
      expect(model.category).toBe('code')
      expect(model.description).toBe('a coder now')
    })

    it('carries the capability dimensions through the update payload', async () => {
      mockPut.mockResolvedValue({ data: { data: { ...dto, thinking: 'mandatory' } } })
      const model = await updateCuratedModel(42, { thinking: 'mandatory' })
      expect(mockPut).toHaveBeenCalledWith('/api/v1/curated-models/42', {
        thinking: 'mandatory',
      })
      expect(model.thinking).toBe('mandatory')
    })
  })

  describe('removeCuratedModel', () => {
    it('deletes by row id', async () => {
      mockDelete.mockResolvedValue({ status: 204 })
      await removeCuratedModel(42)
      expect(mockDelete).toHaveBeenCalledWith('/api/v1/curated-models/42')
    })
  })

  describe('verifyCuratedModelWindow', () => {
    // The endpoint answers FLAT (no `{data: …}` envelope), so this is the body verbatim.
    const verification = {
      curated_id: 42,
      provider: 'openrouter',
      model_id: 'test/model-1',
      curated: 8192,
      discovered: 262144,
      window: 262144,
      verified: true,
      mismatch: true,
      stale: false,
      age_hours: 3.5,
      refreshed: false,
      thinking_curated: 'none',
      thinking_provider: 'reasoning: {mandatory: true}',
      max_completion: 32768,
      note: "adopted the provider's 262144 over this row's 8192",
      thinking_adopted: 'mandatory',
    }

    it('posts to the row and returns the flat body', async () => {
      mockPost.mockResolvedValue({ data: verification })
      const result = await verifyCuratedModelWindow(42)

      expect(mockPost).toHaveBeenCalledWith(
        '/api/v1/curated-models/42/verify-window',
        { refresh: false },
      )
      expect(result.window).toBe(262144)
      expect(result.mismatch).toBe(true)
      expect(result.thinking_adopted).toBe('mandatory')
    })

    it('asks the provider again only when that is what was asked', async () => {
      mockPost.mockResolvedValue({ data: verification })
      await verifyCuratedModelWindow(42, true)
      expect(mockPost).toHaveBeenCalledWith(
        '/api/v1/curated-models/42/verify-window',
        { refresh: true },
      )
    })

    it('raises the server message rather than returning a hollow row', async () => {
      mockPost.mockResolvedValue({
        error: { code: 'HTTP_404', message: 'Curated model not found' },
        status: 404,
      })
      await expect(verifyCuratedModelWindow(9)).rejects.toThrow('Curated model not found')
    })
  })
})
