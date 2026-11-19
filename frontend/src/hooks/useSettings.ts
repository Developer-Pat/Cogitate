/**
 * useSettings Hook
 *
 * Hook for managing application settings with persistence and validation
 */

import { useState, useCallback, useMemo } from 'react';
import { z } from 'zod';
import useLocalStorage from './useLocalStorage';
import { frontendLoggingService } from '../services/frontendLoggingService';
import type {
  Settings,
  UseSettingsReturn,
  SettingsExport
} from '../types/settings';
import {
  defaultSettings,
  SettingsSchema,
  SETTINGS_STORAGE_KEY
} from '../types/settings';

/**
 * Hook for settings management
 */
export const useSettings = (): UseSettingsReturn => {
  const {
    value: storedSettings,
    setValue: setStoredSettings,
    loading: storageLoading,
  } = useLocalStorage<Settings>(SETTINGS_STORAGE_KEY, defaultSettings);

  const [error, setError] = useState<string | null>(null);

  /**
   * Validate settings against schema
   */
  const validateSettings = useCallback((settings: Settings): boolean => {
    try {
      SettingsSchema.parse(settings);
      return true;
    } catch (validationError) {
      if (validationError instanceof z.ZodError) {
        frontendLoggingService.error('useSettings', 'Settings validation error', validationError, { issues: validationError.issues });
        setError(`Invalid settings format: ${validationError.issues[0]?.message}`);
      } else {
        frontendLoggingService.error('useSettings', 'Settings validation error', validationError);
        setError('Invalid settings format');
      }
      return false;
    }
  }, []);

  /**
   * Update settings with validation
   */
  const updateSettings = useCallback((updates: Partial<Settings>) => {
    try {
      const currentSettings = storedSettings;
      const newSettings: Settings = {
        ...currentSettings,
        ...updates,
        lastUpdated: new Date().toISOString(),
      };

      if (validateSettings(newSettings)) {
        setStoredSettings(newSettings);
        setError(null);
      }
    } catch (error) {
      frontendLoggingService.error('useSettings', 'Error updating settings', error);
      setError('Failed to update settings');
    }
  }, [storedSettings, setStoredSettings, validateSettings]);

  /**
   * Reset settings to defaults
   */
  const resetSettings = useCallback(() => {
    try {
      const resetSettings: Settings = {
        ...defaultSettings,
        lastUpdated: new Date().toISOString(),
      };
      setStoredSettings(resetSettings);
      setError(null);
    } catch (error) {
      frontendLoggingService.error('useSettings', 'Error resetting settings', error);
      setError('Failed to reset settings');
    }
  }, [setStoredSettings]);

  /**
   * Export settings as JSON string
   */
  const exportSettings = useCallback((): string => {
    try {
      const exportData: SettingsExport = {
        settings: storedSettings,
        exportedAt: new Date().toISOString(),
        version: '1.0.0',
      };
      return JSON.stringify(exportData, null, 2);
    } catch (error) {
      frontendLoggingService.error('useSettings', 'Error exporting settings', error);
      setError('Failed to export settings');
      return '';
    }
  }, [storedSettings]);

  /**
   * Import settings from JSON string
   */
  const importSettings = useCallback((settingsData: string): boolean => {
    try {
      const importData = JSON.parse(settingsData) as SettingsExport;

      // Validate imported settings
      if (!importData.settings || !validateSettings(importData.settings)) {
        setError('Invalid settings format in import data');
        return false;
      }

      const importedSettings: Settings = {
        ...importData.settings,
        lastUpdated: new Date().toISOString(),
      };

      setStoredSettings(importedSettings);
      setError(null);
      return true;
    } catch (error) {
      frontendLoggingService.error('useSettings', 'Error importing settings', error);
      setError('Failed to import settings - invalid format');
      return false;
    }
  }, [setStoredSettings, validateSettings]);

  /**
   * Settings with validation
   */
  const settings = useMemo(() => {
    if (!validateSettings(storedSettings)) {
      // If settings are invalid, reset to defaults
      const resetSettings: Settings = {
        ...defaultSettings,
        lastUpdated: new Date().toISOString(),
      };
      setStoredSettings(resetSettings);
      return resetSettings;
    }
    return storedSettings;
  }, [storedSettings, validateSettings, setStoredSettings]);

  return {
    settings,
    updateSettings,
    resetSettings,
    exportSettings,
    importSettings,
    loading: storageLoading,
    error,
  };
};

export default useSettings;