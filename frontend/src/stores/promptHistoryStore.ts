/**
 * promptHistoryStore — THE PROMPT HISTORY. A straight copy of what the user sends.
 *
 * HOW THIS WORKS (2026-09-15, the user's model): "I thought you were getting them
 * from the input user window. A straight copy to the history table." That is exactly
 * what this is — the composer hands over the text on send, and it lands here.
 *
 * WHAT IT REPLACED, AND WHY THE FIRST VERSION WAS WRONG. The first pass DERIVED the
 * history from `currentSession.messages`. Three problems fell out of that:
 *   1. Tossing a session cascades on chat_messages (ondelete="CASCADE"), so the
 *      prompts were DESTROYED, not hidden — the history could never show them again;
 *   2. the tab was empty for a session you had not opened, because messages are
 *      lazily loaded;
 *   3. it needed the dismissed-set workaround, because a derived list has nothing
 *      you can actually delete from.
 * Copy-on-send has none of those: the history is its own data.
 *
 * DEDUPED AND ALPHABETICAL (2026-09-17, the user's ask). Two changes, and together
 * they change what this list IS:
 *
 *   - A prompt already in the history is NOT added again. Matching ignores case and
 *     collapses whitespace, so it agrees with what the eye sees in the row (the
 *     display collapses whitespace too).
 *   - The list is kept in ALPHABETICAL order, not newest-first.
 *
 * The pair matters: repeats removed turns this from a LOG into a LIBRARY of the
 * distinct prompts you have used — and a library is something you scan to find one
 * again, which is what alphabetical order is for. The previous behaviour kept a row
 * per send, deliberately ("the same prompt may be sent twice on purpose"), which
 * stacked a retry as a second copy of the same text.
 *
 * A duplicate does NOT move to the top. "Do not add" means the existing entry keeps
 * its place — it is not treated as "recently used".
 *
 * STORAGE: sessionStorage, deliberately, NOT localStorage.
 *   - the user's ask: "persisted for the application duration. It does not need to
 *     survive a restart. Front end storage is fine."
 *   - pure in-memory would satisfy that literally, but it dies on every page
 *     refresh, and a refresh (or a Vite hot-reload) wiping the history reads as a
 *     bug rather than a choice.
 *   - sessionStorage survives a refresh and dies with the tab. That is the
 *     application's duration, and it keeps the feature honest: nothing crosses a
 *     browser session, so nothing needs migrating later.
 *
 * A FLAT LIST, not per-session — "a straight copy to the history table". The
 * originating sessionId IS recorded, so a scope filter is a small later step rather
 * than a rewrite; but nothing filters on it today.
 */
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

/** Bounded so the store cannot creep; generous enough to be a real history. */
export const MAX_HISTORY = 200
/** How many the panel renders. Older entries stay stored but are not drawn. */
export const MAX_DISPLAYED = 100

export interface HistoryPrompt {
  /** Stable key for React and for removal. Not the text — two prompts may differ only
      by whitespace and still be distinct ENTRIES if their text differs at all. */
  id: string
  text: string
  /** Which session it was sent in. Recorded, not filtered on. */
  sessionId: string | null
  createdAt: number
  /** THE TIE-BREAK (2026-11-25). `createdAt` is milliseconds, and a burst of sends
      — a paste-and-send, a keyboard run — lands several inside the SAME one. The cap
      must still know which of them is oldest, so insertion order is recorded here.
      Absent on rows persisted before this field existed; they fall back to 0. */
  seq?: number
}

// ── the pure helpers, exported so the behaviour is testable without the store ──

/**
 * What counts as "the same prompt". Case and runs of whitespace are ignored, which
 * is what the display already does — so a prompt is a duplicate exactly when it
 * looks like one in the list.
 */
export const matchKey = (text: string): string =>
  text.replace(/\s+/g, ' ').trim().toLowerCase()

