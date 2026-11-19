import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { eventBus } from '@/services/eventBus'
import { useRunEstimator, type RunEstimate } from '../useRunEstimator'

describe('useRunEstimator (the run-time estimate)', () => {
  beforeEach(() => {
    eventBus.clear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    eventBus.clear()
    vi.useRealTimers()
  })

  it('computes progress + the remaining estimate from batch:done events', () => {
    vi.setSystemTime(0)
    const { result } = renderHook(() => useRunEstimator('wf-1'))

    // 2 of 10 batches done, 5s apart
    act(() => {
      eventBus.emit('batch:1:done', { workflow_id: 'wf-1', batch_id: 1, total_batches: 10 })
      vi.setSystemTime(5000)
      eventBus.emit('batch:2:done', { workflow_id: 'wf-1', batch_id: 2, total_batches: 10 })
    })

    const e = result.current as RunEstimate
    expect(e).not.toBeNull()
    expect(e.done).toBe(2)
    expect(e.total).toBe(10)
    expect(e.progress).toBeCloseTo(0.2)
    // 5s elapsed / 2 done = 2.5s per batch; 8 remaining x 2.5 = 20s
    expect(e.rateSec).toBeCloseTo(2.5)
    expect(e.remainingSec).toBeCloseTo(20)
    expect(e.finished).toBe(false)
  })

  it('marks finished when done reaches total', () => {
    const { result } = renderHook(() => useRunEstimator('wf-2'))
    act(() => {
      eventBus.emit('batch:1:done', { workflow_id: 'wf-2', batch_id: 1, total_batches: 2 })
      eventBus.emit('batch:2:done', { workflow_id: 'wf-2', batch_id: 2, total_batches: 2 })
    })
    const e = result.current as RunEstimate
    expect(e.finished).toBe(true)
    expect(e.progress).toBe(1)
  })

  it('ignores events for other workflows', () => {
    const { result } = renderHook(() => useRunEstimator('wf-3'))
    act(() => {
      eventBus.emit('batch:1:done', { workflow_id: 'wf-OTHER', batch_id: 1, total_batches: 10 })
    })
    expect(result.current).toBeNull()
  })

  it('returns null without a workflowId', () => {
    const { result } = renderHook(() => useRunEstimator())
    expect(result.current).toBeNull()
  })
})
