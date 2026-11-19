import Tooltip from './ui/Tooltip'
import { buildModeInfo } from '@/utils/buildMode'

/**
 * THE BUILD-MODE BADGE (the frontend mode switch, Phase A).
 *
 * Reports the BUILD, not the host. `import.meta.env.DEV` is baked in by Vite at
 * build time, so it cannot drift from the code that is actually running — which
 * matters, because a badge that could lie is worse than no badge.
 *
 * WHY IT EXISTS. The two builds are otherwise behaviourally identical: the only
 * mode-gated code in the app is the Zustand devtools bridge. So the build is
 * invisible, yet it is the single biggest thing the user can feel — during a
 * stream the production build measured ~6x less non-idle main-thread work, with
 * 41 long tasks collapsing to 2. The badge is what tells them which build they
 * are looking at.
 *
 * DEV reads as the anomaly (it is the slower one); PROD is the state a
 * deployment runs, so it stays quiet.
 */

export const BuildModeBadge = () => {
  const { label, tip } = buildModeInfo(import.meta.env.DEV)

  return (
    <Tooltip content={tip} position="bottom">
      <span
        className={`badge badge-xs badge-outline font-mono ${
          import.meta.env.DEV ? 'badge-warning' : 'badge-success'
        }`}
      >
        {label}
      </span>
    </Tooltip>
  )
}

export default BuildModeBadge
