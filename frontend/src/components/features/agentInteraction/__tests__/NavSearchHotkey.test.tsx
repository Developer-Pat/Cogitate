/**
 * NavSearchHotkey — the app-wide Cmd/Ctrl+K, and the sidebar's half of it.
 *
 * THE USER'S ASK (2026-09-18): one key, `Cmd/Ctrl+K`, reaches the command box
 * wherever it lives, with the NAV SIDEBAR as its home — and the sidebar's box is
 * the one that reads "Search" (2026-09-18; see NavSearchSection). The rules
 * this file pins down, and the reason each one is worth a test:
 *
 *  - the key opens the rolled-up section and lands the caret in its input (the
 *    whole point: type immediately, no mouse);
 *  - it expands the sidebar first when the rail is COLLAPSED — the case that
 *    forced the listener into the shell at all, since the section is not
 *    rendered while the rail is collapsed and a listener inside it would be
 *    dead exactly there;
 *  - a press while the box is already open FOCUSES it rather than toggling it
 *    away, and does not grow a second box;
 *  - ONE keystroke opens exactly ONE box even with the header flyout mounted
 *    beside the section — two armed listeners was the real bug (flyout opened
 *    AND focus pulled into the sidebar);
 *  - the request is CONSUMED: an old press cannot re-open the box later, when
 *    the rail is collapsed and expanded again.
 *
 * Cmd/Ctrl+F is the second key on the SAME listener (2026-09-19), so it is
 * pinned here rather than in a suite of its own — the point of adding it to
 * this listener is that it is the same action, and a second suite would invite
 * a second implementation. Two rules are specific to F and worth stating:
 *
 *  - `preventDefault` is not a nicety for it: without it the browser's FIND BAR
 *    opens on top of the box, which is the whole reason the key is claimed.
 *  - it must fire while the CARET IS IN ANOTHER TEXT FIELD — it is a global
 *    accelerator, so the usual "ignore keys from text fields" rule does not
 *    apply, and `fireEvent` on the field bubbles to the window listener exactly
 *    as the real browser does.
 *
 * Cmd/Ctrl+` is the third (2026-09-19): the NAV PANEL's toggle, running the same
 * store action the chevron and the hamburger run. It is pinned here because it is
 * the same listener — one place decides what the app's global keys are. The chord
 * was chosen by measurement, not taste (see the component's docstring): the user's
 * rule for it is CO-EXISTENCE — "don't claim the Ctrl+B from Firefox. we want to
 * co-exist" — so the key has to be one the BROWSER does nothing with, and the
 * census found Ctrl+` silent in both Firefox and Chromium.
 *
 * The harness mirrors App.tsx's real shape, which is the point of the test:
 * the listener is always mounted, the section only while the sidebar is
 * expanded.
 */

import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { NavSearchHotkey } from '../NavSearchHotkey';
import { NavSearchSection } from '../NavSearchSection';
import { ExaPromptFlyout } from '../ExaPromptFlyout';
import { useUIStore } from '@/stores/uiStore';

/** App.tsx's two lines: the shell's listener always, the section per sidebar. */
const Shell = () => {
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  return (
    <>
      <NavSearchHotkey />
      {!collapsed && <NavSearchSection />}
    </>
  );
};

const renderShell = () =>
  render(
    <MemoryRouter>
      <Shell />
    </MemoryRouter>
  );

const input = () => screen.queryByLabelText('Search commands') as HTMLInputElement | null;
/** Every command-box input on the page — one, if the one-listener rule holds. */
const boxes = () => document.querySelectorAll('[aria-label="Search commands"]');
const press = () => fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
const pressF = () => fireEvent.keyDown(window, { key: 'f', ctrlKey: true });

