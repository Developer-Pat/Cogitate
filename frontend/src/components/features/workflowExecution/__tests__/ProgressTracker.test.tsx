import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { eventBus } from '@/services/eventBus'
import ProgressTracker from '../ProgressTracker'
import type { WorkflowExecution } from '@/types/workflows'

const feedMocks = vi.hoisted(() => ({
  add: vi.fn(),
  remove: vi.fn(),
}))
vi.mock('@/services/messagingFeed', () => ({
  addTopics: (t: string) => feedMocks.add(t),
  removeTopics: (t: string) => feedMocks.remove(t),
  connectMessaging: vi.fn(),
  disconnectMessaging: vi.fn(),
}))

const runningExecution = {
  id: 'wf-1',
  status: 'running',
  stepExecutions: [],
  logs: [],
  executionResult: null,
} as unknown as WorkflowExecution

describe('ProgressTracker (the run-time estimate)', () => {
  beforeEach(() => {
    eventBus.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    eventBus.clear()
  })

  it('renders the estimate line from the batch:done events', () => {
    render(
      <ProgressTracker
        execution={runningExecution}
        progressStatus="connected"
      />,
    )

    // 2 of 10 batches done (the bus events drive the estimator)
    act(() => {
      eventBus.emit('batch:1:done', { workflow_id: 'wf-1', batch_id: 1, total_batches: 10 })
      eventBus.emit('batch:2:done', { workflow_id: 'wf-1', batch_id: 2, total_batches: 10 })
    })

    expect(screen.getByText(/2\/10 batches/)).toBeTruthy()
    expect(screen.getByText(/remaining/)).toBeTruthy()
  })

  it('registers the estimator topics with the feed', () => {
    render(
      <ProgressTracker
        execution={runningExecution}
        progressStatus="connected"
      />,
    )
    expect(feedMocks.add).toHaveBeenCalledWith('batch:*,workflow:*')
  })

  it('shows the completed line when the run finishes', () => {
    render(
      <ProgressTracker
        execution={runningExecution}
        progressStatus="connected"
      />,
    )
    act(() => {
      eventBus.emit('batch:1:done', { workflow_id: 'wf-1', batch_id: 1, total_batches: 2 })
      eventBus.emit('batch:2:done', { workflow_id: 'wf-1', batch_id: 2, total_batches: 2 })
    })
    expect(screen.getByText(/Completed 2 batches/)).toBeTruthy()
  })
})
