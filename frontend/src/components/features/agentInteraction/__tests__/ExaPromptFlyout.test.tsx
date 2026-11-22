/** ExaPromptFlyout — the ask-Exa flyout: opens, asks, streams, fails loud,
 *  and (form 2) takes you to the page Exa named.
 *
 * The rules this file pins down (see the component's docstring +
 * local/exa-flyout/study.md): chunks COALESCE into one line, Send stays
 * disabled until there is text, a failure is LOUD (never a silent
 * flatline), Escape closes, the coexisting "Full page" path still reaches
 * the Exa page — and a navigation request either lands on a real
 * destination or is refused, never guessed at.
 */

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { ExaPromptFlyout } from '../ExaPromptFlyout';
import { recordNav } from '@/services/navHistory';
import { FOCUS_HANDOFF_KEY } from '@/services/focusContract';
import { useSettingsStore } from '@/stores/settingsStore';
import { useUIStore } from '@/stores/uiStore';

class MockWebSocket {
  url: string;
  static instances: MockWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  sent: string[] = [];
  closed = false;
  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }
  send(data: string) { this.sent.push(data); }
  close() { this.closed = true; }
  static openAll() { MockWebSocket.instances.forEach((i) => i.onopen?.()); }
  static emitAll(data: string) { MockWebSocket.instances.forEach((i) => i.onmessage?.({ data })); }
  static reset() { MockWebSocket.instances = []; }
}

/**
 * The component uses useNavigate, so it renders inside a router.
 *
 * THE LOCATION PROBE (2026-09-18): `nav`/`goto` move the CURRENT page, so an
 * in-place navigation is a change to the ROUTER, not a `window.open` call. The
 * probe renders where the router ended up, which is what those tests assert
 * now. `window.open` stays the right assertion for a TAB landing — `open`/
 * `show`, and Exa's own `OPEN:` marker.
 */
const LocationProbe = () => {
  const loc = useLocation();
  return <span data-testid="loc">{loc.pathname + loc.search}</span>;
};

const renderFlyout = () =>
  render(
    <MemoryRouter>
      <LocationProbe />
      <ExaPromptFlyout />
    </MemoryRouter>
  );

/** Where the router ended up — the in-place landing, asserted. */
const landedAt = () => screen.getByTestId('loc').textContent ?? '';

const openFlyout = () => fireEvent.click(screen.getByLabelText('Ask Exa — the system agent'));
const type = (v: string) => fireEvent.change(screen.getByLabelText('Ask Exa a question'), { target: { value: v } });
const send = () => fireEvent.click(screen.getByLabelText('Send to Exa'));

