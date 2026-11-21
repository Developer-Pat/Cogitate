/**
 * ProviderDashboard Page - Phase 4
 *
 * Main dashboard for provider management.
 * Integrates provider configuration, usage tracking, and sync scheduling.
 * Unified page replacing legacy ProviderManagement.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { PageContainer } from '../components/ui/PageContainer';
import { PageBanner } from '../components/ui/PageBanner';
import { usePageTitle } from '../hooks/usePageTitle';
import Tooltip from '../components/ui/Tooltip';
import ProviderConfigModal from '../components/features/providers/ProviderConfigModal';
import ProviderHealthModal from '../components/features/providers/ProviderHealthModal';
import ProviderModal from '../components/features/providers/ProviderModal';
import UsageDashboard from '../components/features/providers/UsageDashboard';
import ModelSyncScheduler from '../components/features/providers/ModelSyncScheduler';
import CuratedModelsManager from '../components/features/providers/CuratedModelsManager';
import ProviderKeyManager from '../components/features/providers/ProviderKeyManager';
import { DefaultProviderConfig } from '../components/features/providers/DefaultProviderConfig';
import { HelpButton } from '../components/help/HelpButton';
import { useProviderConfig } from '../hooks/useProviderConfig';
import { useDefaultProvider } from '../hooks/useDefaultProvider';
import { useUsage } from '../hooks/useUsage';
import { useSyncSchedule } from '../hooks/useSyncSchedule';
import { useNotificationStore } from '../stores/notificationStore';
import { frontendLoggingService } from '../services/frontendLoggingService';
import { modelBrowserService, type ModelInfo } from '../services/domains/providers/modelBrowserService';
import { providerLocationOf } from '../utils/providerLocation';
import ModelFilters from '../components/features/providers/ModelBrowser/ModelFilters';
import ModelTable from '../components/features/providers/ModelBrowser/ModelTable';
import type {
  ProviderConfig,
  ProviderConfigCreate,
  ProviderConfigUpdate,
  UsagePeriod,
} from '../types/providers';
import type { ModelBrowserFilters } from '../services/domains/providers/modelBrowserService';

/** The page's tabs, in the order they render. Curated is FIRST and is the DEFAULT. */
const TAB_KEYS = ['curated', 'overview', 'default', 'usage', 'keys'] as const;
type ProviderTab = (typeof TAB_KEYS)[number];

/**
 * The wiki help page each tab opens (`wiki/help/<context>.md`). A `Record<ProviderTab, string>`
 * rather than a ternary chain: a tab added or removed without a case here is a TYPE error, which is
 * the one thing a chained ternary cannot give — it silently falls through to the last branch.
 */
const HELP_CONTEXT: Record<ProviderTab, string> = {
  curated: 'providers-curated',
  overview: 'providers-overview',
  default: 'providers-default',
  usage: 'providers-usage',
  keys: 'providers-keys',
};

/**
 * The tab comes FROM THE URL (`?tab=usage`): a reload, an HMR edit or a shared link lands on the
 * same tab, which component state cannot do. Absent or unrecognised → the default, Curated.
 */
function readTab(param: string | null): ProviderTab {
  return TAB_KEYS.includes((param ?? '') as ProviderTab)
    ? (param as ProviderTab)
    : 'curated';
}

/**
 * ProviderDashboard Page Component
 */
