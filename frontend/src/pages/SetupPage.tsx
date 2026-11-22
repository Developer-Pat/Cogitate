/**
 * SetupPage — first-run setup (tabs, not a tunnel).
 *
 * Design (local/roadmaps/setup-page-proposal.md v2, LOCKED 2026-08-04):
 * - Tabbed sections, each with per-tab help (HelpModal machinery)
 * - Overview = live "doctor" checklist
 * - Keys decision: .env is THE secrets store (Keys tab writes .env)
 *
 * THE VERDICT MOVED TO THE BACKEND (2026-11-20). This page used to compute its own checklist
 * from three calls in the browser — including a POST to provider id 1 to guess whether Ollama
 * was up — with `agentReady` hardcoded true. So its icons reported FACTS ("0 of 0 providers
 * have keys") instead of DEFECTS, it asked a stranger to pick a profile while none could
 * exist, and the Dashboard could show nothing at all. The facts are now measured once in
 * `domain/providers/readiness.py` and both surfaces render the same verdict.
 */

import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, CircleDashed, Hourglass, XCircle } from 'lucide-react'
import ProviderKeyManager from '../components/features/providers/ProviderKeyManager'
import ExpressSetup from '../components/features/setup/ExpressSetup'
import { readinessService, type ReadinessItem, type ReadinessState } from '../services/readinessService'
import { HelpButton } from '../components/help'
import { AskExaButton } from '../components/agentPanel/AskExaButton'

type SetupTab = 'express' | 'overview' | 'local' | 'keys' | 'model' | 'agent'

const TABS: { id: SetupTab; label: string; tip: string }[] = [
  { id: 'express', label: 'Express', tip: 'One model, one key — the short path to a working install' },
  { id: 'overview', label: 'Overview', tip: 'What this install still needs, in order' },
  { id: 'local', label: 'Local LLM', tip: 'Run a model on this machine instead of using a key' },
  { id: 'keys', label: 'API Keys', tip: "Where a provider key goes — the project's .env" },
  { id: 'model', label: 'Default Model', tip: 'Which model answers, and what inherits it' },
  { id: 'agent', label: 'Agent', tip: 'The agents a configured install carries' },
]

const HELP_CONTEXT: Record<SetupTab, string> = {
  express: 'setup-express',
  overview: 'setup-overview',
  local: 'setup-local',
  keys: 'setup-keys',
  model: 'setup-model',
  agent: 'setup-agent',
}

/** The icon and the tone are the STATE's, not decoration: red = the user must act. */
const STATE_LOOK: Record<ReadinessState, { Icon: typeof AlertTriangle; tone: string; tip: string }> = {
  unmet: { Icon: XCircle, tone: 'text-error', tip: 'Not configured — this needs you.' },
  blocked: { Icon: Hourglass, tone: 'text-warning', tip: 'Waiting on an earlier step — nothing to do here yet.' },
  ok: { Icon: CheckCircle2, tone: 'text-success', tip: 'Configured.' },
  optional: { Icon: CircleDashed, tone: 'text-readout', tip: 'Optional — not needed for the app to answer.' },
}

