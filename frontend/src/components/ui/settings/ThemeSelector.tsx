/**
 * ThemeSelector Component
 *
 * Reusable component for theme selection with visual previews
 */

import React, { useState } from 'react';
import useTheme from '@/hooks/useTheme';
import type { ThemeMode } from '@/types/settings';
import { ToggleSwitch } from '../ToggleSwitch';

interface ThemeSelectorProps {
  label?: string;
  showLabel?: boolean;
  className?: string;
  fontSize?: number;
  onFontSizeChange?: (value: number) => void;
  compactMode?: boolean;
  onCompactModeChange?: (value: boolean) => void;
  showAnimations?: boolean;
  onShowAnimationsChange?: (value: boolean) => void;
  chatBubbleGhost?: boolean;
  onChatBubbleGhostChange?: (value: boolean) => void;
  /** Quiet Mode (2026-09-05): 'quiet' = the app-wide quiet CSS
   * layer (solid semantic fills demote to outlines). */
  loudness?: 'normal' | 'quiet';
  onLoudnessChange?: (value: 'normal' | 'quiet') => void;
  /** Keep the Command Box Open (2026-09-18): the Ask-Exa box stays up across
   * navigations with its input focused. Default OFF (see the setting's own
   * note in types/settings.ts). */
  keepCommandBoxOpen?: boolean;
  onKeepCommandBoxOpenChange?: (value: boolean) => void;
}

interface ThemeCategory {
  name: string;
  icon: string;
  themes: { value: string; label: string; description: string }[];
}

// Fun themes merged into Light; categories alphabetized within themselves
const themeCategories: ThemeCategory[] = [
  {
    name: 'Dark',
    icon: '🌙',
    themes: [
      { value: 'black', label: 'Black', description: 'Pure black OLED' },
      { value: 'business', label: 'Business', description: 'Professional gray' },
      { value: 'coffee', label: 'Coffee', description: 'Warm brown' },
      { value: 'dark', label: 'Dark', description: 'Easy on the eyes' },
      { value: 'dim', label: 'Dim', description: 'Low-light dark' },
      { value: 'dracula', label: 'Dracula', description: 'Dark with pink' },
      { value: 'forest', label: 'Forest', description: 'Natural green' },
      { value: 'halloween', label: 'Halloween', description: 'Orange & black' },
      { value: 'luxury', label: 'Luxury', description: 'Gold and black' },
      { value: 'night', label: 'Night', description: 'Deep blue dark' },
      { value: 'sunset', label: 'Sunset', description: 'Warm orange' },
      { value: 'synthwave', label: 'Synthwave', description: 'Retro 80s neon' },
    ],
  },
  {
    name: 'Light',
    icon: '☀️',
    themes: [
      { value: 'acid', label: 'Acid', description: 'Bright neon' },
      { value: 'corporate', label: 'Corporate', description: 'Modern blue' },
      { value: 'cupcake', label: 'Cupcake', description: 'Soft pastel' },
      { value: 'garden', label: 'Garden', description: 'Fresh green' },
      { value: 'light', label: 'Light', description: 'Clean and minimal' },
      { value: 'lofi', label: 'Lofi', description: 'Minimalist gray' },
      { value: 'nord', label: 'Nord', description: 'Arctic blue' },
      { value: 'wireframe', label: 'Wireframe', description: 'Sketch outline' },
      { value: 'winter', label: 'Winter', description: 'Cool blue' },
    ],
  },
  {
    name: 'Vibrant',
    icon: '🎨',
    themes: [
      { value: 'aqua', label: 'Aqua', description: 'Blue & cyan' },
      { value: 'autumn', label: 'Autumn', description: 'Warm fall colors' },
      { value: 'bumblebee', label: 'Bumblebee', description: 'Yellow & black' },
      { value: 'cyberpunk', label: 'Cyberpunk', description: 'High-tech neon' },
      { value: 'emerald', label: 'Emerald', description: 'Green & blue' },
      { value: 'fantasy', label: 'Fantasy', description: 'Purple & gold' },
      { value: 'lemonade', label: 'Lemonade', description: 'Fresh yellow' },
      { value: 'pastel', label: 'Pastel', description: 'Soft pastels' },
      { value: 'retro', label: 'Retro', description: 'Vintage orange' },
      { value: 'valentine', label: 'Valentine', description: 'Pink romantic' },
    ],
  },
];

