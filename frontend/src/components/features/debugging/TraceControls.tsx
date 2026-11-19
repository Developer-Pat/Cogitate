/**
 * TraceControls - Runtime controls for flow tracing
 *
 * Allows enabling/disabling trace logging at runtime:
 * - Global trace toggle
 * - Per-flow trace enabling
 * - Trace sampling rate control
 *
 * All changes are applied immediately without page reload.
 */

import { useState, useEffect } from 'react'
import { loggingConfigService } from '@/services/domain/LoggingConfigService'
import { frontendLoggingService } from '@/services/frontendLoggingService'

interface TraceControlsProps {
  onConfigChange?: (config: TraceConfig) => void
}

interface TraceConfig {
  enableTracing: boolean
  enableFlowTraces: boolean
  traceSamplingRate: number
}

export const TraceControls: React.FC<TraceControlsProps> = ({ onConfigChange }) => {
  const [config, setConfig] = useState<TraceConfig>({
    enableTracing: false,
    enableFlowTraces: false,
    traceSamplingRate: 1.0
  })

  useEffect(() => {
    // Load current config
    const currentConfig = loggingConfigService.getConfig()
    setConfig({
      enableTracing: currentConfig.enableTracing,
      enableFlowTraces: currentConfig.enableFlowTraces,
      traceSamplingRate: currentConfig.traceSamplingRate
    })
  }, [])

  const updateConfig = (updates: Partial<TraceConfig>) => {
    const newConfig = { ...config, ...updates }
    setConfig(newConfig)

    // Apply to logging config service
    loggingConfigService.updateConfig({
      enableTracing: newConfig.enableTracing,
      enableFlowTraces: newConfig.enableFlowTraces,
      traceSamplingRate: newConfig.traceSamplingRate
    })

    frontendLoggingService.info('TraceControls', 'Trace configuration updated', {
      enableTracing: newConfig.enableTracing,
      enableFlowTraces: newConfig.enableFlowTraces,
      traceSamplingRate: newConfig.traceSamplingRate
    })

    onConfigChange?.(newConfig)
  }

  const resetToDefaults = () => {
    loggingConfigService.reset()
    const defaultConfig = loggingConfigService.getConfig()
    setConfig({
      enableTracing: defaultConfig.enableTracing,
      enableFlowTraces: defaultConfig.enableFlowTraces,
      traceSamplingRate: defaultConfig.traceSamplingRate
    })

    frontendLoggingService.info('TraceControls', 'Trace configuration reset to defaults')
    onConfigChange?.(config)
  }

  return (
    <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
      <div className="card-body gap-[var(--card-gap)]">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h3 className="card-title text-lg">Trace Controls</h3>
          <button
            className="btn btn-sm btn-outline"
            onClick={resetToDefaults}
          >
            Reset to Defaults
          </button>
        </div>

        {/* Global Trace Toggle */}
        <div className="form-control">
          <label className="label cursor-pointer">
            <div>
              <div className="label-text font-medium">Enable Tracing</div>
              <div className="label-text-alt text-readout">
                Master switch for all trace logging (OFF by default)
              </div>
            </div>
            <input
              type="checkbox"
              className="toggle toggle-primary"
              checked={config.enableTracing}
              onChange={(e) => updateConfig({ enableTracing: e.target.checked })}
            />
          </label>
        </div>

        {/* Flow Traces Toggle */}
        <div className="form-control">
          <label className="label cursor-pointer">
            <div>
              <div className="label-text font-medium">Enable Flow Traces</div>
              <div className="label-text-alt text-readout">
                Log flow trace events (requires Enable Tracing to be ON)
              </div>
            </div>
            <input
              type="checkbox"
              className="toggle toggle-secondary"
              checked={config.enableFlowTraces}
              onChange={(e) => updateConfig({ enableFlowTraces: e.target.checked })}
              disabled={!config.enableTracing}
            />
          </label>
        </div>

        {/* Sampling Rate */}
        <div className="form-control">
          <label className="label">
            <div>
              <div className="label-text font-medium">Trace Sampling Rate</div>
              <div className="label-text-alt text-readout">
                Percentage of traces to log (100% = all traces)
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min="0"
                max="100"
                value={Math.round(config.traceSamplingRate * 100)}
                onChange={(e) => updateConfig({ traceSamplingRate: parseInt(e.target.value) / 100 })}
                className="range range-primary range-sm w-32"
                disabled={!config.enableTracing || !config.enableFlowTraces}
              />
              <span className="text-sm font-mono w-12 text-right">
                {Math.round(config.traceSamplingRate * 100)}%
              </span>
            </div>
          </label>
        </div>

        {/* Status Indicator */}
        <div className="divider my-0"></div>
        <div className="flex items-center gap-2">
          <div className={`indicator ${config.enableTracing && config.enableFlowTraces ? 'text-success' : 'text-warning'}`}>
            <span className="indicator-item badge-sm badge"></span>
            <span className="text-sm font-medium">
              {config.enableTracing && config.enableFlowTraces
                ? 'Tracing Active'
                : config.enableTracing
                  ? 'Tracing Enabled (Flow Traces OFF)'
                  : 'Tracing Disabled'}
            </span>
          </div>
        </div>

        {/* Usage Tips */}
        <details className="collapse collapse-arrow bg-base-100 rounded-[var(--card-radius)] mt-2">
          <summary className="collapse-title text-sm font-medium cursor-pointer">
            📖 How to Use
          </summary>
          <div className="collapse-content text-sm space-y-2">
            <p className="text-readout">
              <strong>Default State:</strong> Tracing is OFF to prevent log flooding.
            </p>
            <p className="text-readout">
              <strong>To Enable Tracing:</strong>
            </p>
            <ol className="list-decimal list-inside space-y-1 text-readout">
              <li>Toggle "Enable Tracing" ON</li>
              <li>Toggle "Enable Flow Traces" ON</li>
              <li>Adjust sampling rate if needed (100% recommended for debugging)</li>
            </ol>
            <p className="text-readout">
              <strong>When to Use:</strong> Enable tracing only when debugging complex flows or hard-to-find errors. Disable after debugging to reduce log noise.
            </p>
            <p className="text-readout">
              <strong>Trace Logs:</strong> Traces appear in the Trace Analysis tab with [FLOW TRACE #N] prefix for easy filtering.
            </p>
          </div>
        </details>
      </div>
    </div>
  )
}
