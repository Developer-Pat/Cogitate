/**
 * appNavigation — the "take me there" resolver.
 *
 * The load-bearing properties, not the implementation:
 *  - the map is GENERATED (every real route resolves to itself),
 *  - the user's actual first request works ("themes" -> the Settings
 *    Appearance tab, which is not a route at all),
 *  - an unknown destination FAILS LOUDLY and never opens a best guess,
 *  - the marker Exa emits is stripped from what the reader sees,
 *  - navigation goes through exactly one function.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  COMMAND_VERBS,
  pageMap,
  pageMapPrompt,
  parseCommand,
  nearVerb,
  noCommandAnswer,
  resolveTarget,
  resolveWikiCommand,
  searchAll,
  openTarget,
  targetForPath,
  extractOpenRequest,
  landingFor,
  verbHelp,
} from '../appNavigation';

describe('the map', () => {
  it('is generated from the route table, so every route resolves to itself', () => {
    const map = pageMap();
    expect(map.length).toBeGreaterThan(10);
    for (const entry of map) {
      const res = resolveTarget(entry.path);
      expect(res.ok, `${entry.path} should resolve`).toBe(true);
      if (res.ok) expect(res.target.to).toBe(entry.path);
    }
  });

  it('resolves routes by their human title too', () => {
    const map = pageMap();
    for (const entry of map.slice(0, 10)) {
      const res = resolveTarget(entry.title);
      expect(res.ok, `title "${entry.title}" should resolve`).toBe(true);
      if (res.ok) expect(res.target.to).toBe(entry.path);
    }
  });

  it('hands Exa the map as prompt text', () => {
    const text = pageMapPrompt();
    expect(text).toContain('/settings');
    expect(text).toContain('themes');
  });
});

describe('the user\'s first real request', () => {
  it('resolves "themes" to the Settings Appearance tab (not a route at all)', () => {
    const res = resolveTarget('themes');
    expect(res.ok).toBe(true);
    if (res.ok) {
      expect(res.target.to).toBe('/settings?tab=appearance');
      expect(res.target.label).toContain('themes');
    }
  });

  it('accepts the address itself, query and all', () => {
    const res = resolveTarget('/settings?tab=appearance');
    expect(res.ok).toBe(true);
    if (res.ok) expect(res.target.to).toBe('/settings?tab=appearance');
  });

  it('tolerates the decoration a model wraps a target in', () => {
    const res = resolveTarget('`/settings?tab=appearance`.');
    expect(res.ok).toBe(true);
    if (res.ok) expect(res.target.to).toBe('/settings?tab=appearance');
  });
});

describe('the loud failure (never a best guess)', () => {
  it('refuses a path that is not in the map', () => {
    const res = resolveTarget('/definitely-not-a-page');
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.error).toContain('/definitely-not-a-page');
  });

  it('refuses an invented name, and offers what it has', () => {
    const res = resolveTarget('the quantumbulator page');
    expect(res.ok).toBe(false);
    if (!res.ok) {
      expect(res.error).toContain('quantumbulator');
      expect(Array.isArray(res.candidates)).toBe(true);
    }
  });

  it('refuses an empty target', () => {
    expect(resolveTarget('   ').ok).toBe(false);
  });
});

describe('the app tabs', () => {
  it('routes the TabApp vocabulary through the cross-tab service', () => {
    const res = resolveTarget('wiki');
    expect(res.ok).toBe(true);
    if (res.ok) expect(res.target.kind).toBe('tab');
  });
});

/**
 * THE COLLISION (2026-09-18) — a term that names BOTH a page and an app tab.
 *
 * The user, live: `nav sessions` opened a NEW TAB while `nav logs` moved the
 * current page, the same verb typed both times. `sessions` is the tab app AND
 * the route `/sessions`; the tab stage ran first, so the tab always won and the
 * verb could not matter at all. The names are identical — only the LANDING
 * differs — so the verb's AXIS is what breaks the tie (see dualPage), and the
 * losing side is left a name of its own so it stays reachable by typing.
 */
