---
title: ToggleSwitch
type: atlas-component
path: frontend/src/components/ui/ToggleSwitch.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# ToggleSwitch

**Path**: `frontend/src/components/ui/ToggleSwitch.tsx`
**Last Updated**: 2026-08-01

## Purpose
Modern toggle switch with smooth animations — label + description + sliding knob in three sizes.

## Props Interface
```typescript
interface ToggleSwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label?: string
  description?: string
  disabled?: boolean   // default false
  size?: 'sm' | 'md' | 'lg'  // default 'md'
}
```

## Dependencies
None (pure JSX, controlled component).

## Usage Example
```tsx
<ToggleSwitch
  checked={compactMode}
  onChange={setCompactMode}
  label="Compact mode"
  description="Tighter spacing in lists and tables"
/>
```

## State Used
None — fully controlled via `checked`/`onChange`.

## Related Components
- ui/settings/PreferenceToggle.tsx — settings-specific toggle wrapper