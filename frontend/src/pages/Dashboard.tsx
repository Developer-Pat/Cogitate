import { ErrorBoundary } from '../components/ErrorBoundary'
import { usePageTitle } from '../hooks/usePageTitle'
import { HelpButton } from '../components/help'
import { CacheBuster } from '../components/CacheBuster'
import BuildModeBadge from '../components/BuildModeBadge'
import BuildModeSwitch from '../components/BuildModeSwitch'

import ReadinessCard from '../components/dashboard/ReadinessCard'
import MessagePreviewCard from '../components/dashboard/MessagePreviewCard'
import NavigationCards from '../components/dashboard/NavigationCards'
import VisualCheckCard from '../components/dashboard/VisualCheckCard'
import LifecycleCard from '../components/dashboard/LifecycleCard'
import { BackendStatusIndicator } from '../components/ui/BackendStatusIndicator'

export default function Dashboard() {
  usePageTitle('Dashboard', 'System overview and quick actions')
  
  // The build's own version. Read from the build-time constant, not from localStorage: the stored
  // copy is written by CacheBuster's effect, so a first render (or a fresh profile) read the empty
  // case and the header said "v0.0.0" on a real release. localStorage stays as the fallback.
  const appVersion = (import.meta.env.VITE_APP_VERSION as string | undefined)
    || (typeof window !== 'undefined' ? localStorage.getItem('app_version') : null)
    || '0.0.0'

  return (
    <ErrorBoundary>
      <div className="p-6 max-w-7xl mx-auto">
        {/* Welcome Section with Logo, Version, Status Indicator, Cache Buster, and Help */}
        <div className="flex items-center justify-between mb-6 gap-4">
          <div className="flex items-center gap-3">
            <div className="tooltip tooltip-bottom" data-tip="Cogitate Logo">
              <img
                src="/cogito-logo.svg"
                alt="Cogitate Logo"
                className="h-10 w-10"
              />
            </div>
            <h1 className="text-3xl font-bold text-base-content">
              Cogitate Dashboard
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <BackendStatusIndicator compact={true} className="ml-2" tooltipPosition="bottom" />
            <span className="text-xs text-readout font-mono">v{appVersion}</span>
            {/* WHICH BUILD the user is looking at (the mode-switch arc, Phase A).
                The two builds are otherwise behaviourally identical, so this is
                the only thing that distinguishes the faster one. */}
            <BuildModeBadge />
            <BuildModeSwitch />
            <CacheBuster />
            <HelpButton context="dashboard" tooltipPosition="bottom" />
          </div>
        </div>

        {/* THE SYSTEM VERDICT (2026-11-20) — first, because a fresh install that
            cannot answer used to look completely healthy on this page. */}
        <div className="mb-4">
          <ReadinessCard />
        </div>

        {/* Quick Navigation Cards */}
        <NavigationCards />

        {/* THE SHUTDOWN BUTTON + THE EXIT RECORD (2026-09-15). The button
            PRODUCES the thing the card reports, so they sit together — which
            also makes an unclean exit visible instead of buried in a log. */}
        <div className="mt-4">
          <LifecycleCard />
        </div>

        {/* THE VISUAL CHECK LINKS (2026-09-06): the sweep changed a
            lot of pages — the spot-check list for the human eye. */}
        <div className="mt-4">
          <VisualCheckCard />
        </div>

        {/* THE MESSAGE CENTER CARD (2026-08-25, the roadmap's Phase 3) */}
        <div className="mt-4">
          <MessagePreviewCard />
        </div>

      </div>
    </ErrorBoundary>
  )
}
