/**
 * navigationService - THE SIMPLE NAVIGATION (2026-08-28).
 *
 * The decision (the user's call): the app's a SPA, not a desktop
 * app - the multi-tab orchestration's not the goal. The model:
 * open the destination in a NEW TAB, always. The user navigates
 * by clicking the browser's tabs.
 *
 * (The cross-tab harness keeps the SESSION-CONTEXT service - the
 * inter-tab engage-context; the registry/focus went out with the
 * smart-tab experiment.)
 *
 * ONE WINDOW PER DESTINATION (2026-09-19). Every destination the app opens in its
 * own window is opened BY NAME (`cog-<path>`), so asking for the same place twice
 * switches to the window that already has it instead of stacking a duplicate —
 * the user's rule: "we don't need or want two windows showing logs. If logs is
 * open we just switch to it."
 *
 * AND THE SWITCH MUST NOT RELOAD IT. `window.open(url, name)` on an existing
 * window both focuses it AND re-navigates it — measured: a value set on that
 * window did not survive the second request. For a page that is harmless; for a
 * tab holding state (a draft, a live session, a scroll position) it is
 * destructive, and "switch to it" has to mean exactly that. So an existing window
 * is reached with `window.open('', name)` — no url, so nothing is navigated, the
 * existing context is simply handed back — and only a MISSING one is opened for
 * real. Measured in Chromium: no new tab, no reload.
 *
 * AGENT CHAT IS EXEMPT, deliberately. The user: "a user may have more than one
 * conversation going at a time" — so Agent Chat keeps opening its own tab, and
 * one tab PER CONVERSATION (the conversation's identity in the window name, and a
 * name that survives a reload) is its own arc, still open.
 */

export type TabApp = 'exa' | 'messages' | 'sessions' | 'agent-chat' | 'wiki'

const ROUTES: Record<TabApp, string> = {
  exa: '/exa',
  messages: '/messages',
  sessions: '/sessions',
  'agent-chat': '/agent-interaction',
  wiki: '/wiki',
}

/** The window name for a destination. ONE WINDOW PER PATH, whoever asks. */
export function windowNameFor(path: string): string {
  return 'cog-' + path
}

/**
 * Focus the window that already has this destination, or open it.
 *
 * THE TWO STEPS ARE THE WHOLE POINT: `window.open('', name)` returns the existing
 * window UNTOUCHED (no url means no navigation), and only when what comes back is
 * a blank context — the one this call just made, because no window had the name —
 * is the destination actually loaded into it.
 *
 * `occupied` defaults to TRUE on a cross-origin read failure: the alternative
 * would be to navigate a window we cannot inspect, which is the destructive half
 * of the mistake this exists to avoid.
 */
export function openReusing(path: string): void {
  const name = windowNameFor(path)
  const existing = window.open('', name)
  if (!existing) {
    // popup blocked, or no handle: the plain open is the only remaining move
    window.open(path, name)
    return
  }
  let occupied = true
  try {
    occupied = existing.location.href !== 'about:blank'
  } catch {
    occupied = true
  }
  if (occupied) {
    existing.focus()
    return
  }
  existing.location.href = path
}

/** open the destination in a new tab — the current tab untouched. */
export function navigateTo(app: TabApp): void {
  if (app === 'agent-chat') {
    // EXEMPT: more than one conversation at a time is legitimate, so this one
    // keeps a fresh tab per request (see the module docstring).
    window.open(ROUTES[app], '_blank')
    return
  }
  openReusing(ROUTES[app])
}

/** The tab app's own route — for surfaces that carry plain paths (search
 *  results, the navigator's history) rather than TabApp keys. */
export function tabAppPath(app: TabApp): string {
  return ROUTES[app]
}
