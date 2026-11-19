/**
 * NavSearchSection — the command box's NAV SIDEBAR attachment.
 *
 * IN THE UI THIS BOX IS CALLED "Search" (2026-09-18). The sidebar's box is a
 * NAVIGATOR: snappy, local, no model call, so it reads "Search" and its button
 * RUNS the command ("Go") instead of sending it. The header's flyout is the
 * Exa surface and keeps the Exa name and "Send". THE FILE, THE COMPONENT AND
 * THE STORE FIELDS CARRY THAT NAME TOO (2026-09-19): this file was
 * AskExaSidebarSection and the store's flag was `askExaOpen`, and both were
 * renamed once the user confirmed it — the box's identity is Search, and the
 * code now says what the box is. The copy that differs between the two mounts
 * lives in one place (CommandBoxPanel's `COPY`, keyed by `variant`).
 *
 * P2 of local/studies/exa-box-redesign-roadmap.md, the ATTACHMENT half. The
 * box used to be one component mounted in each page's header, so navigating
 * in place unmounted it, its open flag reset, and 19 pages never had it at
 * all. The sidebar is mounted ONCE by the shell and never remounts, which is
 * what makes the box reachable from every page and lets its thread survive a
 * navigation.
 *
 * THE THIRD PIECE OF THE DECOUPLING:
 *   - the ENGINE   — services/appNavigation (parse -> resolve -> act)
 *   - the PANEL    — CommandBoxPanel, which fills whatever container it is
 *                    given (its `variant`)
 *   - the ATTACHMENT — this file. The header's ExaPromptFlyout is the other
 *                    one; both mount the same hook and the same panel, so a
 *                    third attachment is a wrapper, not a rewrite.
 *
 * What this file deliberately does NOT own: the app-wide hotkey. Its listener
 * lives in the shell (NavSearchHotkey), because this section is not even rendered
 * while the sidebar is collapsed. What this file owns is the OTHER half of that
 * key: answering the focus signal, which only the place that holds the input
 * can do.
 *
 * It also owns the caret ON ARRIVAL: this is the one mount whose box can be
 * open on a fresh page load, so it is the one that has to put the reader ready
 * to type there (see the load effect below — P4's focus contract).
 *
 * AND IT OWNS THE TWO FLAGS BEING ONE FACT (2026-09-19). This is the one mount
 * whose open state is NOT the hook's own: the section draws from the store
 * (`navSearchOpen`, persisted), while the hook's flag is what arms Escape, the
 * click-away and the Frequent list. So the store's flag is the truth here and
 * the hook follows it (see the arm effect below), the hook reports every close
 * back through `onClose`, and the section attaches the hook's `wrapRef` at its
 * own boundary so the click-away has something to measure. A box restored open
 * by the store is therefore a box that can also be put away the two ordinary
 * ways — Escape, or a click somewhere else.
 */

import { useEffect } from 'react';
import { declaredPrimaryInput, pageFocusRequested } from '@/services/focusContract';
import { useNavSearchOpen, useUIStore } from '@/stores/uiStore';
import { CommandBoxPanel } from './CommandBoxPanel';
import { useCommandBox } from './useCommandBox';