describe('ExaPromptFlyout', () => {
  beforeEach(() => {
    MockWebSocket.reset();
    (global as unknown as { WebSocket: unknown }).WebSocket = MockWebSocket;
    (window as unknown as { open: unknown }).open = vi.fn();
  });

  it('renders the Exa button and opens the flyout', () => {
    renderFlyout();
    expect(screen.queryByText('Ask Exa')).toBeNull();
    openFlyout();
    expect(screen.getByText('Ask Exa')).toBeTruthy();
    expect(screen.getByLabelText('Ask Exa a question')).toBeTruthy();
  });

  it('keeps Send disabled until there is text (the empty-input rule)', () => {
    renderFlyout();
    openFlyout();
    expect((screen.getByLabelText('Send to Exa') as HTMLButtonElement).disabled).toBe(true);
    type('where?');
    expect((screen.getByLabelText('Send to Exa') as HTMLButtonElement).disabled).toBe(false);
  });

  it('asks over the bridge, tells Exa the page map, and coalesces chunks', () => {
    renderFlyout();
    openFlyout();
    type('what does the compactor do?');
    send();

    const ws = MockWebSocket.instances[0];
    expect(ws.url).toContain('/api/v1/external-agent/ws');
    act(() => { MockWebSocket.openAll(); });
    // the ask carries the generated map — that is how Exa knows the paths
    expect(ws.sent[0]).toContain('what does the compactor do?');
    expect(ws.sent[0]).toContain('OPEN:');
    expect(ws.sent[0]).toContain('/settings');

    act(() => { MockWebSocket.emitAll(JSON.stringify({ type: 'message', text: 'It rolls ' })); });
    act(() => { MockWebSocket.emitAll(JSON.stringify({ type: 'message', text: 'a summary.' })); });
    expect(screen.getByText('It rolls a summary.')).toBeTruthy();
  });

  it('shows a tool call as live activity while Exa works', () => {
    renderFlyout();
    openFlyout();
    type('check the backend');
    send();
    act(() => { MockWebSocket.openAll(); });
    act(() => { MockWebSocket.emitAll(JSON.stringify({ type: 'tool_call', update: { title: 'Verify Backend Health' } })); });
    expect(screen.getByText(/Verify Backend Health/)).toBeTruthy();
  });

  it('prefers the backend reply on done', async () => {
    renderFlyout();
    openFlyout();
    type('q');
    send();
    act(() => { MockWebSocket.openAll(); });
    act(() => { MockWebSocket.emitAll(JSON.stringify({ type: 'message', text: 'partial' })); });
    act(() => { MockWebSocket.emitAll(JSON.stringify({ type: 'done', reply: 'the full reply' })); });
    await waitFor(() => expect(screen.getByText('the full reply')).toBeTruthy());
  });

  it('reports a failure loudly instead of flatlining (the skill rule)', () => {
    renderFlyout();
    openFlyout();
    type('q');
    send();
    act(() => { MockWebSocket.openAll(); });
    act(() => { MockWebSocket.emitAll(JSON.stringify({ type: 'status', status: 'time_limit', message: 'Exa hit the turn limit' })); });
    expect(screen.getByText(/Exa hit the turn limit/)).toBeTruthy();
  });

  it('closes on Escape', () => {
    renderFlyout();
    openFlyout();
    expect(screen.getByLabelText('Ask Exa a question')).toBeTruthy();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByLabelText('Ask Exa a question')).toBeNull();
  });

  it('keeps the coexisting path: Full page reaches the Exa page', () => {
    const onOpen = vi.fn();
    render(
      <MemoryRouter>
        <ExaPromptFlyout onOpenExaPage={onOpen} />
      </MemoryRouter>
    );
    openFlyout();
    fireEvent.click(screen.getByLabelText('Open the Exa page'));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  // ── form 2: Exa opens the page ────────────────────────────────────────
  it('takes the user to the page Exa named, and never shows the marker', async () => {
    renderFlyout();
    openFlyout();
    // NOTE (2026-09-18): this used to type "open the themes page", which now
    // starts with a VERB — so it takes the command path instead of reaching
    // Exa. That is the trade the two axes accept (`exa <question>` is the
    // escape hatch for a question that opens with a verb word). This test is
    // about Exa NAMING a page, so it asks in a shape no verb claims.
    type('where do the themes live?');
    send();
    act(() => { MockWebSocket.openAll(); });
    act(() => {
      MockWebSocket.emitAll(JSON.stringify({
        type: 'done',
        reply: 'Themes live in Settings, under Appearance.\n\nOPEN: themes',
      }));
    });
    // the stable name is what makes a repeated request focus, not stack
    await waitFor(() =>
      expect(window.open).toHaveBeenCalledWith('/settings?tab=appearance', 'cog-/settings?tab=appearance')
    );
    // the machinery stays out of the reader's way
    expect(screen.queryByText(/OPEN:/)).toBeNull();
    expect(screen.getByText(/Themes live in Settings/)).toBeTruthy();
    expect(screen.getByText(/Opened Settings/)).toBeTruthy();
  });

  it('refuses an unknown destination loudly, and opens nothing', async () => {
    renderFlyout();
    openFlyout();
    type('go to the quantum page');
    send();
    act(() => { MockWebSocket.openAll(); });
    act(() => {
      MockWebSocket.emitAll(JSON.stringify({ type: 'done', reply: 'Not sure.\n\nOPEN: /quantum-page' }));
    });
    await waitFor(() => expect(screen.getByText(/no page at/i)).toBeTruthy());
    expect(window.open).not.toHaveBeenCalled();
  });
});

describe('ExaPromptFlyout — the command verbs', () => {
  beforeEach(() => {
    MockWebSocket.reset();
    (global as unknown as { WebSocket: unknown }).WebSocket = MockWebSocket;
    (window as unknown as { open: unknown }).open = vi.fn();
  });

  it('resolves "nav logs" locally: no socket, no Exa call', async () => {
    renderFlyout();
    openFlyout();
    type('nav logs');
    send();

    // `nav` moves the CURRENT page — a router change, not a tab
    await waitFor(() => expect(landedAt()).toBe('/logs'));
    expect(window.open).not.toHaveBeenCalled();
    // THE POINT: a command is deterministic — it never reaches the LLM
    expect(MockWebSocket.instances.length).toBe(0);
    expect(screen.getByText(/Opened/i)).toBeTruthy();
  });

  it('refuses a destination it does not know, and opens nothing', async () => {
    renderFlyout();
    openFlyout();
    type('nav the quantumbulator');
    send();

    await waitFor(() => expect(screen.getByText(/do not know a page|no page at/i)).toBeTruthy());
    expect(window.open).not.toHaveBeenCalled();
    expect(MockWebSocket.instances.length).toBe(0);
  });

  it('offers candidates for a wiki tie instead of picking one', async () => {
    (global as unknown as { fetch: unknown }).fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        results: [
          { path: 'dev-notes/a', title: 'Note A', score: 7, snippet: 'x' },
          { path: 'dev-notes/b', title: 'Note B', score: 7, snippet: 'y' },
        ],
      }),
    }));
    renderFlyout();
    openFlyout();
    type('dev architecture');
    send();

    await waitFor(() => expect(screen.getByText(/which one/i)).toBeTruthy());
    expect(window.open).not.toHaveBeenCalled();
    expect(screen.getByText('Note A')).toBeTruthy();
    expect(screen.getByText('Note B')).toBeTruthy();
  });

  it('teaches the shape when a verb arrives with no destination', async () => {
    renderFlyout();
    openFlyout();
    type('nav');
    send();
    await waitFor(() => expect(screen.getByText(/Nothing to open/i)).toBeTruthy());
    expect(MockWebSocket.instances.length).toBe(0);
  });
});

