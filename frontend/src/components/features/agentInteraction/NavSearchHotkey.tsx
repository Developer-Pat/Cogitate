/**
 * NavSearchHotkey — the ONE app-wide key listener (2026-09-18).
 *
 * THE USER'S ASK (2026-09-18): one key — Cmd/Ctrl+K — reaches the box wherever
 * it lives, with the NAV SIDEBAR as its home. The sidebar rail it should expand
 * is part of that: "the side panel" is where they go to navigate pages.
 *
 * THREE KEYS NOW, ONE LISTENER (2026-09-19). The component keeps the name of its
 * first job; what it owns is the app's GLOBAL keys, and there is exactly one
 * listener for all of them:
 *
 *   Ctrl+K / Ctrl+F  →  open the Search box and put the caret in it
 *   Ctrl+`           →  toggle the navigation panel (its own key, below)
 *
 * A key on this listener is a key NO MOUNT ARMS. The natural-looking place for a
 * listener is inside the widget that owns the box, and that is where it used to
 * live (`useCommandBox`'s `hotkey` option): it cannot live there any more, because
 * with the sidebar as the box's home the section is rendered ONLY while the rail
 * is expanded (`{!sidebarCollapsed && <NavSearchSection />}`) — a listener inside
 * it would be dead for exactly the case the key exists to fix. This component is
 * rendered by the shell unconditionally and never unmounts.
 *
 * WHAT IT DOES NOT DO: reach into the box. It writes ONE store action. The section
 * renders the box and owns the input's ref, so the section answers the focus
 * signal (see uiStore's `navSearchFocusPending`) — the shell does not get a second
 * copy of the hook to duplicate its logic in.
 *
 * EXACTLY ONE LISTENER APP-WIDE is the rule this shape buys: no mount arms a
 * hotkey of its own (`hotkey: false` everywhere — the header flyout and the
 * sidebar section both), so a keystroke cannot open two boxes or pull focus into a
 * box the reader was not looking at. Two armed mounts WAS the bug.
 *
 * THE KEYS THEMSELVES:
 *  - Cmd on macOS, Ctrl elsewhere, and `preventDefault` is the entire mechanism:
 *    without it Ctrl+K is the address bar's search and Ctrl+F the browser's find
 *    bar. Both are the study's platform test passed (`local/studies/
 *    keyboard-accelerators.md` §1) — the platform has an answer for them, and it
 *    means nothing in an app with its own search.
 *  - **Ctrl+`** toggles the nav panel. Chosen by MEASUREMENT, not taste: the
 *    browser must not have an answer for it, because the user's rule for this key
 *    is CO-EXISTENCE, not claiming — "don't claim the Ctrl+B from Firefox. we want
 *    to co-exist." A census over the candidate chords (trusted key events, Firefox
 *    145 and Chromium 1228, page reporting every keydown and every
 *    resize/visibility change) found Ctrl+` silent in BOTH: the page receives it
 *    and the browser does nothing, so there is no browser action to suppress. The
 *    controls in the same run behaved as expected — Ctrl+B is Firefox's bookmarks
 *    sidebar, Ctrl+Shift+B a toolbar in both, Alt+1 Firefox's tab switch, Ctrl+T a
 *    new tab — so the apparatus was demonstrably able to detect a claim.
 *  - F is a GLOBAL ACCELERATOR, not a text-field key, so the listener keeps NO
 *    "ignore keys from text fields" rule: it fires while the caret is in another
 *    input (the Exa box, a page's own field), which is exactly where a reader who
 *    wants to search from that field already is. The panel toggle types nothing
 *    either, so it needs no such rule for the same reason.
 *
 * WHERE THE CARET GOES WHEN THE PANEL COLLAPSES is the shell's business, not this
 * listener's: see `Layout`'s collapse effect, which moves it to the control that
 * brings the panel back.
 */

import { useEffect } from 'react';
import { useUIStore } from '@/stores/uiStore';

export function NavSearchHotkey() {
  const openNavSearch = useUIStore((state) => state.openNavSearch);
  const toggleSidebar = useUIStore((state) => state.toggleSidebar);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const key = e.key.toLowerCase();
      if ((e.ctrlKey || e.metaKey) && (key === 'k' || key === 'f')) {
        e.preventDefault();
        openNavSearch();
        return;
      }
      // THE NAV PANEL. Silent in both browsers (see the docstring), so nothing
      // here is being taken from the platform. Shift is tolerated: Ctrl+Shift+`
      // produced the same `~` key and is just as free, and refusing it would be
      // a keystroke that looks identical to the user doing nothing.
      if ((e.ctrlKey || e.metaKey) && (key === '`' || key === '~')) {
        e.preventDefault();
        toggleSidebar();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [openNavSearch, toggleSidebar]);

  return null;
}

export default NavSearchHotkey;
