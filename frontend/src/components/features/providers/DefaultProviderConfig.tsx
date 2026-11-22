/**
 * DefaultProviderConfig Component
 *
 * Simple provider and model selector for default provider configuration.
 * Similar to Agent Profiles page - select provider and model from dropdowns.
 */

import React, { useState, useEffect } from 'react';
import { apiClient } from '@/services/apiClient';

interface DefaultProviderConfigProps {
  currentProviderId?: number;
  currentProviderName?: string;
  currentProviderType?: string;
  currentModel?: string;
  onProviderChange: (providerId: number, providerName: string, providerType: string) => void;
  onModelChange: (model: string) => void;
  className?: string;
}

interface ProviderInfo {
  id: number;
  name: string;
  provider_type: string;
  is_active: boolean;
  is_default: boolean;
}

interface ModelInfo {
  name: string;
  display_name?: string;
}

/**
 * DefaultProviderConfig Component
 */
export const DefaultProviderConfig: React.FC<DefaultProviderConfigProps> = ({
  currentProviderId,
  currentProviderName = '',
  currentProviderType: _currentProviderType = '',
  currentModel = '',
  onProviderChange,
  onModelChange,
  className = '',
}) => {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [loadingModels, setLoadingModels] = useState(false);
  const [selectedProviderId, setSelectedProviderId] = useState<number>(currentProviderId ?? 0);
  const [selectedModel, setSelectedModel] = useState<string>(currentModel);
  const [modelSearch, setModelSearch] = useState('');
  const [, setSelectedProviderName] = useState<string>(currentProviderName);

  // Load providers on mount
  useEffect(() => {
    loadProviders();
  }, []);

  // Sync internal state with props when they change
  useEffect(() => {
    setSelectedProviderId(currentProviderId ?? 0);
    setSelectedProviderName(currentProviderName);
    setSelectedModel(currentModel);
  }, [currentProviderId, currentProviderName, currentModel]);

  // THE FIRST PROVIDER IS THE DEFAULT SELECTION (2026-11-21). This component is also the way a
  // fresh install CHOSES its default, and there is no `currentProviderId` then — the selects
  // used to seed themselves with `1` and `llama3.2:latest`, guesses about a machine nobody had
  // looked at. Now an unset selection takes the install's first real provider.
  useEffect(() => {
    if (loadingProviders || providers.length === 0) return
    if (providers.some((p) => p.id === selectedProviderId)) return
    const first = providers[0]
    setSelectedProviderId(first.id)
    setSelectedProviderName(first.name)
    onProviderChange(first.id, first.name, first.provider_type)
  }, [providers, loadingProviders, selectedProviderId, onProviderChange]);

  // Load models when provider changes
  useEffect(() => {
    if (selectedProviderId) {
      loadModels(selectedProviderId);
    }
  }, [selectedProviderId]);

  /**
   * Load available providers
   */
  const loadProviders = async () => {
    setLoadingProviders(true);
    try {
      const response = await apiClient.get<unknown>('/api/v1/providers/managed');
      const data = response.data as { providers?: ProviderInfo[] } | undefined;
      if (data && data.providers) {
        setProviders(data.providers);
      }
    } catch (err) {
      console.error('[DefaultProviderConfig] Failed to load providers:', err);
    } finally {
      setLoadingProviders(false);
    }
  };

  /**
   * Load models for a specific provider
   */
  const loadModels = async (providerId: number) => {
    setLoadingModels(true);
    try {
      const response = await apiClient.get<unknown>(`/api/v1/providers/managed/${providerId}/models`);
      const data = response.data as { models?: ModelInfo[] } | undefined;
      if (data && data.models) {
        setModels(data.models);
      }
    } catch (err) {
      console.error('[DefaultProviderConfig] Failed to load models:', err);
      setModels([]);
    } finally {
      setLoadingModels(false);
    }
  };

  /**
   * Handle provider selection
   */
  const handleProviderChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const providerId = parseInt(e.target.value);
    const provider = providers.find(p => p.id === providerId);
    
    if (provider) {
      setSelectedProviderId(providerId);
      setSelectedProviderName(provider.name);
      setSelectedModel(''); // Reset model when provider changes
      setModelSearch('');
      onProviderChange(providerId, provider.name, provider.provider_type);
    }
  };

  /**
   * Handle model selection
   */
  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const model = e.target.value;
    setSelectedModel(model);
    onModelChange(model);
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Provider Selection */}
      <div className="form-control">
        <label className="label">
          <span className="label-text font-semibold">Provider</span>
        </label>
        <select
          className="select select-bordered w-full"
          value={selectedProviderId}
          onChange={handleProviderChange}
          disabled={loadingProviders}
        >
          {loadingProviders ? (
            <option>Loading providers...</option>
          ) : (
            providers.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.name}
                {provider.provider_type !== provider.name && ` (${provider.provider_type})`}
                {provider.is_default && ' • Current Default'}
              </option>
            ))
          )}
        </select>
      </div>

      {/* Model Selection — searchable; curated list first, then full catalog */}
      <div className="form-control">
        <label className="label">
          <span className="label-text font-semibold">Model</span>
        </label>
        {loadingModels ? (
          <select className="select select-bordered w-full" disabled>
            <option>Loading models...</option>
          </select>
        ) : models.length === 0 ? (
          <select className="select select-bordered w-full" disabled>
            <option value={currentModel}>{currentModel || 'No models available'}</option>
          </select>
        ) : (
          <div className="space-y-2">
            <input
              type="text"
              value={modelSearch}
              onChange={(e) => setModelSearch(e.target.value)}
              placeholder={`Search ${models.length} models...`}
              className="input input-bordered input-sm w-full"
            />
            <select
              className="select select-bordered w-full"
              value={selectedModel}
              onChange={handleModelChange}
            >
              <option value="">Select a model...</option>
              {/* THE STORED VALUE MUST BE AN OPTION. An install's default can be a model its
                  provider's catalogue no longer lists (measured: `deepseek-v4-flash` against a list
                  carrying `deepseek-flash`), and a select with no matching option renders BLANK — so
                  the first Save would silently replace a working model string with whatever the
                  reader then picked. Always offer the current value, and say it is current. */}
              {currentModel && !models.some((m) => m.name === currentModel) && (
                <option value={currentModel}>{currentModel} (current)</option>
              )}
              {models
                .filter((model) => {
                  const q = modelSearch.trim().toLowerCase()
                  if (!q) return true
                  return (
                    (model.name || '').toLowerCase().includes(q) ||
                    (model.display_name || '').toLowerCase().includes(q)
                  )
                })
                .map((model) => (
                  <option key={model.name} value={model.name}>
                    {model.display_name || model.name}
                  </option>
                ))}
            </select>
          </div>
        )}
      </div>
    </div>
  );
};
