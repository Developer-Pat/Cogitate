/**
 * CognitiveProfileSelector — Table-based cognitive profile picker.
 *
 * Shows each profile as a card/row with name, part-code, pipeline config,
 * memory type, and tooltip description. User selects via radio buttons.
 */

import { useState, useEffect } from 'react'
import { cognitiveProfileService, type CognitiveProfile } from '@/services/domain/CognitiveProfileService'
import { frontendLoggingService } from '@/services/frontendLoggingService'

interface CognitiveProfileSelectorProps {
  value: number | null | undefined
  onChange: (profileId: number | null) => void
  disabled?: boolean
}

// Part codes for each pipeline dimension
const CODES: Record<string, Record<string, string>> = {
  context_builder: { default: 'd', minimal: 'm', augmented: 'a', skill_aware: 's' },
  executor: { default: 'd', fast: 'f', hybrid: 'h', structured: 's' },
  response_formatter: { default: 'd', direct_yield: 'y', structured: 's' },
  memory_profile_name: { default: 'd', stateless: 'n', kv_store: 'k', noop: 'n' },
}

function partCode(p: CognitiveProfile): string {
  const ctx = CODES.context_builder[p.context_builder] || '?'
  const exe = CODES.executor[p.executor] || '?'
  const fmt = CODES.response_formatter[p.response_formatter] || '?'
  const mem = CODES.memory_profile_name[p.memory_profile_name || ''] || '?'
  return `${ctx}-${exe}-${fmt}-${mem}`
}

function memoryLabel(memName: string | null | undefined): string {
  switch (memName) {
    case 'kv_store': return 'Persistent'
    case 'default': return 'In-Memory'
    case 'stateless': case 'noop': return 'None'
    default: return memName || '--'
  }
}

function memoryIcon(memName: string | null | undefined): string {
  switch (memName) {
    case 'kv_store': return '💾'
    case 'default': return '🧠'
    case 'stateless': case 'noop': return '---'
    default: return '?'
  }
}

export default function CognitiveProfileSelector({
  value,
  onChange,
  disabled = false,
}: CognitiveProfileSelectorProps) {
  const [profiles, setProfiles] = useState<CognitiveProfile[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const fetchProfiles = async () => {
      setLoading(true)
      try {
        const data = await cognitiveProfileService.list()
        setProfiles(data)
      } catch (error) {
        frontendLoggingService.error('CognitiveProfileSelector', 'Failed to fetch profiles', error)
      } finally {
        setLoading(false)
      }
    }
    fetchProfiles()
  }, [])

  if (loading) {
    return (
      <div>
        <label className="flex items-center gap-1.5 text-sm font-medium text-label mb-2">
          <span>🧠</span>
          <span>Cognitive Profile</span>
        </label>
        <p className="text-sm text-readout">Loading profiles...</p>
      </div>
    )
  }

  return (
    <div>
      <label className="flex items-center gap-1.5 text-sm font-medium text-label mb-2">
        <span>🧠</span>
        <span>Cognitive Profile</span>
      </label>

      {/* None option */}
      <label
        className={`flex items-center gap-3 p-2.5 rounded-lg border cursor-pointer transition-colors mb-1.5 ${
          value === null || value === undefined
            ? 'border-primary bg-primary/5'
            : 'border-base-300 hover:border-base-content/30 bg-base-100'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <input
          type="radio"
          name="cognitive-profile"
          className="radio radio-sm radio-primary"
          checked={value === null || value === undefined}
          onChange={() => onChange(null)}
          disabled={disabled}
        />
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm">--- None ---</div>
          <div className="text-xs text-readout">
            No cognitive pipeline --- basic LLM chat only
          </div>
        </div>
      </label>

      {/* Profile cards */}
      <div className="max-h-80 overflow-y-auto space-y-1.5 pr-1">
        {profiles.map((p) => {
          const selected = value === p.id
          const code = partCode(p)
          return (
            <label
              key={p.id}
              className={`flex items-start gap-3 p-2.5 rounded-lg border cursor-pointer transition-colors ${
                selected
                  ? 'border-primary bg-primary/5'
                  : 'border-base-300 hover:border-base-content/30 bg-base-100'
              } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <input
                type="radio"
                name="cognitive-profile"
                className="radio radio-sm radio-primary mt-0.5"
                checked={selected}
                onChange={() => onChange(p.id)}
                disabled={disabled}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm">{p.name}</span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-base-200 text-readout">{code}</span>
                </div>
                {p.description && (
                  <div className="text-xs text-readout mt-0.5 line-clamp-2" title={p.description}>
                    {p.description}
                  </div>
                )}
                <div className="flex items-center gap-3 mt-1.5 text-xs text-readout">
                  <span className="flex items-center gap-1">
                    <span className="font-medium">Context:</span> {p.context_builder}
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="font-medium">Reasoning:</span> {p.executor}
                  </span>
                  <span className="flex items-center gap-1" title={memoryLabel(p.memory_profile_name)}>
                    {memoryIcon(p.memory_profile_name)}
                    <span className="font-medium">Memory:</span> {memoryLabel(p.memory_profile_name)}
                  </span>
                </div>
              </div>
            </label>
          )
        })}
      </div>
    </div>
  )
}