describe('a name that is BOTH a page and a tab — the verb decides', () => {
  beforeEach(() => {
    (global as unknown as { window: { open: unknown } }).window.open = vi.fn();
  });

  it('`nav sessions` takes the PAGE in place; `open sessions` takes the TAB', () => {
    const inPlace = resolveTarget('sessions', landingFor('nav'));
    expect(inPlace.ok).toBe(true);
    if (inPlace.ok) {
      expect(inPlace.target.kind).toBe('route');
      expect(inPlace.target.to).toBe('/sessions');
      expect(inPlace.target.landing).toBe('replace');
    }

    const tab = resolveTarget('sessions', landingFor('open'));
    expect(tab.ok).toBe(true);
    if (tab.ok) {
      expect(tab.target.kind).toBe('tab');
      expect(tab.target.app).toBe('sessions');
    }
  });

  it('...and the page really MOVES instead of a tab opening (the live report)', () => {
    for (const term of ['sessions', 'messages']) {
      (window.open as unknown as { mockClear: () => void }).mockClear();
      const res = resolveTarget(term, landingFor('nav'));
      if (!res.ok) throw new Error('expected ok: ' + term);
      const move = vi.fn();
      openTarget(res.target, move);
      expect(move, term).toHaveBeenCalledWith('/' + term);
      expect(window.open, term).not.toHaveBeenCalled();
    }
  });

  it('`goto` is the same axis as `nav`, through the parser', () => {
    const cmd = parseCommand('goto sessions')!;
    const res = resolveTarget(cmd.rest, landingFor(cmd.verb));
    expect(res.ok).toBe(true);
    if (res.ok) {
      expect(res.target.kind).toBe('route');
      expect(res.target.to).toBe('/sessions');
    }
  });

  it('the same pair for messages / message center — and the tab stays a tab', () => {
    for (const term of ['messages', 'message center']) {
      const page = resolveTarget(term, landingFor('nav'));
      expect(page.ok, term).toBe(true);
      if (page.ok) {
        expect(page.target.kind, term).toBe('route');
        expect(page.target.to, term).toBe('/messages');
      }
      const tab = resolveTarget(term, landingFor('open'));
      expect(tab.ok, term).toBe(true);
      if (tab.ok) {
        expect(tab.target.kind, term).toBe('tab');
        expect(tab.target.app, term).toBe('messages');
      }
    }
  });

  it('the alias names the losing side whatever verb asked (`message list` is the page)', () => {
    for (const landing of ['replace', 'tab'] as const) {
      const res = resolveTarget('message list', landing);
      expect(res.ok, landing).toBe(true);
      if (res.ok) {
        expect(res.target.kind, landing).toBe('route');
        expect(res.target.to, landing).toBe('/messages');
      }
    }
  });

  it('"session list" still names the SESSIONS tab — it names no page', () => {
    const res = resolveTarget('session list', landingFor('nav'));
    expect(res.ok).toBe(true);
    if (res.ok) {
      expect(res.target.kind).toBe('tab');
      expect(res.target.app).toBe('sessions');
    }
  });

  it('the OTHER overlapping TAB_APPS behave the same way', () => {
    // `exa` is the /exa route (titled "Exa Agent") AND the Exa tab
    const exa = resolveTarget('exa', landingFor('nav'));
    expect(exa.ok).toBe(true);
    if (exa.ok) {
      expect(exa.target.kind).toBe('route');
      expect(exa.target.to).toBe('/exa');
    }
    // `agent chat` / `chat` / `agent interaction` is the /agent-interaction page
    for (const term of ['agent chat', 'chat', 'agent interaction']) {
      const res = resolveTarget(term, landingFor('nav'));
      expect(res.ok, term).toBe(true);
      if (res.ok) {
        expect(res.target.kind, term).toBe('route');
        expect(res.target.to, term).toBe('/agent-interaction');
      }
    }
    // ...and the tab vocabulary still takes the tab
    const chatTab = resolveTarget('agent chat', landingFor('open'));
    if (!chatTab.ok) throw new Error('expected ok');
    expect(chatTab.target.kind).toBe('tab');
    expect(chatTab.target.app).toBe('agent-chat');
  });

  it('`wiki` overlaps NOTHING (its route is a wildcard), so it stays a tab', () => {
    for (const landing of ['replace', 'tab'] as const) {
      const res = resolveTarget('wiki', landing);
      expect(res.ok, landing).toBe(true);
      if (res.ok) expect(res.target.kind, landing).toBe('tab');
    }
  });

  it('no axis at all keeps the OLD behaviour — the tab (Exa\'s own OPEN: marker)', () => {
    for (const term of ['sessions', 'messages', 'exa']) {
      const res = resolveTarget(term);
      expect(res.ok, term).toBe(true);
      if (res.ok) expect(res.target.kind, term).toBe('tab');
    }
  });
});

