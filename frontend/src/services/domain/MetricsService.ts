import type { MessageMetadata } from '@/types/agentInteraction'

export interface FormattedMetrics {
  totalTime: string
  tokenCount: string
  tokensPerSecond: string
  model?: string
  provider?: string
}

/**
 * MetricsService - Calculate and format streaming metrics
 *
 * Pure calculation service with no side effects.
 * Extracted from useChatStreaming.ts and metadataUtils.ts
 *
 * @example
 * ```typescript
 * const metricsService = new MetricsService()
 * const metadata = metricsService.calculateStreamMetrics('Hello World', 1000, 'gpt-4', 'openai')
 * const formatted = metricsService.formatMetrics(metadata)
 * ```
 */
export class MetricsService {
  /**
   * Calculate tokens per second from token count and duration
   *
   * @param tokenCount - Number of tokens generated
   * @param totalTimeMs - Total time in milliseconds
   * @returns Tokens per second, or undefined if inputs are invalid
   */
  calculateTokensPerSecond(tokenCount?: number, totalTimeMs?: number): number | undefined {
    if (!tokenCount || !totalTimeMs || totalTimeMs === 0) {
      return undefined
    }
    const tokensPerSecond = (tokenCount / totalTimeMs) * 1000
    return Math.round(tokensPerSecond * 10) / 10
  }

  /**
   * Create metadata object with calculated metrics
   *
   * @param content - The generated content
   * @param durationMs - Streaming duration in milliseconds
   * @param model - Model name (optional)
   * @param provider - Provider name (optional)
   * @returns Calculated message metadata
   */
  calculateStreamMetrics(
    content: string,
    durationMs: number,
    model?: string,
    provider?: string
  ): MessageMetadata {
    const tokenCount = Math.round(content.length / 4)
    const tokensPerSecond = this.calculateTokensPerSecond(tokenCount, durationMs)

    return {
      tokenCount,
      totalTimeMs: Math.round(durationMs),
      tokensPerSecond,
      model,
      provider,
    }
  }

  /**
   * Format metrics for display
   *
   * @param metadata - Message metadata to format
   * @returns Formatted metrics for UI display
   */
  formatMetrics(metadata: MessageMetadata): FormattedMetrics {
    return {
      totalTime: this.formatTime(metadata.totalTimeMs),
      tokenCount: metadata.tokenCount ? `${metadata.tokenCount} tokens` : '',
      tokensPerSecond: metadata.tokensPerSecond ? `${metadata.tokensPerSecond.toFixed(1)} t/s` : '',
      model: metadata.model,
      provider: metadata.provider,
    }
  }

  /**
   * Format time in human-readable format
   *
   * @param ms - Time in milliseconds
   * @returns Formatted time string (e.g., "2.50s" or "500ms")
   */
  private formatTime(ms?: number): string {
    if (!ms) return ''
    if (ms < 1000) return `${Math.round(ms)}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }
}
