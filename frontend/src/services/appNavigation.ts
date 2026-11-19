/**
 * appNavigation — ONE navigator for "take me there" requests.
 *
 * THE USER'S FRAMING (2026-09-15): "the application is so large now that
 * remembering all the nav paths is becoming a cognitive load I don't
 * want... This is a simple navigation request. Get me there."
 *
 * So this module answers one question: given a name, a path, or something
 * Exa said, WHERE is it — and if it isn't real, say so LOUDLY instead of
 * pretending. Two rules make it trustworthy:
 *
 *  1. THE MAP IS GENERATED, never hand-kept. Pages come from
 *     `getNavigationRoutes()` (config/routes.ts is the single source of
 *     truth), so a new page is reachable the moment it is routed.
 *  2. THE ONE HAND-KEPT TABLE IS DECLARED AS SUCH. The ALIASES below exist
 *     because the Settings tabs are `useState`, invisible to the route
 *     table. The user's very first real request — "open the themes page" —
 *     landed exactly there, so these entries earn their keep. If a tab
 *     becomes a route, delete its alias.
 *
 * Navigation has TWO landings — the user's two axes (2026-09-18):
 *
 *   `nav` / `goto`   move the CURRENT page to the target, in place
 *   `open` / `show`  open the target in a NEW TAB and switch to it
 *
 * The tab landing exists for the reason it always did (see
 * crossTab/navigationService): the current page and any live session survive.
 * The in-place landing is what makes `back` mean anything — under the old rule
 * every command verb opened a tab, so the current page never went anywhere.
 *
 * The axes ALSO break the one tie the ladder could not (2026-09-18, the user
 * live: `nav sessions` opened a NEW TAB while `nav logs` moved the current
 * page): a term can name BOTH a page and an app tab — `sessions` is the route
 * `/sessions` AND the Sessions tab — and the names are identical, so only the
 * LANDING can tell them apart. `nav sessions` takes the page in place,
 * `open sessions` takes the tab; see `dualPage`.
 *
 * `landingFor(verb)` is the ONE place that decides which axis a verb is on. The
 * axis travels INTO `resolveTarget` (it is what breaks a dual name) and rides on
 * the target it returns, where `openTarget` is the ONE place that acts.
 */

import { getNavigationRoutes } from '../config/routes'
import { navigateTo, openReusing, tabAppPath, type TabApp } from './crossTab/navigationService'

export interface PageEntry {
  /** The route path, e.g. '/settings'. */
  path: string
  /** The human name, exactly as the nav shows it. */
  title: string
  description?: string
}

export interface NavTarget {
  /** What to open: a path (with any query) or a tab app's route. */
  to: string
  /** The label to show the user, e.g. 'Settings -> Appearance (themes)'. */
  label: string
  /** 'tab' rides navigateTo (the cross-tab service); 'route' is a plain path. */
  kind: 'route' | 'tab'
  app?: TabApp
  /**
   * WHERE THIS LANDS. `nav`/`goto` land 'replace' (the current page moves),
   * `open`/`show` land 'tab'. The axis is READ by `resolveTarget` — it is what
   * decides a term that names both a page and a tab (see `dualPage`) — and it
   * rides on the target back out, where `openTarget` acts on it. Omitted means
   * a tab — what every caller did before the two axes existed, so a caller that
   * does not care keeps the old behaviour.
   */
  landing?: Landing
  /** Set when the target came from a NEAR-MISS, so the fix can be said out loud. */
  note?: string
}

export type NavResolution =
  | { ok: true; target: NavTarget }
  | { ok: false; error: string; candidates: PageEntry[] }

/** The hand-kept exceptions — surfaces that are NOT routes. */
const ALIASES: Array<{ match: string[]; to: string; label: string }> = [
  // THE WIKI'S FRONT DOOR (2026-09-15, the user's "wiki index?"): /wiki IS
  // the Site Index — verified live, it renders the page table. `nav wiki`
  // already reached it through the tab-app vocabulary; this makes the INDEX
  // nameable directly, which is what the question was really asking.
  { match: ['wiki index', 'site index', 'wiki home', 'index page'],
    to: '/wiki', label: 'Wiki — Site Index' },
  { match: ['themes', 'theme', 'theme picker', 'themes page', 'appearance', 'themes and appearance'],
    to: '/settings?tab=appearance', label: 'Settings -> Appearance (themes)' },
  { match: ['general settings', 'settings general'],
    to: '/settings?tab=general', label: 'Settings -> General' },
  { match: ['notification settings', 'settings notifications', 'notifications'],
    to: '/settings?tab=notifications', label: 'Settings -> Notifications' },
  { match: ['data settings', 'settings data'],
    to: '/settings?tab=data', label: 'Settings -> Data' },
  // SYNONYMS for a route whose OWN name is not the word people reach for.
  // The fuzzy stage is edit distance — it catches typos ("worfklows") and can
  // never map "logging" to "logs", because that is a different word, not a
  // misspelling. Measured before adding: `nav logging` failed with NO
  // candidates and `nav tests` failed while suggesting "Collectives".
  //
  // `log` / `test` / `testing` are deliberately NOT here: the title match
  // already covers them, and `includes('log')` would also capture "catalog".
  { match: ['logging'], to: '/logs', label: 'Logs' },
  { match: ['tests'], to: '/testing-dashboard', label: 'Testing Dashboard' },
  // THE CONFIG SUBJECTS (2026-09-18): what people CALL a setting, mapped to
  // where it actually lives. `config <subject>` rides these. Measured against
  // the live resolver first — theme/appearance/notifications/provider/system/
  // agent/settings all resolved already; these two did not.
  // (The bare word `configuration` went with the mock page in the token-limit
  // arc's A.4 — it now REFUSES rather than pointing at a page that is gone.)
  { match: ['keys', 'api key', 'api keys', 'the keys'],
    to: '/provider-dashboard', label: 'Provider Dashboard — the Keys tab' },
  { match: ['models', 'the models'],
    to: '/providers/cloud', label: 'Providers — Cloud' },
  // THE OTHER SIDE OF A DUAL NAME (2026-09-18). `messages` and `message center`
  // each name a PAGE and an app tab (see dualPage), so the verb's axis decides
  // which you get — `nav messages` the page, `open messages` the tab. The tab
  // keeps its own word; the PAGE needs this one, because its own title,
  // "Message Center", is the tab's word too, and under `open` the page would
  // otherwise have no name at all. It lives in THIS table on purpose: the alias
  // stage runs before the tab stage, so it holds whichever verb was typed.
  { match: ['message list'],
    to: '/messages', label: 'Message Center — the page' },
]

