/**
 * The frontend's BUILD/MODE pure functions — what the badge reports and which
 * build a served page is actually running.
 *
 * They live beside the other pure helpers rather than inside the components
 * that use them, for two reasons: a component file that also exports a
 * function loses fast refresh (react-refresh/only-export-components), and
 * these are pure decisions worth testing without rendering anything.
 */

/**
 * THE BADGE'S DECISION — label + tooltip for a build, pure so BOTH branches
 * are testable without env tricks (`import.meta.env.DEV` cannot be faked in a
 * test the way a boolean can).
 *
 * DEV reads as the anomaly (it is the slower one); PROD is the state a
 * deployment runs, so it stays quiet. The tip is SHORT by house rule — the
 * explanation, not a definition.
 */
export const buildModeInfo = (isDev: boolean): { label: string; tip: string } => ({
  label: isDev ? 'DEV' : 'PROD',
  tip: isDev
    ? 'Development build: unbundled, unminified, StrictMode double-rendering — renders slower than production'
    : 'Production build: bundled and minified — this is what a deployment runs',
})

/**
 * The module entry an index.html points at — `/src/main.tsx` on the dev
 * server, `/assets/index.HASH.js` in production.
 */
export const entryFromHtml = (html: string): string | null => {
  const match = html.match(/<script[^>]*\btype="module"[^>]*\bsrc="([^"]+)"/i)
  return match ? match[1] : null
}

/** The module entry the CURRENTLY LOADED page was served with. */
export const entryFromDocument = (doc: Document): string | null => {
  const script = doc.querySelector('script[type="module"][src]')
  return script ? script.getAttribute('src') : null
}
