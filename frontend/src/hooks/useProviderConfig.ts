/**
 * useProviderConfig Hook - Phase 4
 *
 * Hook for managing provider configurations.
 * Provides state management for CRUD operations on providers.
 */

import { useState, useEffect, useCallback } from 'react';
import { providerConfigService } from '../services/domains/providers/providerConfigService';
import type {
  ProviderConfig,
  ProviderConfigCreate,
  ProviderConfigUpdate,
  ProviderTestResponse,
  UseProviderConfigReturn,
} from '../types/providers';

/**
 * Hook for provider configuration management
 */
export const useProviderConfig = (): UseProviderConfigReturn => {
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Load providers from the API
   */
  const loadProviders = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await providerConfigService.getProviders();
      setProviders(response.providers);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load providers');
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Create a new provider
   */
  const createProvider = useCallback(
    async (config: ProviderConfigCreate) => {
      setLoading(true);
      setError(null);

      try {
        await providerConfigService.createProvider(config);
        await loadProviders(); // Refresh the list
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to create provider');
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [loadProviders]
  );

  /**
   * Update an existing provider
   */
  const updateProvider = useCallback(
    async (id: number, config: ProviderConfigUpdate) => {
      setLoading(true);
      setError(null);

      try {
        await providerConfigService.updateProvider(id, config);
        await loadProviders(); // Refresh the list
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update provider');
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [loadProviders]
  );

  /**
   * Delete a provider
   */
  const deleteProvider = useCallback(
    async (id: number) => {
      setLoading(true);
      setError(null);

      try {
        await providerConfigService.deleteProvider(id);
        await loadProviders(); // Refresh the list
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to delete provider');
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [loadProviders]
  );

  /**
   * Set API key for a provider
   */
  const setApiKey = useCallback(
    async (id: number, apiKey: string) => {
      setLoading(true);
      setError(null);

      try {
        await providerConfigService.setApiKey(id, apiKey);
        await loadProviders(); // Refresh the list
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to set API key');
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [loadProviders]
  );

  /**
   * Test provider connection
   */
  const testProvider = useCallback(
    async (id: number): Promise<ProviderTestResponse | null> => {
      setError(null);

      try {
        const result = await providerConfigService.testProvider(id);
        return result;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to test provider');
        return null;
      }
    },
    []
  );

  /**
   * Refresh providers
   */
  const refreshProviders = useCallback(async () => {
    await loadProviders();
  }, [loadProviders]);

  // Load providers on mount
  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  return {
    providers,
    loading,
    error,
    refreshProviders,
    createProvider,
    updateProvider,
    deleteProvider,
    setApiKey,
    testProvider,
  };
};

export default useProviderConfig;
