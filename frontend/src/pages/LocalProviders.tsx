/**
 * LocalProviders Page — the A1 provider split (2026-09-08)
 *
 * The LOCAL-class roof. Where the cloud page manages the SaaS
 * catalog (curated + browse + keys), this page is about the
 * daemons the user runs: what is installed (the hand-picked set —
 * "the local LLMs are already curated"), whether the daemon is
 * reachable, and (in a later phase) what is loaded and what a
 * swap costs. No curated manager, no keys — by class design.
 */

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { PageContainer } from '../components/ui/PageContainer';
import { PageBanner } from '../components/ui/PageBanner';
import { usePageTitle } from '../hooks/usePageTitle';
import Tooltip from '../components/ui/Tooltip';
import ProviderConfigModal from '../components/features/providers/ProviderConfigModal';
import { useProviderConfig } from '../hooks/useProviderConfig';
import { providerLocationOf } from '../utils/providerLocation';
import { fetchLocalOccupancy, type LocalOccupancy, type LocalDaemon } from '../services/domains/providers/occupancyService';
import { queueSwapRequest, composeSwapRequestText } from '../services/domains/providers/swapHandoff';
import type { ProviderConfig, ProviderConfigCreate, ProviderConfigUpdate, ProviderTestResponse } from '../types/providers';

