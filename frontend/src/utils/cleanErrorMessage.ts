/**
 * Strip what litellm wraps around itself, for READING only.
 *
 * Raw shape:  MidStreamFallbackError: litellm.MidStreamFallbackError:
 *             litellm.APIError: APIError: OpenrouterException - Message: ...
 *             Original exception: APIError: litellm.APIError: APIError: ...
 * Everything from "Original exception:" on is the same failure said twice.
 *
 * Lives beside the other pure helpers rather than in the cell that first
 * needed it: the provider-health cell renders the cleaned string and the
 * widget's detail view does too, and a component file that also exports a
 * function loses fast refresh (react-refresh/only-export-components).
 * The COPY button still copies the raw string — this is for eyes only.
 */
export function cleanErrorMessage(raw: string): string {
  let s = raw
  const dup = s.indexOf('Original exception:')
  if (dup > 0) s = s.slice(0, dup)
  // collapse the "litellm.X: litellm." prefix chain
  s = s.replace(/\blitellm\.[A-Za-z_]*Error\b:?\s*/g, '')
  s = s.replace(/\blitellm\./g, '')
  s = s.replace(/\s*,\s*Metadata:\s*\{[^}]*\}/g, '')
  s = s.replace(/\s*User ID:\s*/g, '')
  return s.replace(/\s{2,}/g, ' ').trim()
}