/** The `exa` verb, the synonyms, and the listing. */
describe('ExaPromptFlyout — exa, synonyms and the listing', () => {
  beforeEach(() => {
    MockWebSocket.reset();
    (global as unknown as { WebSocket: unknown }).WebSocket = MockWebSocket;
    (window as unknown as { open: unknown }).open = vi.fn();
  });

  it('nav logging reaches Logs — a synonym, which fuzzy distance cannot do', async () => {
    renderFlyout();
    openFlyout();
    type('nav logging');
    send();
    // `nav` moves the CURRENT page (2026-09-18) — a router change, not a tab
    await waitFor(() => expect(landedAt()).toBe('/logs'));
    // edit distance can never map "logging" -> "logs" (a different word, not a
    // misspelling); this only works because the alias table declares it
    expect(window.open).not.toHaveBeenCalled();
    expect(MockWebSocket.instances.length).toBe(0);
  });

  it('nav tests reaches the Testing Dashboard', async () => {
    renderFlyout();
    openFlyout();
    type('nav tests');
    send();
    await waitFor(() => expect(landedAt()).toBe('/testing-dashboard'));
    expect(window.open).not.toHaveBeenCalled();
  });

  it('open/show take a TAB where nav/goto move the page — the two axes', async () => {
    renderFlyout();
    openFlyout();
    type('show logs');
    send();
    await waitFor(() => expect(window.open).toHaveBeenCalledWith('/logs', 'cog-/logs'));
    // the page did NOT move — that is the whole distinction
    expect(landedAt()).toBe('/');

    (window.open as unknown as { mockClear: () => void }).mockClear();
    type('open logs');
    send();
    await waitFor(() => expect(window.open).toHaveBeenCalledWith('/logs', 'cog-/logs'));
    expect(landedAt()).toBe('/');
  });

  it('a name that is BOTH a page and a tab follows the VERB (the live `nav sessions` report)', async () => {
    // 2026-09-18, the user: `nav sessions` opened a NEW TAB while `nav logs`
    // moved the current page — the same verb. `sessions` names the tab app too,
    // and the tab stage ran first, so the tab always won and the verb could not
    // matter. The axis now decides, and it has to travel INTO the resolution to
    // do it (see resolveTarget / dualPage).
    renderFlyout();
    openFlyout();
    type('nav sessions');
    send();
    await waitFor(() => expect(landedAt()).toBe('/sessions'));
    expect(window.open).not.toHaveBeenCalled();

    // `open` on the same name still takes the tab — that is the other axis
    (window.open as unknown as { mockClear: () => void }).mockClear();
    type('open sessions');
    send();
    await waitFor(() => expect(window.open).toHaveBeenCalledWith('/sessions', 'cog-/sessions'));

    // and the messages pair behaves identically
    type('nav messages');
    send();
    await waitFor(() => expect(landedAt()).toBe('/messages'));
  });

  it('nav list answers with the map — and opens NOTHING', async () => {
    renderFlyout();
    openFlyout();
    type('nav list');
    send();
    // THE REGRESSION THIS GUARDS: "list" is a word inside the key
    // "session list", so before the listing existed the fuzzy stage matched it
    // at distance 0 and opened SESSIONS. A wrong jump is worse than no jump.
    await waitFor(() => expect(screen.getByText(/destinations — pick one/i)).toBeTruthy());
    expect(window.open).not.toHaveBeenCalled();
    expect(MockWebSocket.instances.length).toBe(0);
    // the listing is real destinations, drawn as the listbox's options
    expect(screen.getByText('Logs')).toBeTruthy();
  });

  it('nav pages is the same listing', async () => {
    renderFlyout();
    openFlyout();
    type('nav pages');
    send();
    await waitFor(() => expect(screen.getByText(/destinations — pick one/i)).toBeTruthy());
    expect(window.open).not.toHaveBeenCalled();
  });

  it('a bare exa opens the Exa page and calls nothing', async () => {
    renderFlyout();
    openFlyout();
    type('exa');
    send();
    await waitFor(() => expect(screen.getByText(/Opened Exa/i)).toBeTruthy());
    // it is a tab destination, so it rides navigateTo — not window.open
    expect(MockWebSocket.instances.length).toBe(0);
  });

  it('exa <question> forces the model path with the prefix stripped', async () => {
    renderFlyout();
    openFlyout();
    type('exa how many agents are in the system?');
    send();

    await waitFor(() => expect(MockWebSocket.instances.length).toBe(1));
    act(() => MockWebSocket.openAll());
    const payload = MockWebSocket.instances[0].sent[0];
    expect(payload).toContain('how many agents are in the system?');
    // the verb word itself is machinery, not part of the question
    expect(payload).not.toContain('exa how many');
  });

  it('exa is the ESCAPE HATCH: a verb-shaped question still reaches the model', async () => {
    // WITHOUT the prefix the leading verb word wins and Exa is never consulted.
    const first = renderFlyout();
    openFlyout();
    type('search is broken on the tools page');
    send();
    expect(MockWebSocket.instances.length).toBe(0);
    first.unmount();

    // WITH it, the question arrives intact.
    MockWebSocket.reset();
    renderFlyout();
    openFlyout();
    type('exa search is broken on the tools page');
    send();
    await waitFor(() => expect(MockWebSocket.instances.length).toBe(1));
    act(() => MockWebSocket.openAll());
    expect(MockWebSocket.instances[0].sent[0]).toContain('search is broken on the tools page');
  });
});