describe('the marker', () => {
  it('is stripped from the reader-visible answer', () => {
    const { text, request } = extractOpenRequest('Settings, Appearance tab.\n\nOPEN: /settings?tab=appearance');
    expect(request).toBe('/settings?tab=appearance');
    expect(text).toBe('Settings, Appearance tab.');
    expect(text).not.toContain('OPEN');
  });

  it('is case-insensitive and survives a wrapped path', () => {
    const { request } = extractOpenRequest('here you go\nopen: `/workflows`');
    expect(request).toBe('`/workflows`');
  });

  it('reports nothing when Exa declined to navigate', () => {
    const { text, request } = extractOpenRequest('I could not find such a page.');
    expect(request).toBeNull();
    expect(text).toBe('I could not find such a page.');
  });
});

describe('opening', () => {
  beforeEach(() => {
    (global as unknown as { window: { open: unknown } }).window.open = vi.fn();
  });

  it('opens a route in a new tab (the app keeps the current page)', () => {
    const res = resolveTarget('themes');
    if (!res.ok) throw new Error('expected ok');
    openTarget(res.target);
    // the STABLE NAME is what makes a repeat request FOCUS instead of stack
    expect(window.open).toHaveBeenCalledWith('/settings?tab=appearance', 'cog-/settings?tab=appearance');
  });

  it('sends a tab app through the cross-tab service, under the SAME one-window-per-path name', () => {
    const res = resolveTarget('wiki');
    if (!res.ok) throw new Error('expected ok');
    openTarget(res.target);
    // 2026-09-19: `_blank` stacked a fresh duplicate on every request, which is
    // the window collision the user reported. A tab app is a destination like any
    // other, so it is named and reused (`openReusing`).
    expect(window.open).toHaveBeenCalledWith('/wiki', 'cog-/wiki');
  });

  it('knows what a bare PATH is: a page, or a tab app with no page of its own', () => {
    // The box's rows carry PATHS — that is the shape the listing and the shortcut
    // list have — and `logs`/`wiki` are the two shapes that matter:
    expect(targetForPath('/logs')).toEqual({ to: '/logs', label: '/logs', kind: 'route' });
    // `/wiki` is a WILDCARD route, so it is never in the page map: it can only be
    // the tab app, which is what the helper reads off the same tables the resolver
    // uses. A name that is BOTH (`sessions`) stays a page here, because the page
    // map has it — the axis the verb would have decided is moot for a row, and the
    // dedupe in `allDestinations` never draws the tab-app twin anyway.
    expect(targetForPath('/wiki', 'Wiki')).toEqual({ to: '/wiki', label: 'Wiki', kind: 'tab', app: 'wiki' });
    expect(targetForPath('/sessions')).toEqual({ to: '/sessions', label: '/sessions', kind: 'route' });
  });
});

