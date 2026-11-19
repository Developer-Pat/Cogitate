/**
 * PipelineConfigTab — Strategy selectors for cognitive pipeline components.
 * Shows strategy selectors for context_builder, executor, response_formatter,
 * with a Cognitive Profile selector at the top. Selecting a profile populates
 * the strategy values from the profile.
 */

import { useState, useEffect } from 'react'
import { cognitiveProfileService, type CognitiveProfile } from '@/services/domain/CognitiveProfileService'
import { frontendLoggingService } from '@/services/frontendLoggingService'
import { useSettingsStore } from '@/stores/settingsStore'

export interface PipelineConfig {
  context_builder: string
  executor: string
  memory_manager: string
  response_formatter: string
}

interface PipelineConfigTabProps {
  config: PipelineConfig
  onConfigChange: (config: PipelineConfig) => void
}

interface StrategyOption {
  value: string
  label: string
  description: string
}

const COMPONENT_OPTIONS: Record<keyof PipelineConfig, StrategyOption[]> = {
  context_builder: [
    { value: 'default', label: 'Default', description: 'Standard context assembly from session history' },
    { value: 'minimal', label: 'Minimal', description: 'Only current message + system prompt, no history' },
    { value: 'augmented', label: 'Augmented', description: 'Enhanced context with RAG and external sources' },
    { value: 'skill_aware', label: 'Skill-Aware', description: 'Injects skills from global and per-agent skill files' },
  ],
  executor: [
    { value: 'default', label: 'Default', description: 'Standard LLM call with tool execution (LiteLLM)' },
    { value: 'fast', label: 'Fast', description: 'Single-pass, low tokens, no history. Optimized for speed' },
    { value: 'hybrid', label: 'Hybrid', description: 'Two-pass: fast shallow then deep reasoning when needed' },
    { value: 'stub', label: 'Stub', description: 'Test stub - no real LLM call' },
  ],
  memory_manager: [
    { value: 'default', label: 'Default', description: 'In-memory sliding window (50 turns)' },
    { value: 'noop', label: 'No-op', description: 'Stateless - no memory stored or retrieved' },
    { value: 'kv_store', label: 'KV Store', description: 'Persistent key-value memory across sessions' },
  ],
  response_formatter: [
    { value: 'default', label: 'Default', description: 'Pass-through response formatting' },
    { value: 'direct_yield', label: 'Direct Yield', description: 'Return raw LLM output, no post-processing' },
    { value: 'structured', label: 'Structured', description: 'Validate and enforce JSON schema output' },
  ],
}

const COMPONENT_LABELS: Record<keyof PipelineConfig, string> = {
  context_builder: 'Context Builder',
  executor: 'Executor',
  memory_manager: 'Memory Manager',
  response_formatter: 'Response Formatter',
}

const COMPONENT_ICONS: Record<keyof PipelineConfig, string> = {
  context_builder: '🔍',
  executor: '🧠',
  memory_manager: '💾',
  response_formatter: '✍️',
}

export default function PipelineConfigTab({
  config,
  onConfigChange,
}: PipelineConfigTabProps) {
  const [profiles, setProfiles] = useState<CognitiveProfile[]>([])
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const fetchProfiles = async () => {
      setLoading(true)
      try {
        const data = await cognitiveProfileService.list()
        setProfiles(data)
      } catch (error) {
        frontendLoggingService.error('PipelineConfigTab', 'Failed to fetch profiles', error)
      } finally {
        setLoading(false)
      }
    }
    fetchProfiles()
  }, [])

  const handleProfileSelect = (profileId: string) => {
    const id = profileId ? parseInt(profileId, 10) : null
    setSelectedProfileId(id)
    if (id !== null) {
      const profile = profiles.find((p) => p.id === id)
      if (profile) {
        onConfigChange({
          context_builder: profile.context_builder,
          executor: profile.executor,
          memory_manager: 'default',
          response_formatter: profile.response_formatter,
        })
      }
    }
  }

  const handleStrategyChange = (component: keyof PipelineConfig, value: string) => {
    onConfigChange({ ...config, [component]: value })
  }

  const showIndicators = useSettingsStore((s) => s.settings.general.showPipelineIndicators)

  const handleToggleIndicators = () => {
    const store = useSettingsStore.getState()
    store.updateSettings({
      general: {
        ...store.settings.general,
        showPipelineIndicators: !showIndicators,
      },
    })
  }

  const handleReset = () => {
    setSelectedProfileId(null)
    onConfigChange({
      context_builder: 'default',
      executor: 'default',
      memory_manager: 'default',
      response_formatter: 'default',
    })
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="flex items-center gap-1.5 text-sm font-medium text-label mb-1">
          <span>📋</span>
          <span>Cognitive Profile</span>
        </label>
        <select
          className="select select-bordered select-sm w-full bg-base-100"
          value={selectedProfileId ?? ''}
          onChange={(e) => handleProfileSelect(e.target.value)}
          disabled={loading}
        >
          <option value="">— Manual Configuration —</option>
          {profiles.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}{p.description ? ' — ' + p.description : ''}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-3">
        {(Object.keys(COMPONENT_OPTIONS) as (keyof PipelineConfig)[]).map((component) => {
          const currentValue = config[component]
          const options = COMPONENT_OPTIONS[component]
          const selectedOption = options.find((o) => o.value === currentValue)
          return (
            <div key={component}>
              <label htmlFor={'pipeline-config-' + component} className="flex items-center gap-1.5 text-sm text-readout mb-1">
                <span>{COMPONENT_ICONS[component]}</span>
                <span>{COMPONENT_LABELS[component]}</span>
              </label>
              <select
                id={'pipeline-config-' + component}
                className="select select-bordered select-sm w-full bg-base-100"
                value={currentValue}
                onChange={(e) => handleStrategyChange(component, e.target.value)}
              >
                {options.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              {selectedOption && (
                <p className="text-[11px] text-readout mt-0.5">{selectedOption.description}</p>
              )}
            </div>
          )
        })}
      </div>

      <div className="pt-2">
        <button type="button" className="btn btn-outline btn-xs w-full" onClick={handleReset}>
          Reset to Defaults
        </button>
      </div>

      {/* Pipeline indicators toggle */}
      <div className="border-t border-base-300 pt-4">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            className="toggle toggle-sm toggle-primary"
            checked={showIndicators}
            onChange={handleToggleIndicators}
          />
          <div>
            <span className="text-sm font-medium">Show pipeline indicators</span>
            <p className="text-xs text-readout">Display pipeline strategy badges in response footers</p>
          </div>
        </label>
        <p className="text-xs text-readout mt-2">
          Tip: A quick-toggle icon in the Agent Chat header is also available if you need faster access.
        </p>
      </div>
    </div>
  )
}
