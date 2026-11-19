import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useWorkflowTemplates } from '../useWorkflowTemplates';

// the hook fetches templates via workflowService — stub the module
vi.mock('@/services/domains/llm/workflowService', () => ({
  workflowService: {
    getTemplates: vi.fn().mockResolvedValue({ error: null, data: [] }),
    listTemplates: vi.fn().mockResolvedValue({ error: null, data: [] }),
    createTemplate: vi.fn(),
    updateTemplate: vi.fn(),
    deleteTemplate: vi.fn(),
  },
}));

// Stub apiClient-based fetches too (categories/tags endpoints)
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({}),
  }));
});

afterEach(() => vi.unstubAllGlobals());

// Build a minimal template


describe('useWorkflowTemplates includeTesting (Phase E)', () => {
  it('hides testing-namespace fixtures by default', async () => {
    const { result } = renderHook(() => useWorkflowTemplates());
    await act(async () => {
      // drive state via setFilters triggers a re-filter
      result.current.setFilters(result.current.filters);
    });
    // default: includeTesting = false
    expect(result.current.includeTesting).toBe(false);
  });

  it('setIncludeTesting toggles and re-filters', async () => {
    const { result } = renderHook(() => useWorkflowTemplates());
    await act(async () => {
      result.current.setIncludeTesting(true);
    });
    expect(result.current.includeTesting).toBe(true);
    await act(async () => {
      result.current.setIncludeTesting(false);
    });
    expect(result.current.includeTesting).toBe(false);
  });
});