/** The answer is markdown, and its links work. */
describe('ExaPromptFlyout — the answer renders as markdown', () => {
  beforeEach(() => {
    MockWebSocket.reset();
    (global as unknown as { WebSocket: unknown }).WebSocket = MockWebSocket;
    (window as unknown as { open: unknown }).open = vi.fn();
  });

  it('renders a link in the answer as a real link', async () => {
    renderFlyout();
    openFlyout();
    type('where are the logs?');
    send();
    await waitFor(() => expect(MockWebSocket.instances.length).toBe(1));
    act(() => MockWebSocket.openAll());
    act(() =>
      MockWebSocket.emitAll(
        JSON.stringify({ type: 'done', reply: 'The logs live at [Logs](/logs) — **live**.' })
      )
    );

    // before this change the answer was a plain <p>, so this was characters
    const link = await screen.findByRole('link', { name: 'Logs' });
    expect(link.getAttribute('href')).toBe('/logs');
    expect(screen.getByText('live').tagName).toBe('STRONG');
  });

  it('still strips the OPEN: marker rather than rendering it', async () => {
    renderFlyout();
    openFlyout();
    type('take me to the logs');
    send();
    await waitFor(() => expect(MockWebSocket.instances.length).toBe(1));
    act(() => MockWebSocket.openAll());
    act(() =>
      MockWebSocket.emitAll(
        JSON.stringify({ type: 'done', reply: 'Opening it now.\nOPEN: /logs' })
      )
    );

    await waitFor(() => expect(screen.getByText(/Opening it now/)).toBeTruthy());
    // the marker is machinery — it must not survive into the rendered answer
    expect(screen.queryByText(/OPEN:/)).toBeNull();
  });
});

