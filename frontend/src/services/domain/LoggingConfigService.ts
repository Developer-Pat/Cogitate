/**
 * LoggingConfigService - Runtime logging configuration
 *
 * Allows toggling logging features at runtime:
 * - Enable/disable flow traces
 * - Enable/disable deduplication
 * - Adjust trace sampling rate
 * - Enable/disable backend logging
 * - Enable/disable tracing (controls if trace logs are written at all)
 *
 * Default: Tracing disabled, other logging enabled
 */

export interface LoggingConfig {
  /** Enable flow trace logging */
  enableFlowTraces: boolean
  /** Enable log deduplication */
  enableDeduplication: boolean
  /** Trace sampling rate (0.0 to 1.0) */
  traceSamplingRate: number
  /** Enable backend logging */
  backendLoggingEnabled: boolean
  /** Enable tracing (when false, no trace logs are written) */
  enableTracing: boolean
}

const DEFAULT_CONFIG: LoggingConfig = {
  enableFlowTraces: false,  // OFF by default - enable for debugging only
  enableDeduplication: true,
  traceSamplingRate: 1.0,
  backendLoggingEnabled: true,
  enableTracing: false  // OFF by default - traces disabled until explicitly enabled
}

class LoggingConfigService {
  private config: LoggingConfig = { ...DEFAULT_CONFIG }

  /**
   * Get current logging configuration
   */
  getConfig(): LoggingConfig {
    return { ...this.config }
  }

  /**
   * Update logging configuration
   * @param updates - Partial config updates
   */
  updateConfig(updates: Partial<LoggingConfig>): void {
    this.config = { ...this.config, ...updates }
  }

  /**
   * Reset configuration to defaults
   */
  reset(): void {
    this.config = { ...DEFAULT_CONFIG }
  }

  /**
   * Check if should log based on source and sampling rate
   *
   * @param source - Log source (e.g., 'FlowTrace', 'ChatFlow')
   * @param level - Log level (e.g., 'info', 'debug')
   * @returns true if should log, false if should skip
   */
  shouldLog(source: string, level: string): boolean {
    // Always log errors and critical
    if (level === 'error' || level === 'critical') {
      return true
    }

    // Check flow trace config
    if (source === 'FlowTrace' || source.includes('FlowTrace')) {
      if (!this.config.enableFlowTraces) {
        return false
      }

      // Apply sampling rate for traces
      if (this.config.traceSamplingRate < 1.0) {
        const random = Math.random()
        return random <= this.config.traceSamplingRate
      }
    }

    return true
  }

  /**
   * Check if deduplication is enabled
   */
  isDeduplicationEnabled(): boolean {
    return this.config.enableDeduplication
  }

  /**
   * Check if backend logging is enabled
   */
  isBackendLoggingEnabled(): boolean {
    return this.config.backendLoggingEnabled
  }

  /**
   * Check if tracing is enabled
   */
  isTracingEnabled(): boolean {
    return this.config.enableTracing
  }
}

// Export singleton instance
export const loggingConfigService = new LoggingConfigService()
