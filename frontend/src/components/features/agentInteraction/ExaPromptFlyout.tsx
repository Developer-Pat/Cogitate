/**
 * ExaPromptFlyout — the Exa button becomes an ask-Exa surface.
 *
 * THE USER'S ASK (2026-09-15): "The next thing I want to work on is the
 * exa button. It currently navigates to the exa page. I want to be able
 * to send Exa a prompt and have Exa respond." Two response forms were
 * specified; this is FORM 1 — Exa answers with a message. FORM 2 (Exa
 * opens the right page) is Phase B and hooks in at the `tool_call`
 * branch in useCommandBox, which is exactly where the bridge's full
 * frame (including rawInput) already arrives.
 *
 * Why the button no longer navigates: the two behaviours COEXIST, not
 * swap — the flyout carries an explicit "Full page" control, so the
 * tab-services path the button had is one click away instead of gone.
 *
 * THE SPLIT WITH THE SIDEBAR'S BOX (2026-09-18). The Ask-Exa box has two
 * mounts with different jobs, and the difference is ONE option on the hook they
 * share (`useCommandBox`'s `exaFallthrough`):
 *
 *   - THIS MOUNT keeps the Exa path (`exaFallthrough: true`): it has the room
 *     for a short answer and for stopping a run, and it is where a DISPATCH is
 *     typed — "tell Exa to do that thing" — background work whose report
 *     arrives through the app's message system rather than inline.
 *   - The NAV SIDEBAR's box passes false: it is a navigator, so an input that
 *     is not a command is answered locally in one line, and `exa <question>`
 *     opens the Exa chat tab rather than sending anything from a 16rem column.
 *
 * THE VISIBLE HALF OF THAT SPLIT (2026-09-18, the user: "change the name of the
 * box from Ask Exa to Search"). The sidebar's mount READS "Search", its button
 * is "Go", and its panel draws no "Full page" control and no answer area — the
 * panel's `variant` + `COPY` own all of that. THIS MOUNT IS UNCHANGED: the
 * trigger still says Exa, the button still says Send, and "Full page" and the
 * streamed answer stay, because this is the mount that genuinely sends.
 *
 * The channel is the SAME bridge the Exa page and ConsultComposer use
 * (/api/v1/external-agent/ws), so the ask lands in the same Exa session:
 * Exa remembers it, even though this flyout's transcript is transient.
 *
 * Pattern lessons carried over from ConsultComposer + the ExaSchedulePanel:
 *  - COALESCE the streamed chunks into one line. One <div> per chunk is
 *    900 DOM nodes and a stuck render.
 *  - The input starts EMPTY, the placeholder teaches the shape, and Send
 *    stays disabled until there is text.
 *  - A failure is LOUD (the backend's status:error / cancelled /
 *    time_limit frames), never a silent flatline.
 *  - Escape closes and aborts an in-flight ask.
 */

import { CommandBoxPanel } from './CommandBoxPanel';
import { useCommandBox } from './useCommandBox';
import { useSettingsStore } from '@/stores/settingsStore';

interface ExaPromptFlyoutProps {
  /**
   * The coexisting path: open/focus the Exa Agent page. Optional — the
   * widget defaults to the app's own Exa destination, so `ExaPromptFlyout`
   * with no props is a complete mount (that is how PageBanner carries it).
   */
  onOpenExaPage?: () => void;
}

export function ExaPromptFlyout({ onOpenExaPage }: ExaPromptFlyoutProps) {
  /**
   * `appearance.keepCommandBoxOpen` — the preference this mount answers to,
   * beside Quiet Mode in Settings > Appearance. ON: the header's box is a
   * mount that stays open, so taking you somewhere does not cost you the
   * input and a run of pages is visited from the keyboard. OFF (default): the
   * mount is left alone and the header behaves exactly as it always has —
   * navigate, and the box goes with the page it was sitting on.
   */
  const staysOpen = useSettingsStore((s) => s.settings.appearance.keepCommandBoxOpen);
  /**
   * `hotkey: false` — the app-wide Cmd/Ctrl+K is the SHELL's one listener
   * (NavSearchHotkey) and its home is the sidebar box, so this mount must not arm
   * a second one: armed, it opened the flyout while the keystroke also raised
   * and focused the sidebar's box. Nothing else about this mount changes — the
   * button, the open/close, and the close-on-navigate the preference above
   * decides are exactly as they were.
   *
   * `exaFallthrough: true` — THIS IS THE MOUNT WITH THE EXA PATH (2026-09-18).
   * The flyout has the room (440px) for a short answer and for stopping a run,
   * and it is where a DISPATCH is typed — "tell Exa to do that thing" — so an
   * input that is not a command still falls through to the bridge, and
   * `exa <question>` still forces it there. The nav sidebar asks for the
   * opposite (see NavSearchSection): it is a navigator and answers locally,
   * because a 16rem column has no room for either. The split is ONE option on
   * the shared hook — `useCommandBox` — so nothing else about the two mounts
   * can drift.
   */
  const commandBox = useCommandBox({ onOpenExaPage, hotkey: false, exaFallthrough: true, staysOpen });
  const { open, setOpen, close, wrapRef } = commandBox;

  return (
    <div className="relative inline-block" ref={wrapRef}>
      {/* THE LABEL, NOT THE FACE (2026-09-15, the user's call): at 20px the
          face is unreadable — "too small to make out... I know what it is
          because I've seen the full size version" — so the trigger says what
          it does and wears the SAME tokens as its neighbours (pill-button
          --normal, exactly like the ⚡ ACP control beside it). The face keeps
          the places where it is legible and meaningful: the Exa chat page
          (full size in the page) and the Exa config page (the preview). */}
      <div className="tooltip tooltip-bottom" data-tip="Ask Exa">
        <button
          type="button"
          onClick={() => (open ? close() : setOpen(true))}
          className={'pill-button pill-button--normal cursor-pointer ' + (open ? 'ring-1 ring-primary' : '')}
          aria-label="Ask Exa — the system agent"
          aria-expanded={open}
          aria-haspopup="dialog"
        >
          Exa
        </button>
      </div>

      {open && <CommandBoxPanel {...commandBox} />}
    </div>
  );
}

export default ExaPromptFlyout;
