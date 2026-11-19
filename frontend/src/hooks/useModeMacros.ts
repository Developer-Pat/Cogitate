/**
 * useModeMacros - React hook for fetching and managing mode macros.
 * 
 * This hook provides a clean interface for loading system macros from the backend
 * using the flat API (GET /macros) and managing their state in React components.
 * 
 * Phase 2: Migrated from mode-scoped to flat API. The hook now loads all macros
 * via loadAllMacros() and filters by topic client-side.
 */

import { useEffect, useRef } from 'react';
import { useSystemMacrosStore } from '../stores/macroSetsStore';
import { frontendLoggingService } from '../services/frontendLoggingService';

interface UseModeMacrosOptions {
  autoLoad?: boolean;
  refreshOnModeChange?: boolean;
  enableDebugLogging?: boolean;
}

interface UseModeMacrosReturn {
  // Data
  macros: Record<string, string>[];
  
  // State
  isLoading: boolean;
  error: string | null;
  
  // Actions
  loadAllMacros: () => void;
  clearErrors: () => void;
  clearData: () => void;
}

/**
 * Hook for fetching and managing mode macros.
 * 
 * Now uses the flat API (GET /macros) to load all macros globally.
 * The initialModeSlug parameter is kept for backward compatibility but ignored.
 * 
 * @param _initialModeSlug - Deprecated. All macros are loaded globally.
 * @param options - Configuration options
 * @returns Hook state and actions
 */
export function useModeMacros(
  _initialModeSlug?: string,
  options: UseModeMacrosOptions = {}
): UseModeMacrosReturn {
  const {
    autoLoad = true,
    enableDebugLogging = false,
  } = options;

  // Get state and actions from the dedicated macros store
  const {
    macros,
    isLoading,
    error,
    loadAllMacros,
    clearErrors,
    clearData,
  } = useSystemMacrosStore();

  // Log hook call
  frontendLoggingService.info('useModeMacros', 'Hook called', {
    autoLoad,
    macroCount: macros.length,
  });

  // Track previous macro count to detect changes
  const prevMacroCountRef = useRef<number>(macros.length);

  if (enableDebugLogging) {
    frontendLoggingService.debug('useModeMacros', 'Hook initialized', {
      options: { autoLoad, enableDebugLogging },
      timestamp: new Date().toISOString(),
      storeState: {
        macroCount: macros.length,
      },
    });
  }

  // Auto-load all macros on mount
  useEffect(() => {
    if (enableDebugLogging) {
      frontendLoggingService.debug('useModeMacros', 'Auto-load effect triggered', {
        autoLoad,
      });
    }

    // Detect macro count changes
    if (macros.length !== prevMacroCountRef.current) {
      if (enableDebugLogging) {
        frontendLoggingService.debug('useModeMacros', 'Macro count changed', {
          previous: prevMacroCountRef.current,
          current: macros.length,
        });
      }
      prevMacroCountRef.current = macros.length;
    }
    
    if (autoLoad && macros.length === 0) {
      if (enableDebugLogging) {
        frontendLoggingService.debug('useModeMacros', 'Auto-loading all system macros');
      }
      loadAllMacros();
    }
  }, [autoLoad, loadAllMacros, macros.length, enableDebugLogging]);

  return {
    // Data
    macros,
    
    // State
    isLoading,
    error,
    
    // Actions
    loadAllMacros,
    clearErrors,
    clearData,
  };
}

/**
 * Helper hook to get a specific macro by its F-button key (F1-F5)
 * 
 * Now searches across all loaded macros instead of mode-scoped ones.
 */
export function useMacroByKey(macroKey: string) {
  const { macros, loadAllMacros } = useSystemMacrosStore();
  
  // Find macro with the specified F-button key across all macros
  const macro = macros.find(m => {
    if (macroKey === 'F1' && m.f1_macro) return true;
    if (macroKey === 'F2' && m.f2_macro) return true;
    if (macroKey === 'F3' && m.f3_macro) return true;
    if (macroKey === 'F4' && m.f4_macro) return true;
    if (macroKey === 'F5' && m.f5_macro) return true;
    return false;
  });
  
  return {
    macro,
    loadAllMacros,
  };
}

/**
 * Helper hook to get all macro keys (F1-F5) that have macros
 * 
 * Now searches across all loaded macros instead of mode-scoped ones.
 */
export function useMacroKeys() {
  const { macros, loadAllMacros } = useSystemMacrosStore();
  
  const keys: string[] = [];
  macros.forEach(m => {
    if (m.f1_macro) keys.push('F1');
    if (m.f2_macro) keys.push('F2');
    if (m.f3_macro) keys.push('F3');
    if (m.f4_macro) keys.push('F4');
    if (m.f5_macro) keys.push('F5');
  });
  
  // Remove duplicates
  const uniqueKeys = [...new Set(keys)];
  
  return {
    keys: uniqueKeys,
    loadAllMacros,
  };
}
