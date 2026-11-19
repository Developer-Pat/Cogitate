/**
 * THE LOCAL SERVICES PAGE (2026-09-03, the Local Services arc)
 *
 * The capability-driven surface for LOCAL services: the local
 * providers (llama-server, ollama) with reachability + test, and the
 * capability assignment cards — the first capability is SESSION
 * TITLES (the title-model preference + auto-title + a test rename).
 *
 * Structure (the SpeechPage model — see SpeechPage.tsx):
 * - Local service providers section: reachable/unreachable badge,
 *   base URL, model, a TEST button per provider.
 * - Capability cards: which provider a capability uses + its test.
 *
 * Availability doctrine: an unavailable local service shows its
 * state (never a silent empty) and its test surfaces the error.
 */

import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { PageBanner } from '../components/ui/PageBanner'
import { PageContainer } from '../components/ui/PageContainer'
import { usePageTitle } from '../hooks/usePageTitle'
import { useSettingsStore } from '../stores/settingsStore'
import { useNotificationStore } from '../stores/notificationStore'
import { providerConfigService } from '../services/domains/providers/providerConfigService'
import { frontendLoggingService } from '../services/frontendLoggingService'
import { apiClient } from '../services/apiClient'
import type { ProviderConfig } from '../types/providers'

// A provider is "local" when its base_url points at this machine —
// the local-service abstraction is keyed on that, not on provider_type
// (the llama row is provider_type 'openai' but LOCAL).
function isLocalProvider(p: ProviderConfig): boolean {
  const url = p.base_url || ''
  return /localhost|127\.0\.0\.1|0\.0\.0\.0/.test(url)
}

interface TitleStatus {
  enabled: boolean
  /** The pair the SERVICE last loaded — null until it configures itself (it is lazy). */
  resolved_provider: string | null
  resolved_model: string | null
  resolved_base_url: string | null
  reasoning_effort: string | null
  /** Whether the `title` CAPABILITY resolves to a provider row — read live, never the default row. */
  default_provider_ready: boolean
  /** The capability's answer: the provider the title would actually use right now. */
  default_provider: { id: number; name: string; type: string; model: string | null } | null
  /** Why the capability is not ready, when it is not — the resolution's own reason. */
  default_provider_issues: string[]
}

interface TestState {
  status: 'idle' | 'testing' | 'ok' | 'error'
  detail: string
}

