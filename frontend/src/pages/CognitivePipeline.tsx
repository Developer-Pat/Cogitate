/**
 * CognitivePipeline page — Management page for cognitive pipeline configuration.
 *
 * Three tabs:
 *   - Pipeline Config: Strategy selectors + Cognitive Profile picker
 *   - Memory Profiles: CRUD for named memory configurations
 *   - Cognitive Profiles: CRUD that bundles pipeline config + memory profile
 */

import { useState } from 'react'
import PipelineConfigTab, { type PipelineConfig } from '../components/features/cognitive/PipelineConfigTab'
import MemoryProfilesTab from '../components/features/cognitive/MemoryProfilesTab'
import CognitiveProfilesTab from '../components/features/cognitive/CognitiveProfilesTab'
import AgentMemoryTab from '../components/features/cognitive/AgentMemoryTab'
import { HelpButton } from '../components/help';

type TabId = 'pipeline' | 'memory' | 'cognitive' | 'agent-memory'

interface TabConfig {
  id: TabId
  label: string
  icon: string
}

const TABS: TabConfig[] = [
  { id: 'pipeline', label: 'Pipeline Config', icon: '⚙️' },
  { id: 'memory', label: 'Memory Profiles', icon: '💾' },
  { id: 'cognitive', label: 'Cognitive Profiles', icon: '🧠' },
  { id: 'agent-memory', label: 'Agent Memory', icon: '📦' },
]

export default function CognitivePipeline() {
  const [activeTab, setActiveTab] = useState<TabId>('pipeline')
  const [pipelineConfig, setPipelineConfig] = useState<PipelineConfig>({
    context_builder: 'default',
    executor: 'default',
    memory_manager: 'default',
    response_formatter: 'default',
  })

  return (
    <div className="container mx-auto p-4 max-w-5xl">
      {/* Page header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <span>🧠</span>
            <span>Cognitive Pipeline</span>
          </h1>
          <HelpButton context="cognitive-pipeline" tooltipPosition="bottom" />
        </div>
        <p className="text-sm text-readout mt-1">
          Configure cognitive pipeline strategies, memory profiles, and cognitive profiles for agents
        </p>
      </div>

      {/* Tabs */}
      <div className="tabs tabs-bordered mb-6">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`tab tab-sm ${activeTab === tab.id ? 'tab-active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span className="flex items-center gap-1.5">
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)]">
        <div className="card-body p-[var(--card-padding)]">
          {activeTab === 'pipeline' && (
            <PipelineConfigTab
              config={pipelineConfig}
              onConfigChange={setPipelineConfig}
            />
          )}
          {activeTab === 'memory' && <MemoryProfilesTab />}
          {activeTab === 'cognitive' && <CognitiveProfilesTab />}
          {activeTab === 'agent-memory' && <AgentMemoryTab />}
        </div>
      </div>
    </div>
  )
}
