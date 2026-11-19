/**
 * SetupPage — first-run setup wizard (tabs, not a tunnel).
 *
 * Design (local/roadmaps/setup-page-proposal.md v2, LOCKED 2026-08-04):
 * - Tabbed sections, each with per-tab help (HelpModal machinery)
 * - Overview = live "doctor" checklist (✅/⚠️/⏳ per item)
 * - Keys decision: .env is THE secrets store (Keys tab writes .env)
 * - First-run: auto-redirect (Option A) when unconfigured
 */

import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import ProviderKeyManager from '../components/features/providers/ProviderKeyManager'
import { apiClient } from '../services/apiClient'
import { HelpButton } from '../components/help'
import { AskExaButton } from '../components/agentPanel/AskExaButton'

type SetupTab = 'overview' | 'local' | 'keys' | 'model' | 'agent'

interface ChecklistItem {
  key: string
  label: string
  detail: string
  status: 'ok' | 'warn' | 'pending'
  tab: SetupTab
}

interface SetupStatus {
  ollamaRunning: boolean
  keysConfigured: number
  keysTotal: number
  defaultModelSet: boolean
  agentReady: boolean
}

const TABS: { id: SetupTab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'local', label: 'Local LLM' },
  { id: 'keys', label: 'API Keys' },
  { id: 'model', label: 'Default Model' },
  { id: 'agent', label: 'Agent' },
]

const HELP_CONTEXT: Record<SetupTab, string> = {
  overview: 'setup-overview',
  local: 'setup-local',
  keys: 'setup-keys',
  model: 'setup-model',
  agent: 'setup-agent',
}

