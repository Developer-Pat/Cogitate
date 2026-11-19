/**
 * navHistory — where you have actually been going.
 *
 * The user: "Maybe give it a history of most frequent or last N
 * navigations. I don't want to lose the mouse even with the hotkey."
 *
 * So the command box is not only a text field: opening it offers the
 * destinations you actually use, one click away, no typing. The store is
 * localStorage — the app's existing client-state idiom (the theme lives
 * there too) — and it is deliberately small: aggregated BY destination, so
 * a repeat raises a count instead of filling the list with duplicates.
 *
 * It is a CONVENIENCE, never a source of truth: an absent or corrupt store
 * degrades to "no history", never to an exception in the header of every
 * page in the app.
 */

export interface NavHistoryEntry {
  to: string
  label: string
  /** How many times this destination has been opened. */
  count: number
  /** Unix ms of the most recent open — the tie-break for equal counts. */
  lastAt: number
}

const KEY = 'cog-nav-history'
/** Bounded: the list is a shortcut, not a log. */
const MAX_KEPT = 40

function read(): NavHistoryEntry[] {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (e): e is NavHistoryEntry =>
        !!e && typeof e === 'object' && typeof (e as NavHistoryEntry).to === 'string'
    )
  } catch {
    return []
  }
}

function write(list: NavHistoryEntry[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(list.slice(0, MAX_KEPT)))
  } catch {
    // a private-mode quota error must not break the header
  }
}

/**
 * Record a successful navigation. MOST FREQUENT first, most recent as the
 * tie-break — so a place you live in stays at the top and a one-off drifts
 * down, which is the thing that makes the list worth showing.
 */
export function recordNav(to: string, label: string, now: number = Date.now()): void {
  if (!to) return
  const list = read()
  const existing = list.find((e) => e.to === to)
  if (existing) {
    existing.count += 1
    existing.lastAt = now
    if (label) existing.label = label
  } else {
    list.push({ to, label, count: 1, lastAt: now })
  }
  list.sort((a, b) => b.count - a.count || b.lastAt - a.lastAt)
  write(list)
}

/** The shortcuts to offer, most-used first. */
export function navHistory(limit = 6): NavHistoryEntry[] {
  return read().slice(0, limit)
}

/** For tests and for the user's own reset — never called automatically. */
export function clearNavHistory(): void {
  try {
    localStorage.removeItem(KEY)
  } catch {
    // nothing to do
  }
}
