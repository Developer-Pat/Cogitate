/**
 * Settings Types and Interfaces
 * 
 * Type definitions for settings persistence and theme management
 */

import { z } from 'zod';

/**
 * Theme modes
 */
export type ThemeMode = 'light' | 'dark' | 'night' | 'synthwave' | 'dracula' | 'business' | 'luxury' | 'forest' | 'black' | 'auto';

/**
 * Language options
 */
export type Language = 'en' | 'es' | 'fr' | 'de';

/**
 * Time zone options
 */
export type TimeZone = 'UTC-5' | 'UTC-6' | 'UTC-7' | 'UTC-8';

/**
 * Notification frequency options
 */
export type NotificationFrequency = 
  | 'realtime' 
  | '5min' 
  | '15min' 
  | 'hourly' 
  | 'daily';

/**
 * Title generation model preference
 */
export type TitleModelPreference = 'agent' | 'backend_default' | 'custom';

/**
 * General settings
 */
export interface GeneralSettings {
  language: Language;
  timeZone: TimeZone;
  autoSave: boolean;
  showWelcomeScreen: boolean;
  enableAutoTitle: boolean;
  titleModelPreference: TitleModelPreference;
  titleCustomModel: string;
  /**
   * Show onboarding tips on first visit to each page.
   * @deprecated These tips were added before the help system was improved.
   * Defaults to `false` to phase out usage. Will be removed in a future release.
   */
  /**
   * Show macro set IDs in M-key and F-key tooltips.
   * Provides a stable shared identifier for referencing macros
   * between the user and the system during macro development.
   */
  showMacroIds: boolean;
  showPipelineIndicators: boolean;
}

/**
 * Appearance settings
 */
export interface AppearanceSettings {
  theme: ThemeMode;
  fontSize: number;
  compactMode: boolean;
  showAnimations: boolean;
  /** THE GHOST BUBBLES (2026-09-01, the user's ask): the chat
   * bubbles vanish into the background (the clutter-free look);
   * hovering shows a soft backlight glow — no fill change (the
   * burn/dodge tokens were removed 2026-09-03). */
  chatBubbleGhost: boolean;
  /** THE CONTROL LOUDNESS (2026-09-05, Quiet Mode): 'normal' =
   * DaisyUI solid fills; 'quiet' = the app-wide quiet layer (the
   * semantic fills demote to outlines — html[data-loudness]). */
  loudness: 'normal' | 'quiet';
  /** THE COMMAND BOX STAYS UP (2026-09-18): when true, the Ask-Exa box keeps
   * open across navigations with its input focused, so several pages can be
   * visited from the keyboard. Default OFF — it changes behaviour everywhere,
   * so it is an explicit grant (integration-boundaries P4: capabilities start
   * off, and the grant is visible and revocable). P1 of
   * local/studies/exa-box-redesign-roadmap.md. */
  keepCommandBoxOpen: boolean;
}

/**
 * Notification settings
 */
export interface NotificationSettings {
  emailNotifications: boolean;
  pushNotifications: boolean;
  systemAlerts: boolean;
  agentStatusUpdates: boolean;
  errorReports: boolean;
  frequency: NotificationFrequency;
}

/**
 * Complete settings object
 */
export interface Settings {
  general: GeneralSettings;
  appearance: AppearanceSettings;
  notifications: NotificationSettings;
  lastUpdated: string;
  version: string;
}

/**
 * Settings schema for validation
 */
export const SettingsSchema = z.object({
  general: z.object({
    language: z.enum(['en', 'es', 'fr', 'de']),
    timeZone: z.enum(['UTC-5', 'UTC-6', 'UTC-7', 'UTC-8']),
    autoSave: z.boolean(),
    showWelcomeScreen: z.boolean(),
    enableAutoTitle: z.boolean(),
    titleModelPreference: z.enum(['agent', 'backend_default', 'custom']),
    titleCustomModel: z.string(),
    showMacroIds: z.boolean(),
    showPipelineIndicators: z.boolean(),
  }),
  appearance: z.object({
    theme: z.enum(['light', 'dark', 'night', 'synthwave', 'dracula', 'business', 'luxury', 'forest', 'black', 'auto']),
    fontSize: z.number().min(12).max(24),
    compactMode: z.boolean(),
    showAnimations: z.boolean(),
    chatBubbleGhost: z.boolean(),
    loudness: z.enum(['normal', 'quiet']),
    keepCommandBoxOpen: z.boolean(),
  }),
  notifications: z.object({
    emailNotifications: z.boolean(),
    pushNotifications: z.boolean(),
    systemAlerts: z.boolean(),
    agentStatusUpdates: z.boolean(),
    errorReports: z.boolean(),
    frequency: z.enum(['realtime', '5min', '15min', 'hourly', 'daily']),
  }),
  lastUpdated: z.string(),
  version: z.string(),
});

/**
 * Default settings values
 */
export const defaultSettings: Settings = {
  general: {
    language: 'en',
    timeZone: 'UTC-5',
    autoSave: true,
    showWelcomeScreen: false,
    showPipelineIndicators: true,
    enableAutoTitle: true,
    titleModelPreference: 'agent',
    titleCustomModel: '',
    showMacroIds: true,
  },
  appearance: {
    theme: 'auto',
    fontSize: 16,
    compactMode: false,
    showAnimations: true,
    chatBubbleGhost: false,
    loudness: 'normal',
    keepCommandBoxOpen: false,
  },
  notifications: {
    emailNotifications: true,
    pushNotifications: false,
    systemAlerts: true,
    agentStatusUpdates: true,
    errorReports: true,
    frequency: 'realtime',
  },
  lastUpdated: new Date().toISOString(),
  version: '1.0.0',
};

/**
 * Settings context type
 */
export interface SettingsContextType {
  settings: Settings;
  updateSettings: (updates: Partial<Settings>) => void;
  resetSettings: () => void;
  exportSettings: () => string;
  importSettings: (settingsData: string) => boolean;
  loading: boolean;
  error: string | null;
}

/**
 * Theme context type
 */
export interface ThemeContextType {
  theme: ThemeMode;
  resolvedTheme: 'light' | 'dark';
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
}

/**
 * Settings storage keys
 */
export const SETTINGS_STORAGE_KEY = 'cogitate-settings';
export const THEME_STORAGE_KEY = 'cogitate-theme';

/**
 * Settings import/export types
 */
export interface SettingsExport {
  settings: Settings;
  exportedAt: string;
  version: string;
}

/**
 * Hook return types
 */
export interface UseSettingsReturn {
  settings: Settings;
  updateSettings: (updates: Partial<Settings>) => void;
  resetSettings: () => void;
  exportSettings: () => string;
  importSettings: (settingsData: string) => boolean;
  loading: boolean;
  error: string | null;
}

export interface UseThemeReturn {
  theme: ThemeMode;
  resolvedTheme: 'light' | 'dark';
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
  isDark: boolean;
  isLight: boolean;
}

export interface UseLocalStorageReturn<T> {
  value: T;
  setValue: (value: T) => void;
  removeValue: () => void;
  loading: boolean;
}