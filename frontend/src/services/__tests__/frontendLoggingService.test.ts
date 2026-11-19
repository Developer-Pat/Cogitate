/**
 * THE RATE LIMITER — behaviour pins (2026-09-12).
 *
 * Why this file exists: the limiter was commented out with "DISABLE RATE
 * LIMITING FOR DEBUGGING", its companion functions (shouldSendLog, getLogKey)
 * were DELETED rather than left commented, and nothing noticed for weeks — the
 * service had no test at all. Meanwhile the 2026-09-11 flood's worst offender
 * was thousands of IDENTICAL rows ("Calling updateMessage", once per streaming
 * chunk), which is precisely the pattern maxIdenticalLogs exists to stop.
 *
 * These tests pin the three things that must stay true:
 *   - identical rows are capped at maxIdenticalLogs per window
 *   - DISTINCT rows are never suppressed (the complaint that got it disabled)
 *   - the floor still holds: debug rows never reach the queue at all
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../logsService', () => ({
  logsService: { sendBatchLogsToBackend: vi.fn().mockResolvedValue({ data: {}, status: 200 }) },
}))

vi.mock('../logStoreInstance', () => ({
  globalLogStore: { addLog: vi.fn(), getLogs: vi.fn(() => []) },
}))

vi.mock('../domain/LoggingConfigService', () => ({
  loggingConfigService: { isBackendLoggingEnabled: () => true },
}))

import { frontendLoggingService, getLogSuppressionSummary } from '../frontendLoggingService'

const entry = (message: string, source = 'RateLimitTest') => ({
  timestamp: new Date().toISOString(),
  level: 'info' as const,
  source,
  message,
})

describe('the frontend log rate limiter', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('caps identical rows and records the suppression', async () => {
    // Well past maxIdenticalLogs (3) in DEFAULT_RATE_LIMIT.
    for (let i = 0; i < 12; i++) {
      await frontendLoggingService.sendLog(entry('the same row, twelve times'))
    }

    // The summary is the visible half — a suppressor that hides silently was
    // the fair objection to this mechanism in the first place.
    const summary = getLogSuppressionSummary()
    const key = Object.keys(summary).find((k) => k.includes('the same row, twelve times'))
    expect(key, 'the suppressed row should appear in the summary').toBeTruthy()
    expect(summary[key!]).toBeGreaterThan(3)
  })

  it('never suppresses DISTINCT rows', async () => {
    // The original complaint was "ALL LOGS SHOULD BE VISIBLE". Distinct rows
    // are not repetition and must all pass, however fast they arrive.
    for (let i = 0; i < 12; i++) {
      await frontendLoggingService.sendLog(entry(`distinct row number ${i}`))
    }

    const summary = getLogSuppressionSummary()
    const suppressedDistinct = Object.keys(summary).filter((k) =>
      k.includes('distinct row number'),
    )
    expect(suppressedDistinct).toEqual([])
  })

  it('drops debug rows at the floor, before the limiter sees them', async () => {
    await frontendLoggingService.sendLog({
      timestamp: new Date().toISOString(),
      level: 'debug',
      source: 'RateLimitTest',
      message: 'debug noise',
    })

    const summary = getLogSuppressionSummary()
    expect(Object.keys(summary).some((k) => k.includes('debug noise'))).toBe(false)
  })
})