describe('NavSearchHotkey', () => {
  beforeEach(() => {
    useUIStore.setState({ sidebarCollapsed: false, navSearchOpen: false, navSearchFocusPending: false });
    localStorage.clear();
  });

  it('opens the rolled-up section on Cmd/Ctrl+K and leaves the caret in its input', () => {
    renderShell();
    expect(input()).toBeNull();

    press();

    expect(input()).not.toBeNull();
    expect(useUIStore.getState().navSearchOpen).toBe(true);
    // typing straight away is the point of the key — no click, no Tab
    expect(document.activeElement).toBe(input());
  });

  it('answers Cmd on macOS as well as Ctrl', () => {
    renderShell();
    fireEvent.keyDown(window, { key: 'k', metaKey: true });
    expect(input()).not.toBeNull();
  });

  it('expands the sidebar first when the rail is collapsed', () => {
    useUIStore.setState({ sidebarCollapsed: true });
    renderShell();
    // the section is not rendered at all here — nothing to press on the rail
    expect(input()).toBeNull();

    press();

    expect(useUIStore.getState().sidebarCollapsed).toBe(false);
    expect(input()).not.toBeNull();
    expect(useUIStore.getState().navSearchOpen).toBe(true);
    expect(document.activeElement).toBe(input());
  });

  it('focuses the input again when the box is already open — never a second box', () => {
    renderShell();
    press();
    const box = input()!;
    expect(document.activeElement).toBe(box);

    // the reader drifted off to something else on the page
    box.blur();
    expect(document.activeElement).not.toBe(box);

    press();

    expect(input()).toBe(box);
    expect(document.activeElement).toBe(box);
    expect(boxes().length).toBe(1);
  });

  it('opens exactly ONE box with the header flyout mounted beside the section', () => {
    // THE BUG THIS GUARDS (two listeners, one keystroke): with the header's
    // mount armed as well, Cmd/Ctrl+K opened the flyout AND pulled focus into
    // the sidebar box. The header's mount no longer arms a hotkey, so the
    // sidebar's box is what the key reaches — and the only box on screen.
    render(
      <MemoryRouter>
        <ExaPromptFlyout />
        <Shell />
      </MemoryRouter>
    );
    expect(screen.getByLabelText('Ask Exa — the system agent')).toBeTruthy(); // the trigger, closed

    press();

    expect(boxes().length).toBe(1);
    expect(boxes()[0]).toBe(input());
    expect(document.activeElement).toBe(input());
  });

  it('CONSUMES the request — an old press cannot re-open the box later', () => {
    renderShell();
    press();
    expect(input()).not.toBeNull();

    // the reader puts it away, then collapses and expands the rail
    fireEvent.click(screen.getByLabelText('Close Search'));
    act(() => {
      useUIStore.setState({ sidebarCollapsed: true });
      useUIStore.setState({ sidebarCollapsed: false });
    });

    // a counter the section compared against would re-fire its stale request
    // here; the flag is cleared the moment the section answers it
    expect(useUIStore.getState().navSearchFocusPending).toBe(false);
    expect(input()).toBeNull();
  });

  // Cmd/Ctrl+F — the second key on this one listener (2026-09-19).

  it('opens the box on Cmd/Ctrl+F — the same action as Cmd/Ctrl+K', () => {
    renderShell();
    expect(input()).toBeNull();

    pressF();

    expect(input()).not.toBeNull();
    expect(useUIStore.getState().navSearchOpen).toBe(true);
    expect(document.activeElement).toBe(input());
  });

  it('answers Cmd+F on macOS as well as Ctrl+F', () => {
    renderShell();
    fireEvent.keyDown(window, { key: 'f', metaKey: true });
    expect(input()).not.toBeNull();
    expect(document.activeElement).toBe(input());
  });

  it('preventDefaults Cmd/Ctrl+F — the browser find bar never gets the key', () => {
    renderShell();
    // `fireEvent` reports the dispatch result: `false` means the listener
    // cancelled the default, which is what suppresses the browser's find bar.
    // The same holds for the key the box has always claimed.
    expect(pressF()).toBe(false);
    expect(press()).toBe(false);
  });

  it('fires while the caret is inside ANOTHER text field', () => {
    // A global accelerator, not a text-field key: a reader mid-sentence in a
    // page's own input presses Cmd/Ctrl+F to search, and the listener must not
    // step aside for it.
    render(
      <MemoryRouter>
        <Shell />
        <input aria-label="a page's own field" />
      </MemoryRouter>
    );
    const field = screen.getByLabelText("a page's own field") as HTMLInputElement;
    field.focus();
    expect(document.activeElement).toBe(field);
    expect(input()).toBeNull();

    // fired ON the field, bubbling to the shell's window listener as it really
    // would in the browser
    expect(fireEvent.keyDown(field, { key: 'f', ctrlKey: true })).toBe(false);

    expect(input()).not.toBeNull();
    expect(document.activeElement).toBe(input());
  });

  it('expands the sidebar first on Cmd/Ctrl+F too', () => {
    useUIStore.setState({ sidebarCollapsed: true });
    renderShell();
    expect(input()).toBeNull();

    pressF();

    expect(useUIStore.getState().sidebarCollapsed).toBe(false);
    expect(input()).not.toBeNull();
    expect(document.activeElement).toBe(input());
  });

  // Cmd/Ctrl+` — the nav panel toggle (2026-09-19).

  it('toggles the navigation panel on Cmd/Ctrl+` — one key, both ways', () => {
    renderShell();
    expect(useUIStore.getState().sidebarCollapsed).toBe(false);

    // `fireEvent` reports the dispatch result: `false` means the listener
    // cancelled the default
    expect(fireEvent.keyDown(window, { key: '`', ctrlKey: true })).toBe(false);
    expect(useUIStore.getState().sidebarCollapsed).toBe(true);

    fireEvent.keyDown(window, { key: '`', ctrlKey: true });
    expect(useUIStore.getState().sidebarCollapsed).toBe(false);
  });

  it('answers Cmd+` on macOS, and the shifted spelling of the same key', () => {
    renderShell();

    fireEvent.keyDown(window, { key: '`', metaKey: true });
    expect(useUIStore.getState().sidebarCollapsed).toBe(true);

    // Shift+` produces `~`: the same physical key, just as free in both browsers,
    // and refusing it would be a keystroke that looks identical to doing nothing
    fireEvent.keyDown(window, { key: '~', ctrlKey: true });
    expect(useUIStore.getState().sidebarCollapsed).toBe(false);
  });

  it('leaves the panel alone on a bare backtick', () => {
    // No modifier, no accelerator: typing a backtick is typing.
    renderShell();
    fireEvent.keyDown(window, { key: '`' });
    expect(useUIStore.getState().sidebarCollapsed).toBe(false);
  });
});