describe('the command verbs', () => {
  it('parses the canonical verbs, and resolves aliases to them', () => {
    expect(parseCommand('nav logs')).toEqual({ verb: 'nav', typed: 'nav', rest: 'logs' });
    expect(parseCommand('INFO workflows')).toEqual({ verb: 'info', typed: 'info', rest: 'workflows' });
    expect(parseCommand('dev architecture')).toEqual({ verb: 'dev', typed: 'dev', rest: 'architecture' });
    expect(parseCommand('atlas settings page')).toEqual({ verb: 'atlas', typed: 'atlas', rest: 'settings page' });
    // THE ALIASES resolve to their canonical verb but keep what was TYPED, so a
    // confirmation can echo the user's own word back at them.
    expect(parseCommand('goto logs')).toEqual({ verb: 'nav', typed: 'goto', rest: 'logs' });
    expect(parseCommand('show workflows')).toEqual({ verb: 'open', typed: 'show', rest: 'workflows' });
    expect(parseCommand('conf theme')).toEqual({ verb: 'config', typed: 'conf', rest: 'theme' });
    expect(parseCommand('configure provider')).toEqual({ verb: 'config', typed: 'configure', rest: 'provider' });
    // anything else falls through — the CALLER then decides: the nav sidebar's
    // box answers locally (see noCommandAnswer), the header flyout hands it to
    // Exa. Which of the two is a mount's own option, not this function's job.
    expect(parseCommand('where do I set up a trigger?')).toBeNull();
    expect(parseCommand('navigation is hard')).toBeNull();
  });

  it('keeps a bare verb parseable so the shape can be taught', () => {
    expect(parseCommand('nav')).toEqual({ verb: 'nav', typed: 'nav', rest: '' });
  });

  it('offers the verb on a ONE-EDIT typo — the expensive failure, since a typo otherwise costs a model turn', () => {
    // the user's OWN example: `gotto` is one edit from the ALIAS `goto`, so the
    // scan has to cover aliases too — and the offer names the word they meant
    expect(nearVerb('gotto macros')).toEqual({ verb: 'nav', typed: 'gotto', suggest: 'goto' });
    // a transposition is one edit under Damerau-Levenshtein
    expect(nearVerb('opne logs')).toEqual({ verb: 'open', typed: 'opne', suggest: 'open' });
    expect(nearVerb('confg theme')).toEqual({ verb: 'config', typed: 'confg', suggest: 'config' });
    // THE MOVED VERB (2026-09-19): `search` was an alias of `list`, so a typo of
    // it used to offer `search` and MEAN list. Same offer, different
    // destination — and `find`, the alias the move added, is scanned too.
    expect(nearVerb('serch triggers')).toEqual({ verb: 'search', typed: 'serch', suggest: 'search' });
    expect(nearVerb('fnd notes')).toEqual({ verb: 'search', typed: 'fnd', suggest: 'find' });
  });

  it('does NOT invent a verb: a question is not a typo, and a tie is not a winner', () => {
    // real words, not misspellings — these are questions or gibberish, and
    // nothing here may be read as a verb
    expect(nearVerb('where do I set up a trigger?')).toBeNull();
    expect(nearVerb('what broke in the pipeline yesterday?')).toBeNull();
    // far from every verb
    expect(nearVerb('zzzzz')).toBeNull();
    // too short to judge
    expect(nearVerb('nv')).toBeNull();
  });

  it('the LOCAL ANSWER for an input that matched no verb — the typo is offered back', () => {
    // THE DECISION (2026-09-18): the SIDEBAR's box makes no model call, so this
    // is where a typo lands there — instantly, and correctable. (The header
    // flyout keeps its fall-through to Exa; `exaFallthrough` in useCommandBox.)
    expect(noCommandAnswer('navv logs')).toEqual({ text: 'Did you mean `nav`?', error: false });
    // the alias was what they meant, so the alias is what comes back
    expect(noCommandAnswer('gotto macros')).toEqual({ text: 'Did you mean `goto`?', error: false });
  });

  it('...and anything else is told it is not a command, in ONE line, pointing at help', () => {
    // a QUESTION is not a failure of the grammar, and the line must not scold:
    // state only (the house rule for UI copy), and it names the one thing that
    // teaches the rest
    expect(noCommandAnswer('what does the compactor do?')).toEqual({
      text: 'Unknown command — help lists them.',
      error: true,
    });
    // plain nonsense gets the same line — there is nothing to offer
    expect(noCommandAnswer('zzzzz')).toEqual({
      text: 'Unknown command — help lists them.',
      error: true,
    });
  });

  it('"nav logs" is pure client-side — no network involved', () => {
    const cmd = parseCommand('nav logs')!;
    const res = resolveTarget(cmd.rest);
    expect(res.ok).toBe(true);
    if (res.ok) expect(res.target.to).toContain('logs');
  });

  it('"nav the logs page" resolves the PHRASE — the weak version of this test hid a real gap', () => {
    const logs = pageMap().find((p) => p.title.toLowerCase() === 'logs');
    expect(logs, 'the map should have a Logs page').toBeTruthy();
    for (const phrase of ['the logs page', 'logs page', 'go to the logs', 'logs screen']) {
      const cmd = parseCommand('nav ' + phrase)!;
      const res = resolveTarget(cmd.rest);
      expect(res.ok, phrase).toBe(true);
      if (res.ok) expect(res.target.to, phrase).toBe(logs!.path);
    }
  });
});

