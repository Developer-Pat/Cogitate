---
title: TopicFlyoutButton
type: atlas-component
path: frontend/src/components/features/agentInteraction/TopicFlyoutButton.tsx
confidence: high
updated: 2026-09-03
tags: [type/component, domain/atlas-ui]
---

# TopicFlyoutButton

**Path**: `frontend/src/components/features/agentInteraction/TopicFlyoutButton.tsx`
**Last Updated**: 2026-09-03

## Purpose

Renders a bank-aware meta-topic selector: the trigger opens a flyout
listing all available system meta-topics. **bank='f'** (default)
selects the topic driving the macro keyboard's F/M keys
(`selectMetaTopic`); **bank='a'** selects the ACTION-KEY source
(`setAKeysDefault` — select IS persist, no separate default step).
The store's ACTIVE SURFACE (agent vs exa) scopes the persisted
localStorage key either way. The keyboard-attached selectors are
**icon-only** with upward-opening flyouts (the chat input sits at
the bottom of the page). The flyout supports marking a topic as the
default and shows explicit loading and empty states. The refresh
button was REMOVED (2026-09-03, the akeys Phase 5c) — the UI
auto-syncs via `useMacroSync`'s event bus.

## Props Interface

```typescript
interface TopicFlyoutButtonProps {
  className?: string;
  size?: 'sm' | 'md';
  label?: string;
  dropdownUp?: boolean;
  namespace?: string;
  bank?: 'f' | 'a';
  iconOnly?: boolean;
}
```

All props are optional:

- `className` (default `''`) — extra classes appended to the wrapper `div`.
- `size` (default `'md'`) — `'sm'` or `'md'` button sizing.
- `label` (default `'Topic'`) — the pill's text (the non-icon form).
- `dropdownUp` (default `false`) — the flyout opens above the trigger (the chat input's four selectors all pass `true`).
- `namespace` — scopes the topic list (the tsc-b tail fix, 2026-08-26).
- `bank` (default `'f'`) — `'f'` = the F/M topic (`selectMetaTopic`);
  `'a'` = the ACTION-KEY source (`setAKeysDefault`, select = persist).
- `iconOnly` (default `false`) — the keyboard-attached tiny glyph form
  (no label text); the tooltip + aria-label carry the state readout
  ("F topic: X" / "A source: Y").

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `useSystemMacrosStore` (`stores/macroSetsStore`) | Zustand store | Source of `metaTopics`, `selectedMetaTopicId`, `aKeysMetaTopicId`, `defaultMetaTopicId`, `isLoadingMetaTopics` plus actions `loadMetaTopics`, `selectMetaTopic`, `setAKeysDefault`, `setAsDefaultTopic`; persists the selections surface-scoped (agent = bare keys, exa = `:exa` suffix) |
| `SystemMetaTopic` (`types/macros`) | Type | Shape of a meta-topic item |
| `Layers`, `ChevronDown` (`lucide-react`) | Icon components | Trigger icon, chevron indicator (rotates 180deg when open) — the `RefreshCw` reload icon is GONE (the refresh removal, Phase 5c) |
| `useState`, `useEffect`, `useRef`, `useCallback` (`react`) | Hooks | Flyout open state, mount-time fetch, outside-click / Escape dismissal, memoized handlers |

## Usage Example

```tsx
import { TopicFlyoutButton } from '../components/features/agentInteraction/TopicFlyoutButton';

// The F selector (the MacroKeyboard compact row, after the M keys):
<TopicFlyoutButton size="sm" bank="f" iconOnly={true} dropdownUp={true} />

// The A selector (beside the A-key bank, same row):
<TopicFlyoutButton size="sm" bank="a" iconOnly={true} dropdownUp={true} />

// The Macros page (the pill form, custom label):
<TopicFlyoutButton size="sm" label="Select Meta" />
```

## State Used

- Local `useState`: `flyoutOpen` (boolean) — controls flyout visibility.
- Local `useRef`: `dropdownRef` — wrapper `div` ref used for outside-click detection.
- Store state (from `useSystemMacrosStore`): `metaTopics`, `isLoadingMetaTopics`, `selectedMetaTopicId`, `defaultMetaTopicId`.
- Store actions: `loadMetaTopics` (called on mount when `metaTopics` is empty and not already loading), `selectMetaTopic` (bank='f' option click), `setAKeysDefault` (bank='a' option click — select IS persist), `setAsDefaultTopic` (toggles default, passing `null` to clear).
- Persistence: the store saves the F-selection under `cogitate_selected_meta_topic` and the A-source under `cogitate_akeys_meta_topic` — bare keys for the agent surface, `:exa`-suffixed for the Exa surface (`utils/macroSurface`).

## Flyout Behavior

- Trigger click toggles the flyout; it closes on option select, on outside `mousedown`, or on `Escape`.
- On mount, fetches meta-topics from the store if none are loaded yet.
- While `isLoadingMetaTopics`, shows a spinner + "Loading meta-topics...".
- When loaded with zero topics, shows "No meta-topics available — create one in the Macros page".
- Each option row shows the topic name, a two-line-clamped description, an "Active" tag when selected (with primary left-border highlight), and a ★ indicator when it is the default topic, plus a "Set as default" / "★ Default" toggle button (stopPropagation so it doesn't select the row). In bank='a' mode the F-default ★ is hidden and the header reads "Select the A-Key Source".
- The flyout header has NO refresh button (removed 2026-09-03, Phase 5c — `useMacroSync` auto-reloads on the backend's `macro:<id>:<event>` / `meta-topic:*` publishes).
- ARIA: trigger uses `aria-expanded` / `aria-haspopup="listbox"`; the flyout uses `role="listbox"` with `role="option"` items and `aria-selected`. The trigger's aria-label reads the state ("F topic: X" / "A source: Y"); the DaisyUI tooltip is the static bank label ("Select F-Key Macros" / "Select A-Key Macros").

## Related Components

- `MacroKeyboard` — `frontend/src/components/features/agentInteraction/MacroKeyboard.tsx` (renders the F selector after the M group + the A selector beside the A-key bank — both `iconOnly` + `dropdownUp`; the afterAKeys slot carries the Exa ACP trio after the A selector)
- `Macros` page — `frontend/src/pages/Macros.tsx` (renders `<TopicFlyoutButton size="sm" label="Select Meta" />` — the pill form)
- Barrel export — `frontend/src/components/features/agentInteraction/index.ts`
- The selected meta-topic drives the macro keyboard's M-key / F-key display within the agent interaction feature.