/**
 * The words that ask for the whole map instead of one page. `nav list` and
 * `nav pages` both mean "show me where I can go".
 *
 * These live HERE, above the fuzzy stage, because they need to: measured, a
 * bare `list` resolved to SESSIONS — "list" is a word inside the key
 * "session list", so edit distance gave it a confident distance-0 match. That
 * is exactly the plausible-wrong-jump this module says it refuses to make.
 */
export const LISTING_WORDS = new Set(['list', 'lists', 'pages', 'all', 'everything'])

/** Every destination, for the listing — routes, then aliases, then tabs. */
export function allDestinations(): PageEntry[] {
  const out: PageEntry[] = []
  const seen = new Set<string>()
  const push = (e: PageEntry) => {
    if (!e.path || seen.has(e.path)) return
    seen.add(e.path)
    out.push(e)
  }
  for (const p of pageMap()) push(p)
  for (const a of ALIASES) push({ path: a.to, title: a.label })
  for (const t of TAB_APPS) push({ path: tabAppPath(t.app), title: t.label })
  return out
}

/**
 * Destinations the app opens as its own tab (the TabApp vocabulary).
 *
 * A few of these share their name with a PAGE — `sessions` is also the route
 * `/sessions`, `messages` / `message center` the `/messages` page, `exa` the
 * `/exa` route, `chat` / `agent chat` the `/agent-interaction` page — which is
 * the collision `dualPage` below breaks with the verb's axis. `wiki` is the one
 * that does NOT overlap: its route is `/wiki/*`, and a wildcard route is not in
 * the page map, so `wiki` can only ever be the tab.
 */
const TAB_APPS: Array<{ match: string[]; app: TabApp; label: string }> = [
  { match: ['exa', 'exa page', 'system agent'], app: 'exa', label: 'Exa' },
  { match: ['message center', 'messages'], app: 'messages', label: 'Message Center' },
  { match: ['sessions', 'session list'], app: 'sessions', label: 'Sessions' },
  { match: ['agent chat', 'chat', 'agent interaction'], app: 'agent-chat', label: 'Agent Chat' },
  { match: ['wiki', 'the wiki'], app: 'wiki', label: 'Wiki' },
]

/**
 * WHAT A PATH IS (2026-09-19) — the resolver's own knowledge, for the surfaces
 * that carry only a path.
 *
 * The Search box's rows name a destination as a bare path (`to`), because the
 * history and the listing are path-shaped. That is not enough to know WHERE a
 * row should land: `wiki` is a tab app with no page of its own (its route is a
 * wildcard, so the page map never holds it), while `logs` is a plain page. The
 * rows used to be rebuilt as `kind: 'route'` regardless — which quietly turned
 * every row into a tab, the defect the user reported as *"selecting from the
 * list opens a new tab as opposed to navigating the current page"*.
 *
 * So the question is answered from the tables that already know, in one place,
 * the way `dualPage` answers it for a typed name: a path that is a TAB APP and
 * is NOT a page route is a tab; everything else is a page. Callers get a
 * `NavTarget` they can hand straight to `openTarget`.
 */
export function targetForPath(to: string, label?: string): NavTarget {
  const tab = TAB_APPS.find((t) => tabAppPath(t.app) === to)
  if (tab && !pageMap().some((p) => p.path === to)) {
    return { to, label: label ?? tab.label, kind: 'tab', app: tab.app }
  }
  return { to, label: label ?? to, kind: 'route' }
}

/** The page map, generated from the route table. */
export function pageMap(): PageEntry[] {
  return getNavigationRoutes()
    .filter((r) => !r.path.includes('*') && !r.path.includes(':'))
    .map((r) => ({ path: r.path, title: r.title, description: r.description }))
}

/**
 * THE DUAL NAMES (2026-09-18) — a term that means BOTH a page and an app tab.
 *
 * Found live: `nav sessions` opened a NEW TAB while `nav logs` moved the current
 * page, the same verb both times. `sessions` is the tab app above AND the route
 * `/sessions`; the tab stage ran first, so the tab always won and the verb made
 * no difference at all. The names are identical — only the LANDING differs —
 * which is why the verb's AXIS is the thing that breaks the tie:
 *
 *   `nav` / `goto`   take the PAGE, in place
 *   `open` / `show`  take the tab
 *   no axis given    the tab, as every caller did before the axes existed
 *
 * The page is looked up the way the resolver's own ladder looks one up — its
 * TITLE first, then its ADDRESS (`/sessions` is what `sessions` names) — and
 * ONLY when a tier yields exactly one page. A term that names several pages is
 * not a clean dual name, so the tab keeps the term rather than this stage
 * guessing between pages, which is the one thing this module refuses to do.
 */