describe('the wiki verbs', () => {
  const mockFetch = (results: unknown[], ok = true) => {
    (global as unknown as { fetch: unknown }).fetch = vi.fn(async () => ({
      ok,
      json: async () => ({ results }),
    }));
  };

  it('scopes dev-notes, and opens the page the search found', async () => {
    mockFetch([{ path: 'dev-notes/architecture', title: 'Architecture', score: 9, snippet: 's' }]);
    const res = await resolveWikiCommand(parseCommand('dev architecture')!);
    expect(res.ok).toBe(true);
    if (res.ok) expect(res.target.to).toBe('/wiki/dev-notes/architecture');
    const called = String((global.fetch as unknown as { mock: { calls: string[][] } }).mock.calls[0][0]);
    expect(called).toContain('prefix=dev-notes');
  });

  it('scopes the atlas without a prefix for info', async () => {
    mockFetch([{ path: 'atlas/ui/pages/Settings', title: 'Settings', score: 5, snippet: 's' }]);
    await resolveWikiCommand(parseCommand('atlas settings page')!);
    const atlasCall = String((global.fetch as unknown as { mock: { calls: string[][] } }).mock.calls[0][0]);
    expect(atlasCall).toContain('prefix=atlas');

    mockFetch([{ path: 'docs/workflows', title: 'Workflows', score: 4, snippet: 's' }]);
    await resolveWikiCommand(parseCommand('info workflows')!);
    const infoCall = String((global.fetch as unknown as { mock: { calls: string[][] } }).mock.calls[0][0]);
    expect(infoCall).not.toContain('prefix=');
  });

  it('a TIE returns candidates instead of guessing', async () => {
    mockFetch([
      { path: 'dev-notes/a', title: 'A', score: 7, snippet: 'x' },
      { path: 'dev-notes/b', title: 'B', score: 7, snippet: 'y' },
    ]);
    const res = await resolveWikiCommand(parseCommand('dev architecture')!);
    expect(res.ok).toBe(false);
    if (!res.ok) {
      expect(res.candidates.length).toBe(2);
      expect(res.error).toContain('which one');
    }
  });

  it('refuses loudly when the namespace has nothing', async () => {
    mockFetch([]);
    const res = await resolveWikiCommand(parseCommand('dev quantum')!);
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.error).toContain('dev notes');
  });

  it('a bare wiki verb teaches the shape rather than guessing', async () => {
    const res = await resolveWikiCommand(parseCommand('dev')!);
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.error).toContain('dev <topic>');
  });

  /**
   * `search` / `find` (2026-09-19) — the WIKI's own search across EVERY
   * namespace. It was an alias of `list`; it is a verb of its own now, and the
   * difference from `info` is what it does with the hits, not what it searches:
   * `info` opens the best one, `search` lists them all and opens nothing.
   */
  it('searches the WHOLE wiki — the request carries no prefix', async () => {
    mockFetch([{ path: 'dev-notes/triggers', title: 'Triggers', score: 5, snippet: 'x' }]);
    await resolveWikiCommand(parseCommand('search triggers')!);
    const called = String((global.fetch as unknown as { mock: { calls: string[][] } }).mock.calls[0][0]);
    expect(called).toContain('q=triggers');
    expect(called).not.toContain('prefix=');
  });

  it('`find` is the same verb — the alias reaches the wiki too', async () => {
    mockFetch([{ path: 'docs/triggers', title: 'Triggers', score: 5, snippet: 'x' }]);
    const res = await resolveWikiCommand(parseCommand('find triggers')!);
    const called = String((global.fetch as unknown as { mock: { calls: string[][] } }).mock.calls[0][0]);
    expect(called).not.toContain('prefix=');
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.candidates[0].path).toBe('/wiki/docs/triggers');
  });

  it('LISTS every hit instead of opening one — even a single clear winner', async () => {
    mockFetch([
      { path: 'docs/triggers', title: 'Triggers', score: 9, snippet: 'x' },
      { path: 'dev-notes/triggers', title: 'Trigger Notes', score: 4, snippet: 'y' },
    ]);
    const res = await resolveWikiCommand(parseCommand('search triggers')!);
    // ok:false is "nothing was opened", and the candidates ARE the answer —
    // the same shape a tie returns, so the panel renders them the same way
    expect(res.ok).toBe(false);
    if (!res.ok) {
      expect(res.candidates).toEqual([
        { path: '/wiki/docs/triggers', title: 'Triggers', description: 'x' },
        { path: '/wiki/dev-notes/triggers', title: 'Trigger Notes', description: 'y' },
      ]);
      expect(res.error).toContain('2 pages in the wiki');
    }
  });

  it('...and `info` with the SAME term still opens that winner — the two are told apart', async () => {
    mockFetch([{ path: 'docs/triggers', title: 'Triggers', score: 9, snippet: 'x' }]);
    const res = await resolveWikiCommand(parseCommand('info triggers')!);
    expect(res.ok).toBe(true);
    if (res.ok) expect(res.target.to).toBe('/wiki/docs/triggers');
  });

  it('a bare `search` teaches the shape rather than guessing', async () => {
    const res = await resolveWikiCommand(parseCommand('search')!);
    expect(res.ok).toBe(false);
    if (!res.ok) {
      expect(res.error).toContain('search <term>');
      expect(res.candidates).toEqual([]);
    }
  });
});

