/**
 * useDefaultProvider Hook
 *
 * Hook for managing the system-wide default LLM provider.
 * Provides functionality to get, set, and initialize the default provider.
 */

import { useState, useEffect, useCallback } from 'react';
import { defaultProviderService } from '../services/domains/providers/defaultProviderService';
import type {
  DefaultProviderResponse,
} from '../types/providers/default';

/**
 * Hook return type
 */
interface UseDefaultProviderReturn {
  defaultProvider: DefaultProviderResponse | null;
  loading: boolean;
  error: string | null;
  refreshDefaultProvider: () => Promise<void>;
  setDefaultProvider: (providerId: number, model?: string) => Promise<boolean>;
  initializeDefaultProvider: () => Promise<boolean>;
}

/**
 * Hook for default provider management
 */
export const useDefaultProvider = (): UseDefaultProviderReturn => {
  const [defaultProvider, setDefaultProvider] = useState<DefaultProviderResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Load the current default provider
   */
  const loadDefaultProvider = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await defaultProviderService.getDefaultProvider();
      if (response.data) {
        setDefaultProvider(response.data);
      } else if (response.error) {
        // 404 means no default configured, which is OK
        if (response.error.message.includes('404')) {
          setDefaultProvider(null);
        } else {
          setError(response.error.message);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load default provider');
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Set a provider as the default
   */
  const handleSetDefaultProvider = useCallback(
    async (providerId: number, model?: string): Promise<boolean> => {
    setLoading(true);
    setError(null);

    try {
      const response = await defaultProviderService.setDefaultProvider(providerId, model);
      if (response.data) {
        setDefaultProvider(response.data);
        return true;
      } else if (response.error) {
        setError(response.error.message);
        return false;
      }
      return false;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set default provider');
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Initialize default provider if none exists
   */
  const handleInitializeDefaultProvider = useCallback(async (): Promise<boolean> => {
    setLoading(true);
    setError(null);

    try {
      const response = await defaultProviderService.initializeDefaultProvider();
      if (response.data && response.data.status === 'success') {
        if (response.data.provider_id) {
          // Reload to get full details
          await loadDefaultProvider();
        }
        return true;
      } else if (response.error) {
        setError(response.error.message);
        return false;
      }
      return false;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to initialize default provider');
      return false;
    } finally {
      setLoading(false);
    }
  }, [loadDefaultProvider]);

  /**
   * Load default provider on mount
   */
  useEffect(() => {
    loadDefaultProvider();
  }, [loadDefaultProvider]);

  return {
    defaultProvider,
    loading,
    error,
    refreshDefaultProvider: loadDefaultProvider,
    setDefaultProvider: handleSetDefaultProvider,
    initializeDefaultProvider: handleInitializeDefaultProvider,
  };
};