export default function SetupPage() {
  const [activeTab, setActiveTab] = useState<SetupTab>('overview')
  const [status, setStatus] = useState<SetupStatus | null>(null)
  const [loading, setLoading] = useState(true)

  const loadStatus = useCallback(async () => {
    try {
      const [keysResp, defaultResp] = await Promise.allSettled([
        apiClient.get('/api/v1/providers/managed/keys'),
        apiClient.get('/api/v1/providers/default'),
      ])
      const keysData = (keysResp as PromiseFulfilledResult<{ data?: { providers?: Array<{ has_key: boolean }> } }>).value?.data
      const providers = keysData?.providers ?? []
      const keysConfigured = providers.filter((p: { has_key: boolean }) => p.has_key).length

      const defaultData = (defaultResp as PromiseFulfilledResult<{ data?: { provider_name?: string; model?: string } }>).value?.data
      const defaultModelSet = Boolean(defaultData?.provider_name && defaultData?.model)

      // Ollama check via the test endpoint (provider id 1)
      let ollamaRunning = false
      try {
        const ollamaResp = await apiClient.post('/api/v1/providers/managed/1/test')
        ollamaRunning = (ollamaResp.data as { status?: string })?.status === 'connected'
      } catch {
        ollamaRunning = false
      }

      setStatus({
        ollamaRunning,
        keysConfigured,
        keysTotal: providers.length,
        defaultModelSet,
        agentReady: true, // seeded agents exist; refined below
      })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadStatus() }, [loadStatus])

  const checklist: ChecklistItem[] = [
    {
      key: 'ollama',
      label: 'Local LLM running',
      detail: status?.ollamaRunning
        ? 'Ollama is running — session titles will work'
        : 'Ollama not detected — session titles may be disabled',
      status: status?.ollamaRunning ? 'ok' : 'warn',
      tab: 'local',
    },
    {
      key: 'keys',
      label: 'API keys',
      detail: status
        ? `${status.keysConfigured} of ${status.keysTotal} providers have keys`
        : 'Checking…',
      status: status && status.keysConfigured > 0 ? 'ok' : 'pending',
      tab: 'keys',
    },
    {
      key: 'model',
      label: 'Default model',
      detail: status?.defaultModelSet
        ? 'Default provider + model configured'
        : 'No default model set yet',
      status: status?.defaultModelSet ? 'ok' : 'pending',
      tab: 'model',
    },
    {
      key: 'agent',
      label: 'Starter agent',
      detail: 'Pick a capability profile to start chatting',
      status: 'pending',
      tab: 'agent',
    },
  ]

  const statusIcon = (s: ChecklistItem['status']) =>
    s === 'ok' ? '✅' : s === 'warn' ? '⚠️' : '⏳'

  const incompleteCount = checklist.filter(i => i.status !== 'ok').length

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-base-content">Setup</h1>
          <p className="text-sm text-readout mt-1">
            Get Cogitate running in a few steps. {incompleteCount > 0
              ? `${incompleteCount} item${incompleteCount > 1 ? 's' : ''} remaining — the checklist below is what's next.`
              : 'Everything looks configured — you can jump to Chat.'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <AskExaButton context="setup" size="sm" tooltip="Ask Exa to guide you through setup" />
          {/* THE INSTALL TOPIC (2026-11-18): the Setup page is where a broken
              environment is met, so the install document is help here rather
              than a page nobody's looking at when they need it. */}
          <HelpButton
            context="setup-install"
            size="sm"
            showIcon={false}
            showLabel
            label="Install"
            tooltipPosition="left"
          />
          <HelpButton context={HELP_CONTEXT[activeTab]} size="sm" tooltipPosition="left" />
        </div>
      </div>

      {/* Tabs */}
      <nav className="flex gap-1 border-b border-base-300 overflow-x-auto">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`pb-2 px-3 font-medium text-sm whitespace-nowrap rounded-t transition-colors ${
              activeTab === tab.id
                ? 'border-b-2 border-primary text-primary'
                : 'text-base-content/60 hover:text-base-content'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Overview — the doctor */}
      {activeTab === 'overview' && (
        <div className="space-y-3">
          {loading ? (
            <div className="flex justify-center py-10">
              <span className="loading loading-spinner loading-md text-primary" />
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {checklist.map(item => (
                <button
                  key={item.key}
                  onClick={() => setActiveTab(item.tab)}
                  className="text-left bg-base-200 rounded-lg border border-base-300 p-4 hover:border-primary transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{statusIcon(item.status)}</span>
                    <span className="font-medium text-base-content">{item.label}</span>
                  </div>
                  <p className="text-sm text-readout mt-1">{item.detail}</p>
                </button>
              ))}
            </div>
          )}
          <p className="text-xs text-readout">
            Click an item to jump to its tab. See{' '}
            <Link to="/provider-dashboard" className="link link-primary">Provider Dashboard</Link>{' '}
            for the full management view.
          </p>
        </div>
      )}

      {/* Local LLM */}
      {activeTab === 'local' && (
        <div className="bg-base-200 rounded-lg border border-base-300 p-5 space-y-3">
          <h3 className="font-semibold text-base-content">Local LLM (Ollama)</h3>
          <p className="text-sm text-readout">
            Ollama powers session titles and can serve local models. It needs to be
            running on this machine (<code className="font-mono text-xs bg-base-300 px-1 rounded">ollama serve</code>).
          </p>
          <div className={`badge ${status?.ollamaRunning ? 'badge-success badge-outline' : 'badge-warning badge-outline'}`}>
            {status?.ollamaRunning ? '✅ Running' : '⚠️ Not detected'}
          </div>
          <ul className="text-sm text-readout list-disc list-inside space-y-1">
            <li>Install: <code className="font-mono text-xs bg-base-300 px-1 rounded">curl -fsSL https://ollama.com/install.sh | sh</code></li>
            <li>Pull a model: <code className="font-mono text-xs bg-base-300 px-1 rounded">ollama pull llama3.2</code></li>
            <li>Start the daemon: <code className="font-mono text-xs bg-base-300 px-1 rounded">ollama serve</code></li>
          </ul>
        </div>
      )}

      {/* API Keys — reuse the Keys tab */}
      {activeTab === 'keys' && (
        <ProviderKeyManager />
      )}

      {/* Default Model */}
      {activeTab === 'model' && (
        <div className="bg-base-200 rounded-lg border border-base-300 p-5 space-y-3">
          <h3 className="font-semibold text-base-content">Default Model</h3>
          <p className="text-sm text-readout">
            Pick the provider and model used as the system default. Manage it fully
            on the{' '}
            <Link to="/provider-dashboard" className="link link-primary">Provider Dashboard</Link>{' '}
            (Overview tab → Default Provider).
          </p>
          <Link to="/provider-dashboard" className="btn btn-primary btn-sm rounded-[var(--button-radius)]">
            Choose Default Model
          </Link>
        </div>
      )}

      {/* Agent */}
      {activeTab === 'agent' && (
        <div className="bg-base-200 rounded-lg border border-base-300 p-5 space-y-3">
          <h3 className="font-semibold text-base-content">Starter Agent</h3>
          <p className="text-sm text-readout">
            Agents use capability profiles (not roles) to pick strategies. Choose a
            profile that matches how you work, then start chatting.
          </p>
          <Link to="/agent-profiles" className="btn btn-primary btn-sm rounded-[var(--button-radius)]">
            Pick a Profile
          </Link>
          <Link to="/agent-interaction" className="btn btn-ghost btn-sm ml-2">
            Go to Chat
          </Link>
        </div>
      )}
    </div>
  )
}