function dualPage(term: string): PageEntry | null {
  const all = pageMap()
  const only = (list: PageEntry[]) => (list.length === 1 ? list[0] : null)
  const asAddress = (p: PageEntry) =>
    p.path.replace(/^\//, '').replace(/[/-]/g, ' ').toLowerCase()
  return (
    // the title itself: `message center` is the /messages page
    only(all.filter((p) => p.title.toLowerCase() === term)) ??
    // the page's own address: `sessions` is `/sessions`, `exa` is `/exa`
    only(all.filter((p) => asAddress(p) === term)) ??
    // a title the term sits inside: `chat` is the `Agent Chat` page
    only(all.filter((p) => p.title.toLowerCase().includes(term)))
  )
}

/** The map as prompt text — this is how Exa learns where things are. */
export function pageMapPrompt(): string {
  const lines = pageMap().map((p) => '- ' + p.path + ' — ' + p.title)
  const aliases = ALIASES.map((a) => '- ' + a.to + ' — ' + a.label)
  return [...lines, ...aliases].join('\n')
}

/** Strip the decoration a model likes to wrap a path in. */
function clean(raw: string): string {
  // leading/trailing decoration a model wraps a target in — replaced with
  // "anything that is not a letter, digit or slash", which needs no escapes
  return raw
    .trim()
    .replace(/^[^a-z0-9/]+/i, '')
    .replace(/[^a-z0-9/]+$/i, '')
    .trim()
}

/**
 * THE FILLER (2026-09-15, found live): "nav logs page" failed while "nav
 * logs" worked — and the phrase form is half the point of a vernacular
 * helper, since not knowing the exact name is the reason to use one.
 * Articles and structural nouns carry no destination information, so they
 * come off before matching. A query that is ALL filler keeps its original
 * form rather than becoming an empty string.
 */
const FILLER = new Set([
  'the', 'a', 'an', 'to', 'go', 'please',
  'page', 'pages', 'screen', 'view', 'tab', 'panel', 'section',
])

function normalizeDestination(input: string): string {
  const kept = input
    .toLowerCase()
    .split(/[^a-z0-9/]+/)
    .filter(Boolean)
    .filter((w) => !FILLER.has(w))
  return kept.length > 0 ? kept.join(' ') : input.trim()
}

/** Nearest titles for a loud rejection — never a silent shrug. */
function candidatesFor(needle: string, limit = 5): PageEntry[] {
  const n = needle.toLowerCase()
  const scored = pageMap().map((p) => {
    const t = p.title.toLowerCase()
    let score = 0
    if (t.includes(n) || n.includes(t)) score += 4
    for (const word of n.split(/[^a-z0-9]+/).filter((w) => w.length > 2)) {
      if (t.includes(word)) score += 2
      if (p.path.toLowerCase().includes(word)) score += 1
    }
    return { p, score }
  })
  return scored
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((s) => s.p)
}

/**
 * Resolve anything — a path, a title, an alias — to a real destination.
 * A path that is not in the map is a FAILURE, not a best guess: opening a
 * 404 because it looked plausible is worse than saying "I don't know that
 * one".
 *
 * `landing` is the command verb's AXIS (`landingFor(verb)`), and it decides
 * exactly ONE thing: a name that means BOTH a page and an app tab (see
 * `dualPage`). Every other term resolves the same whichever axis asked, and
 * OMITTED keeps the tab for a dual name — what every caller did before the two
 * axes existed.
 */
export function resolveTarget(raw: string, landing?: Landing): NavResolution {
  const wanted = clean(raw)
  if (!wanted) {
    return { ok: false, error: 'Nothing to open — no destination given.', candidates: [] }
  }

  // 1. a path (with an optional query): validate its base against the map
  if (wanted.startsWith('/')) {
    const base = wanted.split(/[?#]/)[0].replace(/\/+$/, '') || '/'
    const entry = pageMap().find((p) => (p.path.replace(/\/+$/, '') || '/') === base)
    if (entry) {
      return { ok: true, target: { to: wanted, label: entry.title, kind: 'route' } }
    }
    // the aliases are paths too — '/settings?tab=appearance' must survive
    const alias = ALIASES.find((a) => a.to === wanted.split(/\s/)[0])
    if (alias) {
      return { ok: true, target: { to: alias.to, label: alias.label, kind: 'route' } }
    }
    if (wanted.startsWith('/settings')) {
      return { ok: true, target: { to: wanted, label: 'Settings', kind: 'route' } }
    }
    const nearPath = fuzzyResolve(base.replace(/^\//, '').replace(/[/-]/g, ' '))
    if (nearPath.target) return { ok: true, target: nearPath.target }
    return {
      ok: false,
      error: 'There is no page at "' + wanted + '".',
      candidates: mergeCandidates(
        nearPath.candidates,
        candidatesFor(base.replace(/^\//, '').replace(/[/-]/g, ' '))
      ),
    }
  }

  // 2. a named surface that is NOT a route (the declared alias table)
  const low = normalizeDestination(wanted).toLowerCase()
  for (const a of ALIASES) {
    if (a.match.some((m) => low === m || low.includes(m))) {
      return { ok: true, target: { to: a.to, label: a.label, kind: 'route' } }
    }
  }

  // 3. an app tab — UNLESS the same words also name a page, in which case the
  // verb's axis decides (see dualPage). The tab stage runs before the title
  // stage, so without this a dual name could never reach its page.
  for (const t of TAB_APPS) {
    if (t.match.some((m) => low === m)) {
      const page = dualPage(low)
      if (page && landing === 'replace') {
        return { ok: true, target: { to: page.path, label: page.title, kind: 'route', landing } }
      }
      const target: NavTarget = { to: '', label: t.label, kind: 'tab', app: t.app }
      if (landing) target.landing = landing
      return { ok: true, target }
    }
  }

  // 4. a page title, exact then partial
  const byTitle = pageMap()
  const exact = byTitle.find((p) => p.title.toLowerCase() === low)
  if (exact) return { ok: true, target: { to: exact.path, label: exact.title, kind: 'route' } }

  const partial = byTitle.find((p) => p.title.toLowerCase().includes(low))
  if (partial) return { ok: true, target: { to: partial.path, label: partial.title, kind: 'route' } }

  // 5. a NEAR-MISS — the typo case, resolved out loud (see the ladder above)
  const near = fuzzyResolve(normalizeDestination(wanted))
  if (near.target) return { ok: true, target: near.target }

  return {
    ok: false,
    error: 'I do not know a page called "' + wanted + '".',
    candidates: mergeCandidates(near.candidates, candidatesFor(wanted)),
  }
}

/**
 * Take the user there — the ONLY place a navigation happens.
 *
 * The landing comes from the TARGET (`NavTarget.landing`), which the command
 * verbs set from `landingFor(verb)`: `nav`/`goto` move the CURRENT page in
 * place, `open`/`show` take a new tab. The fallback stays a tab, so a caller
 * that does not care keeps the old behaviour.
 */
export function openTarget(target: NavTarget, inPlaceNavigate?: (to: string) => void): void {
  if (target.kind === 'tab' && target.app) {
    navigateTo(target.app)
    return
  }
  const inPlace = (target.landing ?? 'tab') === 'replace'
  if (!inPlace || !inPlaceNavigate) {
    // ONE WINDOW PER DESTINATION, SWITCHED TO RATHER THAN RELOADED (2026-09-19
    // — `openReusing` carries the whole rule, including the measured reason the
    // older `window.open(to, name)` was not enough: it re-navigates the window
    // it finds). The stable name itself is older and unchanged: a second request
    // for the SAME page switches to the tab that already has it instead of
    // stacking a duplicate. (The full tab registry went out with the smart-tab
    // experiment; this is the light version that survives.)
    openReusing(target.to)
    return
  }
  inPlaceNavigate(target.to)
}

/** The machine-readable line Exa is asked to end with. */
export const OPEN_MARKER = 'OPEN:'

/** Pull the marker out of a reply. Returns the cleaned prose + the request. */
export function extractOpenRequest(reply: string): { text: string; request: string | null } {
  const lines = reply.split('\n')
  let request: string | null = null
  const kept: string[] = []
  for (const line of lines) {
    const m = line.match(new RegExp('^\\s*' + OPEN_MARKER + '\\s*(.+?)\\s*$', 'i'))
    if (m && request === null) {
      request = m[1]
      continue // the marker is machinery, never shown
    }
    kept.push(line)
  }
  return { text: kept.join('\n').replace(/\n{3,}/g, '\n\n').trim(), request }
}

// ── THE COMMAND VERBS (2026-09-15) ──────────────────────────────────────
//
// The user: "we can use a small vernacular helper. for example 'nav
// sessions' would mean navigate to the sessions page... we can have an
// info command. like 'Info workflows' that opens the wiki page to a
// suitable page. other command option 'dev architecture' would open a dev
// note on the wiki. 'atlas settings page' would open the wiki atlas on the
// settings page."
//
// THE POINT: these are DETERMINISTIC. `nav` never leaves the browser — the
// routes are already here — so it costs nothing and cannot hallucinate.
// `info`/`dev`/`atlas`/`search` ride the wiki search endpoint that already
// exists.
// The LLM path stays for everything that is not a command — but WHICH MOUNT
// takes it is a per-mount decision (2026-09-18): the header flyout does, and
// the nav sidebar's box answers locally instead (`noCommandAnswer`).

/**
 * THE COMMAND SET.
 *
 * CANONICAL verbs only — aliases resolve to these (see VERB_ALIASES), so `help`
 * lists eleven entries rather than sixteen and a new alias never needs a new
 * help line.
 */
export const COMMAND_VERBS = [
  'nav', 'open', 'config', 'list', 'help', 'back', 'exa', 'info', 'dev', 'atlas',
  'search',
] as const
export type CommandVerb = (typeof COMMAND_VERBS)[number]

/**
 * THE TWO AXES, in the user's words: `nav`/`goto` navigate the CURRENT page to
 * the target; `open`/`show` open it in a NEW TAB and switch to it. That
 * distinction is what makes `back` mean anything at all — under the old
 * rule (every command verb opened a tab) the current page never went anywhere.
 */
const VERB_ALIASES: Record<string, CommandVerb> = {
  goto: 'nav',
  show: 'open',
  conf: 'config',
  configure: 'config',
  // `search` USED TO BE HERE, pointing at `list` (2026-09-19). It is a verb of
  // its own now — the WIKI's search across every namespace — so a search for
  // something and a list of it are told apart by the word typed (see VERB_SCOPE
  // and resolveWikiCommand). `find` is what it gained in the move.
  find: 'search',
}

/** Where a verb's destination lands. Only `open` (and its alias `show`) takes a tab. */
export type Landing = 'tab' | 'replace'
export function landingFor(verb: CommandVerb): Landing {
  return verb === 'open' ? 'tab' : 'replace'
}

export interface ParsedCommand {
  verb: CommandVerb
  /** The verb AS TYPED, so a confirmation can echo what the user actually wrote. */
  typed: string
  /** Everything after the verb; '' when the user typed the verb alone. */
  rest: string
}

/**
 * "nav logs" -> { verb: 'nav', typed: 'nav', rest: 'logs' }.
 *
 * An alias resolves to its canonical verb but keeps `typed`, so "goto logs"
 * echoes as `goto` while behaving exactly as `nav`.
 *
 * A bare verb parses too (rest: '') so the caller can TEACH the shape rather
 * than swallow the input. Anything that is not a verb returns null — and the
 * caller MUST NOT read that as a failure on its own: see nearVerb below.
 */
export function parseCommand(input: string): ParsedCommand | null {
  const m = input.trim().match(/^([A-Za-z]+)\b\s*([\s\S]*)$/)
  if (!m) return null
  const typed = m[1].toLowerCase()
  const verb = (COMMAND_VERBS as readonly string[]).includes(typed)
    ? (typed as CommandVerb)
    : VERB_ALIASES[typed]
  if (!verb) return null
  return { verb, typed, rest: m[2].trim() }
}

/**
 * THE NEAR-VERB — outcome 3 of the parse contract.
 *
 * `parseCommand` returning null used to mean one thing: not a command, hand the
 * text to the agent. That conflates two very different inputs — a QUESTION, and
 * a TYPO of a verb — and the typo is the one that costs something, because it
 * spends a model turn on what the user meant locally.
 *
 * This module already applies exactly this rule to TARGETS ("a near-miss
 * RESOLVES, and the correction is stated out loud"). This is the same rule one
 * level up: only the FIRST word is considered, and only when it is a clear
 * single winner. Two equally-close verbs means the tolerance cannot help, and
 * picking between them would be the guessing this module refuses to do.
 */
export function nearVerb(
  input: string
): { verb: CommandVerb; typed: string; suggest: string } | null {
  const first = input.trim().match(/^([A-Za-z]+)\b/)
  if (!first) return null
  const word = first[1].toLowerCase()
  if (word.length < 3) return null
  // CANONICAL verbs AND the aliases. The user's own example was "gotto", which
  // is one edit from the ALIAS `goto` — scanning only the canonical set would
  // miss the very case this exists for.
  const candidates = [...COMMAND_VERBS, ...Object.keys(VERB_ALIASES)]
  let best: { word: string; verb: CommandVerb; dist: number } | null = null
  // A rival is a DIFFERENT verb at the same distance. Two SPELLINGS of one verb
  // are not a rival: "confg" is one edit from both `conf` and `config`, which is
  // the same destination twice, and refusing that would break the very typo this
  // exists for. Canonical verbs come first in `candidates`, so the suggestion
  // naturally prefers the canonical spelling.
  let rival = false
  for (const w of candidates) {
    const dist = editDistance(word, w)
    const verb = (COMMAND_VERBS as readonly string[]).includes(w)
      ? (w as CommandVerb)
      : VERB_ALIASES[w]
    if (!best || dist < best.dist) {
      best = { word: w, verb, dist }
      rival = false
    } else if (dist === best.dist && verb !== best.verb) {
      rival = true
    }
  }
  // One edit, no rival verb at the same distance. A wider net starts inventing
  // verbs the user did not type.
  if (!best || rival || best.dist > 1) return null
  // `suggest` is the WORD to offer back — an alias when that is what was meant,
  // so the message reads "did you mean `goto`?" rather than naming `nav`.
  return { verb: best.verb, typed: word, suggest: best.word }
}

/**
 * OUTCOMES 3 AND 4 — what an input that matched NO VERB is told (2026-09-18).
 *
 * THE DECISION (the user, 2026-09-18): **the box in the NAV SIDEBAR is a
 * NAVIGATOR and makes no model call.** "talking to exa requires an llm call and
 * takes time; the idea is we want a snappy commandline navigation system, not a
 * tiny chat service." So in THAT mount an input the parser cannot read is
 * answered HERE, instantly, out of what this module already knows — it never
 * becomes a model turn.
 *
 * THE HEADER FLYOUT IS THE OTHER MOUNT, and it keeps the fall-through: it has
 * the room for a short answer and for a stop control, and it is where a
 * DISPATCH is typed ("tell Exa to do that thing"). Which of the two a mount is
 * is ONE option on `useCommandBox` (`exaFallthrough`) — see its docstring.
 *
 * The two cases are kept apart because they are different failures:
 *
 *   - A NEAR-MISS ON A VERB (outcome 3) OFFSETS IT: `navv logs` -> "Did you mean
 *     `nav`?". `nearVerb` above does the work, aliases included.
 *   - ANYTHING ELSE (outcome 4) is told plainly that it is not a command and
 *     pointed at `help` — ONE line, state only (the house rule for UI copy).
 *
 * A REAL VERB IS NOT THIS FUNCTION'S BUSINESS. `nav quantumbulator` parsed
 * fine, and its refusal comes from `resolveTarget` — name what was not found,
 * offer the close matches. That is outcome 2, it already exists, and it is
 * unchanged: the box still says "I do not know a page called ...".
 *
 * `error` drives the panel's tint and its ARIA role. A refusal stays LOUD (this
 * module's rule for anything it refuses), while a correction is the calm
 * near-miss the rest of the module already speaks in — `help confgx` answers
 * with a `did you mean` and is not an error either.
 */
export function noCommandAnswer(input: string): { text: string; error: boolean } {
  const near = nearVerb(input)
  if (near) return { text: 'Did you mean `' + near.suggest + '`?', error: false }
  return { text: 'Unknown command — help lists them.', error: true }
}

/** What each verb searches, and how to describe it in a refusal. */
const VERB_SCOPE: Record<CommandVerb, { prefix: string; label: string }> = {
  nav: { prefix: '', label: 'the app' },
  open: { prefix: '', label: 'the app' },
  config: { prefix: '', label: 'the settings' },
  list: { prefix: '', label: 'everything' },
  // These three are answered LOCALLY and never search a namespace. Their
  // entries exist only because the record is total.
  help: { prefix: '', label: 'the command list' },
  back: { prefix: '', label: 'your history' },
  // `exa` searches NOTHING — it is the escape hatch TO the model. It exists so
  // a question that opens with a verb word ("search is broken on the tools
  // page") reaches Exa instead of being read as that verb. Bare, it opens the
  // Exa page. (2026-09-18: a mount WITHOUT the Exa path — the nav sidebar's box
  // — opens the Exa CHAT TAB for the question instead of sending it.)
  exa: { prefix: '', label: 'Exa' },
  info: { prefix: '', label: 'the wiki' },
  dev: { prefix: 'dev-notes', label: 'the dev notes' },
  atlas: { prefix: 'atlas', label: 'the atlas' },
  // `search` (and its alias `find`) is the WIKI's own search across EVERY
  // namespace — no prefix — so it reads `info`'s scope. What separates the two
  // is what they DO with the hits, not what they search (see
  // resolveWikiCommand): `info` opens the one best page, `search` lists them
  // all. And it is the CONTENT search: the word `wiki` alone names the wiki
  // TAB, which `open wiki` takes.
  search: { prefix: '', label: 'the wiki' },
}

/**
 * WHAT EACH VERB DOES — one line each, for `help`.
 *
 * The LIST is generated from COMMAND_VERBS and never hand-typed: a verb with no
 * description here fails LOUDLY at `verbHelp` rather than going quietly
 * undocumented. Same principle as the page map — generated, and it fails loudly.
 */
const VERB_HELP: Record<CommandVerb, string> = {
  nav: 'go to a page in THIS tab — `nav logs`, `nav the settings page`',
  open: 'open a page in a NEW tab — `open logs`',
  config: 'go to the page holding a setting — `config theme`, `config provider`',
  list: 'list what matches and open nothing — `list workflow`; bare `list` shows everything',
  help: 'this list; `help nav` describes one verb',
  back: 'return to the previous page in this tab',
  exa: 'ask the system agent — `exa is search broken?` skips the grammar entirely',
  info: 'open the best wiki page — `info workflows`',
  dev: 'open the best dev note — `dev architecture`',
  atlas: 'open the best atlas page — `atlas settings page`',
  search: 'list every wiki page that matches, and open NOTHING — `search triggers`; `info` opens the best hit',
}

/** The aliases, grouped by canonical verb, for the help line. */
function aliasesOf(verb: CommandVerb): string[] {
  return Object.keys(VERB_ALIASES).filter((a) => VERB_ALIASES[a] === verb)
}

/**
 * `help` and `help <verb>`. Generated from COMMAND_VERBS, so the list cannot
 * drift from the parser — a verb added to the set appears here immediately, and
 * one added without a VERB_HELP line throws instead of hiding.
 */
export function verbHelp(which?: string): string {
  const wanted = (which ?? '').trim().toLowerCase()
  if (wanted) {
    const verb = (COMMAND_VERBS as readonly string[]).includes(wanted)
      ? (wanted as CommandVerb)
      : VERB_ALIASES[wanted]
    if (!verb) {
      const near = nearVerb(wanted)
      return near ? `I do not know \`${wanted}\`. Did you mean \`${near.suggest}\`?` : `I do not know \`${wanted}\`.`
    }
    const line = VERB_HELP[verb]
    if (!line) throw new Error('no help line for verb: ' + verb)
    const alias = aliasesOf(verb)
    return `\`${verb}\` — ${line}` + (alias.length ? `\n(also: ${alias.join(', ')})` : '')
  }
  const lines = COMMAND_VERBS.map((v) => {
    const line = VERB_HELP[v]
    if (!line) throw new Error('no help line for verb: ' + v)
    const alias = aliasesOf(v)
    return `${v.padEnd(7)}${line}` + (alias.length ? `   (also: ${alias.join(', ')})` : '')
  })
  return lines.join('\n')
}

export interface WikiHit {
  path: string
  title: string
  score: number
  snippet: string
}

/** The wiki's own search — already built, no new backend surface. */
export async function searchWiki(q: string, prefix = ''): Promise<WikiHit[]> {
  const params = new URLSearchParams({ q })
  if (prefix) params.set('prefix', prefix)
  const res = await fetch('/api/v1/wiki/search?' + params.toString())
  if (!res.ok) throw new Error('wiki search failed: HTTP ' + res.status)
  const body = (await res.json()) as { results?: WikiHit[] }
  return Array.isArray(body?.results) ? body.results : []
}

/**
 * Walk the wiki for `info` / `dev` / `atlas` / `search`. The first three open
 * one clear winner, and a TIE returns the candidates instead of picking one —
 * the same rule as resolveTarget, for the same reason. `search` lists every
 * hit and opens none of them; see the listing branch below.
 */
export async function resolveWikiCommand(cmd: ParsedCommand): Promise<NavResolution> {
  const scope = VERB_SCOPE[cmd.verb]
  // LISTS or OPENS — the one thing `search` does differently, read once here
  // rather than at each return (see the search verb docstring for why).
  const lists = cmd.verb === 'search'
  if (!cmd.rest) {
    return {
      ok: false,
      error: lists
        ? `Search ${scope.label} for what? Try "${cmd.verb} <term>".`
        : `Which ${scope.label} page? Try "${cmd.verb} <topic>".`,
      candidates: [],
    }
  }

  let hits: WikiHit[]
  try {
    hits = await searchWiki(cmd.rest, scope.prefix)
  } catch {
    return { ok: false, error: 'Could not reach the wiki search.', candidates: [] }
  }

  if (hits.length === 0) {
    return {
      ok: false,
      error: `Nothing in ${scope.label} matches "${cmd.rest}".`,
      candidates: [],
    }
  }

  const asCandidates = (h: WikiHit[]): PageEntry[] =>
    h.slice(0, 5).map((x) => ({ path: '/wiki/' + x.path, title: x.title, description: x.snippet }))

  // `search` LISTS — the matches ARE the answer, so every hit comes back as a
  // candidate and `pickWinner` is never consulted: even a single clear winner
  // is offered rather than opened. Same shape as a tie's refusal, because it
  // lands in the same panel (the candidates are buttons the user opens).
  if (lists) {
    return {
      ok: false,
      error:
        `"${cmd.rest}" matches ${hits.length} page${hits.length === 1 ? '' : 's'}` +
        ` in ${scope.label} — pick one.`,
      candidates: asCandidates(hits),
    }
  }

  const winner = pickWinner(hits, cmd.rest)
  if (!winner) {
    return {
      ok: false,
      error: `"${cmd.rest}" matches ${hits.length} pages in ${scope.label} — which one?`,
      candidates: asCandidates(hits),
    }
  }

  return {
    ok: true,
    target: { to: '/wiki/' + winner.path, label: winner.title || cmd.rest, kind: 'route' },
  }
}

/**
 * WHICH of the tied hits to open.
 *
 * Real data makes the ties the normal case, not the exception: measured
 * against the live wiki, "dev architecture" returns FOUR notes at the same
 * score (the title term alone) and "atlas settings page" returns four as
 * well. Handing back a list every time would make the flagship commands
 * feel broken, so ties break on evidence the USER gave us, in order:
 *
 *  1. A STRUCTURAL SEGMENT they named. The atlas mirrors the app's shape
 *     (api/routers, ui/hooks, ui/pages), so "atlas settings page" means the
 *     `ui/pages/` one — that is what the word "page" was doing.
 *  2. THE REMAINING NOUN IN THE TITLE. "settings page" leaves "settings":
 *     the note actually TITLED Settings beats one that merely mentions it.
 *  3. A HUB. "dev architecture" ties four ways, and the Architecture Index
 *     is the documented entry point to the other three.
 *
 * Still tied after all that? Return null and let the caller show the
 * candidates — picking then is guessing, which is the one thing this module
 * refuses to do.
 */
const STRUCTURE_SEGMENTS = [
  'page', 'hook', 'router', 'service', 'component', 'workflow', 'node', 'store',
]

function pathSegments(path: string): string[] {
  return path.toLowerCase().split('/')
}

function pickWinner(hits: WikiHit[], query: string): WikiHit | null {
  const top = hits[0]
  const tied = hits.filter((h) => h.score === top.score)
  if (tied.length === 1) return top

  const terms = query.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean)

  // 1. a structural segment the query named ("... page" -> ui/pages/...)
  const named = STRUCTURE_SEGMENTS.filter((s) => terms.includes(s) || terms.includes(s + 's'))
  let pool = tied
  for (const seg of named) {
    const inSegment = pool.filter((h) =>
      pathSegments(h.path).some((part) => part === seg || part === seg + 's')
    )
    if (inSegment.length > 0) pool = inSegment
  }

  // 2. the leftover noun, matched against the TITLE (what it is about)
  const leftover = terms.filter((t) => !STRUCTURE_SEGMENTS.includes(t.replace(/s$/, '')))
  if (leftover.length > 0) {
    const titled = pool.filter((h) =>
      leftover.some((t) => h.title.toLowerCase().includes(t))
    )
    if (titled.length === 1) return titled[0]
    if (titled.length > 1) pool = titled
  }

  // 3. a hub — the entry point to the rest
  const hubs = pool.filter(
    (h) => /\b(index|overview)\b/i.test(h.title) || /index$/i.test(h.path)
  )
  if (hubs.length === 1) return hubs[0]

  return null
}

// ── TYPO TOLERANCE (2026-09-15) ─────────────────────────────────────────
//
// The user, verbatim: "You: nav worfklows / I do not know a page called
// "worfklows"." A transposition is not a wrong request — it is a fast
// typist — and a vernacular helper that dead-ends on one is a helper
// nobody keeps using.
//
// So a near-miss RESOLVES, and the correction is stated out loud. A silent
// fix would be worse than the dead end: it hides the day the guess is
// wrong, and the reader learns not to trust the outcome line.

/**
 * Damerau-Levenshtein (optimal string alignment), so a TRANSPOSITION costs
 * 1: "worfklows" -> "workflows" measures 1, where plain Levenshtein says 2.
 */
function editDistance(a: string, b: string): number {
  const m = a.length
  const n = b.length
  if (!m) return n
  if (!n) return m
  const d: number[][] = Array.from({ length: m + 1 }, () => new Array<number>(n + 1).fill(0))
  for (let i = 0; i <= m; i++) d[i][0] = i
  for (let j = 0; j <= n; j++) d[0][j] = j
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
        d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1)
      }
    }
  }
  return d[m][n]
}

interface FuzzyEntry {
  target: NavTarget
  keys: string[]
}

/** Everything a name could mean: pages, the declared aliases, the app tabs. */
function fuzzyPool(): FuzzyEntry[] {
  const pool: FuzzyEntry[] = pageMap().map((p) => ({
    target: { to: p.path, label: p.title, kind: 'route' as const },
    keys: [p.title, p.path.replace(/^\//, '').replace(/[/-]/g, ' ')],
  }))
  for (const a of ALIASES) {
    pool.push({ target: { to: a.to, label: a.label, kind: 'route' }, keys: [a.label, ...a.match] })
  }
  for (const t of TAB_APPS) {
    pool.push({
      target: { to: '', label: t.label, kind: 'tab', app: t.app },
      keys: [t.label, ...t.match],
    })
  }
  return pool
}

interface FuzzyHit {
  entry: FuzzyEntry
  dist: number
}

function fuzzyHits(query: string): FuzzyHit[] {
  const q = query.toLowerCase().trim()
  if (q.length < 3) return []
  const hits: FuzzyHit[] = []
  for (const entry of fuzzyPool()) {
    let best: number | null = null
    for (const key of entry.keys) {
      const k = key.toLowerCase()
      // compare against the whole key AND its words: "agent profiles" must
      // not lose to "agent" merely because the phrase is longer
      const cands = [k, ...k.split(/[^a-z0-9]+/).filter((w) => w.length > 2)]
      for (const c of cands) {
        const dist = editDistance(q, c)
        if (best === null || dist < best) best = dist
      }
    }
    if (best !== null) hits.push({ entry, dist: best })
  }
  return hits.sort((a, b) => a.dist - b.dist)
}

/**
 * Resolve a near-miss — but only when ONE candidate is clearly nearest.
 * Two equally-close pages means the typo tolerance cannot help, and picking
 * between them would be the guessing this module refuses to do.
 */
function fuzzyResolve(input: string): { target: NavTarget | null; candidates: PageEntry[] } {
  const q = input.toLowerCase().trim()
  const hits = fuzzyHits(q)
  if (hits.length === 0) return { target: null, candidates: [] }

  // longer names tolerate proportionally more, but never a wild swing
  const maxDist = Math.max(1, Math.floor(q.length / 3))
  const best = hits[0]
  const second = hits[1]
  // Measured, not guessed: "worfklows" is distance 1 from the page TITLED
  // Workflows and distance 2 from four sibling Workflow* pages, so demanding
  // a two-point margin refused the very typo this exists for. Strictly
  // nearer than the runner-up (within the proportional ceiling) is the rule
  // that matches the data; equal distances still return candidates.
  const clearWinner = best.dist <= maxDist && (!second || best.dist < second.dist)

  const candidates: PageEntry[] = hits
    .filter((h) => h.dist <= maxDist + 1 && h.entry.target.to)
    .slice(0, 5)
    .map((h) => ({ path: h.entry.target.to, title: h.entry.target.label }))

  if (!clearWinner) return { target: null, candidates }
  return { target: { ...best.entry.target, note: 'read as "' + best.entry.target.label + '"' }, candidates: [] }
}

/** Merge candidate lists by path, order preserved, capped. */
function mergeCandidates(...lists: PageEntry[][]): PageEntry[] {
  const seen = new Set<string>()
  const out: PageEntry[] = []
  for (const list of lists) {
    for (const c of list) {
      if (!c.path || seen.has(c.path)) continue
      seen.add(c.path)
      out.push(c)
    }
  }
  return out.slice(0, 5)
}

// ── THE LIST VERB (2026-09-15; `search` moved off it 2026-09-19) ───────
//
// The user: "lets add a search command to the ask exa... popup -> search ->
// show links -> navigate."
//
// `list` is the verb that NEVER opens anything: showing the matches IS the
// answer. That is the whole distinction from `info`/`dev`/`atlas`, which mean
// "open the best hit" — blur the two and you stop knowing which to type.
//
// Two sources, both already live: the app's own destinations (the route map,
// client-side and therefore instant) and the wiki (its existing search). They
// come back GROUPED, because a term that matches both must not hide one.
//
// 2026-09-19: `search` was this verb's ALIAS and is now a verb of its own — the
// WIKI's search across every namespace, listing its hits in the same panel.
// `list` is the app map PLUS the wiki; `search`/`find` are the wiki alone. Two
// different questions, two words.

export interface SearchResults {
  terms: string
  pages: PageEntry[]
  wiki: PageEntry[]
}

/** Every destination matching the terms. Nothing is opened here. */
export async function searchAll(terms: string): Promise<SearchResults> {
  const query = normalizeDestination(terms).toLowerCase().trim()
  if (!query) return { terms, pages: [], wiki: [] }
  const words = query.split(/\s+/).filter((w) => w.length > 1)
  const matches = (hay: string) => words.some((w) => hay.toLowerCase().includes(w))

  // 1. the app's pages
  const pages: PageEntry[] = []
  const seen = new Set<string>()
  const push = (entry: PageEntry) => {
    if (!entry.path || seen.has(entry.path)) return
    seen.add(entry.path)
    pages.push(entry)
  }
  for (const p of pageMap()) {
    if (matches(p.title) || matches(p.path)) push(p)
  }
  // the declared aliases are destinations too ("themes" -> Settings/Appearance)
  for (const al of ALIASES) {
    if (al.match.some(matches) || matches(al.label)) push({ path: al.to, title: al.label })
  }
  // and the app tabs, which have routes but no PageEntry of their own
  for (const t of TAB_APPS) {
    if (t.match.some(matches) || matches(t.label)) {
      push({ path: tabAppPath(t.app), title: t.label })
    }
  }

  // 2. the wiki
  let wiki: PageEntry[] = []
  try {
    const hits = await searchWiki(terms, '')
    wiki = hits.slice(0, 10).map((h) => ({
      path: '/wiki/' + h.path,
      title: h.title,
      description: h.snippet,
    }))
  } catch {
    // a search that cannot reach the wiki still answers with the pages it has
    wiki = []
  }

  return { terms, pages: pages.slice(0, 12), wiki }
}
