---
title: ThemeSelector
type: atlas-component
path: frontend/src/components/ui/settings/ThemeSelector.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ThemeSelector

**Path**: `frontend/src/components/ui/settings/ThemeSelector.tsx`
**Last Updated**: 2026-08-01

## Purpose

Theme selection UI rendered in the Settings → Appearance tab. Presents the app's DaisyUI themes as a categorized, visually-previewed picker (31 themes grouped into **Dark 🌙**, **Light ☀️**, **Vibrant 🎨** collapsible categories) driven by radio inputs. Also includes a collapsible **Theme Enhancements** panel (open by default) with a font-size slider and toggles for Compact Mode / Show Animations (controlled props), plus local-only toggles for Enable Animations, Reduced Motion, High Contrast, and Auto Theme.

Theme application is **not** routed through a settings store: selecting a theme calls `setTheme` from the `useTheme` hook, which persists to `localStorage` (key `cogitate-theme`) and applies the theme directly to `document.documentElement` (class list + `data-theme` attribute). See [Theme Application](#theme-application) below.

## Props Interface

```typescript
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
}
```

Defaults applied in the destructuring: `label = 'Theme'`, `showLabel = true`, `className = ''`. `fontSize`, `compactMode`, and `showAnimations` are **controlled** — each renders its control only when both the value and its callback are provided (e.g. `fontSize !== undefined && onFontSizeChange`).

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `useTheme` (from `../../../hooks/useTheme`) | hook | Source of `theme` / `setTheme`; persists to localStorage and applies the theme to the DOM |
| `ThemeMode` (from `../../../types/settings`) | type | Union of theme values (`'light' \| 'dark' \| 'night' \| 'synthwave' \| 'dracula' \| 'business' \| 'luxury' \| 'forest' \| 'black' \| 'auto'`) |
| `ToggleSwitch` (from `../ToggleSwitch`) | component | Enhancement toggles (Enable Animations, Reduced Motion, High Contrast, Auto Theme) |
| `React.useState` | hook | Local, non-persisted enhancement state (`animationsEnabled`, `reducedMotion`, `highContrast`) |
| DaisyUI 5 classes | CSS framework | `collapse`, `card`, `radio`, `range`, `toggle`, `form-control` styling; themes applied via `data-theme` |

**Note:** there is no settings-store involvement here. Theme persistence goes through `useLocalStorage` with `THEME_STORAGE_KEY = 'cogitate-theme'` (`frontend/src/types/settings.ts:192`), separate from `SETTINGS_STORAGE_KEY = 'cogitate-settings'` used for the Appearance settings on the Settings page.

## Theme Options Exposed

31 themes across 3 categories (defined in the module-level `themeCategories` constant):

- **Dark 🌙**: `black`, `business`, `coffee`, `dark`, `dim`, `dracula`, `forest`, `halloween`, `luxury`, `night`, `sunset`, `synthwave`
- **Light ☀️**: `acid`, `corporate`, `cupcake`, `garden`, `light`, `lofi`, `nord`, `wireframe`, `winter`
- **Vibrant 🎨**: `aqua`, `autumn`, `bumblebee`, `cyberpunk`, `emerald`, `fantasy`, `lemonade`, `pastel`, `retro`, `valentine`

Each option is `{ value, label, description }`; the picker shows a round color-swatch (`data-theme={value}` on a `bg-base-100` div) and a radio input. The active theme gets `ring-2 ring-primary`.

**Caveat (type mismatch):** the `ThemeMode` union in `types/settings.ts` only contains 10 of the 31 values. Values like `coffee`, `dim`, `halloween`, `nord`, `cupcake`, etc. are not members of the union; the component casts `themeOption.value as ThemeMode` (line 253) so they compile, but the cast is unsound. At runtime all 31 work because `useTheme.applyTheme` passes the raw string straight into the `data-theme` attribute (and `frontend/src/styles/tokens.css` ships `[data-theme=...]` overrides for these names). `tokens.css` defines overrides for `dark`, `light`, `black`, `luxury`, `synthwave`, `dracula`, `night`, `forest`, `business`, `cupcake`, `retro`, `cyberpunk`, `valentine`, `aqua`, `lofi`, `fantasy`, `wireframe`, `autumn`, `dim`, `halloween`, `lemonade`.

## Theme Application (how the theme gets applied)

Theme flow — no settings store, direct DOM + localStorage:

1. `useTheme` reads the stored value via `useLocalStorage<ThemeMode>(THEME_STORAGE_KEY, 'auto')` → localStorage key **`cogitate-theme`** (JSON-encoded string).
2. `setTheme(newTheme)` (from `useTheme`) writes the value to localStorage, resolves light/dark, and calls `applyTheme`:
   - removes `light`/`dark` classes from `document.documentElement.classList`, adds the resolved class;
   - sets `html.setAttribute('data-theme', ...)` — when the stored value is `'auto'`, DaisyUI 5 doesn't recognize it, so the **resolved** `light`/`dark` value is written instead; otherwise the full theme name (e.g. `synthwave`) is used.
3. `App.tsx` additionally renders a `GlobalTheme` component (comment: "This is the actual source of truth for theme selection, since ThemeSelector writes to localStorage") that mirrors this logic on mount and on `theme`/`resolvedTheme` change.
4. `useLocalStorage` dispatches a synthetic `storage` event after writes for cross-tab synchronization.

`'auto'` resolution uses `window.matchMedia('(prefers-color-scheme: dark)')`; for non-`light`/`auto` themes, darkness is detected by parsing the computed `--color-base-100` OKLCH lightness (`L < 0.5` ⇒ dark) rather than a hardcoded theme list. When the stored theme is `'auto'`, the hook also subscribes to `prefers-color-scheme` change events and re-applies live.

## State Used

- **`useTheme()` → `{ theme, setTheme }`**: `theme` is the persisted `ThemeMode` (default `'auto'`); `setTheme` persists + applies (see above).
- **Local `useState` (non-persisted, UI-only):** `animationsEnabled` (default `true`), `reducedMotion` (default `false`), `highContrast` (default `false`). These three do not affect the app — they are decorative local switches. `reducedMotion` is `disabled` when `animationsEnabled === false`.
- **Controlled props (from parent):** `fontSize`, `compactMode`, `showAnimations` and their change callbacks; the parent (Settings page) owns persistence of these via `settings.appearance`.
- **Auto Theme toggle (one-directional):** `checked={theme === 'auto'}`, `onChange={(checked) => checked && setTheme('auto')}` — checking it switches to `'auto'`, but unchecking it does nothing (only selecting a concrete theme leaves auto mode).

## Note on "dark default + manual 🌙 toggle"

The app was previously described as having a dark default with only a manual 🌙 toggle (OS auto-detect reverted). **That is not what the current code does.** As of 2026-08-01:

- `useTheme` still defaults to `'auto'` and actively follows the OS via `prefers-color-scheme` (including a live change listener) — OS auto-detect is present, not reverted.
- There is no 🌙 toggle anywhere in `frontend/src` (no `🌙` glyph, and `toggleTheme` from `useTheme` is unused).
- The only theme UI is this `ThemeSelector` in Settings, which includes the Auto Theme switch described above.

## Usage Example

As used by the Settings page (`frontend/src/pages/Settings.tsx:145`):

```tsx
import { ThemeSelector } from '../components/ui/settings/ThemeSelector';

<ThemeSelector
  fontSize={settings.appearance.fontSize}
  onFontSizeChange={(v) => updateAppearanceSetting('fontSize', v)}
  compactMode={settings.appearance.compactMode}
  onCompactModeChange={(v) => updateAppearanceSetting('compactMode', v)}
  showAnimations={settings.appearance.showAnimations}
  onShowAnimationsChange={(v) => updateAppearanceSetting('showAnimations', v)}
/>
```

Minimal standalone usage:

```tsx
<ThemeSelector label="Theme" showLabel />
```

## Related Components

- `frontend/src/pages/Settings.tsx` — parent; renders `ThemeSelector` inside the Appearance tab card and supplies the controlled enhancement props.
- `frontend/src/components/ui/ToggleSwitch.tsx` — used for the four enhancement toggles.
- `frontend/src/hooks/useTheme.ts` — theme state, persistence, and DOM application; default export also used by `App.tsx`.
- `frontend/src/hooks/useLocalStorage.ts` — localStorage read/write with error logging and cross-tab `storage` event dispatch.
- `frontend/src/types/settings.ts` — `ThemeMode`, `AppearanceSettings`, `THEME_STORAGE_KEY`, `UseThemeReturn`.
- `frontend/src/App.tsx` — `GlobalTheme` component applies the stored theme app-wide (mirrors `useTheme.applyTheme`).
- `frontend/src/components/ui/settings/index.ts` — barrel export (`export { default as ThemeSelector }`).
- `frontend/src/styles/tokens.css` — `[data-theme=...]` token overrides for the exposed themes.