describe('ExaPromptFlyout — the command box in the app shell', () => {
  beforeEach(() => {
    MockWebSocket.reset();
    (global as unknown as { WebSocket: unknown }).WebSocket = MockWebSocket;
    (window as unknown as { open: unknown }).open = vi.fn();
    localStorage.clear();
  });

  it('does NOT answer Cmd/Ctrl+K — the app-wide key belongs to the shell', () => {
    // 2026-09-18: this mount used to open on Cmd/Ctrl+K. It no longer does, and
    // that is the fix, not a regression: the key is ONE listener app-wide, it
    // is the shell's (NavSearchHotkey), and its home is the nav sidebar's box.
    // Armed here as well, one keystroke opened this flyout AND pulled focus
    // into the sidebar box. The shell's listener is covered in
    // NavSearchHotkey.test.tsx.
    renderFlyout();
    expect(screen.queryByLabelText('Ask Exa a question')).toBeNull();
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
    expect(screen.queryByLabelText('Ask Exa a question')).toBeNull();
  });

  it('offers where you have been, one click away — the mouse path', async () => {
    renderFlyout();
    openFlyout();
    type('nav logs');
    send();
    await waitFor(() => expect(landedAt()).toBe('/logs'));

    // the shortcut SURVIVES its own use — the first version hid it the moment
    // there was an exchange, which killed the mouse path after one command
    await waitFor(() => expect(screen.getByText('Frequent')).toBeTruthy());
    (window.open as unknown as { mockClear: () => void }).mockClear();
    // SOMEONE ELSE FIRST, so the row's landing is observable at all
    type('nav gallery');
    send();
    await waitFor(() => expect(landedAt()).toBe('/components'));

    fireEvent.click(screen.getByText('Logs'));
    // A SHORTCUT ROW IS A DESTINATION (2026-09-19): clicking one moves the page
    // the reader is on — the `nav` axis — exactly as accepting it with Enter does.
    await waitFor(() => expect(landedAt()).toBe('/logs'));
    expect(window.open).not.toHaveBeenCalled();
  });

  it('orders the shortcuts by USE, not by the order you typed them', async () => {
    renderFlyout();
    openFlyout();
    for (const cmd of ['nav logs', 'nav gallery', 'nav gallery']) {
      type(cmd);
      send();
      await waitFor(() => expect(screen.getByText('Frequent')).toBeTruthy());
      await new Promise((r) => setTimeout(r, 0));
    }
    // the shortcut ROWS, not the section's own controls (All / Clear)
    const section = (screen.getByText('Frequent').parentElement as HTMLElement)
      .parentElement as HTMLElement;
    const labels = Array.from(section.querySelectorAll('ul button')).map((b) => b.textContent || '');
    expect(labels[0]).toContain('Gallery'); // opened twice
    expect(labels.join(' ')).toContain('Logs');
  });

  it('a wiki lookup records nothing bogus (only real destinations are stored)', async () => {
    (global as unknown as { fetch: unknown }).fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({ results: [{ path: 'dev-notes/a', title: 'Note A', score: 9, snippet: 'x' }] }),
    }));
    renderFlyout();
    openFlyout();
    type('dev architecture');
    send();
    await waitFor(() => expect(screen.getByText('Frequent')).toBeTruthy());
    expect(screen.getByText('Note A')).toBeTruthy();
    // `dev` lands IN PLACE — a wiki note is a page, not a tab
    expect(landedAt()).toBe('/wiki/dev-notes/a');
    expect(window.open).not.toHaveBeenCalled();
  });
});

/** `config`, `help` and `back` (2026-09-18). */
describe('ExaPromptFlyout — config, help and back', () => {
  beforeEach(() => {
    MockWebSocket.reset();
    (global as unknown as { WebSocket: unknown }).WebSocket = MockWebSocket;
    (window as unknown as { open: unknown }).open = vi.fn();
  });

  it('config theme lands IN PLACE on the Appearance TAB, not just the page', async () => {
    renderFlyout();
    openFlyout();
    type('config theme');
    send();
    // the alias table already carried this deep link, so `config` rides it
    await waitFor(() => expect(landedAt()).toBe('/settings?tab=appearance'));
    expect(window.open).not.toHaveBeenCalled();
    expect(MockWebSocket.instances.length).toBe(0);
  });

  it('config keys reaches the page that holds the key fields', async () => {
    renderFlyout();
    openFlyout();
    type('config keys');
    send();
    // The keys act lives on Setup since the 2026-11-22 ruling; the dashboard's Keys tab is gone.
    await waitFor(() => expect(landedAt()).toBe('/setup?tab=keys'));
  });

  it('help lists EVERY canonical verb — generated from the set, so it cannot drift', async () => {
    renderFlyout();
    openFlyout();
    type('help');
    send();
    await waitFor(() => expect(screen.getByText(/go to a page in THIS tab/)).toBeTruthy());
    const shown = document.body.textContent ?? '';
    for (const v of ['nav', 'open', 'config', 'list', 'help', 'back', 'exa', 'info', 'dev', 'atlas', 'search']) {
      expect(shown, 'help must list `' + v + '`').toContain(v);
    }
    // an answer, not an action
    expect(MockWebSocket.instances.length).toBe(0);
    expect(window.open).not.toHaveBeenCalled();
  });

  it('help <verb> describes one verb and names its aliases', async () => {
    renderFlyout();
    openFlyout();
    type('help nav');
    send();
    await waitFor(() => expect(screen.getByText(/also: goto/)).toBeTruthy());
  });

  it('back refuses honestly when the tab started here — never walks out of the app', async () => {
    renderFlyout();
    openFlyout();
    type('back');
    send();
    // no react-router history index in this environment, so idx is 0
    await waitFor(() => expect(screen.getByText(/Nothing to go back to/)).toBeTruthy());
    expect(MockWebSocket.instances.length).toBe(0);
  });
});

