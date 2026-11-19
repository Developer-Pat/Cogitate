import path from 'path'

/**
 * THE PATH LOCATOR — one definition, imported by BOTH configs.
 *
 * Why it lives in its own file: the alias was previously declared only in
 * `vite.config.ts`, while `vitest.config.ts` shadows that file entirely (vitest
 * prefers a dedicated config and does not merge). So `@/...` resolved in the app
 * build and silently did NOT resolve under the test runner — an import that
 * works in one context and fails in the other, which is the worst version of a
 * path bug.
 *
 * Use `@/...` rather than a hand-computed relative climb ('../../../../'):
 * a crawl has to be re-counted every time a file moves, and getting it wrong is
 * a runtime failure rather than a compile error. Counting is not locating.
 */
export const aliases = {
  '@': path.resolve(__dirname, './src'),
}
