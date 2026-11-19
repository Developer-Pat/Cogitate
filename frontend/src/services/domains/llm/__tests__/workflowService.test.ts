/**
 * `workflowService.getExecution` — the run's failure reaches the panel's two props.
 *
 * The mapper is the OTHER half of the panel's contract: the panel can only show the ONE wording
 * and the raw exception if this translation carries them. Two rules bite here:
 *
 * 1. **The backend records a failed run as `"error"`; the UI's union and every `=== 'failed'`
 *    branch say `"failed"`.** Without the rename the run detail recognises no failure at all.
 * 2. **`failure_statement` → `failureStatement`, and `error` keeps the RAW exception** — the
 *    statement is the sentence, the raw cause stays recoverable (A1).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { workflowService } from '../workflowService'

const STATEMENT =
  'Deepseek V4 Flash (deepseek) is not functioning properly — the provider reported: boom. ' +
  'You can have Exa attempt diagnosis (ask Exa).'

const STATUS = {
  workflow_id: 'wf-1',
  template_id: 'tpl',
  status: 'error',
  error: 'litellm.APIConnectionError: boom',
  failure_statement: STATEMENT,
  started_at: '2026-10-04T12:00:00Z',
  completed_at: '2026-10-04T12:00:05Z',
}

describe('workflowService.getExecution — the run-level failure', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, json: async () => STATUS })))
  })

  afterEach(() => vi.unstubAllGlobals())

  it("reads the backend's 'error' as the frontend's 'failed'", async () => {
    const res = await workflowService.getExecution('wf-1')

    expect(res.data?.status).toBe('failed')
  })

  it('carries the ONE wording AND keeps the raw exception', async () => {
    const res = await workflowService.getExecution('wf-1')

    expect(res.data?.failureStatement).toBe(STATEMENT)
    expect(res.data?.error).toBe('litellm.APIConnectionError: boom')
  })
})

// THE SECOND AXIS: a run that COMPLETED with a failure absorbed inside it. The status word stays
// the execution outcome — the flag rides beside it, never folded into one word.
describe('workflowService.getExecution — a degraded run', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('carries the flag while the status stays the execution outcome', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
      ok: true,
      json: async () => ({ ...STATUS, status: 'completed', degraded: true }),
    })))

    const res = await workflowService.getExecution('wf-1')

    expect(res.data?.status).toBe('completed')
    expect(res.data?.degraded).toBe(true)
  })

  it('reads a run the backend did not mark as not degraded', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({
      ok: true,
      json: async () => ({ ...STATUS, status: 'completed' }),
    })))

    const res = await workflowService.getExecution('wf-1')

    expect(res.data?.degraded).toBe(false)
  })
})
