import { describe, it, expect, beforeEach } from 'vitest'
import { MetricsService } from '../MetricsService'
import type { MessageMetadata } from '@/types/agentInteraction'

describe('MetricsService', () => {
  let service: MetricsService

  beforeEach(() => {
    service = new MetricsService()
  })

  describe('calculateTokensPerSecond', () => {
    it('should calculate tokens per second correctly', () => {
      // 100 tokens in 2000ms = 50 tokens/second
      expect(service.calculateTokensPerSecond(100, 2000)).toBe(50)
    })

    it('should round to 1 decimal place', () => {
      // 100 tokens in 1500ms = 66.666... tokens/second
      expect(service.calculateTokensPerSecond(100, 1500)).toBe(66.7)
    })

    it('should return undefined when tokenCount is undefined', () => {
      expect(service.calculateTokensPerSecond(undefined, 2000)).toBeUndefined()
    })

    it('should return undefined when totalTimeMs is undefined', () => {
      expect(service.calculateTokensPerSecond(100, undefined)).toBeUndefined()
    })

    it('should return undefined when totalTimeMs is zero', () => {
      expect(service.calculateTokensPerSecond(100, 0)).toBeUndefined()
    })

    it('should return undefined when tokenCount is zero', () => {
      expect(service.calculateTokensPerSecond(0, 2000)).toBeUndefined()
    })
  })

  describe('calculateStreamMetrics', () => {
    it('should calculate all metrics from content and duration', () => {
      const metrics = service.calculateStreamMetrics('Hello World', 1000, 'gpt-4', 'openai')

      expect(metrics.tokenCount).toBe(3) // 12 chars / 4 = 3 tokens
      expect(metrics.totalTimeMs).toBe(1000)
      expect(metrics.tokensPerSecond).toBe(3) // 3 tokens / 1000ms * 1000 = 3
      expect(metrics.model).toBe('gpt-4')
      expect(metrics.provider).toBe('openai')
    })

    it('should work without optional model and provider', () => {
      const metrics = service.calculateStreamMetrics('Test content', 2000)

      expect(metrics.tokenCount).toBe(3) // 12 chars / 4 = 3 tokens
      expect(metrics.totalTimeMs).toBe(2000)
      expect(metrics.model).toBeUndefined()
      expect(metrics.provider).toBeUndefined()
    })

    it('should handle empty content', () => {
      const metrics = service.calculateStreamMetrics('', 1000)

      expect(metrics.tokenCount).toBe(0)
      expect(metrics.totalTimeMs).toBe(1000)
      expect(metrics.tokensPerSecond).toBeUndefined() // 0 tokens
    })

    it('should round token count to nearest integer', () => {
      // 13 chars / 4 = 3.25 → 3
      const metrics = service.calculateStreamMetrics('Hello World!!', 1000)
      expect(metrics.tokenCount).toBe(3)
    })
  })

  describe('formatMetrics', () => {
    it('should format metrics for display', () => {
      const metadata: MessageMetadata = {
        tokenCount: 100,
        totalTimeMs: 2500,
        tokensPerSecond: 40,
        model: 'gpt-4',
        provider: 'openai',
      }

      const formatted = service.formatMetrics(metadata)

      expect(formatted.tokenCount).toBe('100 tokens')
      expect(formatted.totalTime).toBe('2.50s')
      expect(formatted.tokensPerSecond).toBe('40.0 t/s')
      expect(formatted.model).toBe('gpt-4')
      expect(formatted.provider).toBe('openai')
    })

    it('should format time in milliseconds for short durations', () => {
      const metadata: MessageMetadata = {
        tokenCount: 10,
        totalTimeMs: 500,
        tokensPerSecond: 20,
      }

      const formatted = service.formatMetrics(metadata)

      expect(formatted.totalTime).toBe('500ms')
    })

    it('should handle missing values gracefully', () => {
      const metadata: MessageMetadata = {}

      const formatted = service.formatMetrics(metadata)

      expect(formatted.tokenCount).toBe('')
      expect(formatted.totalTime).toBe('')
      expect(formatted.tokensPerSecond).toBe('')
      expect(formatted.model).toBeUndefined()
      expect(formatted.provider).toBeUndefined()
    })

    it('should format large token counts', () => {
      const metadata: MessageMetadata = {
        tokenCount: 1000,
        totalTimeMs: 5000,
        tokensPerSecond: 200,
      }

      const formatted = service.formatMetrics(metadata)

      expect(formatted.tokenCount).toBe('1000 tokens')
      expect(formatted.totalTime).toBe('5.00s')
      expect(formatted.tokensPerSecond).toBe('200.0 t/s')
    })
  })

  describe('integration: calculate and format', () => {
    it('should calculate and format in one flow', () => {
      const content = 'This is a test response with some content to stream back to the user.'
      const duration = 1500

      const metadata = service.calculateStreamMetrics(content, duration, 'gpt-4', 'openai')
      const formatted = service.formatMetrics(metadata)

      expect(metadata.tokenCount).toBeGreaterThan(0)
      expect(metadata.totalTimeMs).toBe(1500)
      expect(formatted.tokenCount).toMatch(/\d+ tokens/)
      expect(formatted.totalTime).toBe('1.50s')
      expect(formatted.tokensPerSecond).toMatch(/\d+\.\d t\/s/)
    })
  })
})