describe('ExaPromptFlyout — search and the history controls', () => {
  beforeEach(() => {
    MockWebSocket.reset();
    (global as unknown as { WebSocket: unknown }).WebSocket = MockWebSocket;
    (window as unknown as { open: unknown }).open = vi.fn();
    localStorage.clear();
  });

  it('`list` shows the app pages AND the wiki, grouped, and opens NOTHING — the list is the answer', async () => {
    (global as unknown as { fetch: unknown }).fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({ results: [{ path: 'dev-notes/x', title: 'Note X', score: 5, snippet: 's' }] }),
    }));
    renderFlyout();
    openFlyout();
    type('list agents');
    send();

    await waitFor(() => expect(screen.getByText('Pages')).toBeTruthy());
    expect(screen.getByText('Wiki')).toBeTruthy();
    // the verb's whole point: it does not navigate on its own
    expect(window.open).not.toHaveBeenCalled();

    // ...the user picks one, and THAT navigates — in place, because a wiki note is
    // a PAGE (2026-09-19): a row lands by its destination, not by a default
    fireEvent.click(screen.getByText('Note X'));
    await waitFor(() => expect(landedAt()).toBe('/wiki/dev-notes/x'));
    expect(window.open).not.toHaveBeenCalled();
  });

  /**
   * `search` / `find` (2026-09-19) — the WIKI's own search across every
   * namespace, moved OFF `list`. It opens nothing either, and its hits land in
   * the SAME panel a tie uses (candidate buttons), so one can be opened from
   * the keyboard.
   */
  it('`search` lists the WIKI hits as candidates and opens NOTHING', async () => {
    (global as unknown as { fetch: unknown }).fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        results: [
          { path: 'dev-notes/x', title: 'Note X', score: 5, snippet: 's' },
          { path: 'help/triggers', title: 'Triggers', score: 4, snippet: 't' },
        ],
      }),
    }));
    renderFlyout();
    openFlyout();
    type('search triggers');
    send();

    await waitFor(() => expect(screen.getByText(/matches 2 pages in the wiki/)).toBeTruthy());
    // the wiki search, not the app map: no "Pages" group
    expect(screen.queryByText('Pages')).toBeNull();
    expect(window.open).not.toHaveBeenCalled();

    // ...and a hit is a button the user opens — the same panel a tie uses. A WIKI
    // NOTE IS A PAGE, so it lands in the page they are on (2026-09-19); the row's
    // landing follows the destination, not the surface it was picked from.
    fireEvent.click(screen.getByText('Note X'));
    await waitFor(() => expect(landedAt()).toBe('/wiki/dev-notes/x'));
    expect(window.open).not.toHaveBeenCalled();
  });

  it('`find` is the same verb as `search`', async () => {
    (global as unknown as { fetch: unknown }).fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({ results: [{ path: 'help/triggers', title: 'Triggers', score: 4, snippet: 't' }] }),
    }));
    renderFlyout();
    openFlyout();
    type('find triggers');
    send();

    await waitFor(() => expect(screen.getByText(/1 page in the wiki/)).toBeTruthy());
    expect(window.open).not.toHaveBeenCalled();
  });

  it('refuses an empty list honestly', async () => {
    (global as unknown as { fetch: unknown }).fetch = vi.fn(async () => ({ ok: true, json: async () => ({ results: [] }) }));
    renderFlyout();
    openFlyout();
    type('list zzqqxx');
    send();
    await waitFor(() => expect(screen.getByText(/Nothing matches/i)).toBeTruthy());
    expect(window.open).not.toHaveBeenCalled();

    // the wiki's own search names the scope it searched
    type('search zzqqxx');
    send();
    await waitFor(() => expect(screen.getByText(/Nothing in the wiki matches/i)).toBeTruthy());
  });

  it('Clear empties the shortcut list and says so through the toaster', async () => {
    renderFlyout();
    openFlyout();
    type('nav logs');
    send();
    await waitFor(() => expect(screen.getByText('Frequent')).toBeTruthy());
    fireEvent.click(screen.getByLabelText('Clear navigation history'));
    await waitFor(() => expect(screen.queryByText('Frequent')).toBeNull());
    expect(localStorage.getItem('cog-nav-history')).toBeNull();
  });
});

