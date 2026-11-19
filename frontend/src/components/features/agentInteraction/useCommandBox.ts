/**
 * useCommandBox — the command box's logic.
 *
 * Owns the box's state, the local command verbs (resolved against the app's
 * own route table, never sent to Exa), the bridge a free-form question rides,
 * and the effects that open, close and focus the box. The panel that draws it
 * (CommandBoxPanel) and the two widgets that mount it (ExaPromptFlyout,
 * NavSearchSection) hold no logic of their own.
 *
 * THE TWO MOUNTS DO NOT ASK THE SAME QUESTION (2026-09-18).
 *
 *   - THE SIDEBAR (`NavSearchSection`, 16rem) is a NAVIGATOR and makes no
 *     model call: a verb moves you, `exa <question>` opens the Exa CHAT TAB,
 *     and an input that is not a command gets a ONE-LINE LOCAL answer
 *     (`appNavigation.noCommandAnswer`) instead of a fall-through to Exa.
 *     There is no room in that column for an answer or for a stop control,
 *     and the whole value of the box there is being instant.
 *   - THE HEADER FLYOUT (`ExaPromptFlyout`, 440px) KEEPS THE EXA PATH: it has
 *     room for a short answer and for stopping a run, and it is where a
 *     DISPATCH goes — "tell Exa to do that thing" — so an unparseable input
 *     still falls through to the bridge exactly as it always did.
 *
 * The difference is ONE per-mount option, `exaFallthrough` (default FALSE), and
 * it is deliberately a GRANT rather than an inherited capability (the P4 rule:
 * capabilities start off and are turned on by an explicit, visible opt-in). The
 * mounts differ in nothing else — same verbs, same panel, same history.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { clearNavHistory, navHistory, recordNav, type NavHistoryEntry } from '@/services/navHistory';
import { notifyBus } from '@/services/notifyBus';
import { navigateTo } from '@/services/crossTab/navigationService';
import { useNavigate } from 'react-router-dom';
import {
  allDestinations,
  extractOpenRequest,
  LISTING_WORDS,
  noCommandAnswer,
  openTarget,
  pageMapPrompt,
  parseCommand,
  resolveTarget,
  resolveWikiCommand,
  searchAll,
  targetForPath,
  type PageEntry,
  type SearchResults,
  type NavResolution,
  type NavTarget,
  type ParsedCommand,
  type CommandVerb,
  landingFor,
  verbHelp,
} from '@/services/appNavigation';
import { requestPageFocus } from '@/services/focusContract';

/**
 * THE BOX'S LISTS ARE THE COMBOBOX'S LISTBOX (2026-09-19 — the user: a keyboard
 * user reaches for ArrowDown and nothing happens). The material is
 * local/studies/keyboard-accelerators.md: §3 is the pattern, §4 what the box did
 * before, §5 item 4 the Escape order.
 *
 * A text input with a results list is a COMBOBOX, and the WAI-ARIA Authoring
 * Practices are explicit about where the focus is: DOM focus stays in the
 * TEXTBOX, and the list carries a VIRTUAL focus — a highlight named by the
 * input's `aria-activedescendant`. A row is therefore DATA, not a focusable
 * widget: it is not a Tab stop, and the only thing that moves over it is
 * `activeIndex`.
 *
 * AND KEEPING THAT ROW ON SCREEN IS THE PANEL'S HALF (2026-09-19), because the
 * hook cannot do it: a virtual focus scrolls nothing, and the browser's own
 * scrolling of the panel was the arrow keys' behaviour that the combobox
 * replaced — so nothing here may assume the active row is visible. The panel
 * scrolls the row into view whenever it changes; see CommandBoxPanel's scroll
 * effect and local/studies/keyboard-accelerators.md §3.
 *
 * ONE MODEL FOR EVERY LIST (§7). The candidate results, a tie's candidates and
 * the Frequent shortcuts are all `CommandOption`s drawn in ONE order, so the
 * keys and the ARIA contract cannot be right in one list and missing in another.
 * The ACTION is deliberately not on the row: `accept` is the one place a row
 * opens, keyed by the group it came from.
 *
 * THE BOX HAS ONE POPUP, NOT SEVERAL (2026-09-19, the user: "I have a frequent
 * list which I cannot get to"). The Frequent list was a row model the keys could
 * reach but a popup the box did not admit to: `aria-expanded` said false while
 * its rows were on screen, End/Home were refused over it, and Escape closed the
 * whole box rather than the list in front of the reader. So the POPUP is now the
 * drawn set of rows — ANY group, Frequent included — and `listOpen` means
 * exactly "there is a list on screen". Escape puts that whole popup away
 * (`listDismissed`), and Up/Down bring it back: that is what gives a keyboard
 * user a way IN to Frequent that is not one row at a time.
 */
export type CommandOptionGroup = 'pages' | 'wiki' | 'candidates' | 'frequent';

export interface CommandOption {
  /** The DOM id `aria-activedescendant` names while this row is active. */
  id: string;
  /** Which list drew it — the panel draws one listbox per group. */
  group: CommandOptionGroup;
  /** The row's name, as the panel shows it. */
  title: string;
  /** The metadata beside the name (a path); the panel falls back to `to`. */
  sub?: string;
  /** The destination this row opens. */
  to: string;
}

/**
 * The listbox ids, per group. `aria-controls` names the ones a render DREW —
 * the box has more than one list, so the input cannot point at "the" list.
 */
export const COMMAND_LIST_IDS: Record<CommandOptionGroup, string> = {
  pages: 'cmdbx-list-pages',
  wiki: 'cmdbx-list-wiki',
  candidates: 'cmdbx-list-candidates',
  frequent: 'cmdbx-list-frequent',
};

/**
 * Every option row's id. INDEX-BASED on purpose: the ids have to follow the DOM
 * order the panel draws, and a path is not a unique key — the same page can sit
 * in a result group and in Frequent at the same time.
 */