export default function SetupPage() {
  const [params] = useSearchParams()
  const requested = params.get('tab')
  const initialTab = TABS.find((t) => t.id === requested)?.id ?? 'overview'
  const [activeTab, setActiveTab] = useState<SetupTab>(initialTab)
  const [items, setItems] = useState<ReadinessItem[] | null>(null)
  const [remaining, setRemaining] = useState<number | null>(null)
  const [failed, setFailed] = useState(false)

  const load = useCallback(async () => {
    try {
      const report = await readinessService.get()
      setItems(report.items)
      setRemaining(report.remaining)
      setFailed(false)
    } catch {
      setFailed(true)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (TABS.some((t) => t.id === requested)) setActiveTab(requested as SetupTab)
  }, [requested])

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-base-content">Setup</h1>
          <p className="text-sm text-readout mt-1">
            {failed
              ? 'The setup check did not answer — this page cannot say what is configured.'
              : remaining === null
                ? 'Checking what this install needs…'
                : remaining > 0
                  ? `${remaining} thing${remaining > 1 ? 's' : ''} left before an agent can answer.`
                  : 'Everything this app needs is configured — you can go to Chat.'}
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
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            data-tip={tab.tip}
            className={`tooltip tooltip-bottom pb-2 px-3 font-medium text-sm whitespace-nowrap rounded-t transition-colors ${
              activeTab === tab.id
                ? 'border-b-2 border-primary text-primary'
                : 'text-base-content/60 hover:text-base-content'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Express — one model, one key, one press (2026-11-21) */}
      {activeTab === 'express' && <ExpressSetup onApplied={() => void load()} />}

      {/* Overview — the doctor */}
      {activeTab === 'overview' && (
        <div className="space-y-3">
          {failed && (
            <p className="text-sm text-warning">
              The readiness check failed. Nothing here is a verdict about your install — re-open
              this page, or read the logs.
            </p>
          )}
          {!failed && !items && (
            <div className="flex justify-center py-10">
              <span className="loading loading-spinner loading-md text-primary" />
            </div>
          )}
          {!failed && items && (
            <div className="grid gap-3 sm:grid-cols-2">
              {items.map((item) => {
                const look = STATE_LOOK[item.state] ?? STATE_LOOK.optional
                return (
                  <Link
                    key={item.key}
                    to={item.href}
                    data-tip={look.tip}
                    className="tooltip tooltip-top text-left bg-base-200 rounded-lg border border-base-300 p-4 hover:border-primary transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <look.Icon className={`h-4 w-4 shrink-0 ${look.tone}`} aria-hidden="true" />
                      <span className="font-medium text-base-content">{item.label}</span>
                      {!item.counted && (
                        <span className="badge badge-ghost badge-xs ml-auto">optional</span>
                      )}
                    </div>
                    <p className="text-sm text-readout mt-1">{item.detail}</p>
                  </Link>
                )
              })}
            </div>
          )}
          <p className="text-xs text-readout">
            Each item opens where it is fixed. The full management view is the{' '}
            <Link to="/provider-dashboard" className="link link-primary">
              Provider Dashboard
            </Link>
            .
          </p>
        </div>
      )}

      {/* Local LLM */}
      {activeTab === 'local' && (
        <div className="bg-base-200 rounded-lg border border-base-300 p-5 space-y-3">
          <h3 className="font-semibold text-base-content">Local LLM (Ollama)</h3>
          <p className="text-sm text-readout">
            A local server can be the default instead of a cloud key. Nothing needs it: session
            titles take whatever answers chat. If you want one, it must be running on this
            machine (
            <code className="font-mono text-xs bg-base-300 px-1 rounded">ollama serve</code>).
          </p>
          <ul className="text-sm text-readout list-disc list-inside space-y-1">
            <li>
              Install:{' '}
              <code className="font-mono text-xs bg-base-300 px-1 rounded">
                curl -fsSL https://ollama.com/install.sh | sh
              </code>
            </li>
            <li>
              Pull a model:{' '}
              <code className="font-mono text-xs bg-base-300 px-1 rounded">ollama pull llama3.2</code>
            </li>
            <li>
              Start the daemon:{' '}
              <code className="font-mono text-xs bg-base-300 px-1 rounded">ollama serve</code>
            </li>
          </ul>
        </div>
      )}

      {/* API Keys — reuse the Keys tab */}
      {activeTab === 'keys' && <ProviderKeyManager />}

      {/* Default Model */}
      {activeTab === 'model' && (
        <div className="bg-base-200 rounded-lg border border-base-300 p-5 space-y-3">
          <h3 className="font-semibold text-base-content">Default Model</h3>
          <p className="text-sm text-readout">
            Pick the provider and model used as the system default — chat, title, summary,
            workflow and memory all take it from there. Manage it fully on the{' '}
            <Link to="/provider-dashboard" className="link link-primary">
              Provider Dashboard
            </Link>
            .
          </p>
          <Link
            to="/provider-dashboard"
            className="btn btn-primary btn-sm rounded-[var(--button-radius)]"
            data-tip="Opens the Provider Dashboard, where the default provider and model are set"
          >
            Choose Default Model
          </Link>
        </div>
      )}

      {/* Agent */}
      {activeTab === 'agent' && (
        <div className="bg-base-200 rounded-lg border border-base-300 p-5 space-y-3">
          <h3 className="font-semibold text-base-content">Agents</h3>
          <p className="text-sm text-readout">
            The two shipped reporters — Bob and Lois — arrive once a chat model resolves, and
            take their service from this install's chat answer. More agents are yours to add.
          </p>
          <Link
            to="/agent-profiles"
            className="btn btn-primary btn-sm rounded-[var(--button-radius)]"
            data-tip="Open the agents page"
          >
            Open Agents
          </Link>
          <Link to="/agent-interaction" className="btn btn-ghost btn-sm ml-2" data-tip="Open chat">
            Go to Chat
          </Link>
        </div>
      )}
    </div>
  )
}
