/**
 * NavSearchSection — the box's SIDEBAR attachment (P2).
 *
 * The rules this file pins down:
 *  - the section is closed until its toggle is switched on, and the store is
 *    the flag (that is the state the header shortcut will read);
 *  - the panel FILLS the column instead of anchoring under a trigger — the
 *    one mistake that would silently restore the 440px popover and overflow
 *    the 16rem sidebar;
 *  - the panel is height-capped with its own scroll, so the nav list cannot
 *    be pushed off-screen;
 *  - collapsing is a render decision, not a reset: the typed text is still
 *    there when the section is unrolled again;
 *  - Cmd/Ctrl+K is NOT taken by this mount (the shell's single listener
 *    reaches it — see NavSearchHotkey.test.tsx);
 *  - a command typed in the sidebar actually moves the page;
 *  - a navigation does not close this box (the sidebar is a standing region, not
 *    a popover the host page owns) — and the CARET goes to the page, not back to
 *    the input (2026-09-19: "we want to jump to the page we just opened /
 *    navigated to"). The shell's half of that handoff is `ShellHandoff` below,
 *    which is App.tsx's `Layout` reduced to the two lines this needs: a `<main>`
 *    the caret can land in, and the effect that honours the request;
 *  - the box remembers that it is open, and on a fresh load the caret is in its
 *    input — unless the page declares its own primary input (`data-autofocus`,
 *    P4's focus contract), which the box must not fight;
 *  - the box makes NO MODEL CALL IN THIS MOUNT (2026-09-18): an input that is
 *    not a command is answered locally, and `exa <question>` opens the Exa chat
 *    tab. The header's flyout is the mount that KEEPS the Exa path (it passes
 *    `exaFallthrough: true`, see useCommandBox), so the split is asserted on
 *    both sides: the flyout's own suite covers its bridge, and these tests pin
 *    that the sidebar sends nothing.
 *  - THE BOX READS "Search" HERE (2026-09-18): the section's label, its toggle
 *    and its tooltips say Search, the panel's own name is Search, and the
 *    button RUNS the command ("Go" — nothing is sent from a navigator). The
 *    header flyout keeps the Exa name and "Send", asserted in its own suite.
 *  - THE SIDEBAR'S PANEL DROPS THE FLYOUT'S TWO CONTROLS: no "Full page" and no
 *    streamed-answer area (the one-line outcome is this box's answer). The
 *    flyout keeps both — see the flyout's suite.
 *  - THE BOX IS A COMBOBOX (2026-09-19): the input keeps the DOM focus, Down/Up
 *    move the ACTIVE ROW over the one listbox model (candidates and Frequent
 *    together), Enter accepts the active row, Escape closes the list FIRST and
 *    the box on the second press, and Tab leaves the box as one stop — no row
 *    is a tab stop. See the study the pattern comes from,
 *    local/studies/keyboard-accelerators.md §3.
 */

import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { useEffect, useRef, type ReactElement } from 'react';
import { NavSearchSection } from '../NavSearchSection';
import { useUIStore } from '@/stores/uiStore';
import { claimPageFocus } from '@/services/focusContract';

/** Where the router ended up — `nav` moves the current page. */
const LocationProbe = () => {
  const loc = useLocation();
  return <span data-testid="loc">{loc.pathname}</span>;
};

/**
 * A page that takes the focus for its own first field the moment it arrives.
 * Pages really do this (a search box, a chat input), and it is what costs the
 * reader the box they were typing in.
 */
const GrabbingPage = () => {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { ref.current?.focus(); }, []);
  return <input ref={ref} aria-label="the page's own field" />;
};

const renderSection = () =>
  render(
    <MemoryRouter>
      <LocationProbe />
      <NavSearchSection />
    </MemoryRouter>
  );

/**
 * THE SHELL'S HANDOFF HALF (2026-09-19) — `Layout` in App.tsx, reduced to the
 * two things this file needs: the `<main>` region the caret can land in, and the
 * effect that honours a pending request on arrival. The real shell is verified
 * live (the gate for a UI change is the reported action, re-run in the app); what
 * this pins is the COMPOSITION — the box asks (`requestPageFocus`) and the shell
 * answers (`claimPageFocus`), with the box mounting as a SIBLING of the page.
 */
const ShellHandoff = ({ children }: { children: ReactElement }) => {
  const loc = useLocation();
  useEffect(() => {
    claimPageFocus();
  }, [loc.pathname]);
  return <main tabIndex={-1}>{children}</main>;
};

/**
 * THE SHELL'S REAL SHAPE: the section is mounted beside the routed page, not
 * inside it — which is the whole reason the box survives a navigation at all.
 */
const renderSectionInShell = () =>
  render(
    <MemoryRouter initialEntries={['/']}>
      <LocationProbe />
      <NavSearchSection />
      <ShellHandoff>
        <Routes>
          <Route path="/" element={<span />} />
          <Route path="/logs" element={<GrabbingPage />} />
        </Routes>
      </ShellHandoff>
    </MemoryRouter>
  );