export default function LocalServicesPage() {
  usePageTitle('Local Services', 'The local services — providers, reachability, and the capabilities they power')
  const [providers, setProviders] = useState<ProviderConfig[]>([])
  const [tests, setTests] = useState<Record<number, TestState>>({})
  const [titleStatus, setTitleStatus] = useState<TitleStatus | null>(null)

  // Title capability controls (persisted in settings.general)
  const settings = useSettingsStore((s) => s.settings)
  const updateSettings = useSettingsStore((s) => s.updateSettings)
  const [testRename, setTestRename] = useState<TestState>({ status: 'idle', detail: '' })
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const [prov, statusRes] = await Promise.all([
        providerConfigService.getProviders(true),
        apiClient.get<TitleStatus>('/api/v1/chat/title-service/status'),
      ])
      setProviders((prov.providers || []).filter(isLocalProvider))
      if (statusRes.data) setTitleStatus(statusRes.data as TitleStatus)
    } catch (err) {
      frontendLoggingService.error('LocalServices', 'Failed to load', err)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const testProvider = async (p: ProviderConfig) => {
    setTests((t) => ({ ...t, [p.id]: { status: 'testing', detail: '' } }))
    try {
      const result = await providerConfigService.testProvider(p.id)
      // The backend ProviderTestResponse: {status: connected|not_configured|error, message, ...}
      const raw = result as unknown as { status?: string; message?: string; success?: boolean; output?: string; error?: string }
      const connected = raw.status === 'connected' || raw.success === true
      setTests((t) => ({
        ...t,
        [p.id]: {
          status: connected ? 'ok' : 'error',
          detail: raw.message || raw.output || raw.error || raw.status || '',
        },
      }))
    } catch (err) {
      setTests((t) => ({
        ...t,
        [p.id]: { status: 'error', detail: err instanceof Error ? err.message : String(err) },
      }))
    }
  }

  // The title capability: save the preference + auto-title toggle
  const handleSaveTitleConfig = async () => {
    setSaving(true)
    try {
      const general = settings.general || {}
      await updateSettings({ general: { ...general } })
      useNotificationStore.getState().addSuccess('Local Services', 'Title configuration saved')
    } catch {
      useNotificationStore.getState().addError('Local Services', 'Failed to save the title configuration')
    } finally {
      setSaving(false)
    }
  }

  const setTitlePref = (key: 'enableAutoTitle' | 'titleModelPreference' | 'titleCustomModel', value: boolean | string) => {
    const general = settings.general || {}
    updateSettings({ general: { ...general, [key]: value } })
  }

  // Test the rename end-to-end via the chat generate-title endpoint
  const handleTestRename = async () => {
    setTestRename({ status: 'testing', detail: '' })
    try {
      const response = await apiClient.post<{ title: string }>('/api/v1/chat/generate-title', {
        assistant_message: 'The weather in Omaha is 74 degrees and sunny with a light breeze from the south.',
        model: undefined,
      })
      const title = response.data?.title
      if (title) {
        setTestRename({ status: 'ok', detail: `Title generated: "${title}"` })
      } else {
        setTestRename({ status: 'error', detail: 'The title service returned no title' })
      }
    } catch (err) {
      setTestRename({ status: 'error', detail: err instanceof Error ? err.message : String(err) })
    }
  }

  const general = settings.general || {}
  const titlePref = general.titleModelPreference ?? 'agent'
  const localProviders = providers

  return (
    <PageContainer>
      <PageBanner
        title="Local Services"
        className="mb-6"
        tooltip="The local services — the providers on this machine and the capabilities they power"
      />

      {/* ============ LOCAL PROVIDERS ============ */}
      <section className="card bg-base-100 shadow-md mb-6">
        <div className="card-body p-4">
          <h2 className="card-title text-sm">Local service providers</h2>
          <p className="text-xs opacity-60 mb-3">
            The local LLM servers configured on this machine. A provider is unavailable when its
            server is down or its model can't load — the test shows why.
          </p>
          {localProviders.length === 0 ? (
            <p className="text-sm opacity-60">No local providers configured.</p>
          ) : (
            <div className="space-y-3">
              {localProviders.map((p) => {
                const t = tests[p.id] || { status: 'idle', detail: '' }
                return (
                  <div key={p.id} className="flex flex-wrap items-center gap-3 border border-base-300 rounded-lg p-3">
                    <div className="min-w-36">
                      <div className="font-medium text-sm">{p.display_name || p.name}</div>
                      <div className="text-xs opacity-60 font-mono">{p.base_url}</div>
                    </div>
                    <div className="flex-1 min-w-40 text-xs">
                      {t.status === 'idle' && <span className="opacity-50">Unknown — test to check reachability</span>}
                      {t.status === 'testing' && <span className="opacity-60">Testing…</span>}
                      {t.status === 'ok' && <span className="text-success font-medium">Reachable ✓ {t.detail}</span>}
                      {t.status === 'error' && <span className="text-error font-medium">Unavailable — {t.detail}</span>}
                    </div>
                    <button
                      className="btn btn-xs btn-outline"
                      disabled={t.status === 'testing'}
                      onClick={() => void testProvider(p)}
                    >
                      {t.status === 'testing' ? 'Testing…' : 'Test'}
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </section>

      {/* ============ CAPABILITY: SESSION TITLES ============ */}
      <section className="card bg-base-100 shadow-md">
        <div className="card-body p-4">
          <h2 className="card-title text-sm">Session titles</h2>
          <p className="text-xs opacity-60 mb-3">
            The title capability names sessions from their conversation. Which model does it use —
            and does it run automatically? The service it uses, and its fallbacks, are on{' '}
            <Link to="/providers/capabilities" className="link link-primary">
              Capabilities
            </Link>
            .
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* The preference */}
            <div className="form-control">
              <label className="label">
                <span className="label-text font-semibold">Title Generation Model</span>
              </label>
              <select
                className="select select-bordered w-full"
                data-tip="Sent with the rename request as an override — it picks who answers FIRST for that request"
                value={titlePref}
                onChange={(e) => setTitlePref('titleModelPreference', e.target.value as 'agent' | 'backend_default' | 'custom')}
              >
                <option value="agent">The agent&apos;s model</option>
                <option value="backend_default">No override — the title capability&apos;s own answer</option>
                <option value="custom">A model string</option>
              </select>
              <label className="label">
                {/* `whitespace-normal`: DaisyUI's .label is nowrap, so a long helper runs out of its
                    column and under the panel beside it. */}
                <span className="label-text-alt whitespace-normal">
                  An override picks who answers FIRST for that rename. With none, the title capability
                  answers.
                </span>
              </label>

              {titlePref === 'custom' && (
                <input
                  type="text"
                  className="input input-bordered input-sm w-full mt-1"
                  placeholder="e.g. deepseek/deepseek-v4-flash or llama/Bonsai-27B-Q1_0.gguf"
                  value={general.titleCustomModel ?? ''}
                  onChange={(e) => setTitlePref('titleCustomModel', e.target.value)}
                />
              )}

              <label className="label cursor-pointer justify-start gap-3 mt-2">
                <input
                  type="checkbox"
                  className="toggle toggle-primary toggle-sm"
                  checked={general.enableAutoTitle ?? true}
                  onChange={(e) => setTitlePref('enableAutoTitle', e.target.checked)}
                />
                <span className="label-text font-medium">Auto-title</span>
              </label>
              <p className="text-xs opacity-50 ml-1">
                Off = you rename deliberately. Sessions starting with &quot;hello&quot; make
                uninformative titles.
              </p>
            </div>

            {/* What the title capability answers + the test */}
            <div className="border border-base-300 rounded-lg p-3 text-sm space-y-2">
              <div className="font-semibold text-xs uppercase opacity-60">Resolved state</div>
              {titleStatus ? (
                <>
                  {/* FIRST, because it is the answer that always exists: the capability is read live,
                      while the service's own pair stays null until it lazily loads its config. */}
                  <div className="flex justify-between">
                    <span className="opacity-60">Title capability</span>
                    <span className="font-mono font-medium">
                      {titleStatus.default_provider
                        ? `${titleStatus.default_provider.name}/${titleStatus.default_provider.model ?? '?'}`
                        : '—'}
                    </span>
                  </div>
                  {!titleStatus.default_provider_ready && (
                    <p className="text-xs text-warning">
                      Not ready
                      {titleStatus.default_provider_issues.length > 0
                        ? ` — ${titleStatus.default_provider_issues.join('; ')}`
                        : ''}
                    </p>
                  )}
                  <div className="flex justify-between">
                    <span className="opacity-60">Service provider</span>
                    <span className="font-mono">{titleStatus.resolved_provider ?? '—'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="opacity-60">Service model</span>
                    <span className="font-mono">{titleStatus.resolved_model ?? '—'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="opacity-60">Reasoning</span>
                    <span className="font-mono">{titleStatus.reasoning_effort ?? 'default'}</span>
                  </div>
                </>
              ) : (
                <p className="opacity-60">Unavailable</p>
              )}

              <div className="divider my-1" />
              <div className="text-xs">
                {testRename.status === 'idle' && <span className="opacity-50">Test the rename end-to-end below.</span>}
                {testRename.status === 'testing' && <span className="opacity-60">Generating…</span>}
                {testRename.status === 'ok' && <span className="text-success font-medium">{testRename.detail}</span>}
                {testRename.status === 'error' && <span className="text-error font-medium">{testRename.detail}</span>}
              </div>
              <div className="flex gap-2 mt-2">
                <button className="btn btn-sm btn-outline" disabled={testRename.status === 'testing'} onClick={() => void handleTestRename()}>
                  Test rename
                </button>
                <button className="btn btn-sm btn-primary ml-auto" disabled={saving} onClick={() => void handleSaveTitleConfig()}>
                  {saving ? 'Saving…' : 'Save'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </PageContainer>
  )
}