export function NavSearchSection() {
  /**
   * The open flag rides `useUIStore`, beside `sidebarCollapsed` — UI state
   * ("unrolled right now"), not the `appearance.keepCommandBoxOpen`
   * preference. It lives in the store rather than in this component's
   * `useState` for the same reason the section is in the sidebar at all: the
   * store outlives a navigation, so the section comes back the way it was
   * left.
   */
  const open = useNavSearchOpen();
  const toggleNavSearch = useUIStore((state) => state.toggleNavSearch);
  /**
   * The hook's close, answered in the store (2026-09-19). A CLOSE, not the
   * toggle: the panel's ✕, Escape and a click away all report through the
   * hook's `onClose`, and a flip would re-open the box in the one case where
   * the two flags disagree. See the arm effect below for the whole rule.
   */
  const closeNavSearch = useUIStore((state) => state.closeNavSearch);
  /**
   * The other half of the app-wide Cmd/Ctrl+K (see NavSearchHotkey): the shell can
   * set store flags but cannot touch the input, which lives in this mount.
   */
  const focusPending = useUIStore((state) => state.navSearchFocusPending);
  const navSearchFocusSettled = useUIStore((state) => state.navSearchFocusSettled);

  /**
   * The box's SECOND mount (the header flyout is the first).
   *
   * `hotkey: false` — the app-wide Cmd/Ctrl+K is ONE listener, and it is the
   * shell's (NavSearchHotkey). A second armed mount here would open this box while
   * the header's flyout opened too: two boxes, one keystroke.
   *
   * `staysOpen: true` — this section is a standing region of the page, so a
   * resolved navigation must not take it away and must leave the input ready
   * for the next command: the point of a box in the sidebar is to visit
   * several pages from the keyboard. The header's mount asks for the same
   * thing only when `appearance.keepCommandBoxOpen` grants it.
   *
   * `exaFallthrough: false` — THIS IS THE MOUNT WITHOUT THE EXA PATH, and the
   * line is explicit so the decision is visible where it is taken (2026-09-18).
   * Measured: this column is 16rem and the flyout is 440px, and a streamed
   * answer plus a stop control do not fit here — the first thing to go below
   * the fold would be the input the reader came for. So this mount answers a
   * non-command LOCALLY in one line and never makes a model call; the header's
   * flyout keeps the Exa path (it passes `exaFallthrough: true`) because it has
   * the room and because it is where a dispatch is typed. Nothing else about
   * the two mounts differs — one hook, one panel, one set of verbs. The PANEL
   * draws the visible half of that decision: this variant has no "Full page"
   * control and no streamed-answer area, and its button is "Go" (see
   * CommandBoxPanel's `COPY` and `variant`).
   *
   * TWO OPTIONS MORE THAN THE FLYOUT TAKES (2026-09-19), and both are the same
   * fact: this mount's open state lives in the STORE, so the hook has to be told
   * where it starts (`initiallyOpen`) and has to report where it ends
   * (`onClose`). Both names are one line each here; the arm effect below is the
   * rest of the rule.
   */
  const commandBox = useCommandBox({
    hotkey: false,
    exaFallthrough: false,
    staysOpen: true,
    initiallyOpen: open,
    onClose: closeNavSearch,
  });
  const { setOpen, inputRef, wrapRef, open: hookOpen } = commandBox;

  /**
   * ANSWER THE FOCUS SIGNAL — the end of the app-wide key's journey.
   *
   * The section's rolled-out state (`navSearchOpen`) is the SECTION's; the box's
   * own open flag is the hook's, and it is not the same fact. Both are needed
   * before the reader can type: the box being open is what arms Escape and the
   * click-away handler inside the panel, and it is what the hook's own focus
   * effect keys on.
   *
   * The explicit focus is not bookkeeping — it is the case the hook's effect
   * cannot cover: a second Cmd/Ctrl+K while the box is ALREADY open sets no new
   * hook state, so no effect re-runs, and the caret would stay wherever it was.
   * The ref is the hook's own (the panel puts it on the input); nothing here
   * duplicates the hook's logic, it uses what the hook exposes.
   *
   * This is the FOCUS half only (2026-09-19): the flag itself is kept in step
   * with the store by the arm effect below, so a store write is never what
   * leaves Escape unarmed.
   */
  useEffect(() => {
    if (!focusPending) return;
    setOpen(true);
    inputRef.current?.focus();
    navSearchFocusSettled();
  }, [focusPending, setOpen, inputRef, navSearchFocusSettled]);

  /**
   * THE TWO FLAGS, KEPT AS ONE FACT (2026-09-19).
   *
   * The section draws from the STORE; the hook's own flag is what ARMS Escape
   * and the click-away and what loads the Frequent list. Two facts about one
   * box, so whenever they disagree the store's is the truth and the hook is
   * brought to it. Two arrivals fell through that gap, and both were visible:
   *
   *   - A FRESH PAGE LOAD (the reported defect). The flag is persisted, so a
   *     new tab draws the panel on its first paint while the hook's flag —
   *     which started false — left Escape, a click away and the shortcut list
   *     dead in that tab until Ctrl+K was pressed. The mount's starting state
   *     covers the arrival half (`initiallyOpen`); THIS effect is what keeps
   *     them together from then on.
   *   - THE TOGGLE. It writes the store only, so switching the box ON drew a
   *     panel that Escape and a click away could not put away, and switching it
   *     OFF left the hook armed behind a panel that was already gone.
   *
   * CLOSING DOES NOT COME THROUGH HERE. The hook reports its closes back to the
   * store (`onClose`), so by the time this effect runs both flags already say
   * closed — it is a mirror, never a referee, because forcing the hook open
   * again is exactly how Escape would stop working.
   */
  useEffect(() => {
    if (open !== hookOpen) setOpen(open);
  }, [open, hookOpen, setOpen]);

  /**
   * THE CARET ON ARRIVAL — P4's focus contract, and the defect that led here
   * (2026-09-18, the user: `nav sessions` opened a NEW TAB, the box was there,
   * "but I have to click it before I can type").
   *
   * A new tab is a FRESH PAGE LOAD, and the opener cannot focus it — that is
   * browser security, not a bug — so the new tab's own page has to put the
   * caret somewhere. Nothing did. The hook's focus effect keys on ITS `open`
   * flag, which started false, while this section renders from the store's,
   * which is the persisted one; so the box was restored and the caret was left
   * on the body. This effect closes that gap, and it is why the work belongs to
   * the ATTACHMENT rather than to the hook's host-agnostic logic.
   *
   * THE HOOK NO LONGER RACES IT (2026-09-19). The hook's flag is in step with
   * the store now (see the arm effect above), so its own focus effect does run
   * on an arrival — and it STANDS DOWN there (`initiallyOpen`: an arrival is
   * not an opening), so this rule stays the only one deciding where the caret
   * lands. The YIELD below is exactly what that buys.
   *
   * IT YIELDS TO THE PAGE (the roadmap's `data-autofocus`, services/focusContract):
   * a page built around its own first field declares it, and a standing box
   * that took the caret anyway would fight that page on every load. No
   * declaration means the caret is free, and the box — the one surface the
   * reader came to the sidebar for — takes it.
   *
   * AND IT YIELDS TO A REQUESTED ARRIVAL (2026-09-19). A navigation the reader
   * asked for hands the caret to the DESTINATION — the page's declared field, else
   * the `<main>` region — and the request is on the record before this effect
   * runs, because a tab is a fresh document and the token has to be readable on
   * arrival. This PEEKS (`pageFocusRequested`) and never consumes: honouring the
   * request is the shell's job, after the children's effects. Without this the two
   * would race, and the box — mounting last — would win every time, which is
   * exactly the "stuck in the nav panel" the user reported.
   *
   * The explicit ways in are NOT governed by this: Ctrl+K goes through the
   * focus signal above and lands in the box unconditionally, because a
   * keystroke that asks for the box is intent, not an arrival.
   */
  useEffect(() => {
    if (!open) return;
    if (pageFocusRequested()) return;
    if (declaredPrimaryInput()) return;
    inputRef.current?.focus();
  }, [open, inputRef]);

  /**
   * STICKY, not merely last in the column: the nav list is long enough to
   * scroll on most screens, and a section resting at the end of that flow
   * would sit below the fold — reachable only by scrolling the sidebar to
   * the bottom. Pinned, the box is one toggle away from any page. The opaque
   * `bg-base-200` matters: the nav list's overflow scrolls UNDER this, and a
   * positioned element paints above in-flow text.
   */
  return (
    <section
      className="sticky bottom-0 flex-shrink-0 border-t border-base-300 bg-base-200 px-4 pt-2 pb-4"
      aria-label="Search"
    >
      {/* THE BOX'S OWN REGION — and it is the boundary the hook's click-away
          measures (`wrapRef`). The hook closes when a `mousedown` lands
          outside this element, and a mount that never attaches the ref has no
          click-away at all — which was this mount until 2026-09-19, so the one
          gesture everyone expects from a box like this did nothing here.

          THE TOGGLE IS INSIDE IT ON PURPOSE: the panel's ✕, Escape and a click
          away are now ONE close path, and a close runs on `mousedown`. A toggle
          left outside the region would therefore close the box and then be
          flipped back ON by its own `change`, and the control would look
          broken. The reader's region is the whole section they opened the box
          from, not only the panel under it. */}
      <div ref={wrapRef}>
        {/* ONE ON/OFF CONTROL, and the house's control for one is a DaisyUI
            toggle (design/control-system.md) — not a bare checkbox, and no
            chevron: a control carries an icon OR text, not both. The tooltip
            opens LEFT because this sits against the sidebar's right edge and
            the aside is a scroll container, which clips what leaves its box
            (dev-notes/frontend/tooltip-clipping). The label reads "Search",
            the name this mount's box goes by — it is a navigator, not an Exa
            surface (see the docstring). */}
        <label className="flex cursor-pointer items-center justify-between gap-2">
          <span className="text-sm font-semibold">Search</span>
          <span
            className="tooltip tooltip-left"
            data-tip={open ? 'Hide the command box' : 'Search from any page'}
          >
            <input
              type="checkbox"
              className="toggle toggle-primary toggle-sm"
              checked={open}
              onChange={toggleNavSearch}
              aria-label="Search"
            />
          </span>
        </label>

        {/* NO `close` OVERRIDE HERE ANY MORE (2026-09-19): the panel takes the
            hook's `close` from `{...commandBox}`, and the hook reports every
            close — this ✕, Escape, a click away — through `onClose` into the
            store's flag. One path, so the ✕ and Escape cannot disagree about
            whether the box is open. */}
        {open && (
          <div className="mt-2">
            <CommandBoxPanel {...commandBox} variant="sidebar" />
          </div>
        )}
      </div>
    </section>
  );
}

export default NavSearchSection;
