/**
 * CommandBoxPanel — the command box's panel UI.
 *
 * PRESENTATIONAL: the box's state, its command verbs and its bridge all live
 * in useCommandBox, and the trigger lives in the widget that wires the two
 * together. Every value and callback below arrives as a prop.
 *
 * The panel used to be welded to its popover shell (`absolute right-0
 * top-full`, anchored under the trigger) which is why it could not be
 * attached anywhere but a trigger. The `variant` prop is that weld cut
 * (2026-09-18): the CONTENT is identical, only the shell changes.
 *
 * THE VARIANT CARRIES THE TWO MOUNTS' WHOLE VISIBLE DIFFERENCE (2026-09-18,
 * the rename to "Search"): its COPY (`COPY` below) and which controls are
 * drawn.
 *
 *   - `sidebar` is the NAV SIDEBAR's box, and it is a NAVIGATOR: named
 *     "Search", its button RUNS the command rather than sending one ("Go"),
 *     and it draws NO "Full page" control and NO streamed-answer area —
 *     `exa <question>` opens the Exa chat tab (which owns the call, its own
 *     Stop and its own session) and nothing streams in a 16rem column.
 *   - `flyout` is the header trigger's box and KEEPS the Exa path, so it
 *     keeps the Exa name, the "Send" button, "Full page" and the answer.
 *
 * The split is the VARIANT, not a fork of the panel: one panel, one hook,
 * two mounts, and the differences sit in one place each.
 *
 * WHAT THIS FILE DRAWS OF THE COMBOBOX, AND WHAT IT DOES NOT (2026-09-19).
 * The input is a `role="combobox"` and every list is a `role="listbox"` whose
 * rows are `role="option"` — but WHICH row is active, and what each key does to
 * it, belongs to the hook (useCommandBox): the panel draws the active row and
 * reports the keys, so the mouse and the keyboard cannot disagree about what a
 * row is. See local/studies/keyboard-accelerators.md §3.
 *
 * IT ALSO KEEPS THE ACTIVE ROW ON SCREEN (2026-09-19, the reported defect) —
 * scrolling IS the panel's job, because the panel is what owns the boxes the
 * row has to be visible in. See the effect below the row helpers.
 */

import { useEffect, useRef } from 'react';
import { MarkdownText } from '@/components/ui/MarkdownText';
import {
  COMMAND_LIST_IDS,
  type CommandBoxApi,
  type CommandOption,
  type CommandOptionGroup,
} from './useCommandBox';

export type CommandBoxPanelProps = CommandBoxApi & {
  /**
   * WHERE the panel is drawn AND what it draws (2026-09-18).
   *
   * - `flyout` (default): the header trigger's popover — unchanged. It keeps
   *   the Exa name, the "Send" button, the "Full page" control and the
   *   streamed answer.
   * - `sidebar`: FILLS its container and caps its own height. The nav
   *   sidebar is one scroll column shared with the nav list, so an
   *   unbounded panel would push the list off-screen; the cap plus the
   *   panel's own scroll keeps the list reachable. It is the NAVIGATOR's
   *   box: named "Search", its button is "Go", and it draws neither "Full
   *   page" nor the answer area — nothing streams locally.
   */
  variant?: 'flyout' | 'sidebar';
};

/**
 * THE PANEL'S COPY, PER VARIANT (2026-09-18).
 *
 * The two mounts are the same panel and the same hook, so the words that
 * differ between them live here rather than in a branch per element. The
 * sidebar's box is a NAVIGATOR — it searches and runs commands — so it is
 * named "Search" and its button is "Go" (nothing is sent from it). The
 * header flyout KEEPS the Exa name and "Send", because it genuinely sends.
 */
const COPY = {
  flyout: {
    title: 'Ask Exa',
    inputLabel: 'Ask Exa a question',
    submit: 'Send',
    submitLabel: 'Send to Exa',
    closeLabel: 'Close Ask Exa',
  },
  sidebar: {
    title: 'Search',
    inputLabel: 'Search commands',
    submit: 'Go',
    submitLabel: 'Go',
    closeLabel: 'Close Search',
  },
} as const;

