/**
 * useTheme Hook
 *
 * Hook for managing application theme with persistence and system preference detection
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import useLocalStorage from './useLocalStorage';
import type {
  ThemeMode,
  UseThemeReturn
} from '../types/settings';
import {
  THEME_STORAGE_KEY
} from '../types/settings';

/**
 * Parse the lightness (L) channel from an OKLCH color string.
 * Returns a value between 0 and 1, where < 0.5 is considered "dark".
 */
const getOKLCHLightness = (oklchString: string): number | null => {
  // Match oklch(L% C H) or oklch(L C H) format
  const match = oklchString.match(/oklch\(([\d.]+)%?\s+/);
  if (!match) return null;
  const lightness = parseFloat(match[1]);
  // Convert percentage to 0-1 range if needed
  return lightness > 1 ? lightness / 100 : lightness;
};

/**
 * Determine if a theme is dark by reading the computed --color-base-100 value.
 * This is more reliable than maintaining a hardcoded list of theme names.
 *
 * EXPORTED (2026-10-10): the wiki viewer's mermaid diagrams decide their palette by
 * DARKNESS, not by the theme's name — see the trap documented at its call site.
 */
export const isDarkThemeByLuminance = (): boolean => {
  if (typeof window === 'undefined') return false;
  
  const style = getComputedStyle(document.documentElement);
  const base100 = style.getPropertyValue('--color-base-100').trim();
  
  if (!base100) return false;
  
  const lightness = getOKLCHLightness(base100);
  if (lightness === null) return false;
  
  // L < 0.5 is considered dark
  return lightness < 0.5;
};

/**
 * Hook for theme management
 */
export const useTheme = (): UseThemeReturn => {
  const {
    value: storedTheme,
    setValue: setStoredTheme,
  } = useLocalStorage<ThemeMode>(THEME_STORAGE_KEY, 'auto');

  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>('light');

  /**
   * Get system theme preference
   */
  const getSystemTheme = useCallback((): 'light' | 'dark' => {
    if (typeof window === 'undefined') return 'light';

    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }, []);

  /**
   * Resolve theme based on stored theme and system preference.
   * Uses computed luminance detection instead of hardcoded theme names.
   */
  const resolveTheme = useCallback((theme: ThemeMode): 'light' | 'dark' => {
    if (theme === 'auto') {
      return getSystemTheme();
    }
    // For 'light' theme, always return 'light'
    if (theme === 'light') return 'light';
    
    // For all other themes, detect darkness by luminance
    // This works for any DaisyUI theme without maintaining a hardcoded list
    return isDarkThemeByLuminance() ? 'dark' : 'light';
  }, [getSystemTheme]);

  /**
   * Apply theme to document
   */
  const applyTheme = useCallback((theme: 'light' | 'dark', fullTheme: ThemeMode) => {
    if (typeof document === 'undefined') return;

    const html = document.documentElement;

    // Remove existing theme classes
    html.classList.remove('light', 'dark');

    // Add new theme class
    html.classList.add(theme);

    // Update data-theme attribute for DaisyUI 5.
    // DaisyUI does not recognise 'auto' as a theme name, so when the stored
    // preference is 'auto' we resolve it to the actual 'light' or 'dark' value.
    const dataTheme = fullTheme === 'auto' ? theme : fullTheme;
    html.setAttribute('data-theme', dataTheme);
  }, []);

  /**
   * Set theme
   */
  const setTheme = useCallback((theme: ThemeMode) => {
    setStoredTheme(theme);
    const resolved = resolveTheme(theme);
    setResolvedTheme(resolved);
    applyTheme(resolved, theme);
  }, [setStoredTheme, resolveTheme, applyTheme]);

  /**
   * Toggle between light and dark themes
   */
  const toggleTheme = useCallback(() => {
    const currentResolved = resolveTheme(storedTheme);
    const newTheme: ThemeMode = currentResolved === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
  }, [storedTheme, resolveTheme, setTheme]);

  /**
   * Initialize theme on mount
   */
  useEffect(() => {
    const resolved = resolveTheme(storedTheme);
    setResolvedTheme(resolved);
    applyTheme(resolved, storedTheme);
  }, [storedTheme, resolveTheme, applyTheme]);

  /**
   * Listen for system theme changes when using auto mode
   */
  useEffect(() => {
    if (storedTheme !== 'auto') return;

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const handleSystemThemeChange = (e: MediaQueryListEvent) => {
      const newTheme = e.matches ? 'dark' : 'light';
      setResolvedTheme(newTheme);
      applyTheme(newTheme, 'auto');
    };

    mediaQuery.addEventListener('change', handleSystemThemeChange);
    return () => mediaQuery.removeEventListener('change', handleSystemThemeChange);
  }, [storedTheme, applyTheme]);

  /**
   * Computed values
   */
  const isDark = useMemo(() => resolvedTheme === 'dark', [resolvedTheme]);
  const isLight = useMemo(() => resolvedTheme === 'light', [resolvedTheme]);

  return {
    theme: storedTheme,
    resolvedTheme,
    setTheme,
    toggleTheme,
    isDark,
    isLight,
  };
};

export default useTheme;