const OPTION_ID_PREFIX = 'cmdbx-option-';

/**
 * WHAT THE PANEL DRAWS ONCE THE POPUP IS PUT AWAY (`listDismissed`) — a stable
 * empty array, so the state change does not hand the panel a new identity per
 * render. See `options` and `closeList`.
 */
const NO_OPTIONS: CommandOption[] = [];

/**
 * THE DIRECTIVE (v1 of form 2 — Exa opens the page).
 *
 * This is how Exa learns where things are: the MAP IS GENERATED from the
 * route table (see services/appNavigation), so a new page is known the
 * moment it is routed — nobody hand-keeps this list.
 *
 * The refinement is a typed tool whose schema carries the same enum, which
 * removes the free-text step. The frontend side is identical either way:
 * something produces a destination, resolveTarget validates it, openTarget
 * navigates. The prose instruction is the part that gets replaced.
 */
let cachedDirective: string | null = null;

/**
 * THE DIRECTIVE, BUILT LAZILY — and that is not a style choice.
 *
 * It was a module-scope template literal, and PageBanner importing this
 * widget closed a CYCLE (config/routes -> pages -> PageBanner -> this file ->
 * services/appNavigation -> config/routes). The literal therefore evaluated
 * before `routes` had initialised, and every mount threw
 * "Cannot access '__vite_ssr_import_0__' before initialization" — a crash
 * that only shows up at runtime, never at type-check time.
 *
 * Computing it on first use costs one build per session and cannot race the
 * import graph.
 */
function appNavDirective(): string {
  if (cachedDirective === null) {
    cachedDirective = `

[App navigation] If the user asks you to open, show, or take them to a page in this app, end your reply with ONE final line:
OPEN: <path>
Use an EXACT path from this list:
${pageMapPrompt()}
If nothing in the list matches what they asked for, do NOT emit the line — say plainly that you could not find it.`;
  }
  return cachedDirective;
}

interface UseCommandBoxOptions {
  /**
   * The coexisting path: open/focus the Exa Agent page. Optional — the
   * widget defaults to the app's own Exa destination, so a mount with no
   * props is complete (that is how PageBanner carries it).
   */
  onOpenExaPage?: () => void;
  /**
   * Cmd/Ctrl+K opens the box. Default FALSE — and nobody arms it (2026-09-18).
   *
   * The app-wide key is ONE listener, and it belongs to the SHELL
   * (NavSearchHotkey), not to a mount: the box's home is the nav sidebar's
   * section, which is not even rendered while the sidebar is collapsed, so a
   * listener inside a mount would be dead in the very case the key exists to
   * serve — and with two mounts armed it was a real bug, Cmd/Ctrl+K opening
   * the header flyout AND pulling focus into the sidebar box.
   *
   * The default is false rather than true so that shape cannot come back by
   * accident: arming a second listener takes a deliberate opt-in, and the one
   * place that means it is the shell. The header's mount passes false
   * explicitly so the decision is visible where the trigger is; the capability
   * stays here because a mount that ever legitimately needs its own key (a
   * full-page surface with no shell around it) should reuse this listener
   * rather than write a second one.
   */
  hotkey?: boolean;
  /**
   * THE CARET POLICY FOR A MOUNT THAT OUTLIVES A NAVIGATION (2026-09-18,
   * restated 2026-09-19).
   *
   * TRUE: on a TAB landing — the destination is a window of its own and THIS
   * document is untouched — the input takes the caret back, so the next command
   * is typed without reaching for the mouse. FALSE (default): the hook does not
   * touch the caret at all.
   *
   * IT DOES NOT DECIDE WHERE THE CARET GOES ON AN IN-PLACE NAVIGATION. That one
   * is the app's rule and it is uniform: a navigation the reader asked for hands
   * the caret to the PAGE (`requestPageFocus` / `claimPageFocus`,
   * services/focusContract) — the user's report was being left in the nav panel,
   * and "the box stays open" is not a reason to keep them there. The box does
   * stay open either way: nothing in this hook closes a box on a navigation, and
   * a mount that wants it gone owns that itself.
   *
   * The header's flyout asks for true only when `appearance.keepCommandBoxOpen`
   * is granted (Settings > Appearance); the sidebar asks for it always.
   */
  staysOpen?: boolean;
  /**
   * THE EXA PATH, GRANTED PER MOUNT (2026-09-18). Default FALSE.
   *
   * TRUE — the HEADER FLYOUT. An input that is not a command falls through to
   * Exa over the bridge (`sendPrompt`), and `exa <question>` forces it there
   * with the prefix stripped. This is the box's original behaviour, and the
   * flyout asks for it explicitly because it has room for a short answer and
   * for a stop control, and because it is where a DISPATCH is typed: "tell Exa
   * to do that thing" — background work whose report arrives through the app's
   * message system rather than in the box.
   *
   * FALSE (default) — the NAV SIDEBAR, and any future mount. The box is a
   * NAVIGATOR and makes NO model call: a non-command input is answered LOCALLY
   * and instantly (`noCommandAnswer`: the near-verb offer, or the one-line
   * "Unknown command — help lists them."), and `exa <question>` opens the Exa
   * CHAT TAB — the chat owns the call, its own Stop and its own session, which
   * is why a nav-only mount needs no stop button anywhere.
   *
   * WHY THE DEFAULT IS FALSE: a capability is a GRANT, not something a new
   * mount inherits by accident (design/integration-boundaries.md, P4) — and the
   * expensive, slow path is exactly the one that must be opted into visibly.
   * A third attachment therefore gets the snappy navigator unless it says
   * otherwise, and the one line that says otherwise is where the mount is.
   */
  exaFallthrough?: boolean;
  /**
   * THE BOX CAN BE OPEN BEFORE THIS MOUNT DRAWS IT (2026-09-19). Default
   * FALSE, read ONCE at mount — it is a starting state, not a live link.
   *
   * The header flyout owns its flag outright: it starts closed and opens on a
   * click. The nav sidebar does not — its open state is the STORE's
   * (`navSearchOpen`, persisted), so a fresh page load can draw the panel on
   * the first paint. Handing that fact in makes the hook's own flag agree with
   * the one on screen, and it is not bookkeeping: the hook's `open` is what
   * ARMS Escape and the click-away (see the close effect below) and what loads
   * the shortcut list. A mount that draws an open box without it gets a panel
   * that looks open and behaves closed — Escape and a click away did nothing,
   * and Frequent was empty.
   *
   * An ARRIVAL IS NOT AN OPENING (see the open effect below): the mount that
   * arrived open owns the CARET, because the yield to a page declaring its own
   * primary input (`data-autofocus`, services/focusContract) is a rule about
   * arriving, and it belongs to the mount that arrives.
   */
  initiallyOpen?: boolean;
  /**
   * THE MOUNT'S OWN HALF OF CLOSING (2026-09-19). Optional; called from
   * `close()`, so EVERY way out reports it — the panel's ✕, Escape, a click
   * away.
   *
   * The flyout passes none: its flag IS the hook's. The nav sidebar passes one
   * because the flag it renders from is the STORE's, and a close that stopped
   * at the hook would leave the panel drawn (the section draws from the store)
   * while the hook believed it was closed — the desync this exists to prevent.
   * One close path, one place for a mount to mirror it.
   */
  onClose?: () => void;
}