describe('ExaPromptFlyout — the history controls', () => {
  beforeEach(() => {
    MockWebSocket.reset();
    (global as unknown as { WebSocket: unknown }).WebSocket = MockWebSocket;
    (window as unknown as { open: unknown }).open = vi.fn();
    localStorage.clear();
  });

  const shortcutRows = () => {
    const section = (screen.getByText('Frequent').parentElement as HTMLElement)
      .parentElement as HTMLElement;
    return section.querySelectorAll('ul button').length;
  };

  it('shows six by default, and ALL of them when asked', async () => {
    for (let i = 0; i < 8; i++) recordNav('/page-' + i, 'Page ' + i, 1000 + i);
    renderFlyout();
    openFlyout();
    await waitFor(() => expect(screen.getByText('Frequent')).toBeTruthy());
    expect(shortcutRows()).toBe(6);

    fireEvent.click(screen.getByLabelText('Show all shortcuts'));
    await waitFor(() => expect(shortcutRows()).toBe(8));

    fireEvent.click(screen.getByLabelText('Show fewer shortcuts'));
    await waitFor(() => expect(shortcutRows()).toBe(6));
  });

  it('offers no expand control when there is nothing more to show', async () => {
    recordNav('/logs', 'Logs');
    renderFlyout();
    openFlyout();
    await waitFor(() => expect(screen.getByText('Frequent')).toBeTruthy());
    expect(screen.queryByLabelText('Show all shortcuts')).toBeNull();
    expect(screen.getByLabelText('Clear navigation history')).toBeTruthy();
  });
});

/**
 * `appearance.keepCommandBoxOpen` (Settings > Appearance) — the preference the
 * HEADER's mount answers to, and its meaning after 2026-09-19:
 *
 *  - an IN-PLACE navigation hands the caret to the PAGE for every mount. That is
 *    the app's rule (the user's report was being left in the nav panel) and no
 *    mount's preference overrules it;
 *  - a TAB landing leaves THIS document alone, so a mount that stays open keeps
 *    its input ready for the next command — which is what this setting still
 *    decides, and what the `open logs` test below pins.
 *
 * OFF is the default and leaves the widget as it always was.
 */
describe('ExaPromptFlyout — the keep-command-box-open preference', () => {
  /** Grant or revoke it the way the Appearance toggle does. */
  const setKeepOpen = (value: boolean) =>
    useSettingsStore.setState((s) => ({
      settings: { ...s.settings, appearance: { ...s.settings.appearance, keepCommandBoxOpen: value } },
    }));

  beforeEach(() => {
    MockWebSocket.reset();
    (global as unknown as { WebSocket: unknown }).WebSocket = MockWebSocket;
    (window as unknown as { open: unknown }).open = vi.fn();
    localStorage.clear();
    setKeepOpen(false);
  });

  const field = () => screen.getByLabelText('Ask Exa a question') as HTMLInputElement;

  it('OFF (the default): a navigation is the navigation it always was, and nothing more', async () => {
    renderFlyout();
    openFlyout();
    type('nav logs');
    field().blur();

    send();
    await waitFor(() => expect(landedAt()).toBe('/logs'));
    // a tick, so a refocus would have landed by now if this mount had asked
    // for one — the hook must not reach into a mount that did not
    await new Promise((r) => setTimeout(r, 0));

    expect(window.open).not.toHaveBeenCalled();
    expect(document.activeElement).not.toBe(field());
  });

  it('ON: the box stays up, and the PAGE takes the caret — the app rule wins', async () => {
    setKeepOpen(true);
    renderFlyout();
    openFlyout();
    const input = field();
    input.focus();
    type('nav logs');
    input.blur();

    send();
    await waitFor(() => expect(landedAt()).toBe('/logs'));

    // the box is still standing — ready for the next command
    expect(screen.getByText('Frequent')).toBeTruthy();
    // ...but the caret does NOT come back to it (2026-09-19): the reader asked to
    // go somewhere, and an in-place navigation hands them the destination. The
    // request is on the record for the shell to answer.
    expect(document.activeElement).not.toBe(input);
    expect(localStorage.getItem(FOCUS_HANDOFF_KEY)).toBeTruthy();
  });

  it('ON: a TAB landing still keeps the input ready — the preference, where it is true', async () => {
    setKeepOpen(true);
    renderFlyout();
    openFlyout();
    const input = field();
    input.focus();
    type('open logs');
    send();

    await waitFor(() => expect(window.open).toHaveBeenCalledWith('/logs', 'cog-/logs'));
    // this document did not go anywhere, so the box that stays open keeps its
    // caret — which is the half of the old behaviour that still holds.
    await waitFor(() => expect(document.activeElement).toBe(input));
  });

  it('OFF: the header box still goes with the page it was sitting on', async () => {
    // THE REAL HEADER LAYOUT: the trigger sits on each page's own header row,
    // so an in-place navigation replaces the PAGE — each route is its own
    // component — and the box goes with it. That is "navigate, then close",
    // and the default changes none of it.
    const DashboardPage = () => <><LocationProbe /><ExaPromptFlyout /></>;
    const LogsPage = () => <><LocationProbe /><ExaPromptFlyout /></>;
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/logs" element={<LogsPage />} />
        </Routes>
      </MemoryRouter>
    );
    openFlyout();
    type('nav logs');
    send();

    await waitFor(() => expect(landedAt()).toBe('/logs'));
    expect(screen.queryByLabelText('Ask Exa a question')).toBeNull();
  });
});