const ProviderDashboard: React.FC = () => {
  usePageTitle('Cloud Providers', 'The cloud-class provider page (the A1 split): the SaaS providers, their usage and keys, the default provider, and the curated recommendation layer')

  // Provider config hook
  const {
    providers,
    loading: providersLoading,
    error: providersError,
    refreshProviders: _refreshProviders,
    createProvider,
    updateProvider,
    setApiKey: _setApiKey,
  } = useProviderConfig();

  // THE CLASS SEAM (2026-09-08, the A1 split): this page is the
  // CLOUD roof. The local daemons live on /providers/local (the
  // LocalProviders page). The filter tolerates a stale backend
  // (location absent) via the providerLocationOf fallback.
  const visibleProviders = providers.filter((p) => providerLocationOf(p) === 'cloud')

  // Default provider hook
  const {
    defaultProvider,
    loading: defaultLoading,
    refreshDefaultProvider,
    initializeDefaultProvider,
  } = useDefaultProvider();

  // Usage hook
  const {
    usage,
    usageByProvider: _usageByProvider,
    usageByModel,
    usageTrend,
    costBreakdown,
    loading: usageLoading,
    error: usageError,
    refreshUsage,
  } = useUsage({ period: 'monthly', trendDays: 30 });

  // Sync schedule state
  const [selectedProviderId, setSelectedProviderId] = useState<number | null>(null);
  const {
    schedule,
    syncStatus,
    loading: scheduleLoading,
    error: scheduleError,
    setSchedule,
    disableSchedule,
    runSync,
    getSyncStatus,
  } = useSyncSchedule(selectedProviderId || 0);

  // Modal state
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [modalMode, setModalMode] = useState<'add' | 'edit'>('add');
  const [editingProvider, setEditingProvider] = useState<ProviderConfig | null>(null);
  // THE URL IS THE TAB (see `readTab`): Curated opens the page, and any tab survives a reload.
  // `replace` on purpose — a tab is a view, not a navigation, so Back leaves the page rather than
  // walking back through the tabs visited.
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab: ProviderTab = readTab(searchParams.get('tab'));
  const setActiveTab = useCallback(
    (tab: ProviderTab) => {
      setSearchParams(
        prev => {
          const next = new URLSearchParams(prev);
          next.set('tab', tab);
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  // Default provider pending changes state
  const [pendingProvider, setPendingProvider] = useState<{
    providerId: number;
    providerName: string;
    providerType: string;
    model: string;
  } | null>(null);
  const [savingDefault, setSavingDefault] = useState(false);
  const [defaultError, setDefaultError] = useState<string | null>(null);

  // The provider whose Health modal is open. The check runs inside the modal (on open and on
  // demand), so the page holds the SELECTION only — not the result.
  const [healthProvider, setHealthProvider] = useState<ProviderConfig | null>(null);

  // Model browser modal state
  const [showModelBrowser, setShowModelBrowser] = useState(false);
  const [browseProviderId, setBrowseProviderId] = useState<number | null>(null);
  const [browseProviderName, setBrowseProviderName] = useState('');
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [modelsTotal, setModelsTotal] = useState(0);
  const [modelsTotalPages, setModelsTotalPages] = useState(0);
  const [modelsFromCache, setModelsFromCache] = useState(false);
  const [modelFilters, setModelFilters] = useState<ModelBrowserFilters>({
    page: 1,
    page_size: 50,
    sort_by: 'name',
    sort_order: 'asc',
  });

  /**
   * Handle add provider
   */
  const handleAddProvider = () => {
    setModalMode('add');
    setEditingProvider(null);
    setShowConfigModal(true);
  };

  /**
   * Handle edit provider
   */
  const handleEditProvider = (provider: ProviderConfig) => {
    setModalMode('edit');
    setEditingProvider(provider);
    setShowConfigModal(true);
  };

  /**
   * Handle save provider config
   */
  const handleSaveProvider = async (config: ProviderConfigCreate | ProviderConfigUpdate) => {
    if (modalMode === 'add') {
      await createProvider(config as ProviderConfigCreate);
    } else if (editingProvider) {
      await updateProvider(editingProvider.id, config as ProviderConfigUpdate);
    }
    setShowConfigModal(false);
  };

  /**
   * Handle cancel modal
   */
  const handleCancelModal = () => {
    setShowConfigModal(false);
    setEditingProvider(null);
  };

  /**
   * Handle provider select for sync scheduler
   */
  const handleProviderSelect = (providerId: number) => {
    setSelectedProviderId(providerId === selectedProviderId ? null : providerId);
  };

  /**
   * Handle period change
   */
  const handlePeriodChange = (_period: UsagePeriod) => {
    // Usage hook will automatically refresh when period changes
    refreshUsage();
  };

  // ─── Default Provider Handlers ───────────────────────────────────────

  /**
   * Handle default provider change (stores pending changes)
   */
  const handleDefaultProviderChange = (providerId: number, providerName: string, providerType: string) => {
    setPendingProvider({
      providerId,
      providerName,
      providerType,
      model: defaultProvider?.model_name || '',
    });
    setDefaultError(null);
  };

  /**
   * Handle default model change (stores pending changes)
   */
  const handleDefaultModelChange = (model: string) => {
    setPendingProvider(prev => {
      if (prev) {
        return { ...prev, model };
      }
      if (defaultProvider) {
        return {
          providerId: defaultProvider.provider_id,
          providerName: defaultProvider.provider_name,
          providerType: defaultProvider.provider_type,
          model,
        };
      }
      return null;
    });
    setDefaultError(null);
  };

  /**
   * Save pending default provider configuration
   */
  const handleSaveDefaultConfiguration = async () => {
    if (!pendingProvider) {
      setDefaultError('No changes to save');
      return;
    }

    if (!pendingProvider.providerId) {
      setDefaultError('No provider selected. Please select a provider from the dropdown.');
      return;
    }

    if (!pendingProvider.model) {
      setDefaultError('No model selected. Please select a model from the dropdown.');
      return;
    }

    setSavingDefault(true);
    setDefaultError(null);

    try {
      frontendLoggingService.info(
        'ProviderDashboard',
        'Saving default provider configuration',
        { pendingProvider, defaultProvider }
      );

      const requestBody = {
        provider_id: pendingProvider.providerId,
        model: pendingProvider.model,
      };

      const response = await fetch('/api/v1/providers/default', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(errorData.detail || 'Failed to save configuration');
      }

      await response.json();

      // Refresh to get updated state
      await refreshDefaultProvider();

      const { addSuccess } = useNotificationStore.getState();
      addSuccess('Default Provider Updated', `${pendingProvider.providerName} / ${pendingProvider.model} is now the default`);

      setPendingProvider(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to save configuration';
      setDefaultError(errorMessage);

      frontendLoggingService.error(
        'ProviderDashboard',
        `Failed to save default provider configuration: ${errorMessage}`,
        err instanceof Error ? err : undefined
      );

      const { addError } = useNotificationStore.getState();
      addError('Failed to Save', errorMessage);
    } finally {
      setSavingDefault(false);
    }
  };

  /**
   * Handle initialize default provider
   */
  const handleInitializeDefaultProvider = async () => {
    const success = await initializeDefaultProvider();
    if (success) {
      _refreshProviders();
    }
  };

  // ─── Model Browser Handlers ──────────────────────────────────────────

  /**
   * Open model browser for a specific provider
   */
  const handleOpenModelBrowser = (provider: ProviderConfig) => {
    setBrowseProviderId(provider.id);
    setBrowseProviderName(provider.display_name || provider.name);
    setModelFilters({ page: 1, page_size: 50, sort_by: 'name', sort_order: 'asc' });
    setModels([]);
    setModelsError(null);
    setShowModelBrowser(true);
  };

  /**
   * Close model browser modal
   */
  const handleCloseModelBrowser = () => {
    setShowModelBrowser(false);
    setBrowseProviderId(null);
    setBrowseProviderName('');
  };

  /**
   * Load models for the model browser
   */
  const loadModels = useCallback(async () => {
    if (!browseProviderId) return;

    setModelsLoading(true);
    setModelsError(null);

    try {
      const response = await modelBrowserService.browseModels(browseProviderId, modelFilters);

      if (response.data) {
        setModels(response.data.models);
        setModelsTotal(response.data.total);
        setModelsTotalPages(response.data.total_pages);
        setModelsFromCache(response.data.from_cache);
      } else if (response.error) {
        setModelsError(response.error.message || 'Failed to load models');
      }
    } catch (err) {
      setModelsError(err instanceof Error ? err.message : 'Failed to load models');
    } finally {
      setModelsLoading(false);
    }
  }, [browseProviderId, modelFilters]);

  // Load models when browser modal opens or filters change
  useEffect(() => {
    if (showModelBrowser && browseProviderId) {
      loadModels();
    }
  }, [showModelBrowser, browseProviderId, loadModels]);

  /**
   * Handle model filter changes in browser
   */
  const handleModelFilterChange = (newFilters: Partial<ModelBrowserFilters>) => {
    const updated = { ...modelFilters, ...newFilters };
    if (newFilters.search !== undefined || newFilters.free_only !== undefined) {
      updated.page = 1;
    }
    setModelFilters(updated);
  };

  /**
   * Handle model page change
   */
  const handleModelPageChange = (page: number) => {
    handleModelFilterChange({ page });
  };

  /**
   * Handle model page size change
   */
  const handleModelPageSizeChange = (pageSize: number) => {
    handleModelFilterChange({ page_size: pageSize, page: 1 });
  };

  /**
   * Handle model selection in browser
   */
  const handleSelectModel = (model: ModelInfo) => {
    frontendLoggingService.info('ProviderDashboard', 'Model selected from browser', {
      modelId: model.id,
      modelName: model.name,
      providerId: browseProviderId,
    });

    // Store selection in sessionStorage for cross-page use
    const selection = {
      modelId: model.id,
      modelName: model.name,
      providerId: browseProviderId,
      providerName: browseProviderName,
      timestamp: Date.now(),
    };
    sessionStorage.setItem('selectedModel', JSON.stringify(selection));

    handleCloseModelBrowser();
  };

  return (
    <PageContainer maxWidth="7xl">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-base-content">
              Cloud Providers
            </h1>
            <p className="text-readout mt-1">
              Configure providers, monitor usage, and manage synchronization
            </p>
            <p className="text-readout mt-1 text-sm">
              Which service each capability uses, and its fallbacks — see{' '}
              <Link to="/providers/capabilities" className="link link-primary">
                Capabilities
              </Link>
              .
            </p>
          </div>
          <div className="flex items-center gap-2">
            <HelpButton
              context={HELP_CONTEXT[activeTab]}
              size="sm"
              tooltipPosition="left"
            />
            <Tooltip content="Add a new LLM provider (Ollama, OpenAI, Anthropic, etc.)" position="left">
              <button
                onClick={handleAddProvider}
                className="px-4 py-2 text-base-content bg-primary rounded-lg hover:bg-primary-focus flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Add Provider
              </button>
            </Tooltip>
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {(providersError || usageError || scheduleError) && (
        <PageBanner title="Error" className="mb-4">
          {providersError || usageError || scheduleError}
        </PageBanner>
      )}

      {/* Tabs */}
      <div className="mb-6 border-b border-base-content/20">
        <nav className="-mb-px flex gap-4">
          <Tooltip content="Manage the human-owned curated model list" position="bottom">
            <button
              onClick={() => setActiveTab('curated')}
              className={`pb-3 px-1 font-medium text-sm transition-colors ${
                activeTab === 'curated'
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-base-content/60 hover:text-base-content'
              }`}
            >
              Curated
            </button>
          </Tooltip>
          <Tooltip content="View and manage your configured providers" position="bottom">
            <button
              onClick={() => setActiveTab('overview')}
              className={`pb-3 px-1 font-medium text-sm transition-colors ${
                activeTab === 'overview'
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-base-content/60 hover:text-base-content'
              }`}
            >
              Overview
            </button>
          </Tooltip>
          <Tooltip content="Set the provider and model used where nothing else chooses one" position="bottom">
            <button
              onClick={() => setActiveTab('default')}
              className={`pb-3 px-1 font-medium text-sm transition-colors ${
                activeTab === 'default'
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-base-content/60 hover:text-base-content'
              }`}
            >
              Default
            </button>
          </Tooltip>
          <Tooltip content="View usage statistics, token consumption, and cost breakdown" position="bottom">
            <button
              onClick={() => setActiveTab('usage')}
              className={`pb-3 px-1 font-medium text-sm transition-colors ${
                activeTab === 'usage'
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-base-content/60 hover:text-base-content'
              }`}
            >
              Usage
            </button>
          </Tooltip>
          <Tooltip content="See and manage provider API keys (set, rotate, clear)" position="bottom">
            <button
              onClick={() => setActiveTab('keys')}
              className={`pb-3 px-1 font-medium text-sm transition-colors ${
                activeTab === 'keys'
                  ? 'border-b-2 border-primary text-primary'
                  : 'text-base-content/60 hover:text-base-content'
              }`}
            >
              Keys
            </button>
          </Tooltip>
        </nav>
      </div>

      {/* Default Provider Tab */}
      {activeTab === 'default' && (
        <div className="space-y-6">
          {/* ── Default Provider Configuration ─────────────────────────── */}
          <div className="bg-base-200 rounded-lg shadow p-4 border border-base-content/20">
            {defaultLoading ? (
              <div className="flex items-center gap-2 text-sm text-readout">
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Loading default provider...
              </div>
            ) : defaultProvider ? (
              <>
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <svg className="h-6 w-6 text-success" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    <div>
                      <h3 className="text-lg font-semibold text-base-content">Default Provider</h3>
                    </div>
                  </div>
                  <div className="badge badge-success badge-outline badge-sm">Active</div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-base-content/10">
                  <DefaultProviderConfig
                    currentProviderId={defaultProvider.provider_id}
                    currentProviderName={defaultProvider.provider_name}
                    currentProviderType={defaultProvider.provider_type}
                    currentModel={defaultProvider.model_name}
                    onProviderChange={handleDefaultProviderChange}
                    onModelChange={handleDefaultModelChange}
                  />
                </div>

                {/* Save Button */}
                <div className="mt-4 flex items-center justify-between">
                  {pendingProvider ? (
                    <div className="flex items-center gap-2 text-sm text-info">
                      <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2V3a1 1 0 00-1-1H8a1 1 0 00-1 1v8a1 1 0 102 0z" clipRule="evenodd" />
                      </svg>
                      <span>
                        Changes pending: <strong>{pendingProvider.providerName}</strong> / <strong>{pendingProvider.model || 'Select a model'}</strong>
                      </span>
                    </div>
                  ) : (
                    <div className="text-sm text-readout">
                      ✓ Configuration is up to date
                    </div>
                  )}

                  <div className="tooltip tooltip-left" data-tip={pendingProvider ? "Save your provider and model selection as the new default" : "No changes to save"}>
                    <button
                      onClick={handleSaveDefaultConfiguration}
                      disabled={savingDefault || !pendingProvider || !pendingProvider.model}
                      className={`btn btn-sm ${pendingProvider && pendingProvider.model ? 'btn-primary' : 'btn-disabled'}`}
                    >
                      {savingDefault ? (
                        <>
                          <span className="loading loading-spinner loading-sm"></span>
                          Saving...
                        </>
                      ) : (
                        <>
                          <svg className="h-4 w-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                          Save Configuration
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {defaultError && (
                  <div className="mt-3 p-2 bg-error/10 border border-error/20 rounded text-xs text-error">
                    ⚠️ {defaultError}
                  </div>
                )}
              </>
            ) : (
              <div className="space-y-4">
                <div className="alert alert-warning">
                  <svg className="h-6 w-6 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <div>
                    <h3 className="font-semibold">No Default Provider Configured</h3>
                    <p className="text-sm">
                      Pick the provider and model that answer chat. Title, summary, workflow and
                      memory all inherit it.
                    </p>
                  </div>
                </div>

                {providers.length === 0 ? (
                  // THE EMPTY DOOR (2026-11-21): a default needs a provider to point at, and a fresh
                  // install has none — so the page asks for the thing it is missing instead of
                  // offering a choice among zero options.
                  <div className="bg-base-200 rounded-lg border border-base-300 p-4 space-y-3">
                    <p className="text-sm text-readout">
                      No provider on this install yet, and a default provider is a choice among
                      providers. Add one first — it carries its own key.
                    </p>
                    <button
                      onClick={handleAddProvider}
                      className="btn btn-primary btn-sm rounded-[var(--button-radius)]"
                      data-tip="Open the add-provider form; the key rides the same form"
                    >
                      Add your first provider
                    </button>
                  </div>
                ) : (
                  <div className="bg-base-200 rounded-lg border border-base-300 p-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <DefaultProviderConfig
                        onProviderChange={handleDefaultProviderChange}
                        onModelChange={handleDefaultModelChange}
                      />
                    </div>
                    <div className="mt-4 flex items-center justify-between">
                      {pendingProvider ? (
                        <div className="text-sm text-info">
                          Pending: <strong>{pendingProvider.providerName}</strong> /{' '}
                          <strong>{pendingProvider.model || 'Select a model'}</strong>
                        </div>
                      ) : (
                        <div className="text-sm text-readout">Choose a provider and a model, then save.</div>
                      )}
                      <div className="tooltip tooltip-left" data-tip={pendingProvider?.model ? 'Make this the default provider and model' : 'Choose a model first'}>
                        <button
                          onClick={handleSaveDefaultConfiguration}
                          disabled={savingDefault || !pendingProvider?.model}
                          className={`btn btn-sm ${pendingProvider?.model ? 'btn-primary' : 'btn-disabled'}`}
                        >
                          {savingDefault ? 'Saving...' : 'Set as Default'}
                        </button>
                      </div>
                    </div>
                    {defaultError && (
                      <div className="mt-3 p-2 bg-error/10 border border-error/20 rounded text-xs text-error">
                        ⚠️ {defaultError}
                      </div>
                    )}
                  </div>
                )}

                {/* The one-click path stays, but only where it can WORK: it points the install at a
                    local Ollama, which is meaningless on a box that has no ollama row. */}
                {providers.some((p) => p.provider_type === 'ollama') && (
                  <div className="text-xs text-readout">
                    Or{' '}
                    <button onClick={handleInitializeDefaultProvider} className="link link-primary">
                      initialize the default from the local Ollama server
                    </button>
                    .
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="space-y-6">

          {/* ── Provider Cards ─────────────────────────────────────────── */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {visibleProviders.map((provider) => (
              <div
                key={provider.id}
                className="bg-base-200 rounded-lg shadow p-4 border border-base-content/20"
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-medium text-base-content">
                      {provider.display_name || provider.name}
                    </h3>
                    <p className="text-sm text-readout">
                      {provider.provider_type}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {provider.is_active ? (
                      <span className="px-2 py-1 text-xs font-medium bg-success/20 text-success rounded-full">
                        Active
                      </span>
                    ) : (
                      <span className="px-2 py-1 text-xs font-medium bg-base-300 text-base-content rounded-full">
                        Inactive
                      </span>
                    )}
                    {provider.has_api_key && (
                      <span className="px-2 py-1 text-xs font-medium bg-primary/20 text-primary rounded-full">
                        API Key
                      </span>
                    )}
                  </div>
                </div>

                <div className="text-sm text-readout mb-3">
                  {provider.base_url && (
                    <p className="truncate">{provider.base_url}</p>
                  )}
                </div>

                {/* Actions */}
                <div className="flex gap-2 pt-3 border-t border-base-content/20">
                  <Tooltip content="Edit provider settings, API key, and configuration" position="top">
                    <button
                      onClick={() => handleEditProvider(provider)}
                      className="flex-1 px-3 py-1.5 text-sm text-primary hover:bg-primary/10 rounded"
                    >
                      Edit
                    </button>
                  </Tooltip>
                  <Tooltip content="Check connectivity, latency and the models this provider serves" position="top">
                    <button
                      onClick={() => setHealthProvider(provider)}
                      className="flex-1 px-3 py-1.5 text-sm text-readout hover:bg-base-content/10 rounded"
                    >
                      Health
                    </button>
                  </Tooltip>
                  <Tooltip content="Browse and select models from this provider" position="top">
                    <button
                      onClick={() => handleOpenModelBrowser(provider)}
                      className="flex-1 px-3 py-1.5 text-sm text-readout hover:bg-base-content/10 rounded"
                    >
                      Models
                    </button>
                  </Tooltip>
                </div>

                {/* Sync Scheduler */}
                <div className="mt-4 pt-4 border-t border-base-content/20">
                  <Tooltip content="Configure automatic model synchronization schedule" position="top">
                    <button
                      onClick={() => handleProviderSelect(provider.id)}
                      className="text-sm text-primary hover:underline w-full text-center block"
                    >
                      {selectedProviderId === provider.id ? 'Hide Sync Settings' : 'Sync Settings'}
                    </button>
                  </Tooltip>
                </div>

                {/* Sync Scheduler Panel */}
                {selectedProviderId === provider.id && (
                  <div className="mt-4">
                    <ModelSyncScheduler
                      providerId={provider.id}
                      providerName={provider.name}
                      schedule={schedule}
                      syncStatus={syncStatus}
                      onSetSchedule={setSchedule}
                      onDisableSchedule={disableSchedule}
                      onRunSync={runSync}
                      onRefreshStatus={getSyncStatus}
                      loading={scheduleLoading}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>

          {visibleProviders.length === 0 && !providersLoading && (
            <div className="text-center py-12">
              <p className="text-readout mb-4">
                No cloud providers configured yet
              </p>
              <button
                onClick={handleAddProvider}
                className="text-primary hover:underline"
              >
                Add your first cloud provider
              </button>
            </div>
          )}

          {providersLoading && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          )}
        </div>
      )}

      {/* Usage Tab */}
      {activeTab === 'usage' && (
        <UsageDashboard
          usage={usage}
          usageByModel={usageByModel}
          usageTrend={usageTrend}
          costBreakdown={costBreakdown}
          loading={usageLoading}
          onPeriodChange={handlePeriodChange}
        />
      )}

      {/* Curated Tab — in-app curated list management (Phase 3) */}
      {activeTab === 'curated' && (
        <CuratedModelsManager
          providers={visibleProviders}
          loading={providersLoading}
        />
      )}

      {/* Keys Tab — provider API key management (Phase 4) */}
      {activeTab === 'keys' && (
        <ProviderKeyManager location="cloud" />
      )}

      {/* Config Modal */}
      {showConfigModal && (
        <ProviderConfigModal
          provider={editingProvider}
          mode={modalMode}
          onSave={handleSaveProvider}
          onCancel={handleCancelModal}
          loading={providersLoading}
          location="cloud"
        />
      )}

      {/* ── Provider Health Modal ──────────────────────────────────────── */}
      {healthProvider && (
        <ProviderHealthModal
          provider={healthProvider}
          onClose={() => setHealthProvider(null)}
        />
      )}

      {/* ── Model Browser Modal — the house shell (Escape, focus, top layer) ── */}
      {showModelBrowser && browseProviderId && (
        <ProviderModal
          onClose={handleCloseModelBrowser}
          label={`Browse models — ${browseProviderName}`}
        >
          {/* The shell's panel carries `--dialog-width-xl` (a model table is a data-heavy panel)
              and its own `p-6`, so this content is unwrapped. No `max-w-*` anywhere: it resolves
              to `none` here, which is how this panel used to be wide by luck, not by design. */}
          {/* Header */}
          <div className="flex items-center justify-between mb-4 pb-4 border-b border-base-300">
            <div>
              <h3 className="text-xl font-semibold text-base-content">
                Browse Models — {browseProviderName}
              </h3>
              <p className="text-sm text-readout mt-1">
                {modelsTotal.toLocaleString()} models available
                {modelsFromCache && (
                  <span className="ml-2 text-xs text-info">• From cache</span>
                )}
              </p>
            </div>
            <div className="flex items-center space-x-3">
              <button
                onClick={loadModels}
                disabled={modelsLoading}
                className="btn btn-sm btn-primary rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
              >
                <svg className={`w-4 h-4 mr-2 ${modelsLoading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Refresh
              </button>
              <button
                onClick={handleCloseModelBrowser}
                className="btn btn-sm btn-ghost btn-circle transition-all duration-[var(--button-transition)]"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Filters */}
          <div className="mb-6">
            <ModelFilters
              filters={modelFilters}
              onFilterChange={handleModelFilterChange}
              providerId={browseProviderId}
            />
          </div>

          {/* Error Display */}
          {modelsError && (
            <div className="mb-6 alert alert-error">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              <span>{modelsError}</span>
            </div>
          )}

          {/* Models Table */}
          <ModelTable
            models={models}
            loading={modelsLoading}
            error={modelsError}
            currentPage={modelFilters.page || 1}
            totalPages={modelsTotalPages}
            pageSize={modelFilters.page_size || 50}
            totalItems={modelsTotal}
            onPageChange={handleModelPageChange}
            onPageSizeChange={handleModelPageSizeChange}
            onSelectModel={handleSelectModel}
          />
        </ProviderModal>
      )}
    </PageContainer>
  );
};

export default ProviderDashboard;
