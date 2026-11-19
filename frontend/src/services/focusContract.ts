/**
 * focusContract — WHERE THE CARET BELONGS, stated once (2026-09-18).
 *
 * P4 of local/studies/exa-box-redesign-roadmap.md. A page built around one
 * field — the chat page's composer, a search page's box — DECLARES it by
 * putting `data-autofocus` on that element. Anything about to take the caret
 * asks here first, so "does this page own the caret?" is answered in ONE place
 * instead of every claimant inventing its own rule about who wins.
 *
 * WHY AN ATTRIBUTE, rather than a class, a ref registry or a context:
 *  - a page opts in by adding one word to the element it already has — no
 *    wiring, no prop threading, no provider to remember to mount;
 *  - it is about the ELEMENT, so it survives whatever the page does with its
 *    own classes and state;
 *  - it is readable straight from the DOM, which is what lets a claimant that
 *    lives far from the page (the shell's box, a mount that arrives with the
 *    route) consult it without an ancestor in between.
 *
 * THE RULE, as the roadmap states it: the page's declared primary input wins;
 * a claimant that finds no declaration is free to take the caret. There is no
 * app-wide focus/tab-order pass behind this — that is its own arc, and the
 * roadmap is explicit that half-doing it inside the box's arc would produce a
 * half-pass. A page that declares nothing behaves exactly as it does today,
 * so pages opt in as they are touched.
 *
 * ── THE HANDOFF (2026-09-19): "WE WANT TO JUMP TO THE PAGE WE JUST WENT TO" ──
 *
 * The rule above decides who wins when a page LOADS. It did not cover what the
 * user reported: after navigating from the Search box, the caret stayed in the
 * box — in the sidebar — because three separate rules all ended there and no
 * page declared a field of its own. Being left in the nav panel after asking to
 * go somewhere is the defect.
 *
 * So a navigation the READER ASKED FOR now announces itself, and the arrival
 * answers it: `requestPageFocus()` is written by whoever performs the
 * navigation, `claimPageFocus()` is called by the shell on arrival and moves the
 * caret to the page — the declared input if there is one, else the `<main>`
 * region itself (focused programmatically; it carries `tabindex="-1"`).
 *
 * WHY A TOKEN AND NOT JUST A CALL: half of these arrivals are a NEW TAB, which is
 * a fresh document the opener cannot reach — browser security, not a bug. The
 * token rides `localStorage` so the arriving document can read it, in the shape
 * the house already uses for exactly this (services/domains/providers/swapHandoff:
 * queue / peek / consume, single-use).
 *
 * A COLD ARRIVAL IS NOT A REQUEST (typed URL, bookmark, reload): no token, so the
 * box keeps the caret exactly as it does today, and the ruling the user made
 * earlier — "I have to click it before I can type" — still stands for a load
 * nobody asked for.
 */

/** The one spelling of the convention — nobody repeats the literal. */
const AUTOFOCUS_ATTR = 'data-autofocus'

/** The one-shot slot's key and its shelf life. Exported: the key is the contract
 *  between a writer in one document and a reader in another. */
export const FOCUS_HANDOFF_KEY = 'cogitate-focus-handoff'
const HANDOFF_TTL_MS = 10_000

/** The landmark the caret falls back to when the page declares no field. */
function mainLandmark(): HTMLElement | null {
  return document.querySelector<HTMLElement>('main')
}

/** Is this element part of the destination rather than of the shell around it? */
function onThePage(el: Element): boolean {
  return Boolean(el.closest('main'))
}

/**
 * The element this page declares as the one focus belongs to.
 *
 * `null` when the page says nothing, which is the caller's signal that the
 * caret is its own to take.
 */
export function declaredPrimaryInput(): HTMLElement | null {
  return document.querySelector<HTMLElement>('[' + AUTOFOCUS_ATTR + ']')
}

/**
 * THE PAGE'S OWN HALF (2026-09-19) — a page takes the caret for the field it
 * declared.
 *
 * The attribute alone is a YIELD: it tells claimants to stand down, and the two
 * claimants that read it do — the standing Search box yields to a declaration on
 * arrival, and the handoff yields to a page that already has the caret. What the
 * attribute cannot do is put the caret anywhere, and the page is the only party
 * that knows when its own field exists:
 *
 *  - ROUTES ARE LAZY. On a cold load the page's chunk resolves AFTER the shell's
 *    arrival effect has run, so the box claims the caret while there is no
 *    declaration in the document to yield to, and nothing takes them off it.
 *    Measured: a cold load of the Message Center left the caret in the box while
 *    the page's search field sat there declared and empty.
 *  - A page built around one field really does focus it (the test double in
 *    NavSearchSection.test.tsx has said so since 2026-09-18, `claim: true`).
 *
 * So a declaring page calls this once, on mount. It runs BEFORE the shell's claim
 * in the same commit (children before parents), which is what lets the claim read
 * "somebody already has it" and leave it alone.
 */
export function claimDeclaredPrimaryInput(): void {
  declaredPrimaryInput()?.focus()
}

/**
 * SAY THAT THE READER ASKED FOR WHERE THEY ARE GOING — written by the surface
 * that performs the navigation, BEFORE it navigates, so an arriving tab can find
 * it. Idempotent and silent on a blocked store: losing the handoff costs one
 * caret position, never the navigation.
 */
export function requestPageFocus(): void {
  try {
    localStorage.setItem(FOCUS_HANDOFF_KEY, String(Date.now()))
  } catch {
    /* storage blocked — the page simply keeps whatever caret it has */
  }
}

/** Is a fresh request waiting? A PEEK: it does not consume. */
export function pageFocusRequested(): boolean {
  return freshRequest()
}

/** A request older than the window is stale — dropped, not honoured. */
function freshRequest(): boolean {
  try {
    const raw = localStorage.getItem(FOCUS_HANDOFF_KEY)
    if (!raw) return false
    const at = Number(raw)
    if (!Number.isFinite(at) || Date.now() - at > HANDOFF_TTL_MS) {
      localStorage.removeItem(FOCUS_HANDOFF_KEY)
      return false
    }
    return true
  } catch {
    return false
  }
}

/**
 * THE ARRIVAL'S HALF: honour a pending request and take the caret to the page.
 *
 * Called by the shell on a route change and on a fresh mount (a new tab is a
 * mount). Consumes — one request, one arrival — and returns whether the caret
 * was moved.
 *
 * IT YIELDS TO A PAGE THAT ALREADY HAS IT. A page's own field effect runs before
 * the shell's (children before parents, same commit), so by the time this runs
 * the caret may already be where it belongs; stealing it back would fight the
 * very contract this serves.
 */
export function claimPageFocus(): boolean {
  if (!freshRequest()) return false
  try {
    localStorage.removeItem(FOCUS_HANDOFF_KEY)
  } catch {
    /* nothing to clear */
  }
  const active = document.activeElement as HTMLElement | null
  if (active && active !== document.body && onThePage(active)) return true
  const target = declaredPrimaryInput() ?? mainLandmark()
  if (!target) return false
  target.focus()
  return document.activeElement === target
}
