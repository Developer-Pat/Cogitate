---
title: NavSearchHotkey
type: atlas-component
path: frontend/src/components/features/agentInteraction/NavSearchHotkey.tsx
confidence: high
updated: 2026-09-19
tags: [type/component, domain/atlas-ui, domain/navigation]
---
# NavSearchHotkey

**Path**: `frontend/src/components/features/agentInteraction/NavSearchHotkey.tsx`
**Last Updated**: 2026-09-19

## Purpose

The **one app-wide key listener**: **Cmd on macOS, Ctrl elsewhere**. It renders nothing (`return null`) and exists to be mounted by the shell unconditionally. It owns every global chord the app has:

| key | action |
|---|---|
| `K` | open the Search box and put the caret in it |
| `F` | the same action — the browser's find bar means nothing in an app with its own search |
| **`` ` ``** | toggle the navigation panel (the same store action the chevron and the mobile hamburger run) |

The natural-looking place for the listener is inside the widget that owns the box, and that is where it used to live (`useCommandBox`'s `hotkey` option). With the nav sidebar as the box's home, it cannot: the section is rendered **only while the sidebar is expanded** (`{!sidebarCollapsed && <NavSearchSection />}`), so a listener inside it would be dead for exactly the case the key exists to fix — a collapsed rail, with nothing on screen to press. This component is rendered by the shell and never unmounts.

## Responsibilities

- **The keys.** `(e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === 'k' || e.key.toLowerCase() === 'f')` runs `openNavSearch()`; `(e.ctrlKey || e.metaKey) && (e.key === '\`' || e.key === '~')` runs `toggleSidebar()`. `preventDefault()` on both, so no browser default fires — Cmd/Ctrl+K would otherwise be the address bar's search, Cmd/Ctrl+F the browser's find bar. `F` has no branch of its own: it is the same action as `K`.
- **THE PANEL KEY WAS CHOSEN FOR CO-EXISTENCE** (2026-09-19). The user's rule: *"don't claim the Ctrl+B from Firefox. we want to co-exist."* So the chord has to be one the BROWSER does nothing with, and `Ctrl+\`` was measured silent in both Firefox 145 and Chromium — the page receives it, the browser ignores it, nothing is claimed. The census (and the controls that proved it could detect a claim) is in [[dev-notes/frontend/keyboard-and-focus|Keyboard and Focus]].
- **One store write.** `openNavSearch()` sets `{ sidebarCollapsed: false, navSearchOpen: true, navSearchFocusPending: true }` in a single set, so a reader never sees an expanded sidebar with the box still rolled up. The panel key writes `toggleSidebar()` and nothing else.
- **Nothing else.** It does not reach into the box. The input's ref lives in `useCommandBox`, inside the section's mount, so the section — the one place the input exists — answers the focus signal (`uiStore`'s `navSearchFocusPending`); the shell does not get a second copy of the hook to duplicate its logic in. Where the caret goes when the panel COLLAPSES is also not this listener's business: `Layout` moves it to the control that brings the panel back.

**Exactly one listener app-wide** is the rule this shape buys: no mount arms a hotkey of its own (`hotkey: false` in both `NavSearchSection` and `ExaPromptFlyout`), so a keystroke cannot open two boxes or pull focus into a box the reader was not looking at.

## Behavior

- A press works from a **collapsed** sidebar: the sidebar is expanded, the section is unrolled, and the caret lands in the input.
- Both box keys behave identically, and both fire while the caret is in **another text field**: `F` is a global accelerator, so the listener keeps no "ignore keys from text fields" rule. The panel key types nothing either, so it needs no such rule for the same reason.
- A press while the box is **already open focuses it** rather than toggling it away, and does not grow a second box.
- **The panel key toggles both ways** — it is one key, because the thing it acts on is a toggle. Collapsing while the caret is inside the sidebar (in the box, which unmounts with the section) does not strand it: `Layout`'s collapse effect moves the caret to the rail's chevron, or to the mobile hamburger on a narrow screen.
- The request is **consumed**, not counted: an old press cannot re-open the box later, when the rail is collapsed and expanded again.
- One keystroke opens exactly one box even with the header's flyout mounted beside the section.

## Props Interface

None. Renders `null` — the component has no DOM output of its own.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `useEffect` (react) | Hook | The listener's lifetime — added on mount, removed on unmount |
| `useUIStore` (`../../../stores/uiStore`) | Zustand store | `openNavSearch` and `toggleSidebar` — the two actions the listener performs |

## Usage Example

```tsx
// App.tsx — the shell, inside the router and above the layout. Mounted once,
// never unmounted.
<NavSearchHotkey />
```

## State Used

No local state, and no store state is read. The component only **writes**: `openNavSearch` from `useUIStore`. The `keydown` handler is registered on `window`.

## Related Components

- Parent: `frontend/src/App.tsx` — the shell and the router
- [[atlas/ui/components/features/agentInteraction/NavSearchSection|NavSearchSection]] — the box it opens, and the mount that answers the focus signal
- `frontend/src/stores/uiStore.ts` — `navSearchOpen`, `navSearchFocusPending` and the `openNavSearch` action
- [[atlas/ui/components/features/agentInteraction/ExaPromptFlyout|ExaPromptFlyout]] — the header mount, which deliberately arms no hotkey of its own
- [[dev-notes/frontend/command-box|The Command Box]] — the box, its verbs, and its mounts