const LocalProviders: React.FC = () => {
  usePageTitle('Local Providers', 'The local-class provider roof — the daemons, the installed models, and the occupancy')

  const {
    providers,
    loading: providersLoading,
    error: providersError,
    createProvider,
    updateProvider,
    testProvider,
  } = useProviderConfig();

  // Memoized: the probe effect below keys on this array, and a fresh array on
  // every render would re-run every provider probe on every render.
  const visibleProviders = useMemo(
    () => providers.filter((p) => providerLocationOf(p) === 'local'),
    [providers],
  )

  const [showConfigModal, setShowConfigModal] = useState(false)
  const [modalMode, setModalMode] = useState<'add' | 'edit'>('add')
  const [editingProvider, setEditingProvider] = useState<ProviderConfig | null>(null)

  // THE OCCUPANCY (A3, the read side): who runs + what is loaded.
  const [occupancy, setOccupancy] = useState<LocalOccupancy | null>(null)
  const [occupancyLoading, setOccupancyLoading] = useState(true)
  const [occupancyError, setOccupancyError] = useState<string | null>(null)

  // THE TABS (2026-09-09): the local page grouped like the cloud
  // page. Occupancy first — the live state is why the page exists;
  // the daemon management (the cards + the health) is the second
  // view. The config modal floats above both.
  const [activeTab, setActiveTab] = useState<'occupancy' | 'daemons'>('occupancy')

  // THE SWAP (A3, the write side): the page ASKS, the system agent
  // RUNS. The authorize-modal states the tradeoff; confirming queues
  // the request and opens the Exa chat tab, where the user sends it.
  const [swapTarget, setSwapTarget] = useState<LocalDaemon | null>(null)

  const handleSwapAuthorized = () => {
    if (!swapTarget) return
    const text = composeSwapRequestText(swapTarget.display_name, occupancy?.running ?? [])
    queueSwapRequest({
      text,
      label: `Swap request: start ${swapTarget.display_name}`,
      queuedAt: Date.now(),
    })
    setSwapTarget(null)
    window.open('/exa', '_blank', 'noopener')
  }

  // THE PER-DAEMON PROBE (2026-09-09, the daemons-tab health): ONE
  // health system — each card runs the live probe and shows its own
  // result (status + latency + the model count). Auto-probes when
  // the tab mounts; the card's Check re-runs it.
  const [probeResults, setProbeResults] = useState<Record<number, ProviderTestResponse>>({})
  const [probingIds, setProbingIds] = useState<Set<number>>(new Set())

  const runProbe = useCallback(async (providerId: number) => {
    setProbingIds((prev) => new Set(prev).add(providerId))
    try {
      const result = await testProvider(providerId)
      if (result) {
        setProbeResults((prev) => ({ ...prev, [providerId]: result }))
      }
    } finally {
      setProbingIds((prev) => {
        const next = new Set(prev)
        next.delete(providerId)
        return next
      })
    }
  }, [testProvider])

  // Auto-probe the local daemons when the tab opens (fast local probes)
  useEffect(() => {
    if (activeTab === 'daemons' && visibleProviders.length > 0) {
      visibleProviders.forEach((p) => runProbe(p.id))
    }
  }, [activeTab, visibleProviders, runProbe])

  const loadOccupancy = useCallback(async () => {
    try {
      setOccupancyLoading(true)
      const data = await fetchLocalOccupancy()
      setOccupancy(data)
      setOccupancyError(null)
    } catch (err) {
      setOccupancyError(err instanceof Error ? err.message : String(err))
    } finally {
      setOccupancyLoading(false)
    }
  }, [])

  useEffect(() => {
    loadOccupancy()
  }, [loadOccupancy])

  const handleAddProvider = () => {
    setEditingProvider(null)
    setModalMode('add')
    setShowConfigModal(true)
  }

  const handleEditProvider = (provider: ProviderConfig) => {
    setEditingProvider(provider)
    setModalMode('edit')
    setShowConfigModal(true)
  }

  const handleSaveProvider = async (config: ProviderConfigCreate | ProviderConfigUpdate) => {
    if (modalMode === 'add') {
      await createProvider(config as ProviderConfigCreate)
    } else if (editingProvider) {
      await updateProvider(editingProvider.id, config as ProviderConfigUpdate)
    }
    setShowConfigModal(false)
  }

  return (
    <PageContainer>
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-base-content">Local Providers</h1>
          <p className="text-sm text-readout mt-1">
            The daemons you run — reachability, what is serving, and the swap
          </p>
          <p className="text-sm text-readout mt-1">
            Which service each capability uses, and its fallbacks — see{' '}
            <Link to="/providers/capabilities" className="link link-primary">
              Capabilities
            </Link>
            .
          </p>
        </div>
        <Tooltip content="Add a local provider (Ollama, llama.cpp)" position="left">
          <button onClick={handleAddProvider} className="btn btn-primary btn-sm rounded-[var(--button-radius)]">
            Add Provider
          </button>
        </Tooltip>
      </div>

      {providersError && <PageBanner title="Error" className="mb-4">{providersError}</PageBanner>}

      {/* The tabs — the cloud page's underline pattern */}
      <div className="mb-6 border-b border-base-content/20">
        <nav className="-mb-px flex gap-4">
          <Tooltip content="Which daemon serves right now — the loaded models and the swap" position="bottom">
            <button
              onClick={() => setActiveTab('occupancy')}
              className={`pb-3 px-1 font-medium text-sm transition-colors ${
                activeTab === 'occupancy'
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-base-content/60 hover:text-base-content'
              }`}
            >
              Occupancy
            </button>
          </Tooltip>
          <Tooltip content="The local daemon cards — reachability, testing, and the connection settings" position="bottom">
            <button
              onClick={() => setActiveTab('daemons')}
              className={`pb-3 px-1 font-medium text-sm transition-colors ${
                activeTab === 'daemons'
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-base-content/60 hover:text-base-content'
              }`}
            >
              Daemons
            </button>
          </Tooltip>
        </nav>
      </div>

      {activeTab === 'daemons' && (
      <>
      {/* The daemon cards — ONE health system: each card carries its
          own live probe result (status + latency + the model count).
          No separate health dashboard — the occupancy tab is the
          reachability read, this tab is the per-daemon probe. */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {visibleProviders.map((provider) => {
          const probe = probeResults[provider.id];
          return (
          <div key={provider.id} className="bg-base-200 rounded-lg shadow p-4 border border-base-content/20">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="font-medium text-base-content">{provider.display_name || provider.name}</h3>
                <p className="text-sm text-readout">{provider.provider_type}</p>
              </div>
              <div className="flex items-center gap-2">
                {provider.is_active ? (
                  <span className="px-2 py-1 text-xs font-medium bg-success/20 text-success rounded-full">Active</span>
                ) : (
                  <span className="px-2 py-1 text-xs font-medium bg-base-300 text-base-content rounded-full">Inactive</span>
                )}
              </div>
            </div>

            <div className="text-sm text-readout mb-2">
              {provider.base_url && <p className="truncate">{provider.base_url}</p>}
            </div>

            {/* The live probe result (the single health check) */}
            {probe ? (
              <div className="mb-3 space-y-1">
                <div className="flex items-center gap-2 text-sm">
                  {probe.status === 'connected' ? (
                    <span className="badge badge-success badge-outline badge-sm">Connected</span>
                  ) : probe.status === 'unreachable' ? (
                    <span className="badge badge-error badge-outline badge-sm">Unreachable</span>
                  ) : (
                    <span className="badge badge-warning badge-outline badge-sm">{probe.status}</span>
                  )}
                  {probe.latency_ms !== undefined && probe.latency_ms !== null && (
                    <span className="text-xs text-readout">{Math.round(probe.latency_ms)}ms</span>
                  )}
                </div>
                {probe.models_available !== undefined && probe.models_available !== null && (
                  <p className="text-xs font-medium text-success">
                    {probe.models_available} {probe.models_available === 1 ? 'model' : 'models'} available
                  </p>
                )}
                {probe.message && probe.status !== 'connected' && (
                  <p className="text-xs text-error truncate" title={probe.message}>{probe.message}</p>
                )}
              </div>
            ) : (
              <p className="text-xs text-readout mb-3">Not probed yet — run a check.</p>
            )}

            {/* Actions — the Test is the ONE health check */}
            <div className="flex gap-2 pt-3 border-t border-base-content/20">
              <Tooltip content="Edit the provider settings" position="top">
                <button
                  onClick={() => handleEditProvider(provider)}
                  className="flex-1 px-3 py-1.5 text-sm text-primary hover:bg-primary/10 rounded"
                >
                  Edit
                </button>
              </Tooltip>
              <Tooltip content="Run the live daemon probe" position="top">
                <button
                  onClick={() => runProbe(provider.id)}
                  className="flex-1 px-3 py-1.5 text-sm text-readout hover:bg-base-content/10 rounded"
                >
                  {probingIds.has(provider.id) ? 'Probing...' : 'Check'}
                </button>
              </Tooltip>
              <Tooltip content="Browse the installed models" position="top">
                <Link
                  to={`/providers/${provider.id}/models`}
                  className="flex-1 px-3 py-1.5 text-sm text-readout hover:bg-base-content/10 rounded text-center"
                >
                  Models
                </Link>
              </Tooltip>
            </div>
          </div>
          );
        })}
      </div>

      {visibleProviders.length === 0 && !providersLoading && (
        <div className="text-center py-12">
          <p className="text-readout mb-4">
            No local providers configured — add Ollama or llama.cpp, or ask the system agent to set one up.
          </p>
          <button onClick={handleAddProvider} className="text-primary hover:underline">
            Add your first local provider
          </button>
        </div>
      )}

      {providersLoading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
      )}

      </>
      )}

      {activeTab === 'occupancy' && (
      /* The occupancy (A3, the read side): the GPU owner + the states */
      <div className="bg-base-200 rounded-lg shadow p-4 border border-base-content/20">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-lg font-semibold text-base-content">Occupancy</h2>
            <p className="text-sm text-readout">
              Which daemon serves right now — a swapped-out daemon is a choice, not an alert
            </p>
          </div>
          <Tooltip content="Re-probe the local daemons" position="left">
            <button
              onClick={loadOccupancy}
              disabled={occupancyLoading}
              className="btn btn-sm btn-ghost rounded-[var(--button-radius)]"
            >
              {occupancyLoading ? 'Probing...' : 'Refresh'}
            </button>
          </Tooltip>
        </div>

        {occupancyError && (
          <p className="text-sm text-error mb-3">Occupancy read failed: {occupancyError}</p>
        )}

        {occupancy && !occupancyLoading && (
          <div className="space-y-3">
            {/* The idle line only — when a daemon serves, its CARD
                carries the state (the Serving badge) and the loaded
                model; no duplicated headline above the grid. */}
            {occupancy.running.length === 0 && (
              <div className="flex items-center gap-2 text-sm">
                <span className="badge badge-ghost badge-sm">Idle</span>
                <span className="text-readout">No local daemon is running</span>
              </div>
            )}

            {/* The per-daemon states */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
              {occupancy.daemons.map((daemon) => (
                <div key={daemon.name} className="bg-base-100 rounded-lg px-3 py-2 border border-base-content/10">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <span className="font-medium text-sm text-base-content truncate">{daemon.display_name}</span>
                      {daemon.loaded_models.length > 0 && (
                        <div className="text-xs font-medium text-success truncate" title={daemon.loaded_models.join(', ')}>
                          loaded: {daemon.loaded_models.join(', ')}
                        </div>
                      )}
                    </div>
                    {daemon.state === 'healthy' && (
                      <span className="badge badge-success badge-outline badge-sm">Serving</span>
                    )}
                    {daemon.state === 'down-by-occupancy' && (
                      <span
                        className="badge badge-sm"
                        title={`Held by: ${occupancy.running.join(', ')}`}
                      >
                        Swapped out
                      </span>
                    )}
                    {daemon.state === 'down' && (
                      <span className="badge badge-ghost badge-outline badge-sm">Stopped</span>
                    )}
                  </div>
                  {daemon.state !== 'healthy' && (
                    <div className="pt-2">
                      <button
                        onClick={() => setSwapTarget(daemon)}
                        className="btn btn-xs btn-ghost border border-base-content/20 text-base-content rounded-[var(--button-radius)]"
                        title={
                          daemon.state === 'down-by-occupancy'
                            ? `Ask the system agent to stop ${occupancy.running.join(', ')} and start ${daemon.display_name}`
                            : `Ask the system agent to start ${daemon.display_name}`
                        }
                      >
                        {daemon.state === 'down-by-occupancy' ? 'Start instead' : 'Start'}
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {!occupancy && !occupancyError && occupancyLoading && (
          <p className="text-sm text-readout">Probing the local daemons...</p>
        )}
      </div>
      )}
      {/* The config modal — class-limited to the local types */}
      {showConfigModal && (
        <ProviderConfigModal
          provider={editingProvider}
          mode={modalMode}
          onSave={handleSaveProvider}
          onCancel={() => setShowConfigModal(false)}
          loading={providersLoading}
          location="local"
        />
      )}
      {/* THE SWAP AUTHORIZE (A3, the write side): the tradeoff is
          stated before anything is queued — the system agent only
          acts on the user's explicit send in the Exa chat. */}
      {swapTarget && (
        <div className="modal modal-open" role="dialog" aria-modal="true">
          <div className="modal-box">
            <h3 className="text-lg font-semibold text-base-content mb-1">
              {swapTarget.state === 'down-by-occupancy'
                ? `Start ${swapTarget.display_name} instead?`
                : `Start ${swapTarget.display_name}?`}
            </h3>
            {swapTarget.state === 'down-by-occupancy' ? (
              <p className="text-sm text-base-content/80 mb-4">
                {occupancy?.running.join(', ')} is serving the GPU right now — starting{' '}
                {swapTarget.display_name} stops it and unloads what it has loaded.
              </p>
            ) : (
              <p className="text-sm text-base-content/80 mb-4">
                No local daemon is running — this just starts {swapTarget.display_name}.
              </p>
            )}
            <p className="text-sm text-readout mb-5">
              The request goes to the system agent in the Exa chat — review it there and send
              when ready.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setSwapTarget(null)}
                className="btn btn-ghost rounded-[var(--button-radius)]"
              >
                Cancel
              </button>
              <button
                onClick={handleSwapAuthorized}
                className="btn btn-primary rounded-[var(--button-radius)]"
              >
                Ask the system agent
              </button>
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  )
}

export default LocalProviders