const toggle = () => screen.getByRole('checkbox', { name: 'Search' });
const input = () => screen.queryByLabelText('Search commands') as HTMLInputElement | null;
/** The panel's shell — the element the `sidebar` variant draws. */
const shell = () => input()!.closest('.max-h-64') as HTMLElement;
/** The panel's submit — this mount's button runs the command, it does not send. */
const go = () => screen.getByLabelText('Go') as HTMLButtonElement;

/**
 * A page that declares its primary input the way the focus contract says to
 * (`data-autofocus`, see services/focusContract). `claim` is the page taking
 * the caret for itself — what a page built around one field really does, and
 * the thing the box must not fight.
 */
const DeclaringPage = ({ claim = false }: { claim?: boolean }) => {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { if (claim) ref.current?.focus(); }, [claim]);
  return <input ref={ref} data-autofocus aria-label="the page's primary input" />;
};

/** The section beside a routed page — the shell's real shape. */
const renderSectionBesidePage = (page: ReactElement) =>
  render(
    <MemoryRouter initialEntries={['/']}>
      <NavSearchSection />
      <Routes>
        <Route path="/" element={page} />
      </Routes>
    </MemoryRouter>
  );

describe('NavSearchSection', () => {
  beforeEach(() => {
    useUIStore.setState({ navSearchOpen: false });
    localStorage.clear();
  });

  it('starts closed, and its toggle rolls the box out', () => {
    renderSection();
    expect(input()).toBeNull();

    fireEvent.click(toggle());

    expect(input()).not.toBeNull();
    expect(useUIStore.getState().navSearchOpen).toBe(true);
  });

  it('fills the column and caps its own height instead of anchoring', () => {
    renderSection();
    fireEvent.click(toggle());

    const el = shell();
    expect(el.className).toContain('relative');
    expect(el.className).toContain('overflow-y-auto');
    // the popover shell would overflow the 16rem sidebar and drop the panel
    // below the wheel instead of inside the section
    expect(el.className).not.toContain('absolute');
    expect(el.className).not.toContain('440px');
    // the input is the one control that must not scroll away: in a capped
    // column a long answer pushes it out of view, so the row pins
    expect(input()!.parentElement!.className).toContain('sticky');
  });

  it('collapsing is not a reset — the typed text survives', () => {
    renderSection();
    fireEvent.click(toggle());
    fireEvent.change(input()!, { target: { value: 'nav logs' } });

    fireEvent.click(toggle());
    expect(input()).toBeNull();

    fireEvent.click(toggle());
    expect(input()!.value).toBe('nav logs');
  });

  it("puts the box away from the panel's own ✕", () => {
    renderSection();
    fireEvent.click(toggle());

    fireEvent.click(screen.getByLabelText('Close Search'));

    expect(input()).toBeNull();
    expect(useUIStore.getState().navSearchOpen).toBe(false);
  });

  it('arms no hotkey of its own — the shell holds the app-wide one', () => {
    // One listener app-wide. The section cannot hold it: while the sidebar is
    // collapsed this component is not rendered at all, so the key would be dead
    // exactly where it is needed. It is the shell's (NavSearchHotkey, mounted in
    // App.tsx) and it answers through the store flag this section consumes —
    // see NavSearchHotkey.test.tsx for that half.
    renderSection();
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
    expect(input()).toBeNull();
    expect(useUIStore.getState().navSearchOpen).toBe(false);
  });

  it('runs a command from its new home — nav logs moves the page', async () => {
    renderSection();
    fireEvent.click(toggle());
    fireEvent.change(input()!, { target: { value: 'nav logs' } });

    fireEvent.click(go());

    await waitFor(() => expect(screen.getByTestId('loc').textContent).toBe('/logs'));
  });

  it('stays open through a navigation, and the PAGE takes the caret', async () => {
    // THE DEFECT (2026-09-18, the user): "If I am using the side panel for
    // navigation, I would like it to remain stable not jump around." A panel
    // that vanishes the instant it takes you somewhere cannot be navigated with.
    //
    // AND THE SECOND HALF (2026-09-19, the same reader): "it leaves us stuck in
    // the nav panel … we want to jump to the page we just opened / navigated to."
    // Stable does not mean the caret stays: the box stays standing, and the
    // arrival takes the caret — the page's own field if it has one, else <main>.
    renderSectionInShell();
    fireEvent.click(toggle());
    const box = input()!;
    box.focus();
    fireEvent.change(box, { target: { value: 'nav logs' } });
    expect(document.activeElement).toBe(box);

    fireEvent.click(go());
    await waitFor(() => expect(screen.getByTestId('loc').textContent).toBe('/logs'));

    // the page swap did not take the box with it — same element, still standing
    expect(input()).toBe(box);
    // and the caret is ON THE PAGE, not in the panel the reader just used
    await waitFor(() => expect(document.querySelector('main')!.contains(document.activeElement)).toBe(true));
    expect(document.activeElement).not.toBe(box);
  });
});