interface WsMsg {
  type: 'status' | 'message' | 'thought' | 'tool_call' | 'done';
  text?: string;
  status?: string;
  message?: string;
  reply?: string;
  update?: { title?: string; kind?: string; rawInput?: unknown };
}

export function useCommandBox({
  onOpenExaPage,
  hotkey = false,
  staysOpen = false,
  exaFallthrough = false,
  initiallyOpen = false,
  onClose,
}: UseCommandBoxOptions = {}) {
  const openExaPage = onOpenExaPage ?? (() => navigateTo('exa'));
  const [open, setOpen] = useState(initiallyOpen);
  /**
   * True until the open effect's first run — that run is the ARRIVAL when the
   * mount was handed an open box, and an arrival is not an opening (see the
   * effect below).
   */
  const arrivedOpen = useRef(initiallyOpen);
  const [question, setQuestion] = useState('');
  /** The question the current answer belongs to — the exchange reads as Q/A. */
  const [asked, setAsked] = useState('');
  const [answer, setAnswer] = useState('');
  const [activity, setActivity] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  /** The shortcuts this session has earned — shown when the box is idle. */
  const [history, setHistory] = useState<NavHistoryEntry[]>([]);
  /** True when the shortcut list is expanded past its first six. */
  const [showAllHistory, setShowAllHistory] = useState(false);
  /** The `list` verb's grouped matches — the box's listbox; nothing opened. */
  const [results, setResults] = useState<SearchResults | null>(null);

  /** The navigation result, shown inline — success tinted, failure loud. */
  const [outcome, setOutcome] = useState<{
    text: string
    error: boolean
    candidates?: PageEntry[]
  } | null>(null);

  /**
   * THE ACTIVE OPTION — the row the list's VIRTUAL focus is on (2026-09-19).
   *
   * `-1` is "no active option", and it is a state, not a gap to be papered
   * over: with no row active the box is being EDITED, and Enter runs the typed
   * command exactly as it always has. So `-1` is where the box starts, where
   * typing puts it back, and where Up from the first row returns.
   */
  const [activeIndex, setActiveIndex] = useState(-1);

  /**
   * THE READER PUT THE POPUP AWAY (2026-09-19) — Escape's second job.
   *
   * The settled rule (local/studies/keyboard-accelerators.md §5 item 4) is that
   * Escape closes the LIST first and the box second. Until now only the lists a
   * COMMAND produced could answer "is a list on screen", so with Frequent in
   * front of the reader the first Escape closed the BOX — a key that dismissed
   * more than the reader asked it to, and the reason the box's `aria-expanded`
   * was false while rows were drawn.
   *
   * The Frequent list is not a command's answer; it is what the box shows when
   * the reader has typed nothing, so there is no state to clear to put it away.
   * This flag is that state: while it is set the drawn set is EMPTY — the panel
   * draws no list, `aria-expanded` is false, and the second Escape closes the
   * box. Up/Down (and Alt+Down) bring the popup back, which is also how a
   * keyboard user gets INTO Frequent rather than tapping Down once per row.
   *
   * It is cleared where a list is PRODUCED (`ask`) and where the box is opened,
   * so a stale dismissal can never hide a list a command just earned.
   */
  const [listDismissed, setListDismissed] = useState(false);

  /**
   * THE BOX'S ROWS, IN DRAW ORDER — one model for every list.
   *
   * The panel draws these grouped and in this order (pages, wiki, a tie's
   * candidates, then the shortcuts) and the keys move over them, so the two
   * halves cannot disagree about what "the next row" is. The conditions mirror
   * the panel's own — the shortcuts are drawn only while the box is idle — so
   * the active row can never name a row the reader cannot see.
   *
   * THIS IS THE WHOLE MODEL, DISMISSAL OR NOT (`allRows`), because the keys have
   * to be able to move over the rows the reader just put away: Up opens a
   * dismissed popup at its LAST row, and a mover that only knew about what is
   * drawn would find nothing to open. What the panel DRAWS is `options` below.
   */
  const allRows = useMemo<CommandOption[]>(() => {
    const rows: CommandOption[] = [];
    const push = (group: CommandOptionGroup, title: string, sub: string, to: string) =>
      rows.push({ id: OPTION_ID_PREFIX + rows.length, group, title, sub, to });

    // THE CANDIDATE LISTS — what the `list`/`search` verbs put up to be picked.
    results?.pages.forEach((r) => push('pages', r.title, r.path, r.path));
    results?.wiki.forEach((r) => push('wiki', r.title, r.path, r.path));
    // A TIE'S CANDIDATES are rows of the same shape, so they are the same kind
    // of option — the reader picks one the same way.
    outcome?.candidates?.forEach((c) => push('candidates', c.title, c.path, c.path));
    // THE SHORTCUTS — drawn whenever the box is idle, including after a command.
    if (!busy && history.length > 0) {
      (showAllHistory ? history : history.slice(0, 6)).forEach((h) =>
        push('frequent', h.label, h.to, h.to)
      );
    }
    return rows;
  }, [results, outcome, history, showAllHistory, busy]);

  /**
   * THE ROWS ON SCREEN — WHAT THE PANEL DRAWS AND WHAT `aria-expanded` REPORTS
   * (2026-09-19). One popup: the whole model, or nothing once the reader has put
   * it away. Every list the panel draws comes from HERE, so "a list is up" and
   * "aria-expanded is true" cannot part company — which they did while the
   * Frequent list was drawn behind `aria-expanded="false"`.
   */
  const options = listDismissed ? NO_OPTIONS : allRows;

  /** The option the input's `aria-activedescendant` names; null = editing. */
  const activeOption = options[activeIndex] ?? null;

  /**
   * A NEW LIST STARTS AT ITS FIRST ROW (2026-09-19).
   *
   * This is the combobox's `type -> the active option resets to the first`,
   * kept where it is TRUE. The candidate lists ARE the box's listbox — a
   * command whose answer is a list, or a tie — so when one ARRIVES the first
   * row is active and Enter opens it. That is the reset the convention asks
   * for: the reader issued a command whose answer is this list, and nothing
   * they typed is waiting to be run.
   *
   * WHY TYPING IS NOT WHAT RESETS IT, and why it clears the active row instead
   * (see `clearActive`): these lists are not FILTERED by what is typed — a
   * command produces them — so a row activated by a keystroke would be a row
   * the reader never chose. With the first row active, Enter after typing
   * `nav logs` would open whatever sat at the top of Frequent instead of going
   * to Logs; the reset that makes sense in a real combobox (whose list is
   * filtered by the typed value) is exactly the thing that would break this
   * box's grammar.
   */
  const candidateList = results
    ? 'results:' + results.terms + ':' + results.pages.length + ':' + results.wiki.length
    : outcome?.candidates?.length
      ? 'candidates:' + outcome.candidates.length
      : '';

  useEffect(() => {
    // a fresh candidate list -> its first row, and the popup is BACK (a
    // dismissal is a dismissal of what was on screen, never of what just
    // arrived). A cleared list answers nothing to this branch — the reader's
    // Escape must survive it, or Escape could not put a list away at all.
    if (candidateList) setListDismissed(false);
    // nothing on screen -> editing
    setActiveIndex(candidateList ? 0 : -1);
  }, [candidateList]);

  /**
   * THE ARROWS' ONE MOVER (2026-09-19).
   *
   * `+1`/`-1` step a row; `'first'`/`'last'` are Home/End's jump. Up from the
   * FIRST row returns to editing the input (`-1`) and Down at the last row
   * stays there — the convention, and the reason the caret and the list cannot
   * fight: the input never lost DOM focus, so "back to the input" is a flag,
   * not a focus move (local/studies/keyboard-accelerators.md §3).
   *
   * WITH NO ROW ACTIVE THE TWO ARROWS OPEN THE LIST — Down at the FIRST row, Up
   * at the LAST (2026-09-19). The APG's editable combobox says exactly that, and
   * the box was ignoring half of it: Up with nothing active fell off the front
   * of the list (`-1 + -1` is still "nothing") and did NOTHING, which is the
   * user's second report ("the up button is not needed... let me check" — it was
   * not doing anything, and the instinct that it should was right).
   *
   * "NOTHING ACTIVE" IS ALSO "THE LIST IS CLOSED": this is the only entry the
   * keys have into a popup the reader put away with Escape, so the mover clears
   * that dismissal too (see `listDismissed`). The row count comes from
   * `allRows`, not the drawn set, because the rows the reader is asking for are
   * precisely the ones currently not drawn.
   */
  const moveActive = useCallback(
    (to: 1 | -1 | 'first' | 'last') => {
      setListDismissed(false);
      setActiveIndex((i) => {
        if (allRows.length === 0) return -1;
        if (to === 'first') return 0;
        if (to === 'last') return allRows.length - 1;
        // nothing active: Down starts at the top, Up at the BOTTOM — the same
        // rule as the closed list, which is what this state is
        if (i < 0) return to === -1 ? allRows.length - 1 : 0;
        const next = i + to;
        if (next < 0) return -1;
        return Math.min(next, allRows.length - 1);
      });
    },
    [allRows.length]
  );

  /**
   * ALT+DOWN — OPEN THE LIST WITHOUT MOVING IN IT (2026-09-19).
   *
   * The APG's third way in, and the one key in its table the box had left
   * unwired ("there is no closed list to open on demand" was true only while
   * Frequent was not a popup). It opens the popup and leaves the active row
   * where it is; with NO row active there is no position worth keeping, so the
   * first row takes the virtual focus — a list with nothing active names nothing
   * to assistive tech, and Down already means "the first row" here.
   */
  const openList = useCallback(() => {
    setListDismissed(false);
    setActiveIndex((i) => (i >= 0 ? Math.min(i, allRows.length - 1) : allRows.length > 0 ? 0 : -1));
  }, [allRows.length]);

  /** Typing is EDITING: the list's active row goes away (see `candidateList`). */
  const clearActive = useCallback(() => setActiveIndex(-1), []);

  const wsRef = useRef<WebSocket | null>(null);
  const answerRef = useRef('');
  const wrapRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const abort = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  const close = useCallback(() => {
    abort();
    setOpen(false);
    setBusy(false);
    setActivity('');
    // THE MOUNT'S HALF (2026-09-19) — a mount whose open flag lives outside
    // the hook (the nav sidebar's store field) mirrors the close here, so the
    // panel it draws goes away with the hook's flag rather than one of them
    // closing alone.
    onClose?.();
  }, [abort, onClose]);

  /**
   * Open a destination AND remember it — the single place a navigation
   * happens, so the history cannot drift from what actually opened.
   * (A tab-app target has no path to store, so it is not recorded; the
   * history offers one-click repeats of real destinations.)
   *
   * THE CARET GOES WITH THE READER (2026-09-19). This used to hand the caret BACK
   * to the input on a mount that stays open ("type the next command without the
   * mouse"), and the user's report is what that cost: *"it leaves us stuck in the
   * nav panel … we want to jump to the page we just opened/navigated to."* So a
   * navigation the reader ASKED FOR now announces itself (`requestPageFocus`) and
   * the arrival answers it — the page's declared field, else the `<main>` region.
   *
   * The box still stays OPEN (the mount's `staysOpen`, unchanged): it is a
   * standing region, its thread survives, and one Ctrl+F puts the caret back in
   * its input — which is the way back that costs nothing and reads as intent.
   */
  const go = useCallback((target: NavTarget) => {
    if (target.to) {
      recordNav(target.to, target.label);
      setHistory(navHistory(50));
    }
    requestPageFocus();
    openTarget(target, navigate);
    // THE ONE CASE A MOUNT STILL ASKS FOR (2026-09-19): a TAB landing leaves THIS
    // document alone — the destination is a window of its own — so a mount that
    // stays open keeps its input ready for the next command (the header flyout's
    // `appearance.keepCommandBoxOpen`). An IN-PLACE navigation is the one where
    // the caret LEAVES, and it leaves for the page: that is the reported defect,
    // and no mount gets to overrule it by staying open.
    if (staysOpen && (target.landing ?? 'tab') === 'tab') {
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [navigate, staysOpen]);

  /**
   * ACCEPT A ROW — the ONE place a list row opens, whichever list drew it
   * (2026-09-19). The mouse and the keyboard land here together, which is the
   * point of the shared model: a row cannot behave one way when it is clicked
   * and another when it is accepted with Enter.
   *
   * A ROW LANDS BY ITS DESTINATION (2026-09-19 — the reported defect: *"selecting
   * from the list opens a new tab (show or open) as opposed to navigating the
   * current page"*). The row carries a PATH; what that path IS — a page or a tab
   * app — is `targetForPath`'s answer, from the same tables the typed verbs use.
   * A page lands IN PLACE, the `nav` axis; a tab app can only be a tab. Rows were
   * rebuilt as `kind: 'route'` with no landing, and `openTarget`'s rule is
   * *no landing = tab* — so every row took a tab while every verb that produced
   * it moved the page.
   *
   * `askTab` IS THE READER SAYING SO: Ctrl/⌘+Enter (or ctrl/⌘-click) asks for a
   * tab, the way `open` does for a typed command. The list is the `nav` surface;
   * this is the escape hatch that keeps the other axis reachable from it.
   *
   * THE TWO ROW BEHAVIOURS THAT ALREADY EXISTED ARE KEPT APART, because they
   * are both deliberate:
   *   - a RESULT or SHORTCUT row records the destination (so Frequent can offer
   *     it next time) and clears the list — it is a place the reader chose to
   *     go;
   *   - a TIE'S candidate rows a page the resolver had already validated
   *     WITHOUT recording a shortcut for it, and without clearing the question
   *     the candidates belong to (the tie answer is still on screen).
   */
  const accept = useCallback((option: CommandOption, askTab = false) => {
    setActiveIndex(-1);
    setOutcome({ text: 'Opened ' + option.title, error: false });
    const target = targetForPath(option.to, option.title);
    if (target.kind !== 'tab') target.landing = askTab ? 'tab' : 'replace';
    if (option.group === 'candidates') {
      requestPageFocus();
      openTarget(target, navigate);
      return;
    }
    setResults(null);
    go(target);
  }, [go, navigate]);

  /**
   * ESCAPE'S FIRST JOB: CLOSE THE LIST, WHATEVER LIST IS ON SCREEN (2026-09-19
   * — the settled decision, local/studies/keyboard-accelerators.md §5 item 4:
   * "Esc closes the list first, then the box").
   *
   * The box closes on the SECOND Escape (see the Escape listener below). One
   * listener decides, so the ORDER holds wherever the caret happens to be — a
   * reader who clicked "All" and then pressed Escape gets the same two steps as
   * one sitting in the input.
   *
   * THE FREQUENT LIST IS CLOSED BY THE SAME PRESS (2026-09-19). It has no state
   * to clear — it is what the box shows when nothing is typed — so
   * `listDismissed` is what puts it away, and it is what makes the ORDER true in
   * front of it: before this, Escape on an idle box closed the box itself, and
   * the reader who asked for fewer rows lost the caret, their place, and the list
   * they were looking at. Up/Down reopen it (see `moveActive`); the box's own
   * keys are the way back, which is the whole point of §5 item 4.
   *
   * The outcome line goes with the list: it is the list's own sentence ("6
   * destinations — pick one."), and leaving it behind would be a line pointing
   * at rows that are no longer drawn.
   */
  const closeList = useCallback(() => {
    setResults(null);
    setOutcome(null);
    setActiveIndex(-1);
    setListDismissed(true);
  }, []);

  /**
   * THE POPUP — EVERY LIST THE PANEL DRAWS, and the thing Escape closes first.
   *
   * The DRAWN SET decides, so the answer covers EVERY list the panel draws and
   * cannot drift from them: the candidate results, a tie's candidates AND the
   * Frequent shortcuts. It was the first two alone, and that is the gap the user
   * hit — the Frequent list was on screen while the box reported no list
   * (`aria-expanded="false"`), refused Home/End over it, and let the first
   * Escape close the box instead.
   */
  const listOpen = options.length > 0;

  /**
   * Wipe the shortcut list. The confirmation rides the app's toaster (the
   * house rule for confirmations), and there is no typed confirm: this is a
   * convenience cache that rebuilds itself with use, not user content.
   */
  const clearHistory = useCallback(() => {
    clearNavHistory();
    setHistory([]);
    setShowAllHistory(false);
    setResults(null);
    notifyBus.success('Navigation history cleared', 'The shortcut list is empty again.', 3000);
  }, []);

  /** Report a resolution and act on it — the one place a command lands. */
  const applyResolution = useCallback((res: NavResolution, verb?: CommandVerb) => {
    if (res.ok) {
      // THE LANDING TRAVELS ON THE TARGET (2026-09-18). `openTarget` reads it:
      // `nav`/`goto` move the current page in place, `open`/`show` take a tab.
      // A caller that passes no verb — Exa's own `OPEN:` marker, the `exa` page
      // request — keeps the old tab behaviour.
      //
      // A DUAL NAME (a term that is both a page and a tab) needs the axis
      // BEFORE the resolution, because the axis is what decides between them —
      // see `resolveTarget(raw, landing)`. runCommand therefore passes it in,
      // and this line keeps every other caller on the same footing.
      if (verb) res.target.landing = landingFor(verb);
      setOutcome({ text: 'Opened ' + res.target.label + (res.target.note ? ' (' + res.target.note + ')' : ''), error: false });
      go(res.target);
    } else {
      setOutcome({ text: res.error, error: true, candidates: res.candidates });
    }
    setActivity('');
    setBusy(false);
  }, [go]);

  /**
   * A COMMAND — resolved here, never sent to Exa.
   *
   * `nav` cannot leave the browser (the routes already live in it) and the
   * wiki verbs ride the wiki's own search, so a command is deterministic,
   * instant, and impossible to hallucinate. This is the whole reason the
   * verbs exist; what happens to a free-form question is the MOUNT's decision
   * (`exaFallthrough`) — see the module docstring.
   */
  const runCommand = useCallback(async (raw: string, cmd: ParsedCommand) => {
    setBusy(true);
    setError(null);
    setOutcome(null);
    setActivity('');
    setAnswer('');
    answerRef.current = '';
    setAsked(raw);
    setResults(null);

    // THE APP'S OWN DESTINATIONS. `nav`/`goto` land the CURRENT page on the
    // target; `open`/`show` take a new tab — the landing travels on the target
    // (see landingFor / openTarget). It is handed to the RESOLVER as well,
    // because a name that is BOTH a page and an app tab (`sessions`, `messages`)
    // can only be told apart by the axis (see resolveTarget / dualPage).
    if (cmd.verb === 'nav' || cmd.verb === 'open' || cmd.verb === 'config') {
      // THE LISTING, checked BEFORE resolveTarget. "list" must not reach the
      // fuzzy stage: it is a word inside the key "session list", so edit
      // distance matches it at 0 and opens SESSIONS with full confidence.
      // Asking for the map is answered by the map.
      if (LISTING_WORDS.has(cmd.rest.trim().toLowerCase())) {
        const all = allDestinations();
        setResults({ terms: cmd.rest || 'everything', pages: all, wiki: [] });
        setOutcome({ text: all.length + ' destinations — pick one.', error: false });
        setBusy(false);
        return;
      }
      applyResolution(resolveTarget(cmd.rest, landingFor(cmd.verb)), cmd.verb);
      return;
    }

    // `list` NEVER opens anything — the list IS the answer (see searchAll).
    // BARE, it shows the whole map: "list" with nothing after it is a request
    // for everything. (`search`/`find` used to be this verb's alias and are now
    // the WIKI's own search instead — they never reach this branch; they land in
    // resolveWikiCommand below, which returns their hits as candidates.)
    if (cmd.verb === 'list') {
      if (!cmd.rest.trim()) {
        const all = allDestinations();
        setResults({ terms: 'everything', pages: all, wiki: [] });
        setOutcome({ text: all.length + ' destinations — pick one.', error: false });
        setBusy(false);
        return;
      }
      const found = await searchAll(cmd.rest);
      if (found.pages.length === 0 && found.wiki.length === 0) {
        // AN EMPTY LIST IS STILL AN ANSWER, so the box goes back to IDLE: this
        // branch used to set the outcome and leave `busy` true, which left the
        // spinner turning and Send dead — the next command could not be sent at
        // all (the empty-answer test found it, 2026-09-19).
        setOutcome({ text: 'Nothing matches "' + cmd.rest + '".', error: true });
        setBusy(false);
      } else {
        setResults(found);
        setBusy(false);
      }
      return;
    }

    // `back` — THE TAB'S OWN HISTORY (2026-09-18, the user: "can we base the
    // back command from the tab nav history?"). The box's own navHistory is a
    // FREQUENCY list — most-used first — so it cannot answer "where was I just
    // now"; the tab's history can. react-router keeps an index in
    // `history.state`, and at 0 this IS the tab's first entry: `navigate(-1)`
    // would walk OUT of the app, so refuse honestly instead of ejecting you.
    if (cmd.verb === 'back') {
      const idx = (window.history.state as { idx?: number } | null)?.idx ?? 0;
      if (idx > 0) {
        setOutcome({ text: 'Back.', error: false });
        navigate(-1);
      } else {
        setOutcome({ text: 'Nothing to go back to — this tab started here.', error: true });
      }
      setBusy(false);
      return;
    }

    // `help` — the command list, GENERATED from COMMAND_VERBS (see verbHelp),
    // so it cannot drift from the parser.
    if (cmd.verb === 'help') {
      setOutcome({ text: verbHelp(cmd.rest), error: false });
      setBusy(false);
      return;
    }

    applyResolution(await resolveWikiCommand(cmd), cmd.verb);
  }, [applyResolution, navigate]);

  /**
   * The LLM path — the ONLY place a prompt reaches Exa.
   *
   * Extracted from `ask` so the `exa` verb can FORCE it. A question that opens
   * with a verb word ("search is broken on the tools page") is otherwise read
   * as that verb and never arrives; `exa <question>` strips the prefix and
   * lands here, which is what makes the verb an escape hatch rather than a
   * decoration.
   */
  const sendPrompt = useCallback((text: string) => {
    setBusy(true);
    setError(null);
    setOutcome(null);
    setActivity('');
    setAnswer('');
    answerRef.current = '';
    setAsked(text);
    setQuestion('');

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(proto + '://' + window.location.host + '/api/v1/external-agent/ws');
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'prompt', text: text + appNavDirective() }));
    };

    ws.onmessage = (ev: MessageEvent) => {
      let m: WsMsg;
      try { m = JSON.parse(String(ev.data)); } catch { return; }

      if (m.type === 'message') {
        // coalesced — one accumulating line, never one node per chunk
        answerRef.current += m.text || '';
        setAnswer(answerRef.current);
      } else if (m.type === 'thought') {
        // the model's thinking is not the answer; the spinner covers it
      } else if (m.type === 'tool_call') {
        // PHASE B HOOKS IN HERE: the full frame arrives, including
        // m.update.rawInput — that is where "open the right page" will
        // read its target. For now the title is honest progress feedback.
        const title = m.update?.title || m.update?.kind;
        if (title) setActivity(String(title));
      } else if (m.type === 'status' && m.status === 'inactive') {
        // THE GATE (2026-11-18): Exa ships switched off, so an ask gets the
        // state — and a plain sentence — instead of a spinner that never
        // resolves into anything.
        setError(m.message || 'Exa is not active — activate it on the Exa page to ask it anything.');
        setBusy(false);
        setActivity('');
        abort();
      } else if (m.type === 'status' && (m.status === 'error' || m.status === 'cancelled' || m.status === 'time_limit')) {
        // LOUD — the skill's rule: a timeout is a first-class error
        setError(m.message || ('Exa stopped: ' + m.status));
        setBusy(false);
        setActivity('');
        abort();
      } else if (m.type === 'done') {
        // the backend's full reply wins (it has any chunk we missed)
        const { text, request } = extractOpenRequest(m.reply || answerRef.current || '(no answer)');
        setAnswer(text || '(no answer)');

        // FORM 2: Exa asked to go somewhere. The marker is machinery, so it
        // never reaches the reader; the DESTINATION is validated here, and
        // an unknown one is reported instead of opened.
        if (request) {
          const res = resolveTarget(request);
          if (res.ok) {
            applyResolution(res);
          } else {
            const hints = res.candidates.map((c) => c.title).join(', ');
            setOutcome({
              text: res.error + (hints ? ' Did you mean: ' + hints + '?' : ''),
              error: true,
              candidates: res.candidates,
            });
          }
        }
        setBusy(false);
        setActivity('');
        abort();
      }
    };

    ws.onerror = () => {
      setError('Could not reach Exa — the bridge refused the connection.');
      setBusy(false);
      setActivity('');
    };
    ws.onclose = () => {
      setBusy(false);
      wsRef.current = null;
    };
  }, [abort, applyResolution]);

  const ask = useCallback(() => {
    const q = question.trim();
    if (!q || busy) return;

    // A COMMAND PUTS THE POPUP BACK (2026-09-19). The reader's Escape said "not
    // right now" about the rows that were on screen, not about the box: this is
    // the funnel every submitted command comes through, so the dismissal is
    // cleared here and a list a command earned can never arrive hidden behind
    // one — including the case the `candidateList` effect cannot see, running
    // the SAME listing twice (the list's identity does not change, so nothing
    // else would fire).
    setListDismissed(false);

    const cmd = parseCommand(q);

    // `exa` — the escape hatch to the model, and the Exa page when bare.
    // It searches NOTHING; it exists so a verb-shaped question still gets
    // through. Bare, it opens the page `nav exa` already resolves to.
    //
    // WHICH WAY A QUESTION IN A SIDEBAR GOES (2026-09-18): a mount WITHOUT the
    // Exa path — the nav sidebar — does not send it at all. It opens the Exa
    // CHAT TAB instead, which owns the call, its own Stop and its own session;
    // that is why a navigator mount needs no stop button anywhere.
    if (cmd && cmd.verb === 'exa') {
      if (cmd.rest && exaFallthrough) {
        sendPrompt(cmd.rest);
        return;
      }
      const res = resolveTarget('exa');
      setError(null);
      setResults(null);
      setActivity('');
      setAnswer('');
      answerRef.current = '';
      setBusy(false);
      if (res.ok) {
        // THE QUESTION CANNOT RIDE ALONG YET — measured 2026-09-18, and said
        // out loud rather than swallowed. The tab is `navigateTo('exa')`: a
        // `window.open('/exa', '_blank')`, i.e. a FRESH PAGE LOAD this opener
        // cannot write to, and nothing on the Exa page reads a question
        // (ExaChat takes its text from ChatInterface's own state; the one
        // cross-tab slot it reads is swapHandoff — the PROVIDER-SWAP queue, not
        // a question queue). The smallest honest wiring is in the session's
        // report; until it lands, the question STAYS IN THE INPUT so the words
        // are not lost (the grammar spec's rule: losing the text is the one
        // outcome worse than a refusal).
        setOutcome({
          text: cmd.rest
            ? 'Opened Exa — the question cannot ride along yet.'
            : 'Opened Exa',
          error: false,
        });
        go(res.target);
      } else {
        setOutcome({ text: res.error, error: true, candidates: res.candidates });
      }
      // a bare verb leaves nothing worth keeping; a question stays, to be copied
      if (!cmd.rest) setQuestion('');
      return;
    }

    // THE COMMAND PATH, checked FIRST: a recognised verb never reaches Exa.
    if (cmd) {
      setQuestion('');
      void runCommand(q, cmd);
      return;
    }

    // NOT A COMMAND, SO THIS IS THE MOUNT'S DECISION (`exaFallthrough`).
    //
    // THE FLYOUT falls through to Exa exactly as it always has: it has the room
    // for an answer and for a stop control, and it is where a DISPATCH is typed.
    if (exaFallthrough) {
      sendPrompt(q);
      return;
    }

    // THE NAVIGATOR answers LOCALLY and instantly, from data the app already
    // has: a near-miss on a verb offers the verb, anything else says plainly
    // that it is not a command and points at `help`. The one-line copy rule, and
    // no model turn — see noCommandAnswer.
    const miss = noCommandAnswer(q);
    setQuestion('');
    setResults(null);
    setError(null);
    setActivity('');
    setAnswer('');
    answerRef.current = '';
    setBusy(false);
    setAsked(q);
    setOutcome({ text: miss.text, error: miss.error });
  }, [question, busy, exaFallthrough, sendPrompt, runCommand, go]);

  // Escape closes AND aborts (the ConsultComposer rule); click-outside closes.
  // Both land on `close`, which is also what the panel's ✕ calls — so every way
  // out reports to the mount's `onClose`, and the sidebar's Escape and its ✕
  // put the box away the same way (2026-09-19). The ref is the mount's: a
  // wrapper that does not attach `wrapRef` has no click-away (the sidebar was
  // that wrapper until it attached the ref at its own boundary).
  //
  // THE LIST FIRST, THE BOX SECOND (2026-09-19 — local/studies/
  // keyboard-accelerators.md §5 item 4). Escape is the key that dismisses what
  // is in front of the reader, and what is in front of them is the LIST: a box
  // that vanished whole would cost them the caret and re-typing the command for
  // the trouble of asking to see fewer rows. So the list closes and the box —
  // and its caret — stay put; a second Escape puts the box away. The rule lives
  // HERE, in the one listener, so it holds whoever holds the caret.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        if (listOpen) closeList();
        else close();
      }
    };
    const onDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) close();
    };
    window.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDown);
    return () => {
      window.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onDown);
    };
  }, [open, close, listOpen, closeList]);

  // OPENING DOES TWO THINGS, HOWEVER IT WAS OPENED (2026-09-15): focus the
  // input (the flyout's whole point is a quick ask) and LOAD THE SHORTCUTS.
  // The history used to be loaded by the hotkey handler alone, so a CLICK
  // opened an empty list — exactly the mouse path the user asked to keep
  // working. One effect covers both ways in.
  //
  // AN ARRIVAL IS NOT AN OPENING (2026-09-19). A mount can be HANDED an open
  // box (`initiallyOpen`) — the nav sidebar draws from the persisted store
  // flag, so a fresh page load has it open on the first paint — and this
  // effect's first run is then that ARRIVAL, not a transition the reader
  // caused. The shortcut list is loaded either way (an open box must never
  // offer an empty Frequent list); the CARET is not this effect's to take in
  // that case. The yield to a page that declares its own primary input
  // (`data-autofocus`) belongs to the mount that arrives, and it is the one
  // rule a focus taken here would override — see NavSearchSection's caret on
  // arrival and services/focusContract.
  useEffect(() => {
    if (!open) return;
    setHistory(navHistory(50));
    // A FRESH BOX SHOWS ITS LISTS (2026-09-19): an Escape long past must not
    // leave the reopened box with its Frequent list still put away.
    setListDismissed(false);
    if (arrivedOpen.current) {
      arrivedOpen.current = false;
      return;
    }
    inputRef.current?.focus();
  }, [open]);

  // A HOTKEY INSIDE A MOUNT IS OPT-IN AND UNARMED IN THIS APP (2026-09-18).
  // The user's key is Cmd/Ctrl+K from anywhere, and it is ONE listener — the
  // shell's (NavSearchHotkey). This effect is kept as the hook's own capability
  // for a surface with no shell around it; no mount in the app sets
  // `hotkey: true`, because a listener in a mount dies with the mount (the
  // sidebar's box is not even rendered while the rail is collapsed) and two
  // armed mounts opened two boxes on one keystroke.
  useEffect(() => {
    if (!hotkey) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        // the open effect handles the focus AND the shortcut list
        setOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [hotkey]);

  // never leave a socket behind
  useEffect(() => () => wsRef.current?.close(), []);

  const hasThread = Boolean(asked || answer || error);

  return {
    // the trigger
    open,
    setOpen,
    close,
    wrapRef,
    // the panel
    question,
    setQuestion,
    ask,
    asked,
    answer,
    activity,
    error,
    busy,
    history,
    showAllHistory,
    setShowAllHistory,
    clearHistory,
    results,
    setResults,
    outcome,
    setOutcome,
    // THE LISTBOX (2026-09-19) — one model for every list the panel draws, the
    // row the virtual focus is on, and the four things the input's keys do.
    options,
    activeOption,
    listOpen,
    moveActive,
    openList,
    clearActive,
    accept,
    closeList,
    go,
    navigate,
    openExaPage,
    inputRef,
    hasThread,
  };
}

export type CommandBoxApi = ReturnType<typeof useCommandBox>;