/**
 * THE NAME OF EACH LIST (2026-09-19) — the label the reader sees above it, and
 * the one a screen reader hears on the listbox itself. Two of the four draw a
 * visible heading ("Pages", "Frequent"); "Wiki" leads its own group below
 * "Pages"; and a tie's rows sit under the answer that explains them, so they
 * carry no heading of their own and are named for assistive tech only.
 */
const GROUP_LABELS: Record<CommandOptionGroup, string> = {
  pages: 'Pages',
  wiki: 'Wiki',
  candidates: 'Matches',
  frequent: 'Frequent',
};

export function CommandBoxPanel({
  asked,
  answer,
  activity,
  busy,
  error,
  results,
  outcome,
  history,
  showAllHistory,
  setShowAllHistory,
  clearHistory,
  question,
  setQuestion,
  ask,
  close,
  openExaPage,
  inputRef,
  hasThread,
  options,
  activeOption,
  listOpen,
  moveActive,
  openList,
  clearActive,
  accept,
  closeList,
  variant = 'flyout',
}: CommandBoxPanelProps) {
  /** THE COPY THIS MOUNT USES — see COPY above. */
  const copy = COPY[variant];

  /** The rows a group drew — `options` IS the draw order (see useCommandBox). */
  const rowsOf = (group: CommandOptionGroup) => options.filter((o) => o.group === group);

  /** THIS panel's scroll container — what the scroll effect below looks in. */
  const shellRef = useRef<HTMLDivElement>(null);

  /**
   * ONE ROW OF ANY LIST (2026-09-19 — the combobox work:
   * local/studies/keyboard-accelerators.md). EVERY list in the box draws its
   * rows through here — the candidate results, a tie's candidates and the
   * Frequent shortcuts — so the ARIA contract and the active treatment cannot
   * be right in one list and missing in another (§7).
   *
   * THE ROW IS NOT A TAB STOP (`tabIndex={-1}`). Reaching a row is ArrowDown;
   * Tab LEAVES the box. Tabbing through the rows was the browser's focus model
   * repurposed as list navigation — one stop per result, and the list announced
   * as a run of links instead of one control with an active option (§4).
   *
   * THE ACTIVE ROW IS THE HOUSE'S SELECTED ROW — the `bg-primary/10` +
   * `text-primary` tint the tables and the topic picker mark a chosen row with —
   * and it is deliberately NOT a dimmer one: gray-dim means DISABLED in this app
   * (design/control-system.md, the text roles), so the active row has to read as
   * MORE present, not less. The hover tint is dropped while a row is active so a
   * passing mouse cannot wash the highlight out.
   */
  const optionRow = (o: CommandOption) => {
    const active = o.id === activeOption?.id;
    return (
      <li key={o.id} role="presentation">
        <button
          type="button"
          id={o.id}
          role="option"
          aria-selected={active}
          tabIndex={-1}
          className={
            'w-full rounded px-1.5 py-1 text-left ' +
            (active ? 'bg-primary/10 text-primary' : 'hover:bg-base-200')
          }
          onClick={(e) => accept(o, e.ctrlKey || e.metaKey)}
        >
          <span className="font-medium">{o.title}</span>
          <span className="text-readout"> — {o.sub || o.to}</span>
        </button>
      </li>
    );
  };

  /**
   * ONE LIST — a `role="listbox"` with its label, drawn from the same options
   * the keys move over. Its id is what the input's `aria-controls` names, and
   * the element is what `aria-activedescendant` points INTO: the row stays
   * where it is, and the input keeps the DOM focus.
   */
  const optionList = (
    group: CommandOptionGroup,
    label: string | null,
    opts: { labelClass?: string; listClass?: string } = {}
  ) => {
    const its = rowsOf(group);
    if (its.length === 0) return null;
    return (
      <>
        {label && <p className={opts.labelClass ?? 'text-readout mb-1'}>{label}</p>}
        <ul
          id={COMMAND_LIST_IDS[group]}
          role="listbox"
          aria-label={GROUP_LABELS[group]}
          className={'space-y-0.5' + (opts.listClass ?? '')}
        >
          {its.map(optionRow)}
        </ul>
      </>
    );
  };

  /**
   * THE LISTBOXES A RENDER DREW (`aria-controls`), in draw order. The input
   * names them all: the rows come from more than one list, and a control that
   * claimed only the first would be lying about the rest.
   */
  const drawnListIds =
    Array.from(new Set(options.map((o) => COMMAND_LIST_IDS[o.group]))).join(' ') || undefined;

  /**
   * THE ACTIVE OPTION IS SCROLLED INTO VIEW WHENEVER IT MOVES (2026-09-19 —
   * the reported defect: "the arrows DO scroll through the list one item at
   * time starting at the bottom which is off the screen").
   *
   * This is PART OF THE PATTERN, not a nicety bolted onto it
   * (local/studies/keyboard-accelerators.md §3). The keys move a VIRTUAL focus:
   * nothing is focused, so nothing scrolls — and the browser's own scrolling of
   * the panel was precisely the arrow keys' OLD behaviour, which the combobox
   * consumed without replacing. Up opens the list at its LAST row (§3's table),
   * which with no scroll lands below the visible area: the selection moved, and
   * what the reader saw was nothing at all.
   *
   * `block: 'nearest'` IS THE WHOLE REASON NOTHING ELSE ON THE PAGE MOVES. It
   * scrolls the minimum that brings the row fully in — only the containers that
   * are actually short of it — where `'start'`/`'center'` would yank the panel
   * (and then the document) on every keystroke. `'nearest'` does not move a
   * container the row is already inside, which is what makes it safe to run on
   * every change rather than only on the ones that need it.
   *
   * ONE RULE, EVERY LIST. `scrollIntoView` walks the scrollable ANCESTORS, so
   * this covers all four lists the panel draws — pages, wiki, a tie's
   * candidates, Frequent — and whichever box is short of the row: the list's
   * own capped box (`max-h-32` / `max-h-40`) or the panel's shell (`max-h-64`
   * in the sidebar).
   *
   * SCOPED TO THIS PANEL'S OWN SHELL, never the document: the option ids are
   * INDEX-based (`cmdbx-option-3`) and both mounts can be open at once (the
   * header's flyout and the nav sidebar), so a document-wide lookup could find
   * the other box's row first and scroll a panel the reader is not using.
   *
   * A KEYBOARD-DRIVEN CHANGE IS THE REPORTED CASE, but the effect keys on the
   * ROW, not on the key: a row also becomes active when a command's list
   * arrives, and an active row that is out of sight is out of sight either way.
   */
  useEffect(() => {
    if (!activeOption) return;
    const row = shellRef.current?.querySelector<HTMLElement>('#' + activeOption.id);
    // The optional call is jsdom's half: it has no layout and no
    // `scrollIntoView` at all, so the DOM-only step has to be a no-op there
    // rather than a crash (the tests stub it when they want to assert it).
    row?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
  }, [activeOption]);

  /**
   * THE SHELL — the one part that differs per attachment. `flyout` keeps the
   * original popover classes verbatim; `sidebar` replaces the anchoring with
   * a fill, and trades the 440px width for the column it is given.
   *
   * THE SIDEBAR SHELL RESERVES THE PINNED INPUT ROW'S HEIGHT (`scroll-pb-14`,
   * 2026-09-19). Scrolling a row into view was not enough on its own: the input
   * row is `sticky bottom-0`, so the bottom ~49px of this scrollport is covered
   * by it, and `scrollIntoView` — which knows only about the box, not about what
   * is painted over it — stopped with the last row exactly underneath the input.
   * Measured in the running app before this: `End` and Up-from-closed both put
   * the last Frequent row at 336px..360px in a shell whose input row starts at
   * 312px, i.e. scrolled to and still invisible. `scroll-padding-bottom` is the
   * CSS half of the same contract: it tells scroll-into-view where this
   * scrollport's usable bottom edge actually is, so `block: 'nearest'` stops
   * above the pinned row and nothing else about the layout moves.
   */
  const shell =
    variant === 'sidebar'
      ? [
          'relative w-full max-h-64 overflow-y-auto scroll-pb-14',
          'bg-[var(--flyout-panel-bg)] border border-[var(--flyout-panel-border)]',
          'text-[var(--flyout-panel-text)] rounded-lg p-2',
        ]
      : [
          'absolute right-0 top-full mt-2 z-50',
          'w-[440px] max-w-[90vw] max-h-[70vh] overflow-y-auto',
          'bg-[var(--flyout-panel-bg)] border border-[var(--flyout-panel-border)]',
          'text-[var(--flyout-panel-text)] rounded-lg shadow-lg p-3',
          'animate-in fade-in slide-in-from-top-2 duration-200',
        ];

  return (
    <div
      ref={shellRef}
      className={shell.join(' ')}
      // A popover is a dialog; the sidebar's section is a standing region of
      // the page, and the section that wraps it carries the label.
      role={variant === 'flyout' ? 'dialog' : undefined}
      aria-label={copy.title}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold">{copy.title}</span>
        <div className="flex items-center gap-1">
          {/* FULL PAGE IS THE FLYOUT'S (2026-09-18): it is the coexisting way
              to the Exa page, and it belongs to the mount that is an Exa
              surface. A navigator does not need it — it IS a way around the
              app — and the sidebar's control row is the ✕ alone. */}
          {variant === 'flyout' && (
            <div className="tooltip tooltip-left" data-tip="Open the Exa page">
              <button
                type="button"
                className="btn btn-ghost btn-xs text-xs"
                onClick={() => { close(); openExaPage(); }}
                aria-label="Open the Exa page"
              >
                Full page
              </button>
            </div>
          )}
          <div className="tooltip tooltip-left" data-tip="Close">
            <button type="button" className="btn btn-ghost btn-xs" onClick={close} aria-label={copy.closeLabel}>
              ✕
            </button>
          </div>
        </div>
      </div>

      {/* THE STREAMED ANSWER IS THE FLYOUT'S (2026-09-18): the question, the
          answer and the live activity line are what the Exa path produces.
          The sidebar's mount passes `exaFallthrough: false`, so its panel
          would never have anything to put here — nothing streams from a
          navigator; the one-line `outcome` below IS its answer. */}
      {variant === 'flyout' && hasThread && (
        <div className="mb-2 text-xs space-y-1.5">
          {asked && (
            <p className="leading-relaxed">
              <span className="text-readout">You: </span>
              <span className="font-medium">{asked}</span>
            </p>
          )}
          {(answer || busy) && (
            <div className="max-h-56 overflow-y-auto rounded-md bg-base-200/60 p-2">
              {/* Markdown, not a <p>: Exa writes links/lists/tables, and as plain
                  text a link is just characters. The panel keeps its own
                  scroll — a long answer stays inside the 440px box. */}
              <MarkdownText className="leading-relaxed break-words">{answer || '…'}</MarkdownText>
            </div>
          )}
          {busy && activity && (
            <p className="text-readout flex items-center gap-1.5">
              <span className="loading loading-spinner loading-xs" />
              {activity}
            </p>
          )}
        </div>
      )}

      {/* THE SEARCH RESULTS (the `list` verb): grouped, because a term
          that matches the app AND the wiki must not hide one. Each group
          is height-capped and scrollable ON PURPOSE — an unbounded list
          grows the panel into the chat column's overflow-hidden edge.

          THE GROUPS ARE LISTBOXES (2026-09-19): the rows come from the hook's
          one option model, and the keys move over them there — the panel draws
          what the input's `aria-activedescendant` names
          (local/studies/keyboard-accelerators.md §3). */}
      {results && (
        <div className="mb-2 text-xs">
          {optionList('pages', 'Pages', { listClass: ' max-h-32 overflow-y-auto' })}
          {optionList('wiki', 'Wiki', {
            labelClass: 'text-readout mb-1 mt-2',
            listClass: ' max-h-32 overflow-y-auto',
          })}
        </div>
      )}

      {outcome && (
        <div className="mb-2 text-xs leading-relaxed">
          <p
            className={outcome.error ? 'text-error' : 'text-success'}
            role={outcome.error ? 'alert' : 'status'}
          >
            {outcome.text}
          </p>
          {/* a TIE shows its candidates — picking for you is how you land
              on the wrong note and stop trusting the command. They are rows of
              the same listbox, so a tie is picked from the keyboard the same
              way a `list` answer is (2026-09-19). */}
          {outcome.candidates && outcome.candidates.length > 0 && (
            optionList('candidates', null, { listClass: ' mt-1.5' })
          )}
        </div>
      )}

      {error && (
        <p className="mb-2 text-xs text-error leading-relaxed" role="alert">
          {error}
        </p>
      )}

      {/* THE SHORTCUTS (2026-09-15, the user's ask: "a history of most
          frequent or last N navigations"). The mouse path types nothing:
          the places you actually go sit one click away, most-used first.
          Shown whenever the box is idle — including after a command, so
          the shortcut survives its own use.

          IT IS THE SAME LISTBOX AS THE RESULTS (2026-09-19): its rows are
          options of the one model, so Down reaches them and Enter opens the
          active one, exactly as it does in a `list` answer.

          AND THE WHOLE BLOCK GOES WITH ITS ROWS (2026-09-19). The gate below
          asks the MODEL, not `history.length`: once Escape puts the popup away
          (`listDismissed` in useCommandBox) the rows are gone, and a heading
          with a Clear button over an empty list is a control promising rows
          that are not there. "Frequent is on screen" and "Frequent has rows"
          are now the same question, which is what makes `aria-expanded`
          honest. */}
      {rowsOf('frequent').length > 0 && (
        <div className="mb-2 text-xs">
          <div className="flex items-center justify-between mb-1">
            <p className="text-readout">Frequent</p>
            <div className="flex items-center gap-0.5">
              {history.length > 6 && (
                <div className="tooltip tooltip-left" data-tip={showAllHistory ? 'Show fewer' : 'Show all'}>
                  <button
                    type="button"
                    className="btn btn-ghost btn-xs px-1.5 text-[10px]"
                    onClick={() => setShowAllHistory((v) => !v)}
                    aria-label={showAllHistory ? 'Show fewer shortcuts' : 'Show all shortcuts'}
                  >
                    {showAllHistory ? 'Fewer' : 'All ' + history.length}
                  </button>
                </div>
              )}
              <div className="tooltip tooltip-left" data-tip="Clear history">
                <button
                  type="button"
                  className="btn btn-ghost btn-xs px-1.5 text-[10px]"
                  onClick={clearHistory}
                  aria-label="Clear navigation history"
                >
                  Clear
                </button>
              </div>
            </div>
          </div>
          {optionList('frequent', null, {
            listClass: showAllHistory ? ' max-h-40 overflow-y-auto' : '',
          })}
        </div>
      )}

      {/* THE INPUT ROW, and in the sidebar it PINS to the bottom of the
          panel's own scroll (2026-09-18). The panel puts its input LAST, so
          in a capped column the input is the first thing to go below the
          fold the moment a result list or a long answer arrives — measured
          at 256px with a `help` answer: the input sat 75px past the panel's
          bottom edge and had to be scrolled to. Sticky keeps the one control
          the reader came for in view while the thread scrolls above it. The
          flyout is unaffected: it is wide enough that this does not arise,
          and it keeps its exact classes.

          AND THE SHELL RESERVES ITS HEIGHT (`scroll-pb-14` on the sidebar
          shell): a pinned row is painted OVER the content beneath it, so a row
          scrolled to the bottom of this box would come to rest behind the input
          — see the scroll effect above, which is what made that visible. */}
      <div
        className={
          'flex items-center gap-2' +
          (variant === 'sidebar'
            ? ' sticky bottom-0 bg-[var(--flyout-panel-bg)] pt-2'
            : '')
        }
      >
        <input
          ref={inputRef}
          type="text"
          className="input input-bordered input-sm w-full text-sm"
          value={question}
          placeholder="nav logs · nav list · exa <question>"
          onChange={(e) => {
            setQuestion(e.target.value);
            // TYPING IS EDITING: the active row goes away, so Enter runs the
            // command being typed instead of opening a row the reader never
            // chose (see `candidateList` in useCommandBox for the whole rule).
            clearActive();
          }}
          onKeyDown={(e) => {
            // THE COMBOBOX'S KEYS (2026-09-19 — local/studies/
            // keyboard-accelerators.md §3). DOM focus NEVER leaves this input:
            // the list carries a virtual focus, named for assistive tech by
            // `aria-activedescendant` below, and `preventDefault` is what keeps
            // the caret and the browser from acting on a key the list has taken.
            //
            // ALT+DOWN COMES FIRST, because it is a Down with a modifier: it
            // OPENS the list without moving in it (the APG's third way in, and
            // the one key of the table the box had left unwired). Handled after
            // the plain Down below it would be swallowed as a step.
            if (e.altKey && e.key === 'ArrowDown') {
              e.preventDefault();
              openList();
              return;
            }
            // DOWN WITH NOTHING ACTIVE OPENS THE LIST AT ITS FIRST ROW — every
            // list in the box, Frequent included. That is also the way back to
            // a popup Escape put away.
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              moveActive(1);
              return;
            }
            // UP WITH NOTHING ACTIVE OPENS THE LIST AT ITS LAST ROW (2026-09-19
            // — the second half of the same convention, and the user's second
            // report: "the up button is not needed... let me check". It was not
            // doing anything at all — from no row active, `-1 + -1` is still no
            // row — and their instinct that it should do something was right.)
            //
            // Up from the FIRST row still returns to editing: no focus move,
            // the input never lost it.
            if (e.key === 'ArrowUp') {
              e.preventDefault();
              moveActive(-1);
              return;
            }
            // HOME / END JUMP THE LIST, but only while a list is up: with none,
            // they are the caret keys a text field's reader expects, and taking
            // them where there is nothing to move over would be a pure loss.
            // `listOpen` is EVERY list now, so End reaches the bottom of the
            // Frequent list too — which was the only way in it did not have.
            if ((e.key === 'Home' || e.key === 'End') && listOpen) {
              e.preventDefault();
              moveActive(e.key === 'Home' ? 'first' : 'last');
              return;
            }
            // TAB LEAVES THE BOX — ONE stop, not one per result. The list closes
            // (the typed value is what was accepted; Tab is a way OUT, not a way
            // to open a row), and the browser moves the focus on: no
            // `preventDefault` here, and nothing on the page can trap it.
            if (e.key === 'Tab') {
              closeList();
              return;
            }
            // ENTER ACCEPTS THE ACTIVE ROW; with none active it runs the typed
            // command, exactly as it always has. Same key, which is the
            // convention working rather than fighting the box's grammar.
            //
            // CTRL/CMD+ENTER IS THE OTHER AXIS (2026-09-19): the row lands in the
            // page you are on (`nav`), and this asks for a tab (`open`) — the same
            // pair of axes the typed verbs have, reachable from the list. Same
            // shape as ctrl/⌘-clicking a link anywhere else.
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              if (activeOption) accept(activeOption, e.ctrlKey || e.metaKey);
              else ask();
              return;
            }
          }}
          aria-label={copy.inputLabel}
          // THE ARIA CONTRACT (2026-09-19). Without it, assistive tech hears a
          // run of links beside a text field; with it, it hears ONE control
          // whose active option is named — the whole point of the pattern (§3).
          role="combobox"
          aria-expanded={listOpen}
          aria-controls={drawnListIds}
          aria-activedescendant={activeOption?.id}
        />
        <div className="tooltip tooltip-left" data-tip={copy.submitLabel}>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={ask}
            disabled={busy || !question.trim()}
            aria-label={copy.submitLabel}
          >
            {busy ? <span className="loading loading-spinner loading-xs" /> : copy.submit}
          </button>
        </div>
      </div>
    </div>
  );
}
