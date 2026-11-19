/**
 * LoggingConfigPanel - UI for configuring logging settings
 *
 * Allows users to:
 * - Toggle flow trace logging
 * - Toggle deduplication
 * - Adjust trace sampling rate
 * - Toggle backend logging
 */

import { useState, useEffect } from 'react'
import { loggingConfigService, type LoggingConfig } from '@/services/domain/LoggingConfigService'
import ToggleSwitch from '../ui/ToggleSwitch'

interface LoggingConfigPanelProps {
  onConfigChange?: (config: LoggingConfig) => void
}

export default function LoggingConfigPanel({ onConfigChange }: LoggingConfigPanelProps) {
  const [config, setConfig] = useState<LoggingConfig>(loggingConfigService.getConfig())

  // Update local state when config changes externally
  useEffect(() => {
    const interval = setInterval(() => {
      const currentConfig = loggingConfigService.getConfig()
      setConfig(currentConfig)
      onConfigChange?.(currentConfig)
    }, 1000)

    return () => clearInterval(interval)
  }, [onConfigChange])

  const handleToggle = (key: keyof LoggingConfig, value: boolean) => {
    const updates = { [key]: value }
    loggingConfigService.updateConfig(updates)
    setConfig(loggingConfigService.getConfig())
    onConfigChange?.(loggingConfigService.getConfig())
  }

  const handleSamplingChange = (value: number) => {
    const updates = { traceSamplingRate: value }
    loggingConfigService.updateConfig(updates)
    setConfig(loggingConfigService.getConfig())
    onConfigChange?.(loggingConfigService.getConfig())
  }

  const handleReset = () => {
    loggingConfigService.reset()
    setConfig(loggingConfigService.getConfig())
    onConfigChange?.(loggingConfigService.getConfig())
  }

  return (
    <div className="card bg-base-200 shadow-xl">
      <div className="card-body">
        <div className="flex justify-between items-center mb-4">
          <h3 className="card-title text-lg">Logging Configuration</h3>
          <button onClick={handleReset} className="btn btn-ghost btn-sm">
            Reset to Defaults
          </button>
        </div>

        <div className="space-y-6">
          {/* Enable Tracing */}
          <div className="flex justify-between items-center">
            <div>
              <div className="font-medium">Enable Tracing</div>
              <div className="text-sm text-readout">
                Allow trace logs to be written (turn off to reduce log noise)
              </div>
            </div>
            <ToggleSwitch
              checked={config.enableTracing}
              onChange={(checked) => handleToggle('enableTracing', checked)}
              size="md"
            />
          </div>

          {/* Enable Flow Traces */}
          <div className="flex justify-between items-center">
            <div>
              <div className="font-medium">Enable Flow Traces</div>
              <div className="text-sm text-readout">
                Log detailed flow traces for debugging
              </div>
            </div>
            <ToggleSwitch
              checked={config.enableFlowTraces}
              onChange={(checked) => handleToggle('enableFlowTraces', checked)}
              size="md"
            />
          </div>

          {/* Enable Deduplication */}
          <div className="flex justify-between items-center">
            <div>
              <div className="font-medium">Enable Deduplication</div>
              <div className="text-sm text-readout">
                Prevent duplicate log messages
              </div>
            </div>
            <ToggleSwitch
              checked={config.enableDeduplication}
              onChange={(checked) => handleToggle('enableDeduplication', checked)}
              size="md"
            />
          </div>

          {/* Backend Logging */}
          <div className="flex justify-between items-center">
            <div>
              <div className="font-medium">Backend Logging</div>
              <div className="text-sm text-readout">
                Send logs to backend for persistent storage
              </div>
            </div>
            <ToggleSwitch
              checked={config.backendLoggingEnabled}
              onChange={(checked) => handleToggle('backendLoggingEnabled', checked)}
              size="md"
            />
          </div>

          {/* Trace Sampling Rate */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <div>
                <div className="font-medium">Trace Sampling Rate</div>
                <div className="text-sm text-readout">
                  Percentage of traces to log ({Math.round(config.traceSamplingRate * 100)}%)
                </div>
              </div>
              <div className="text-sm font-mono">{config.traceSamplingRate.toFixed(1)}</div>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={config.traceSamplingRate}
              onChange={(e) => handleSamplingChange(parseFloat(e.target.value))}
              className="range range-primary range-sm"
            />
            <div className="flex justify-between text-xs text-readout mt-1">
              <span>0%</span>
              <span>10%</span>
              <span>50%</span>
              <span>100%</span>
            </div>
          </div>
        </div>

        {/* Current Config Summary */}
        <div className="mt-6 p-4 bg-base-300 rounded-lg">
          <div className="text-xs font-mono text-readout">
            <div>Tracing: {config.enableTracing ? '✅ ON' : '❌ OFF'}</div>
            <div>Flow Traces: {config.enableFlowTraces ? '✅' : '❌'}</div>
            <div>Deduplication: {config.enableDeduplication ? '✅' : '❌'}</div>
            <div>Backend Logging: {config.backendLoggingEnabled ? '✅' : '❌'}</div>
            <div>Sampling Rate: {Math.round(config.traceSamplingRate * 100)}%</div>
          </div>
        </div>
      </div>
    </div>
  )
}