describe('the tie-break, on the shapes the LIVE wiki actually returns', () => {
  const mockFetch = (results: unknown[]) => {
    (global as unknown as { fetch: unknown }).fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({ results }),
    }));
  };

  it('"atlas settings page" opens the atlas of the Settings PAGE', async () => {
    // verbatim from GET /api/v1/wiki/search?q=settings page&prefix=atlas
    mockFetch([
      { path: 'atlas/api/routers/settings', title: 'Settings', score: 4, snippet: 'x' },
      { path: 'atlas/ui/hooks/useSettings', title: 'useSettings', score: 4, snippet: 'y' },
      { path: 'atlas/ui/pages/Pages Index', title: 'Pages Index', score: 4, snippet: 'z' },
      { path: 'atlas/ui/pages/Settings', title: 'Settings', score: 4, snippet: 'w' },
    ]);
    const res = await resolveWikiCommand(parseCommand('atlas settings page')!);
    expect(res.ok).toBe(true);
    if (res.ok) expect(res.target.to).toBe('/wiki/atlas/ui/pages/Settings');
  });

  it('"dev architecture" opens the Architecture Index hub', async () => {
    // verbatim from GET /api/v1/wiki/search?q=architecture&prefix=dev-notes
    mockFetch([
      { path: 'dev-notes/macros/macro-architecture', title: 'Macro System Architecture', score: 3, snippet: 'a' },
      { path: 'dev-notes/tracing/tracing-architecture', title: 'Tracing Architecture', score: 3, snippet: 'b' },
      { path: 'dev-notes/architecture/Architecture Index', title: 'Dev Notes — Architecture', score: 3, snippet: 'c' },
      { path: 'dev-notes/api/router-architecture', title: 'Router Architecture', score: 3, snippet: 'd' },
    ]);
    const res = await resolveWikiCommand(parseCommand('dev architecture')!);
    expect(res.ok).toBe(true);
    if (res.ok) expect(res.target.to).toBe('/wiki/dev-notes/architecture/Architecture Index');
  });

  it('a genuine toss-up still refuses and shows the candidates', async () => {
    mockFetch([
      { path: 'dev-notes/a', title: 'Alpha', score: 5, snippet: 'x' },
      { path: 'dev-notes/b', title: 'Beta', score: 5, snippet: 'y' },
    ]);
    const res = await resolveWikiCommand(parseCommand('dev alpha beta')!);
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.candidates.length).toBe(2);
  });
});

