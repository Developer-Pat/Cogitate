---
title: CacheBuster
type: atlas-component
path: frontend/src/components/CacheBuster.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# CacheBuster

**Path**: `frontend/src/components/CacheBuster.tsx`
**Last Updated**: 2026-08-01

## Purpose

Renders a "Clear Cache" button (wrapped in a Tooltip) and an auto-appearing "New Version Available!" update banner. The component detects new deployments by comparing the build-time app version (`import.meta.env.VITE_APP_VERSION`, injected by Vite) against the version previously stored in `localStorage` under the key `app_version`. When the stored version differs from the current one, it shows the update prompt. Both the manual "Clear Cache" button and the banner's "Update Now" button clear `localStorage` (preserving essential keys `auth_token` and `user_preferences`), clear `sessionStorage`, log the action via `navigator.sendBeacon` to `/api/v1/logs/frontend`, and force `window.location.reload()` to bypass the stale cache. "Later" dismisses the prompt and records the current version so it does not reappear.

## Props Interface

The component takes **no props** — it is declared as a zero-argument `React.FC`:

```typescript
export const CacheBuster: React.FC = () => {
  // ...
}
```

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useState`, `useEffect`) | Hook | Local state for current/stored version and update-prompt visibility; runs version check + localStorage sync on mount/version change |
| `Tooltip` (`./ui/Tooltip`) | Component | Wraps the "Clear Cache" button with a bottom-positioned tooltip ("Clear browser cache and reload") |
| `import.meta.env.VITE_APP_VERSION` | Build env var | App version injected by Vite at build time; falls back to `'dev'` |
| `localStorage` (`app_version`) | Browser API | Persists the last-seen app version; source of truth for detecting stale caches |
| `sessionStorage` | Browser API | Cleared on cache reset |
| `navigator.sendBeacon` | Browser API | Fire-and-forget logging of the `cache_clear` action to `${window.location.origin}/api/v1/logs/frontend` (survives page unload) |
| `window.location.reload()` | Browser API | Forces the page reload with cache bypass after clearing |

## Usage Example

```tsx
// In a page header, next to the version display (see frontend/src/pages/Dashboard.tsx)
import { CacheBuster } from '../components/CacheBuster'

<div className="flex items-center gap-2">
  <span className="text-xs text-base-content/50 font-mono">
    v{localStorage.getItem('app_version') || '0.0.0'}
  </span>
  <CacheBuster />
</div>
```

## State Used

| State | Type | Initial | Purpose |
|---|---|---|---|
| `currentVersion` | `string` | `''` | Current app version (`appVersion`), set in the effect; shown in the update banner |
| `storedVersion` | `string` | `''` | Version previously saved in `localStorage` (`'none'` if absent); shown in the update banner |
| `showUpdatePrompt` | `boolean` | `false` | Whether the "New Version Available!" banner is visible; set `true` when the stored version differs from the current one |

On mount (effect keyed on `[appVersion]`), the component stores the current version back to `localStorage['app_version']`, so the prompt only fires once per deployment until the next version change.

## Related Components

- `frontend/src/pages/Dashboard.tsx` — the only consumer; renders `<CacheBuster />` in the header next to the version span and `BackendStatusIndicator`. Reads the same `app_version` key from `localStorage` to display the version.
- `frontend/src/components/ui/Tooltip.tsx` — presentational wrapper used around the "Clear Cache" button.