/** Alphabetical, case-insensitively — `sensitivity: 'base'` compares letters, not case. */
export const sortPrompts = (list: HistoryPrompt[]): HistoryPrompt[] =>
  [...list].sort((a, b) => a.text.localeCompare(b.text, undefined, { sensitivity: 'base' }))

/** Drop later entries whose text matches an earlier one. First occurrence wins. */
export const dedupePrompts = (list: HistoryPrompt[]): HistoryPrompt[] => {
  const seen = new Set<string>()
  return list.filter((p) => {
    const key = matchKey(p.text)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

/**
 * Whichever of two entries is OLDER — by time, then by insertion order.
 *
 * THE TIE IS THE BUG THIS EXISTS FOR (2026-11-25). `createdAt` is milliseconds and a
 * burst of sends lands several inside one; a comparison that only reads `createdAt`
 * treats them as equal and the cap drops an arbitrary row — measured in CI, where a
 * 205-add loop finished inside a millisecond and the "oldest" it discarded was the one
 * just added. The order the adds arrived in is the answer, and `seq` records it.
 */
export const olderOf = (a: HistoryPrompt, b: HistoryPrompt): HistoryPrompt => {
  if (a.createdAt !== b.createdAt) return a.createdAt < b.createdAt ? a : b
  return (a.seq ?? 0) <= (b.seq ?? 0) ? a : b
}

interface PromptHistoryState {
  /** ALPHABETICAL — the store keeps the order the tab draws. */
  prompts: HistoryPrompt[]
  /** Record a prompt the user just sent. Called from the send path. */
  addPrompt: (text: string, sessionId: string | null) => void
  /** Delete one entry. This is the whole of "forget it" — there is no shadow set. */
  removePrompt: (id: string) => void
  /** Delete every entry. */
  clearAll: () => void
}

let seq = 0

export const usePromptHistoryStore = create<PromptHistoryState>()(
  persist(
    (set) => ({
      prompts: [],

      addPrompt: (text, sessionId) =>
        set((state) => {
          const trimmed = text?.trim()
          // A send with nothing in it is not a prompt. Attachments-only sends exist,
          // and an empty row in the history would be noise the user cannot explain.
          if (!trimmed) return state

          // Already here? Don't add it again, and don't disturb where it sits.
          const key = matchKey(trimmed)
          if (state.prompts.some((p) => matchKey(p.text) === key)) return state

          const entry: HistoryPrompt = {
            id: `${Date.now()}-${seq}`,
            text: trimmed,
            sessionId,
            createdAt: Date.now(),
            seq,
          }
          seq += 1

          let next = [entry, ...state.prompts]

          // THE CAP DROPS THE OLDEST BY TIME, NOT BY POSITION. The list is
          // alphabetical, so slicing the tail would discard the END OF THE ALPHABET
          // instead of the oldest prompt — silently losing recent entries and
          // keeping ancient ones.
          if (next.length > MAX_HISTORY) {
            const oldest = next.reduce(olderOf)
            next = next.filter((p) => p.id !== oldest.id)
          }

          return { prompts: sortPrompts(next) }
        }),

      removePrompt: (id) =>
        set((state) => ({ prompts: state.prompts.filter((p) => p.id !== id) })),

      clearAll: () => set({ prompts: [] }),
    }),
    {
      name: 'cogitate-prompt-history',
      // sessionStorage: the application's duration. See the header note.
      storage: createJSONStorage(() => sessionStorage),
      // Only the data is persisted — not the functions.
      partialize: (state) => ({ prompts: state.prompts }),
      // A list persisted BEFORE dedup/ordering existed still holds its repeats and
      // its newest-first order. Normalising it on load is what makes the change take
      // effect immediately instead of appearing not to work until the next send.
      version: 1,
      migrate: (persisted) => {
        const list = Array.isArray((persisted as { prompts?: HistoryPrompt[] })?.prompts)
          ? (persisted as { prompts: HistoryPrompt[] }).prompts
          : []
        return { prompts: sortPrompts(dedupePrompts(list)) }
      },
    }
  )
)
