---
title: MacroKeyboard
type: atlas-component
path: frontend/src/components/features/agentInteraction/MacroKeyboard.tsx
confidence: high
updated: 2026-09-03
tags: [type/component, domain/atlas-ui]
---
# MacroKeyboard

**Path**: `frontend/src/components/features/agentInteraction/MacroKeyboard.tsx`
**Last Updated**: 2026-09-03

## Purpose

Renders the chat input's macro keyboard: the F/M key groups + the
A-KEY bank (A1-A5) + the two bank selectors, and — on the Exa page —
the ACP trio via the `afterAKeys` slot. Key groups:

- **F-keys (F1–F5)** — topic macros: each F-key resolves to a macro
  value from the currently selected meta-topic's `topic_mappings`,
  looked up in the global macro-set list (`getTopicMacro(fIndex)`).
  Clicking a populated F-key calls `onMacroSelect(macroValue)`.
- **M-keys (M1–M5)** — topic/mapping selectors: when the selected
  meta-topic has `topic_mappings`, M-keys switch the active mapping
  index (which F-keys resolve against). When it has no mappings,
  M-keys list the `namespace === 'agent'` meta-topics and call
  `selectMetaTopic(id)` directly.
- **A-keys (A1–A5)** — THE ACTION-KEY BANK (2026-09-03, the akeys
  Phase 2): DATA-DRIVEN flyouts fed by the A-source meta-topic
  (`aKeysMetaTopicId` — the store's own A-source, NEVER the F/M
  selection). A-key i = the source's i-th mapped macro set; the
  flyout items = that set's non-empty f1-f5 macros. No source /
  empty slot -> the key (or the whole row) deactivates with a
  VISIBLE reason — never arbitrary content.
- **The bank selectors** (Phase 5b) — `TopicFlyoutButton` rendered
  INSIDE this component, two icon-only instances: `bank="f"` after
  the M group and `bank="a"` after the A group (both
  `dropdownUp={true}`). Select = set = persist (surface-scoped).
- **The afterAKeys slot** (2026-09-03, the user's ask) — the caller
  passes trailing controls rendered after the A selector in the SAME
  A-UNIT (the A keys + selector + slot wrap as one non-breaking
  group). ChatInterface passes the Exa ACP trio here when
  `agentId === 'exa'`.

"Keyboard" refers to visual key buttons, not physical keyboard
events — the component registers no keydown/keypress listeners.

## Props Interface

```typescript
interface MacroKeyboardProps {
  onMacroSelect: (value: string) => void
  disabled?: boolean
  compact?: boolean
  metaTopics: SystemMetaTopic[]
  selectedMetaTopicId: number | null
  selectMetaTopic: (id: number) => void
  macros?: SystemMacroSet[]
  aKeysMetaTopicId?: number | null
  afterAKeys?: React.ReactNode
}
```

Default values applied in the destructuring: `disabled = false`,
`compact = false`, `macros = []`, `aKeysMetaTopicId = null`.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `useState`, `useRef`, `useEffect` (react) | Hooks | Track `topicMappingIndex`; reset it to 0 whenever `selectedMetaTopicId` changes |
| `SystemMetaTopic`, `SystemMacroSet` (from `../../../types/macros`) | Types | Prop typing |
| `TopicFlyoutButton` (`./TopicFlyoutButton`) | Child | The two icon-only bank selectors (f after M5, a beside the A keys) |
| `useSystemMacrosStore` (stores/macroSetsStore.ts) | Zustand store (via ChatInterface props) | Supplies `metaTopics`, `macroSets`, `selectedMetaTopicId`, `aKeysMetaTopicId`, `selectMetaTopic` |
| `localStorage` keys `cogitate_selected_meta_topic` / `cogitate_akeys_meta_topic` | Storage (via the store) | Persists the F-selection / the A-source, surface-scoped (`:exa` suffix for the Exa surface; agent = legacy bare keys) |

## Usage Example

Used by ChatInterface in compact mode inside the input container
(BOTH the agent chat and the Exa page — the surface derives from
`agentId === 'exa'`):

```tsx
// ChatInterface.tsx (abridged)
<MacroKeyboard
  onMacroSelect={handleMacroSelect}
  disabled={disabled || isStreaming}
  compact={true}
  metaTopics={metaTopics}
  selectedMetaTopicId={selectedMetaTopicId}
  selectMetaTopic={selectMetaTopic}
  macros={macros}
  aKeysMetaTopicId={aKeysMetaTopicId}
  afterAKeys={agentId === 'exa' && onExaAction ? exaToolbar : null}
/>
```

## State Used

- `topicMappingIndex: number` (useState, initial `0`) — index into
  the selected meta-topic's `topic_mappings` array that F-keys
  resolve against. Set by clicking an M-key when the selected topic
  has mappings.
- `prevMetaTopicIdRef` (useRef) — resets `topicMappingIndex` to `0`
  whenever `selectedMetaTopicId` changes.

Derived (not stored): `selectedTopic` (the F meta-topic),
`aSourceTopic` (the A-source meta-topic), `aKeySlots` (the A1-A5
data-driven slots), `aSourceMissing`.

## Related Components

- `frontend/src/components/features/agentInteraction/ChatInterface.tsx` — parent; wires props from `useSystemMacrosStore`, always renders with `compact={true}`, passes `afterAKeys`
- `frontend/src/components/features/agentInteraction/TopicFlyoutButton.tsx` — CHILD now (two icon-only bank instances), not a sibling
- `frontend/src/stores/macroSetsStore.ts` — data source (meta-topics + macro sets + the surface-scoped selections)
- `frontend/src/pages/Macros.tsx`, `frontend/src/hooks/useModeMacros.ts` — other consumers of `useSystemMacrosStore`

## Behavioral Notes (as implemented)

- **F-key resolution** (`getTopicMacro(fIndex)`): requires a
  selected topic with a non-empty `topic_mappings`; uses
  `topicMappings[topicMappingIndex] || topicMappings[0]`; finds the
  macro set where `m.topic === mappingTopic(mapping)`; returns
  `macroSet[f{fIndex+1}_macro]` or `null`. Empty F-keys render
  disabled.
- **Compact M-key list**: `selectedTopic.topic_mappings` if
  non-empty, else `metaTopics.filter(mt => mt.namespace === 'agent')`.
- **A-key slots** (`getAKeySlots`): A-key i = the A-source's i-th
  `topic_mappings` entry -> its macro set -> non-empty f1-f5 items.
  Missing source/mapping/set = an empty slot (disabled + Empty
  tooltip); a missing source deactivates the whole row with the
  visible reason.
- **The A-UNIT**: the A keys + the A selector + the afterAKeys slot
  wrap as ONE non-breaking flex group — the Exa ACP trio sits right
  after the A selector and can never orphan onto its own line.
- **No keyboard-event handling** exists despite the name — all
  interaction is click-driven.
