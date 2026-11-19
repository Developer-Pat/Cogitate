/**
 * useLocalStorage Hook
 *
 * Hook for managing local storage operations with type safety and error handling
 */

import { useState, useEffect, useCallback } from 'react';
import { frontendLoggingService } from '../services/frontendLoggingService';
import type { UseLocalStorageReturn } from '../types/settings';

/**
 * Hook for local storage operations
 */
export const useLocalStorage = <T>(
  key: string,
  defaultValue: T
): UseLocalStorageReturn<T> => {
  const [value, setValue] = useState<T>(defaultValue);
  const [loading, setLoading] = useState<boolean>(true);

  /**
   * Get value from local storage
   */
  const getStoredValue = useCallback((): T => {
    try {
      const item = window.localStorage.getItem(key);
      if (item) {
        return JSON.parse(item);
      }
      return defaultValue;
    } catch (error) {
      frontendLoggingService.error('useLocalStorage', `Error reading localStorage key "${key}"`, error as Error);
      return defaultValue;
    }
  }, [key, defaultValue]);

  /**
   * Set value in local storage
   */
  const setStoredValue = useCallback((newValue: T) => {
    try {
      window.localStorage.setItem(key, JSON.stringify(newValue));
      setValue(newValue);

      // Dispatch storage event for cross-tab synchronization
      window.dispatchEvent(new StorageEvent('storage', {
        key,
        newValue: JSON.stringify(newValue),
        storageArea: window.localStorage
      }));
    } catch (error) {
      frontendLoggingService.error('useLocalStorage', `Error setting localStorage key "${key}"`, error as Error);
    }
  }, [key]);

  /**
   * Remove value from local storage
   */
  const removeStoredValue = useCallback(() => {
    try {
      window.localStorage.removeItem(key);
      setValue(defaultValue);

      // Dispatch storage event for cross-tab synchronization
      window.dispatchEvent(new StorageEvent('storage', {
        key,
        newValue: null,
        storageArea: window.localStorage
      }));
    } catch (error) {
      frontendLoggingService.error('useLocalStorage', `Error removing localStorage key "${key}"`, error as Error);
    }
  }, [key, defaultValue]);

  /**
   * Initialize value from local storage
   */
  useEffect(() => {
    const storedValue = getStoredValue();
    setValue(storedValue);
    setLoading(false);
  }, [getStoredValue]);

  /**
   * Listen for storage changes from other tabs
   */
  useEffect(() => {
    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === key && event.storageArea === window.localStorage) {
        try {
          if (event.newValue === null) {
            setValue(defaultValue);
          } else {
            setValue(JSON.parse(event.newValue));
          }
        } catch (error) {
          frontendLoggingService.error('useLocalStorage', `Error parsing storage change for key "${key}"`, error as Error);
        }
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [key, defaultValue]);

  return {
    value,
    setValue: setStoredValue,
    removeValue: removeStoredValue,
    loading,
  };
};

export default useLocalStorage;