/**
 * THE SESSION PLACEHOLDER CLASS — one definition for the question "has this
 * session been named yet?".
 *
 * A placeholder is not a title: it is what a row carries between its creation
 * and the title service's answer. Three shapes exist, because three different
 * creation paths write one — and each shape used to be hardcoded separately,
 * which is exactly how an Exa session could never be named: the title service's
 * backend-title guard (TitleService.processJob) knew "New Session…" and
 * "Untitled", read the Exa panel's literal "Exa Chat" as a REAL title, and
 * skipped the job. The panel kept the placeholder forever.
 *
 * The backend's twin is the generate-title gate in
 * `api/v1/chat/finalization.py` (None | "Untitled" | startswith("New Session")).
 * Keep the two in step — that is why these strings live here instead of at the
 * call sites that write them.
 */

/** Exact placeholder titles. */
export const SESSION_PLACEHOLDERS = ['Untitled', 'Exa Chat'] as const

/** Placeholder prefixes — the temp-commit fallback writes "New Session <timestamp>". */
export const SESSION_PLACEHOLDER_PREFIXES = ['New Session'] as const

/** The placeholder the Exa panel creates its sessions with. */
export const EXA_SESSION_PLACEHOLDER = 'Exa Chat'

/** True when `title` names nothing yet. An absent title is unnamed, not a title. */
export function isPlaceholderTitle(title?: string | null): boolean {
  const trimmed = title?.trim()
  if (!trimmed) return true
  if (SESSION_PLACEHOLDERS.some((placeholder) => placeholder === trimmed)) return true
  return SESSION_PLACEHOLDER_PREFIXES.some((prefix) => trimmed.startsWith(prefix))
}