/**
 * THE RENAME AND THE SPLIT (2026-09-18).
 *
 * The user settled this box's NAME — "change the name of the box from Ask Exa
 * to Search" — and with it the two things a navigator does not carry: a "Full
 * page" control (the sidebar box IS a way around the app) and a
 * streamed-answer area (nothing streams locally; `exa <question>` opens the Exa
 * chat tab). Both of those stay in the header flyout, which is the mount that
 * actually sends — see ExaPromptFlyout.test.tsx, which pins the other half of
 * the split.
 */
describe('NavSearchSection — the box is "Search", and the flyout\'s controls are gone', () => {
  beforeEach(() => {
    useUIStore.setState({ navSearchOpen: false });
    localStorage.clear();
  });

  it('names the box Search — the section label, its toggle, and the panel itself', () => {
    renderSection();
    // rolled up, the section's own label is the only "Search" on screen
    expect(screen.getByRole('checkbox', { name: 'Search' })).toBeTruthy();
    expect(screen.getByText('Search')).toBeTruthy();

    fireEvent.click(toggle());

    // the PANEL names itself too — its aria-label is the variant's copy, not
    // the section's, so the rename has to have reached the panel as well
    expect(shell().getAttribute('aria-label')).toBe('Search');
    // and the input's label says what this box takes: commands
    expect(screen.getByLabelText('Search commands')).toBeTruthy();
  });

  it('runs the command from a button that says Go — nothing is "sent" from a navigator', () => {
    renderSection();
    fireEvent.click(toggle());

    expect(go().textContent).toBe('Go');
    expect(screen.queryByText('Send')).toBeNull();
    expect(screen.queryByLabelText('Send to Exa')).toBeNull();
  });

  it('draws NO "Full page" control and NO streamed-answer area', () => {
    renderSection();
    fireEvent.click(toggle());
    fireEvent.change(input()!, { target: { value: 'what does the compactor do?' } });
    fireEvent.click(go());

    // the one-line outcome IS this box's answer — no Q/A transcript beside it
    expect(screen.getByText('Unknown command — help lists them.')).toBeTruthy();
    expect(screen.queryByText(/You:/)).toBeNull();

    // and the coexisting Exa-page path belongs to the flyout, not to this mount
    expect(screen.queryByText('Full page')).toBeNull();
    expect(screen.queryByLabelText('Open the Exa page')).toBeNull();
  });
});

/**
 * THE CARET ON ARRIVAL (2026-09-18) — P4's focus contract.
 *
 * The defect that led here: the reader typed `nav sessions` in the box, it
 * opened a NEW TAB, and in that tab the box was open with the caret on the body
 * — "I have to click it before I can type". A new tab is a FRESH PAGE LOAD and
 * the opener cannot focus it (browser security), so the new tab's own page has
 * to put the caret somewhere: the store remembers that the box is open, and
 * this is the half that leaves the reader ready to type.
 *
 * The contract's other half is the YIELD: a page that declares its own primary
 * input (`data-autofocus`) keeps the caret, because a standing box that took it
 * anyway would fight that page on every load.
 */
describe('NavSearchSection — the caret on arrival', () => {
  beforeEach(() => {
    useUIStore.setState({ navSearchOpen: false });
    localStorage.clear();
  });

  it('takes the caret when the box is already open on a fresh load', () => {
    // what a new tab looks like: the remembered open state draws the panel on
    // the first paint, and nothing else has asked for the caret
    useUIStore.setState({ navSearchOpen: true });

    renderSection();

    const box = input()!;
    expect(box).not.toBeNull();
    expect(document.activeElement).toBe(box);
  });

  it('claims nothing when the section arrives rolled up', () => {
    renderSection();
    expect(input()).toBeNull();
    expect(document.activeElement).toBe(document.body);
  });

  it("yields to a page that declares its primary input (P4's data-autofocus)", () => {
    useUIStore.setState({ navSearchOpen: true });

    renderSectionBesidePage(<DeclaringPage />);

    // the page has spoken for the caret, so the box leaves it where it is —
    // even though the box is the only thing asking
    expect(input()).not.toBeNull();
    expect(document.activeElement).not.toBe(input());
  });

  it('does not take the caret off a page that claimed it', () => {
    useUIStore.setState({ navSearchOpen: true });

    renderSectionBesidePage(<DeclaringPage claim />);

    expect(document.activeElement).toBe(screen.getByLabelText("the page's primary input"));
    expect(document.activeElement).not.toBe(input());
  });
});

/**
 * THE TWO FLAGS, KEPT AS ONE FACT (2026-09-19) — the fresh-tab defect.
 *
 * The report: a navigation opened a NEW TAB, and the box was there in it, open.
 * The store's flag is persisted, so the panel was drawn — but the HOOK's own
 * flag started false, and that flag is what arms Escape and the click-away and
 * what loads the Frequent list. So in that tab Escape and a click away did
 * nothing and the shortcut list was empty, until Ctrl+K was pressed. The same
 * gap swallowed the TOGGLE, which writes the store and nothing else.
 *
 * The rule these tests pin: wherever the store's flag goes the hook's follows
 * (the arm effect), and a close starting in the hook comes back out to the
 * store (`onClose`) — so the two flags can never disagree, in either direction.
 */