describe('typo tolerance — the "nav worfklows" case', () => {
  it('resolves a transposition, and SAYS it did', () => {
    // the exact input that dead-ended: "You: nav worfklows"
    const res = resolveTarget('worfklows');
    expect(res.ok).toBe(true);
    if (res.ok) {
      const workflows = pageMap().find((p) => p.title.toLowerCase() === 'workflows');
      expect(workflows, 'the map should have a Workflows page').toBeTruthy();
      expect(res.target.to).toBe(workflows!.path);
      // the correction is stated, never silent
      expect(res.target.note).toContain('Workflows');
    }
  });

  it('rescues a typo on a non-route alias too', () => {
    const res = resolveTarget('thems');
    expect(res.ok).toBe(true);
    if (res.ok) expect(res.target.to).toBe('/settings?tab=appearance');
  });

  it('refuses the word "configuration" now that the mock page is gone', () => {
    // The token-limit arc's A.4 removed /configuration (a static mock with no
    // state and no API). The word used to land there; a page that no longer
    // exists must be REFUSED, never redirected at whatever else looks config-y.
    const res = resolveTarget('configuration');
    expect(res.ok).toBe(false);
    if (!res.ok) {
      expect(pageMap().some((p) => p.path === '/configuration')).toBe(false);
      // the map offers candidates — that is fine — but it must not CLAIM one
      expect(res.error).toContain('configuration');
    }
  });

  it('rescues a doubled letter and a dropped letter', () => {
    for (const typo of ['workfows', 'workflows']) {
      const res = resolveTarget(typo);
      expect(res.ok, typo).toBe(true);
    }
  });

  it('does NOT guess when two pages are equally close — it offers them', () => {
    // several pages carry "template": Agent Templates, Workflow Templates, ...
    const res = resolveTarget('templtes');
    if (res.ok) {
      expect(res.target.to).toContain('template');
    } else {
      expect(res.candidates.length).toBeGreaterThan(0);
    }
  });

  it('still refuses genuine nonsense — tolerance is not credulity', () => {
    const res = resolveTarget('zzqxwv plthb');
    expect(res.ok).toBe(false);
  });

  it('a corrected target navigates exactly like an exact one', () => {
    const res = resolveTarget('worfklows');
    if (!res.ok) throw new Error('expected ok');
    openTarget(res.target);
    const expected = pageMap().find((p) => p.title.toLowerCase() === 'workflows')!.path;
    expect(window.open).toHaveBeenCalledWith(expected, 'cog-' + expected);
  });
});