/**
 * THE HEADER'S MOUNT CLAIMS NOTHING ON ARRIVAL (2026-09-18).
 *
 * The caret-on-arrival belongs to the SIDEBAR's mount, whose box can be open on
 * a fresh load because its open state is remembered — that is P4's focus
 * contract, and `nav sessions` opening a new tab is the case it answers. This
 * mount cannot be open on arrival (its open flag is the hook's own `useState`,
 * which starts false) and it is carried by whichever page owns the header, so a
 * claim here would yank the caret out of the page on every load — a bug, and
 * not what was asked for. The load claim therefore lives in the attachment, not
 * in the hook both mounts share.
 */
describe('ExaPromptFlyout — no caret claim on arrival', () => {
  beforeEach(() => {
    localStorage.clear();
    // the sidebar's box IS remembered as open: this mount must not react to it
    useUIStore.setState({ navSearchOpen: true, navSearchFocusPending: false });
  });

  it('leaves the caret alone, and touches nothing of the sidebar box', () => {
    renderFlyout();

    expect(screen.queryByLabelText('Ask Exa a question')).toBeNull();
    expect(document.activeElement).toBe(document.body);
    // and it did not consume the sidebar's state on its way past
    expect(useUIStore.getState().navSearchOpen).toBe(true);
  });
});

/**
 * THE FLYOUT'S HALF OF THE SPLIT (2026-09-18).
 *
 * The NAV SIDEBAR's box reads "Search", runs commands from a "Go" button, and
 * draws neither a "Full page" control nor a streamed-answer area (see
 * NavSearchSection.test.tsx). THIS mount keeps the Exa path, so it keeps all
 * four of those things — and this test pins that they are still here, because a
 * variant-driven panel is exactly the kind of change that can drop a control
 * from the wrong mount.
 */
describe('ExaPromptFlyout — the controls the sidebar drops', () => {
  beforeEach(() => {
    MockWebSocket.reset();
    (global as unknown as { WebSocket: unknown }).WebSocket = MockWebSocket;
    (window as unknown as { open: unknown }).open = vi.fn();
  });

  it('keeps the Exa name, "Send", "Full page" and the streamed answer', () => {
    renderFlyout();
    openFlyout();

    // the copy is still the Exa surface's, not the navigator's
    expect(screen.getByText('Ask Exa')).toBeTruthy();
    expect(screen.getByText('Full page')).toBeTruthy();
    expect(screen.getByLabelText('Send to Exa').textContent).toBe('Send');

    type('what does the compactor do?');
    send();
    act(() => { MockWebSocket.openAll(); });
    act(() => { MockWebSocket.emitAll(JSON.stringify({ type: 'message', text: 'It rolls a summary.' })); });

    // THE ANSWER AREA — the question AND the streamed answer, neither of which
    // the sidebar's panel draws
    expect(screen.getByText(/You:/)).toBeTruthy();
    expect(screen.getByText('It rolls a summary.')).toBeTruthy();
  });
});