describe('NavSearchSection — the two flags stay in step', () => {
  beforeEach(() => {
    useUIStore.setState({ navSearchOpen: false });
    localStorage.clear();
  });

  /** What a fresh tab looks like: the persisted flag says the box is open. */
  const arriveOpen = () => useUIStore.setState({ navSearchOpen: true });

  /** A destination this browser has already been to. */
  const aShortcut = () =>
    localStorage.setItem(
      'cog-nav-history',
      JSON.stringify([{ to: '/logs', label: 'Logs', count: 3, lastAt: 1 }])
    );

  it('fills Frequent when the box is open on a fresh load', () => {
    aShortcut();
    arriveOpen();

    renderSection();

    expect(input()).not.toBeNull();
    expect(screen.getByText('Frequent')).toBeTruthy();
    expect(screen.getByText('Logs')).toBeTruthy();
  });

  it('arms Escape on a fresh load — and Escape closes BOTH flags', () => {
    arriveOpen();
    renderSection();
    expect(input()).not.toBeNull();

    fireEvent.keyDown(window, { key: 'Escape' });

    // The panel is gone AND the store agrees it is closed. Arming Escape
    // without that second half is the desync the rewire exists to prevent:
    // the panel would stay drawn while the hook believed it was closed.
    expect(input()).toBeNull();
    expect(useUIStore.getState().navSearchOpen).toBe(false);
  });

  it('arms the click-away on a fresh load', () => {
    arriveOpen();
    renderSection();

    fireEvent.mouseDown(document.body);

    expect(input()).toBeNull();
    expect(useUIStore.getState().navSearchOpen).toBe(false);
  });

  it('measures the click-away at the box — a click inside it does not close', () => {
    // The hook closes on any mousedown outside its `wrapRef`, and THIS mount
    // used to attach no ref at all — so the close could never fire. The ref is
    // the section's own boundary now (the toggle is inside it on purpose: a
    // close that ran on the toggle's mousedown would be flipped back on by the
    // toggle's own change).
    arriveOpen();
    renderSection();

    fireEvent.mouseDown(input()!);

    expect(input()).not.toBeNull();
    expect(useUIStore.getState().navSearchOpen).toBe(true);
  });

  it('arms the same when the TOGGLE is what opened it', () => {
    renderSection();
    fireEvent.click(toggle());

    fireEvent.keyDown(window, { key: 'Escape' });

    expect(input()).toBeNull();
    expect(useUIStore.getState().navSearchOpen).toBe(false);
  });

  it('disarms with the flag — a toggle-off leaves no listener behind', () => {
    renderSection();
    fireEvent.click(toggle());
    fireEvent.click(toggle());
    expect(input()).toBeNull();

    fireEvent.keyDown(window, { key: 'Escape' });

    // nothing to close, and — the half that matters — nothing re-opened
    expect(input()).toBeNull();
    expect(useUIStore.getState().navSearchOpen).toBe(false);
  });
});

/**
 * NO MODEL CALL FROM THIS MOUNT (2026-09-18).
 *
 * The two mounts now differ by exactly one option on the hook they share —
 * `exaFallthrough` — and THIS is the mount without it: the sidebar is a
 * navigator. So an input that is not a command is answered locally and
 * instantly, `exa <question>` opens the Exa chat tab, and neither ever
 * constructs a WebSocket. The flyout's own suite covers the other side (it
 * keeps the bridge, and its Exa tests are unchanged); if a future change puts
 * an Exa call back into THIS attachment, this file fails.
 */
class CountingWebSocket {
  static instances: CountingWebSocket[] = [];
  url: string;
  constructor(url: string) {
    this.url = url;
    CountingWebSocket.instances.push(this);
  }
  send() {}
  close() {}
}

describe('NavSearchSection — the mount without the Exa path', () => {
  beforeEach(() => {
    useUIStore.setState({ navSearchOpen: false });
    localStorage.clear();
    CountingWebSocket.instances = [];
    (global as unknown as { WebSocket: unknown }).WebSocket = CountingWebSocket;
    (window as unknown as { open: unknown }).open = vi.fn();
  });

  it('answers a question LOCALLY — no socket, instant, nothing opened', () => {
    renderSection();
    fireEvent.click(toggle());
    fireEvent.change(input()!, { target: { value: 'what does the compactor do?' } });

    fireEvent.click(go());

    // no waitFor: the answer is local and immediate
    expect(screen.getByText('Unknown command — help lists them.')).toBeTruthy();
    expect(CountingWebSocket.instances.length).toBe(0);
    expect(window.open).not.toHaveBeenCalled();
  });

  it('offers the verb on a typo — the local answer, with no model turn', () => {
    renderSection();
    fireEvent.click(toggle());
    fireEvent.change(input()!, { target: { value: 'navv logs' } });

    fireEvent.click(go());

    expect(screen.getByText('Did you mean `nav`?')).toBeTruthy();
    expect(CountingWebSocket.instances.length).toBe(0);
  });

  it('`exa <question>` opens the Exa chat tab, and reaches no socket', () => {
    renderSection();
    fireEvent.click(toggle());
    fireEvent.change(input()!, { target: { value: 'exa is search broken?' } });

    fireEvent.click(go());

    // A TAB APP IS A WINDOW OF ITS OWN, and it is reached by NAME now (2026-09-19):
    // one window per destination, so asking again switches to the one already
    // there instead of stacking a duplicate.
    expect(window.open).toHaveBeenCalledWith('/exa', 'cog-/exa');
    expect(CountingWebSocket.instances.length).toBe(0);
    // the chat tab cannot take the question yet, so it stays here — not lost
    expect(input()!.value).toBe('exa is search broken?');
  });
});

