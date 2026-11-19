---
title: NavSearchSection
type: atlas-component
path: frontend/src/components/features/agentInteraction/NavSearchSection.tsx
confidence: high
updated: 2026-09-19
tags: [type/component, domain/atlas-ui, domain/navigation]
---
# NavSearchSection

**Path**: `frontend/src/components/features/agentInteraction/NavSearchSection.tsx`
**Last Updated**: 2026-09-19

## Purpose

The command box's **nav sidebar attachment** — the mount the UI calls **Search**. It renders the sidebar's labelled toggle and, when the section is unrolled, `CommandBoxPanel` with `variant="sidebar"`.

This mount is a **navigator**: it answers locally, makes **no model call**, and its destinations come from the app's own route map (`services/appNavigation`). The header's `ExaPromptFlyout` is the other mount of the same hook and the same panel — it keeps the Exa path, the "Send" button, "Full page" and the streamed answer; this one has none of those, and its button is **Go**.

The section is mounted **once by the shell** (`App.tsx`), inside the sidebar column, and only while the sidebar is expanded (`{!sidebarCollapsed && <NavSearchSection />}`). That mount point is what makes the box reachable from every page and what lets its state survive a navigation; a per-page header mount could do neither.

## What the mount decides

`useCommandBox({ hotkey: false, exaFallthrough: false, staysOpen: true })` — the three options, and the reason each is set here:

| Option | Reason |
|---|---|
| `hotkey: false` | The app-wide Cmd/Ctrl+K is **one** listener, and it is the shell's (`NavSearchHotkey`). A second armed mount here would open this box while the header's flyout opened too: two boxes, one keystroke. |
| `exaFallthrough: false` | This mount has **no Exa path**. Measured: the column is 16rem against the flyout's 440px, and a streamed answer plus a stop control do not fit — the first thing to go below the fold would be the input the reader came for. An input the parser cannot read is therefore answered locally in one line (`noCommandAnswer`) and never becomes a model turn. `exa <question>` still opens the Exa chat tab, which owns the call, its own Stop and its own session. |
| `staysOpen: true` | The section is a standing region of the page, so a resolved navigation must not take it away and must leave the input ready for the next command. The header's mount asks for the same thing only when `appearance.keepCommandBoxOpen` grants it. |

The visible half of `exaFallthrough: false` is drawn by the panel, not here: the `sidebar` variant has no "Full page" control and no streamed-answer area.

## The open flag, and why it is not local state

The section renders from the **store's** `navSearchOpen` (`useUIStore`), not from the hook's own `open` flag. The store outlives a navigation and the local flag does not, so the store is what makes the section come back the way it was left. `useUIStore` persists this field alone (localStorage `cogitate-ui`), so the section is also closed-or-open the same way on a new tab.

The panel's **✕** is wired as *collapse the section*: it closes the hook's box and toggles the store flag.

Escape and a click outside do **not** put this mount's box away: those are the hook's own handlers, and they clear the hook's `open` flag — the one this section does not render from. The panel stays on screen. The ✕ and the toggle are the two ways out of this mount.

## Answering the focus signal

The shell cannot put the caret in the input — the ref lives in `useCommandBox`, inside this mount. So the shell writes the one-shot `navSearchFocusPending` signal and this section answers it: set the box open, focus the input, clear the signal. The explicit focus is not bookkeeping: a second Cmd/Ctrl+K while the box is already open sets no new hook state, so no effect re-runs and the caret would otherwise stay where it was.

## The caret on arrival

This is the one mount whose box can be open on a **fresh page load** (the open flag is persisted), and a new tab's page has to put the caret somewhere by itself — the opener cannot, which is browser security rather than a bug. On load, while the section is open, it focuses the input **unless a page declares its own first field** (`services/focusContract` — `declaredPrimaryInput()`) **or a navigation the reader asked for is waiting to be honoured** (`pageFocusRequested()`): in that case the arrival belongs to the page, and the shell's `claimPageFocus()` is what takes the caret there (the declared field, else `<main>`). The box PEEKS at the request and never consumes it — the shell owns honouring it, and a box that took its own copy would win the race it used to win every time ("stuck in the nav panel"). A page built around its own first field is not fought for the caret on every load — and that page takes it for itself, because a **lazy route mounts after this effect has already run** (`claimDeclaredPrimaryInput()`). The explicit ways in are not governed by this: Ctrl+K goes through the focus signal above and lands in the box unconditionally.

A row's landing is not this component's decision either: a list row is a DESTINATION, so it lands where `targetForPath` and the `nav` axis send it — in the page the reader is on — with `Ctrl/⌘+Enter` asking for the tab instead. See [[dev-notes/frontend/keyboard-and-focus|Keyboard and Focus]].

## Props Interface

None. The component takes no props — a bare `<NavSearchSection />` is complete.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `useCallback`, `useEffect` (react) | Hooks | The focus-signal effect, the caret-on-arrival effect, and the memoised collapse callback |
| `useNavSearchOpen`, `useUIStore` (`../../../stores/uiStore`) | Zustand store | `navSearchOpen` (the open flag) + `toggleNavSearch`, `navSearchFocusPending`, `navSearchFocusSettled` |
| `useCommandBox` (`./useCommandBox`) | Hook | The box's state, verbs and actions — shared with the header flyout |
| `CommandBoxPanel` (`./CommandBoxPanel`) | Child component | The panel itself, drawn with `variant="sidebar"` (its copy and control set are keyed on that variant) |
| `declaredPrimaryInput` (`../../../services/focusContract`) | Service | The page-level claim on the caret, which this section yields to |

## Usage Example

```tsx
// App.tsx — the sidebar column. The section is FIRST, and the nav <ul> takes
// the remaining height; the shell's NavSearchHotkey is mounted separately.
{!sidebarCollapsed && <NavSearchSection />}
<ul className="menu menu-vertical flex-nowrap p-4 pt-0 flex-1 w-full min-h-0">
  {/* the navigation list */}
</ul>
```

## State Used

- **Store (read)**: `navSearchOpen`; `navSearchFocusPending`. **Store (write)**: `toggleNavSearch` (the toggle and the ✕), `navSearchFocusSettled` (consume the signal).
- **Local state**: none — the input, the results, the outcome line and the shortcut list all live in `useCommandBox`.
- **Refs**: none of its own; it uses the hook's `inputRef`.

The section's wrapper is `sticky bottom-0` with an opaque `bg-base-200`, and carries `aria-label="Search"`: the nav list is long enough to scroll on most screens, and the opaque background is what keeps the scrolling list from painting through it.

## Related Components

- Parent: `frontend/src/App.tsx` — the shell, which mounts this section and the hotkey listener
- The other mount of the same hook + panel: `frontend/src/components/features/agentInteraction/ExaPromptFlyout.tsx` (see [[atlas/ui/components/features/agentInteraction/ExaPromptFlyout|ExaPromptFlyout]])
- `frontend/src/components/features/agentInteraction/CommandBoxPanel.tsx` — the panel, and the `variant` that carries the two mounts' visible differences
- `frontend/src/components/features/agentInteraction/useCommandBox.ts` — the box's state and the verb dispatch
- `frontend/src/stores/uiStore.ts` — the open flag and the focus signal
- `frontend/src/services/focusContract.ts` — the caret contract
- [[atlas/ui/services/appNavigation|appNavigation]] — the verb engine and the page map
- [[atlas/ui/components/features/agentInteraction/NavSearchHotkey|NavSearchHotkey]] — the app-wide Ctrl+K that opens this box
- [[dev-notes/frontend/command-box|The Command Box]] — the verbs, the two landings, and the mounts