describe('the wiki front door (the user\'s "wiki index?")', () => {
  it('"wiki index" reaches /wiki, which IS the Site Index', () => {
    for (const phrase of ['wiki index', 'site index', 'wiki home']) {
      const res = resolveTarget(phrase);
      expect(res.ok, phrase).toBe(true);
      if (res.ok) expect(res.target.to, phrase).toBe('/wiki');
    }
  });

  it('"nav wiki" still works through the tab-app vocabulary', () => {
    const res = resolveTarget('wiki');
    expect(res.ok).toBe(true);
    if (res.ok) expect(res.target.kind).toBe('tab');
  });
});

describe('the list verb (the user\'s "popup -> search -> show links -> navigate")', () => {
  const mockWiki = (results: unknown[], ok = true) => {
    (global as unknown as { fetch: unknown }).fetch = vi.fn(async () => ({
      ok,
      json: async () => ({ results }),
    }));
  };

  it('`list` keeps the verb to itself — `search` is no longer its alias', () => {
    expect(parseCommand('list triggers')).toEqual({ verb: 'list', typed: 'list', rest: 'triggers' });
    // THE REASSIGNMENT (2026-09-19): the same words reach the WIKI's own search
    // now, which is a different answer — see the wiki-verb tests above.
    expect(parseCommand('search triggers')).toEqual({ verb: 'search', typed: 'search', rest: 'triggers' });
    expect(parseCommand('search')).toEqual({ verb: 'search', typed: 'search', rest: '' });
  });

  it('groups the app pages and the wiki — one never hides the other', async () => {
    mockWiki([{ path: 'dev-notes/agents', title: 'Agents in the pipeline', score: 5, snippet: 'x' }]);
    const res = await searchAll('agents');
    expect(res.pages.length).toBeGreaterThan(0);
    expect(res.pages.some((p) => /agent/i.test(p.title))).toBe(true);
    expect(res.wiki.length).toBe(1);
    expect(res.wiki[0].path).toBe('/wiki/dev-notes/agents');
  });

  it('finds the declared aliases too ("themes" is not a route)', async () => {
    mockWiki([]);
    const res = await searchAll('themes');
    expect(res.pages.some((p) => p.path === '/settings?tab=appearance')).toBe(true);
  });

  it('finds the app tabs, which have routes but no page entry', async () => {
    mockWiki([]);
    const res = await searchAll('wiki');
    expect(res.pages.some((p) => p.path === '/wiki')).toBe(true);
  });

  it('still answers with the pages it has when the wiki is unreachable', async () => {
    mockWiki([], false);
    const res = await searchAll('agents');
    expect(res.pages.length).toBeGreaterThan(0);
    expect(res.wiki).toEqual([]);
  });

  it('returns nothing for an empty query rather than everything', async () => {
    mockWiki([]);
    const res = await searchAll('   ');
    expect(res.pages).toEqual([]);
    expect(res.wiki).toEqual([]);
  });
});

/**
 * THE HELP LINES (2026-09-19) — generated from COMMAND_VERBS, so a verb with no
 * description THROWS here rather than shipping undocumented. The moved verb is
 * the case this pins: `search` is in the set, described, and `find` is offered
 * as its alias.
 */
describe('the help lines', () => {
  it('names every canonical verb, `search` included', () => {
    const listed = verbHelp();
    for (const v of COMMAND_VERBS) expect(listed, v).toContain(v);
  });

  it('describes `search` as the wiki listing, and offers `find` as its alias', () => {
    const line = verbHelp('search');
    expect(line).toContain('wiki');
    expect(line).toContain('NOTHING');
    expect(line).toContain('(also: find)');
    // the alias answers with the verb it resolves to
    expect(verbHelp('find')).toBe(line);
  });
});