/**
 * THE BOX IS A COMBOBOX (2026-09-19) — the reported behaviour, in jsdom.
 *
 * THE COMPLAINT: a keyboard user presses ArrowDown and nothing happens. The box
 * reached its rows with TAB — one stop per result — so the natural key for a
 * list did nothing, and the list announced itself to assistive tech as a run of
 * links rather than as ONE control with an active option. The pattern is
 * local/studies/keyboard-accelerators.md §3: DOM focus STAYS in the input, the
 * list carries a VIRTUAL focus (`aria-activedescendant`), Down/Up move over the
 * rows, Enter accepts one, Escape closes the list BEFORE the box, and Tab leaves
 * the box as ONE stop.
 *
 * These are the jsdom half — the half that matters most (a real caret in a real
 * browser, driven by real key presses) is what the session reported separately.
 * jsdom does not move focus on Tab, so "Tab leaves the box" is pinned here as
 * what it actually is in the markup: no row is a tab stop, and Tab is not
 * consumed.
 */
describe('NavSearchSection — the box is a combobox', () => {
  beforeEach(() => {
    useUIStore.setState({ navSearchOpen: false });
    localStorage.clear();
    (window as unknown as { open: unknown }).open = vi.fn();
  });

  /** The row the input's `aria-activedescendant` names (null = editing). */
  const activeRow = (box: HTMLInputElement) => {
    const id = box.getAttribute('aria-activedescendant');
    return id ? document.getElementById(id) : null;
  };

  /** The candidate list's rows, in draw order. */
  const pageRows = () =>
    within(screen.getByRole('listbox', { name: 'Pages' })).getAllByRole('option');

  /**
   * The reported case: a command whose answer is a LIST, run from the keyboard.
   * Enter is the way in — which is also the box's oldest promise (`nav <page>`
   * runs exactly as it always did; the "typed command" test below pins it).
   */
  const runTheListing = async () => {
    renderSection();
    fireEvent.click(toggle());
    const box = input()!;
    box.focus();
    fireEvent.change(box, { target: { value: 'nav list' } });
    fireEvent.keyDown(box, { key: 'Enter' });
    await waitFor(() => expect(screen.getByText('Pages')).toBeTruthy());
    return box;
  };

  /** A shortcut already earned — the Frequent list draws a row for it. */
  const aShortcut = () =>
    localStorage.setItem(
      'cog-nav-history',
      JSON.stringify([{ to: '/logs', label: 'Logs', count: 3, lastAt: 1 }])
    );

  /** The Frequent list's rows, in draw order. */
  const frequentRows = () =>
    within(screen.getByRole('listbox', { name: 'Frequent' })).getAllByRole('option');

  /**
   * Three shortcuts, most-used first — enough rows that a first/last question
   * (Up, Home, End) has a different answer at each end.
   */
  const shortcuts = () =>
    localStorage.setItem(
      'cog-nav-history',
      JSON.stringify([
        { to: '/logs', label: 'Logs', count: 3, lastAt: 1 },
        { to: '/sessions', label: 'Sessions', count: 2, lastAt: 1 },
        { to: '/tools', label: 'Tools', count: 1, lastAt: 1 },
      ])
    );

  /** The box, open and idle with the caret in the input — the Frequent state. */
  const openIdleBox = () => {
    renderSection();
    fireEvent.click(toggle());
    const box = input()!;
    box.focus();
    return box;
  };

  it('draws the rows as ONE listbox of options, and starts on the first', async () => {
    const box = await runTheListing();

    // the input is the combobox, and it says what is on screen
    expect(box.getAttribute('role')).toBe('combobox');
    expect(box.getAttribute('aria-expanded')).toBe('true');
    const list = screen.getByRole('listbox', { name: 'Pages' });
    expect(box.getAttribute('aria-controls')).toContain(list.getAttribute('id')!);

    const rows = pageRows();
    expect(rows.length).toBeGreaterThan(1);

    // THE ACTIVE ROW EXISTS AND IS NAMED — the point of the whole pattern
    const row = activeRow(box)!;
    expect(row).toBe(rows[0]);

    // AND IT IS VISIBLE WITHOUT BEING DIMMED: gray-dim means DISABLED in this
    // app, so the active row wears the house's selected-row tint instead
    expect(row.className).toContain('bg-primary/10');
    expect(row.className).toContain('text-primary');
    expect(row.className).not.toContain('text-disabled');
  });

  it('moves the ACTIVE ROW on Down, and the DOM focus never leaves the input', async () => {
    const box = await runTheListing();
    const rows = pageRows();
    const first = activeRow(box)!;

    // THE KEY THE READER REACHED FOR: consumed by the list, not by the page
    expect(fireEvent.keyDown(box, { key: 'ArrowDown' })).toBe(false);

    const second = activeRow(box)!;
    expect(second).not.toBe(first);
    expect(rows.indexOf(second as HTMLElement)).toBe(rows.indexOf(first as HTMLElement) + 1);
    expect(second.className).toContain('bg-primary/10');
    expect(first.className).not.toContain('bg-primary/10');
    // THERE IS NO SECOND THING TO JUMP TO — the input still has the caret
    expect(document.activeElement).toBe(box);

    // Up walks back one row at a time
    expect(fireEvent.keyDown(box, { key: 'ArrowUp' })).toBe(false);
    expect(activeRow(box)).toBe(first);

    // ...and from the FIRST row it returns to EDITING the input, which costs no
    // focus move because the focus never left
    fireEvent.keyDown(box, { key: 'ArrowUp' });
    expect(box.getAttribute('aria-activedescendant')).toBeNull();
    expect(document.activeElement).toBe(box);

    // Home/End jump the list while it is up...
    expect(fireEvent.keyDown(box, { key: 'End' })).toBe(false);
    expect(activeRow(box)).toBe(rows[rows.length - 1]);
    fireEvent.keyDown(box, { key: 'Home' });
    expect(activeRow(box)).toBe(rows[0]);
  });

  it('accepts the active row on Enter — it opens it', async () => {
    const box = await runTheListing();
    fireEvent.keyDown(box, { key: 'ArrowDown' });
    const row = activeRow(box)!;
    const [, path] = (row.textContent || '').split(' — ');
    const title = row.querySelector('span')!.textContent!;

    fireEvent.keyDown(box, { key: 'Enter' });

    // A ROW LANDS BY ITS DESTINATION (2026-09-19 — the reported defect): the
    // reader picked a place, so the page they are on moves to it — the same axis
    // as the `nav` verb that produced the list, and NOT a new tab.
    await waitFor(() => expect(screen.getByTestId('loc').textContent).toBe(path));
    expect(window.open).not.toHaveBeenCalled();
    expect(screen.getByText('Opened ' + title)).toBeTruthy();
  });

  it('asks for a TAB on Ctrl/⌘+Enter — the other axis, from the same list', async () => {
    const box = await runTheListing();
    fireEvent.keyDown(box, { key: 'ArrowDown' });
    const row = activeRow(box)!;
    const [, path] = (row.textContent || '').split(' — ');

    // ctrl/⌘+Enter is the `open` axis: the same modifier that opens a link in a
    // new tab anywhere else, and the escape hatch that keeps the list from being
    // a one-axis surface.
    fireEvent.keyDown(box, { key: 'Enter', ctrlKey: true });

    await waitFor(() => expect(window.open).toHaveBeenCalledWith(path, 'cog-' + path));
    // ...and this page did not move
    expect(screen.getByTestId('loc').textContent).toBe('/');
  });

  it('runs the TYPED COMMAND on Enter when no row is active — unchanged', async () => {
    // THE OLD PROMISE, and the one a combobox is likeliest to break: with no row
    // active, Enter is the command, not a row.
    renderSection();
    fireEvent.click(toggle());
    const box = input()!;
    fireEvent.change(box, { target: { value: 'nav logs' } });
    expect(box.getAttribute('aria-activedescendant')).toBeNull();

    fireEvent.keyDown(box, { key: 'Enter' });

    await waitFor(() => expect(screen.getByTestId('loc').textContent).toBe('/logs'));
    expect(window.open).not.toHaveBeenCalled();
  });

  it('clears the active row when the reader types again', async () => {
    // WHY THIS IS THE RULE and not "typing activates the first row": these lists
    // are not FILTERED by what is typed, so a row activated by a keystroke would
    // be a row the reader never chose — Enter after `nav logs` would open
    // whatever sat at the top of Frequent instead of going to Logs.
    const box = await runTheListing();
    expect(activeRow(box)).not.toBeNull();

    fireEvent.change(box, { target: { value: 'nav logs' } });
    expect(box.getAttribute('aria-activedescendant')).toBeNull();

    fireEvent.keyDown(box, { key: 'Enter' });
    await waitFor(() => expect(screen.getByTestId('loc').textContent).toBe('/logs'));
    expect(window.open).not.toHaveBeenCalled();
  });

  it('leaves the box as ONE tab stop on Tab — no row is a tab stop', async () => {
    const box = await runTheListing();
    const rows = pageRows();
    expect(rows.length).toBeGreaterThan(1);

    // reaching a row is ArrowDown; Tab is how you LEAVE
    for (const row of rows) expect(row.getAttribute('tabindex')).toBe('-1');
    // and Tab is NOT consumed — nothing here traps the focus in the box
    expect(fireEvent.keyDown(box, { key: 'Tab' })).toBe(true);

    // the list is put away on the way out, not left standing behind
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(input()).toBe(box);
  });

  it('closes the LIST first on Escape, and the box on the second press', async () => {
    const box = await runTheListing();

    fireEvent.keyDown(window, { key: 'Escape' });

    expect(input()).toBe(box);                          // the box is still here
    expect(screen.queryByRole('listbox')).toBeNull();   // the list is not
    expect(box.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(box);           // and the caret never left

    fireEvent.keyDown(window, { key: 'Escape' });

    expect(input()).toBeNull();
    expect(useUIStore.getState().navSearchOpen).toBe(false);
  });

  it('treats Frequent as the SAME listbox — Down reaches it, Enter opens it', async () => {
    aShortcut();
    renderSection();
    fireEvent.click(toggle());
    const box = input()!;
    box.focus();

    const row = within(screen.getByRole('listbox', { name: 'Frequent' })).getByRole('option', {
      name: /Logs/,
    });
    expect(row.getAttribute('tabindex')).toBe('-1');

    fireEvent.keyDown(box, { key: 'ArrowDown' });
    expect(box.getAttribute('aria-activedescendant')).toBe(row.getAttribute('id'));

    fireEvent.keyDown(box, { key: 'Enter' });
    // A SHORTCUT ROW IS A DESTINATION TOO (2026-09-19): the same rule as a result
    // row — it moves the page the reader is on, unless they asked for a tab.
    await waitFor(() => expect(screen.getByTestId('loc').textContent).toBe('/logs'));
    expect(window.open).not.toHaveBeenCalled();
  });

  /**
   * THE FREQUENT LIST IS PART OF THE POPUP (2026-09-19 — the user: "I have a
   * frequent list which I cannot get to").
   *
   * The gap was not that its rows were unreachable — Down walked into them — it
   * was that nothing else about the box knew they were a list: `aria-expanded`
   * said false with rows drawn, Home/End were refused (they were the caret keys,
   * because no list was "up"), the first Escape closed the whole BOX instead of
   * the list in front of the reader, and once it was away there was no key that
   * brought it back. One popup, every list — these pin that.
   */
  it('counts Frequent as the open popup: aria-expanded, End and Home reach it', () => {
    shortcuts();
    const box = openIdleBox();

    // THE BOX ADMITS THE LIST IS THERE. This was the lie: rows drawn, `false`.
    const list = screen.getByRole('listbox', { name: 'Frequent' });
    expect(box.getAttribute('aria-expanded')).toBe('true');
    expect(box.getAttribute('aria-controls')).toContain(list.getAttribute('id')!);

    // ...so the list's own jump keys work over it, as they do over a result list
    const rows = frequentRows();
    expect(rows.length).toBe(3);
    expect(fireEvent.keyDown(box, { key: 'End' })).toBe(false);
    expect(activeRow(box)).toBe(rows[rows.length - 1]);
    fireEvent.keyDown(box, { key: 'Home' });
    expect(activeRow(box)).toBe(rows[0]);
  });

  it('opens the list at its LAST row on Up when no row is active', () => {
    // THE USER'S SECOND REPORT: "the up button is not needed... let me check".
    // It was not doing anything at all — with no row active, `-1 + -1` is still
    // no row — and the APG's editable combobox says the opposite: Down opens the
    // list at the FIRST option, Up at the LAST. So a keyboard user has a way in
    // to the BOTTOM of Frequent, not only one Down per row from the top.
    shortcuts();
    const box = openIdleBox();
    expect(box.getAttribute('aria-activedescendant')).toBeNull();   // editing

    expect(fireEvent.keyDown(box, { key: 'ArrowUp' })).toBe(false);  // consumed

    const rows = frequentRows();
    const row = activeRow(box)!;
    expect(row).toBe(rows[rows.length - 1]);
    expect(row.textContent).toMatch(/Tools/);
    // AND IT IS VISIBLE WITHOUT BEING DIMMED — gray-dim means DISABLED here
    expect(row.className).toContain('bg-primary/10');
    expect(row.className).not.toContain('text-disabled');
    // the caret never moved: the list's focus is virtual
    expect(document.activeElement).toBe(box);

    // Up again walks BACK up the list (it does not fall off the end)
    fireEvent.keyDown(box, { key: 'ArrowUp' });
    expect(activeRow(box)).toBe(rows[rows.length - 2]);
  });

  it('scrolls the active row into view as the selection moves — the panel does it, not the page', () => {
    // THE REPORTED DEFECT (2026-09-19): "the arrows DO scroll through the list
    // one item at a time starting at the bottom which is off the screen... the
    // list panel itself no longer scrolls using the arrows". Up opened the list
    // at its LAST row and NOTHING scrolled down to it — moving the virtual focus
    // focuses no element, so no browser scrolling follows, and the panel's own
    // scrolling was precisely the arrow keys' old behaviour that the combobox
    // consumed. Scrolling the row in is PART OF THE PATTERN
    // (local/studies/keyboard-accelerators.md §3), not a nicety on top of it.
    //
    // jsdom implements no `scrollIntoView` at all, so a stub is the only way to
    // see the call — and `block: 'nearest'` is the half that matters: it scrolls
    // the minimum that reveals the row, which is what keeps the PAGE still.
    const scrolled: Array<{ el: Element; arg: unknown }> = [];
    const proto = Element.prototype as unknown as { scrollIntoView?: (arg?: unknown) => void };
    proto.scrollIntoView = function (this: Element, arg?: unknown) {
      scrolled.push({ el: this, arg });
    };
    try {
      shortcuts();
      const box = openIdleBox();
      const rows = frequentRows();

      // Up from a CLOSED list opens it at its LAST row — the row that was off
      // screen before this fix, and the reported case
      fireEvent.keyDown(box, { key: 'ArrowUp' });

      const last = rows[rows.length - 1];
      expect(activeRow(box)).toBe(last);
      expect(scrolled.length).toBeGreaterThan(0);
      expect(scrolled[scrolled.length - 1].el).toBe(last);
      expect(scrolled[scrolled.length - 1].arg).toEqual({ block: 'nearest', inline: 'nearest' });

      // AND IT FOLLOWS THE SELECTION — every move, not only the opening one
      fireEvent.keyDown(box, { key: 'ArrowUp' });
      const above = frequentRows()[rows.length - 2];
      expect(activeRow(box)).toBe(above);
      expect(scrolled[scrolled.length - 1].el).toBe(above);

      // a box with no row active has nothing to keep in view, so a key that
      // takes the list away (Escape) scrolls nothing
      const before = scrolled.length;
      fireEvent.keyDown(window, { key: 'Escape' });
      expect(activeRow(box)).toBeNull();
      expect(scrolled.length).toBe(before);
    } finally {
      delete proto.scrollIntoView;
    }
  });

  it('puts the Frequent popup away on Escape, and Down/Up bring it back', () => {
    // THE SETTLED ORDER (§5 item 4: "Esc closes the list first, then the box")
    // now holds in front of EVERY list — including the one that is not a
    // command's answer. Before this, the first Escape took the whole box and the
    // reader lost the caret and their place with it.
    shortcuts();
    const box = openIdleBox();

    fireEvent.keyDown(window, { key: 'Escape' });

    expect(input()).toBe(box);                                  // the box is still here
    expect(screen.queryByRole('listbox')).toBeNull();           // the popup is not
    expect(activeRow(box)).toBeNull();
    expect(box.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(box);                   // the caret never left
    // and its heading and controls went with the rows — no Clear button over an
    // empty list
    expect(screen.queryByText('Frequent')).toBeNull();
    expect(screen.queryByLabelText('Clear navigation history')).toBeNull();

    // DOWN brings it back at the FIRST row...
    expect(fireEvent.keyDown(box, { key: 'ArrowDown' })).toBe(false);
    expect(activeRow(box)).toBe(frequentRows()[0]);

    // ...UP at the LAST (the closed list is what Up is for)
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('listbox')).toBeNull();
    fireEvent.keyDown(box, { key: 'ArrowUp' });
    const rows = frequentRows();
    expect(activeRow(box)).toBe(rows[rows.length - 1]);

    // and the box takes its own two steps again: the list first (it is back,
    // because Up just reopened it), then the box
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(input()).toBe(box);
    expect(screen.queryByRole('listbox')).toBeNull();

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(input()).toBeNull();
    expect(useUIStore.getState().navSearchOpen).toBe(false);
  });

  it('opens the list on Alt+Down without moving in it', () => {
    // The APG's third way in, and the one key of its table the box had left
    // unwired: it OPENS the popup and steps nowhere. With no row active there is
    // no position to keep, so the first row takes the virtual focus.
    shortcuts();
    const box = openIdleBox();

    expect(fireEvent.keyDown(box, { key: 'ArrowDown', altKey: true })).toBe(false);
    const rows = frequentRows();
    expect(activeRow(box)).toBe(rows[0]);          // opened, at the top

    // the key does not STEP: with a row already active it stays where it is
    fireEvent.keyDown(box, { key: 'ArrowDown' });                // -> the second row
    expect(activeRow(box)).toBe(rows[1]);
    fireEvent.keyDown(box, { key: 'ArrowDown', altKey: true });  // Alt+Down again
    expect(activeRow(box)).toBe(rows[1]);                        // unmoved

    // and it is one more way back to a popup Escape put away
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('listbox')).toBeNull();
    fireEvent.keyDown(box, { key: 'ArrowDown', altKey: true });
    expect(activeRow(box)).toBe(frequentRows()[0]);
  });

  it('brings the popup back when a command runs after Escape — the same list twice', async () => {
    // A dismissal is about what WAS on screen, never about what ARRIVES. The
    // `candidateList` effect sees a list arrive by its content, so running the
    // SAME listing again changes nothing it can see — the command itself is what
    // has to clear the dismissal, or a list the reader just earned would arrive
    // hidden.
    shortcuts();
    const box = await runTheListing();
    expect(screen.getByRole('listbox', { name: 'Pages' })).toBeTruthy();

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('listbox')).toBeNull();

    fireEvent.change(box, { target: { value: 'nav list' } });
    fireEvent.keyDown(box, { key: 'Enter' });

    await waitFor(() =>
      expect(screen.getByRole('listbox', { name: 'Pages' })).toBeTruthy()
    );
    expect(box.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByRole('listbox', { name: 'Frequent' })).toBeTruthy();
  });
});
