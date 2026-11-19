import { useState } from 'react'
import Tooltip from './ui/Tooltip'
import { useNotificationStore } from '@/stores/notificationStore'
import modeService, { type FrontendMode } from '@/services/domains/system/modeService'
import { entryFromHtml, entryFromDocument } from '@/utils/buildMode'

/**
 * THE MODE SWITCH (2026-09-17) — the button that changes which build the
 * frontend serves, from the running app rather than a terminal.
 *
 * Same contract as the shutdown button: the app REQUESTS, the launcher ACTS.
 * The launcher owns the sequencing (build, stop, start, verify) because a web
 * request cannot outlive the server it is cycling.
 *
 * WHICH MODE AM I IN comes from `import.meta.env.DEV` — the build's own truth,
 * the same source the badge uses. It cannot drift from what is being served,
 * and after a switch the reloaded page reports the NEW mode with no bookkeeping.
 *
 * HOW THE RELOAD IS TIMED. This is the part worth getting right. The launcher
 * writes the mode record BEFORE the new server binds, so polling the mode
 * endpoint would reload the page into the OLD build — a switch that looks like
 * it did nothing. Instead this watches the ENTRY MODULE the server actually
 * serves: `/src/main.tsx` on the dev server, `/assets/index.HASH.js` in
 * production. When that string changes, a different build is genuinely live.
 */

/** How long to wait before telling the user it did not come back. */
export const SWITCH_TIMEOUT_MS = 300_000
const POLL_INTERVAL_MS = 2_000

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

type Phase = 'idle' | 'confirming' | 'switching' | 'timeout'

export const BuildModeSwitch = () => {
  // The CURRENT mode comes from the build itself and needs no variable here:
  // the badge beside this button already reports it, and the button only has to
  // name where it is going.
  const target: FrontendMode = import.meta.env.DEV ? 'production' : 'development'

  const [phase, setPhase] = useState<Phase>('idle')
  const addNotification = useNotificationStore((state) => state.addNotification)

  const label = target === 'production' ? 'Switch to production' : 'Switch to development'
  const tip =
    target === 'production'
      ? 'Rebuild and serve the production bundle — much faster UI, ~70s to build'
      : 'Go back to the development server — hot reload, slower rendering'

  const runSwitch = async () => {
    setPhase('switching')

    // Captured BEFORE the request: the entry the page is running right now.
    const before = entryFromDocument(document)

    try {
      await modeService.switchTo(target)
    } catch {
      // Unlike a shutdown, a failure here is a REAL failure — nothing is
      // supposed to disconnect while the frontend is cycled.
      setPhase('idle')
      addNotification({
        type: 'error',
        title: 'Switch failed',
        message: 'The launcher could not be asked to switch mode. Nothing changed.',
        duration: 6000,
      })
      return
    }

    // Wait for a DIFFERENT build to start serving, then reload onto it.
    const deadline = Date.now() + SWITCH_TIMEOUT_MS
    while (Date.now() < deadline) {
      await sleep(POLL_INTERVAL_MS)
      try {
        const html = await fetch('/', { cache: 'no-store' }).then((r) => r.text())
        const next = entryFromHtml(html)
        if (next && next !== before) {
          window.location.reload()
          return
        }
      } catch {
        // The frontend is down for part of the switch. Expected — keep waiting.
      }
    }

    setPhase('timeout')
  }

  return (
    <>
      <Tooltip content={tip} position="bottom">
        <button className="btn btn-xs btn-outline" onClick={() => setPhase('confirming')}>
          {label}
        </button>
      </Tooltip>

      <dialog className="modal" open={phase === 'confirming' || phase === 'switching' || phase === 'timeout'}>
        <div className="modal-box">
          {phase === 'confirming' && (
            <>
              <h3 className="font-bold text-lg">{label}?</h3>
              <p className="py-4">
                The frontend will {target === 'production' ? 'rebuild and ' : ''}start serving the{' '}
                <span className="font-semibold">{target}</span> build on the same address.
                {' '}You stay signed in and your history is kept — only the build changes.
              </p>
              {target === 'production' && (
                <p className="pb-4 text-sm opacity-80">
                  The rebuild takes about a minute. This page reloads by itself when the new build is up.
                </p>
              )}
              <div className="modal-action">
                <button className="btn btn-ghost" onClick={() => setPhase('idle')}>
                  Cancel
                </button>
                <button className="btn btn-primary" onClick={runSwitch}>
                  {label}
                </button>
              </div>
            </>
          )}

          {phase === 'switching' && (
            <>
              <h3 className="font-bold text-lg">Switching to {target}…</h3>
              <p className="py-4">
                {target === 'production'
                  ? 'Building the production bundle, then the frontend restarts. '
                  : 'The frontend is restarting. '}
                This page reloads by itself when it is up.
              </p>
              <div className="flex justify-center pb-2">
                <span className="loading loading-spinner loading-md" />
              </div>
            </>
          )}

          {phase === 'timeout' && (
            <>
              <h3 className="font-bold text-lg">Still not back</h3>
              <p className="py-4">
                The frontend has not come back after five minutes. The switch may have failed —
                check the launcher's output, or reload this page to see what is serving.
              </p>
              <div className="modal-action">
                <button className="btn btn-ghost" onClick={() => setPhase('idle')}>
                  Close
                </button>
                <button className="btn btn-primary" onClick={() => window.location.reload()}>
                  Reload
                </button>
              </div>
            </>
          )}
        </div>
        {/* No backdrop dismissal while switching — the page is mid-cycle. */}
        {phase !== 'switching' && (
          <form method="dialog" className="modal-backdrop">
            <button onClick={() => setPhase('idle')}>close</button>
          </form>
        )}
      </dialog>
    </>
  )
}

export default BuildModeSwitch