/**
 * Theme selector component
 */
export const ThemeSelector: React.FC<ThemeSelectorProps> = ({
  label = 'Theme',
  showLabel = true,
  className = '',
  fontSize,
  onFontSizeChange,
  compactMode,
  onCompactModeChange,
  showAnimations,
  onShowAnimationsChange,
  chatBubbleGhost,
  onChatBubbleGhostChange,
  loudness,
  onLoudnessChange,
  keepCommandBoxOpen,
  onKeepCommandBoxOpenChange,
}) => {
  const { theme, setTheme } = useTheme();

  // Theme enhancement toggles
  const [animationsEnabled, setAnimationsEnabled] = useState(true);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [highContrast, setHighContrast] = useState(false);

  const handleThemeChange = (newTheme: ThemeMode) => {
    setTheme(newTheme);
  };

  return (
    <div className={`form-control ${className}`}>
      {showLabel && (
        <label className="label">
          <span className="label-text font-semibold">{label}</span>
        </label>
      )}

      {/* Theme Enhancements — Collapsible, open by default */}
      <details className="collapse collapse-arrow bg-base-200/50 mb-4" open>
        <summary className="collapse-title text-sm font-semibold">
          Theme Enhancements
        </summary>
        <div className="collapse-content">
          <div className="space-y-4">
            {/* Font Size */}
            {fontSize !== undefined && onFontSizeChange && (
              <div className="form-control w-full">
                <label className="label">
                  <span className="label-text font-medium">Font Size: {fontSize}px</span>
                </label>
                <input
                  type="range"
                  min="12"
                  max="24"
                  value={fontSize}
                  onChange={(e) => onFontSizeChange(parseInt(e.target.value))}
                  className="range range-primary"
                />
                <div className="flex justify-between text-xs px-2 mt-1">
                  <span>12px</span>
                  <span>24px</span>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Compact Mode */}
              {compactMode !== undefined && onCompactModeChange && (
                <div className="form-control">
                  <label className="label cursor-pointer">
                    <span className="label-text font-medium">Compact Mode</span>
                    <input
                      type="checkbox"
                      className="toggle toggle-primary"
                      checked={compactMode}
                      onChange={(e) => onCompactModeChange(e.target.checked)}
                    />
                  </label>
                </div>
              )}

              {/* Ghost Chat Bubbles (2026-09-01, the user's ask) */}
              {chatBubbleGhost !== undefined && onChatBubbleGhostChange && (
                <div className="form-control">
                  <label className="label cursor-pointer" title="The chat bubbles vanish into the background — the backlight glow appears on hover">
                    <span className="label-text font-medium">Ghost Chat Bubbles</span>
                    <input
                      type="checkbox"
                      className="toggle toggle-primary"
                      checked={chatBubbleGhost}
                      onChange={(e) => onChatBubbleGhostChange(e.target.checked)}
                    />
                  </label>
                  <p className="text-xs opacity-60 -mt-1 pl-1">Bubbles blend into the background; hovering shows a soft glow (no fill change)</p>
                </div>
              )}

              {/* Quiet Mode (2026-09-05, the user's ask) */}
              {loudness !== undefined && onLoudnessChange && (
                <div className="form-control">
                  <label className="label cursor-pointer" title="Quiet the app's filled controls — solid fills demote to outlines everywhere (mixing quiet and loud only makes the loud louder)">
                    <span className="label-text font-medium">Quiet Mode</span>
                    <input
                      type="checkbox"
                      className="toggle toggle-primary"
                      checked={loudness === 'quiet'}
                      onChange={(e) => onLoudnessChange(e.target.checked ? 'quiet' : 'normal')}
                    />
                  </label>
                  <p className="text-xs opacity-60 -mt-1 pl-1">Solid button/badge fills become quiet outlines across the app</p>
                </div>
              )}

              {/* Keep the Command Box Open (2026-09-18 — P1 of the box redesign).
                  The box lives in the page header; with this ON it survives a
                  navigation with its input focused, so several pages can be
                  visited from the keyboard. Default OFF: it changes behaviour
                  everywhere, so it is an explicit grant (integration-boundaries
                  P4 — visible here, revocable by turning it off). */}
              {keepCommandBoxOpen !== undefined && onKeepCommandBoxOpenChange && (
                <div className="form-control">
                  <label className="label cursor-pointer" title="The Ask-Exa box stays up after a navigation with the cursor in its input, so you can move through several pages from the keyboard">
                    <span className="label-text font-medium">Keep the Command Box Open</span>
                    <input
                      type="checkbox"
                      className="toggle toggle-primary"
                      checked={keepCommandBoxOpen}
                      onChange={(e) => onKeepCommandBoxOpenChange(e.target.checked)}
                    />
                  </label>
                  <p className="text-xs opacity-60 -mt-1 pl-1">After a navigation the box stays up, ready for the next command</p>
                </div>
              )}

              {/* Show Animations */}
              {showAnimations !== undefined && onShowAnimationsChange && (
                <div className="form-control">
                  <label className="label cursor-pointer">
                    <span className="label-text font-medium">Show Animations</span>
                    <input
                      type="checkbox"
                      className="toggle toggle-primary"
                      checked={showAnimations}
                      onChange={(e) => onShowAnimationsChange(e.target.checked)}
                    />
                  </label>
                </div>
              )}

              {/* Enable Animations (local) */}
              <ToggleSwitch
                checked={animationsEnabled}
                onChange={setAnimationsEnabled}
                label="Enable Animations"
                description="Smooth transitions and effects"
                size="sm"
              />

              {/* Reduced Motion (local) */}
              <ToggleSwitch
                checked={reducedMotion}
                onChange={setReducedMotion}
                label="Reduced Motion"
                description="Minimize animations for accessibility"
                disabled={animationsEnabled === false}
                size="sm"
              />

              {/* High Contrast (local) */}
              <ToggleSwitch
                checked={highContrast}
                onChange={setHighContrast}
                label="High Contrast"
                description="Enhanced contrast for better visibility"
                size="sm"
              />

              {/* Auto Theme (local) */}
              <ToggleSwitch
                checked={theme === 'auto'}
                onChange={(checked) => checked && setTheme('auto')}
                label="Auto Theme"
                description="Follow system theme preference"
                size="sm"
              />
            </div>
          </div>
        </div>
      </details>

      <div className="space-y-3">
        {themeCategories.map((category) => (
          <details key={category.name} className="collapse collapse-arrow bg-base-200/30">
            <summary className="collapse-title text-sm font-semibold">
              {category.icon} {category.name}
            </summary>
            <div className="collapse-content">
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                {category.themes.map((themeOption) => (
                  <label
                    key={themeOption.value}
                    className={`
                      card card-compact cursor-pointer p-3 transition-all
                      ${theme === themeOption.value
                        ? 'bg-base-200 shadow-md ring-2 ring-primary'
                        : 'bg-base-200/50 hover:bg-base-200 hover:shadow-sm'
                      }
                    `}
                  >
                    <div className="flex items-center gap-2">
                      <div
                        className="w-6 h-6 rounded-full flex-shrink-0 bg-base-100 shadow-sm"
                        data-theme={themeOption.value}
                      />
                      <div className="flex flex-col min-w-0 flex-1">
                        <span className="text-sm font-medium leading-tight truncate">
                          {themeOption.label}
                        </span>
                        <span className="text-xs text-readout leading-tight truncate">
                          {themeOption.description}
                        </span>
                      </div>
                      <input
                        type="radio"
                        name="theme"
                        value={themeOption.value}
                        checked={theme === themeOption.value}
                        onChange={() => handleThemeChange(themeOption.value as ThemeMode)}
                        className="radio radio-primary radio-sm flex-shrink-0"
                      />
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </details>
        ))}
      </div>
    </div>
  );
};

export default ThemeSelector;