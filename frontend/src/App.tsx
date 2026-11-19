
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import { Suspense, useEffect, useRef } from 'react';
import { HelmetProvider } from 'react-helmet-async'
import './App.css'
import { QueryProvider } from './providers/QueryProvider'
import { NotificationContainer } from './components/NotificationContainer'
import { useWorkflowToasts } from './hooks/useWorkflowToasts'
import { useNotifyBridge } from './hooks/useNotifyBridge'
import { enableCrossTabNotifyReceiver } from './services/crossTab/crossTabNotifyReceiver'
import { useAgentSync } from './hooks/useAgentSync'
import { useSessionSync } from './hooks/useSessionSync'
import { useMacroSync } from './hooks/useMacroSync'
import { useCancellingNotice } from './hooks/useCancellingNotice'
import { CognitiveHubProvider } from './providers/CognitiveHubProvider'
import { HelpModal } from './components/help'
import { AgentPanel } from './components/agentPanel'
import FirstRunRedirect from './components/FirstRunRedirect'
import { NavSearchSection } from './components/features/agentInteraction/NavSearchSection'
import { NavSearchHotkey } from './components/features/agentInteraction/NavSearchHotkey'
import { routes } from './config/routes'
import PageLoader from './components/Loading/PageLoader'
import RouteGuard from './components/RouteGuard'
import { useUIStore } from './stores/uiStore'
import { useSettingsStore } from './stores/settingsStore'
import { useTheme } from './hooks/useTheme'
import { useUIStateBridge } from './hooks/useUIStateBridge'
import { claimPageFocus } from './services/focusContract'

// Scroll to top component
function ScrollToTop() {
  const { pathname } = useLocation()

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return null
}

/**
 * Global theme provider — applies theme from localStorage (useTheme hook) to the entire app.
 * This is the actual source of truth for theme selection, since ThemeSelector writes to localStorage.
 */
function GlobalTheme() {
  const { theme, resolvedTheme } = useTheme()

  useEffect(() => {
    if (typeof document === 'undefined') return
    const html = document.documentElement
    const resolved = theme === 'auto' ? resolvedTheme : theme

    html.classList.remove('light', 'dark')
    html.setAttribute('data-theme', resolved)
    html.classList.add(resolved === 'dark' ? 'dark' : 'light')
  }, [theme, resolvedTheme])

  // QUIET MODE (2026-09-05, the user's ask): the control-loudness
  // preference rides the settings store (appearance.loudness) and
  // lands on html[data-loudness] — the index.css quiet layer keys
  // off it app-wide (no per-button classes).
  const loudness = useSettingsStore((s) => s.settings?.appearance?.loudness)

  useEffect(() => {
    if (typeof document === 'undefined') return
    document.documentElement.setAttribute(
      'data-loudness',
      loudness === 'quiet' ? 'quiet' : 'normal'
    )
  }, [loudness])

  return null
}

/**
 * Layout — Navigation sidebar + main content area.
 *
 * REWRITTEN 2026-06-15: Replaced DaisyUI drawer component with plain flexbox layout.
 * The DaisyUI drawer's CSS Grid + @layer cascade system prevented inline width
 * overrides from taking effect (see local/issues/2026-06-15-navigation-drawer-toggle-not-working.md).
 * Flexbox gives us full control over sidebar width via inline style without
 * fighting cascade layers.
 */
function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const { sidebarCollapsed, toggleSidebar } = useUIStore()

  // Initialize the WebSocket UI State Bridge for the lifetime of the app.
  // This pushes UI state changes to the backend and handles incoming
  // navigation requests from external agents / scripts.
  const { isConnected } = useUIStateBridge()

  /**
   * THE CARET HANDOFF, ANSWERED (2026-09-19) — the arrival's half of
   * `services/focusContract`.
   *
   * The user: *"it leaves us stuck in the nav panel either way … we want to jump
   * to the page we just opened / navigated to."* So a navigation the READER ASKED
   * FOR records that fact before it happens (`requestPageFocus`, written by the
   * box), and this effect is what honours it: the destination's declared primary
   * input takes the caret if it declares one, else the `<main>` region itself.
   *
   * IT RUNS ON EVERY ARRIVAL, INCLUDING THE FIRST. A new tab is a fresh document
   * and nobody can focus it from the outside — browser security — so the token
   * rides `localStorage` and this effect is the only way that tab learns to put
   * the caret on the page rather than in the sidebar box.
   *
   * A COLD ARRIVAL (typed URL, bookmark, reload) leaves no token, so nothing here
   * fires and the box keeps the caret exactly as it did before — the earlier
   * ruling ("I have to click it before I can type") stands for a load nobody
   * asked for.
   *
   * It runs AFTER the children's effects (React commits deepest-first), which is
   * what lets `claimPageFocus` yield to a page whose own field effect already took
   * the caret.
   */
  useEffect(() => {
    claimPageFocus()
  }, [location.pathname])

  /**
   * WHERE THE CARET GOES WHEN THE PANEL COLLAPSES (2026-09-19).
   *
   * Ctrl+` can be pressed while the caret is inside the sidebar — most obviously
   * while typing in the Search box, which the collapse then UNMOUNTS — and focus
   * that vanishes into `<body>` is a keyboard user stranded. So a collapse moves
   * the caret to the control that brings the panel back: the rail's chevron on a
   * wide screen, the hamburger on a narrow one (where the aside itself is
   * off-canvas and its chevron would be invisible).
   *
   * It yields when the caret was somewhere that survives the collapse — a page
   * field, the header's own controls — because moving THAT would be the same
   * defect pointed the other way.
   */
  const railToggleRef = useRef<HTMLButtonElement>(null)
  const hamburgerRef = useRef<HTMLButtonElement>(null)
  const wasCollapsed = useRef(sidebarCollapsed)
  useEffect(() => {
    const justCollapsed = !wasCollapsed.current && sidebarCollapsed
    wasCollapsed.current = sidebarCollapsed
    if (!justCollapsed) return
    const active = document.activeElement
    const lost = !active || active === document.body || active.closest('aside') !== null
    if (!lost) return
    const target = window.matchMedia('(min-width: 1024px)').matches
      ? railToggleRef.current
      : hamburgerRef.current
    target?.focus()
  }, [sidebarCollapsed])

  const isActive = (path: string) => {
    return location.pathname === path
  }

  const SIDEBAR_EXPANDED_WIDTH = '16rem'  /* w-64 */
  const SIDEBAR_COLLAPSED_WIDTH = '5rem'   /* w-20 */

  return (
    <div className="flex h-dvh">
      {/* Mobile overlay backdrop — visible only when sidebar is open on small screens */}
      {!sidebarCollapsed && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={toggleSidebar}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed lg:static inset-y-0 left-0 z-40
          flex flex-col
          bg-base-200 text-base-content
          transition-all duration-300 ease-in-out
          h-full overflow-y-auto
          ${sidebarCollapsed ? '-translate-x-full lg:translate-x-0' : 'translate-x-0'}
        `}
        style={{
          width: sidebarCollapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_EXPANDED_WIDTH,
        }}
      >
        {/* Sidebar Header with Toggle */}
        <div className="flex items-center justify-between p-4 flex-shrink-0">
          {!sidebarCollapsed && (
            <Link to="/" className="text-xl font-bold">Navigation</Link>
          )}
          <div className="flex items-center gap-2 ml-auto">
            {/* WebSocket Bridge Status Indicator (2026-09-04: the
                native title -> a proper DAISYUI tooltip; the state
                readout rides the aria-label — the house rule). */}
            <span
              className={`tooltip tooltip-bottom inline-block w-2 h-2 rounded-full cursor-help ${
                isConnected ? 'bg-success' : 'bg-error'
              }`}
              data-tip={isConnected ? 'Bridge connected' : 'Bridge offline'}
              role="status"
              aria-label={isConnected ? 'WebSocket bridge connected' : 'WebSocket bridge disconnected'}
            />
            {/* THE CONTROL THAT BRINGS THE PANEL BACK — and where the caret goes
                when the panel is collapsed from inside it (see Layout's collapse
                effect). It stays rendered while the rail is collapsed, which is
                what makes it a landing place. */}
            <button
              ref={railToggleRef}
              onClick={toggleSidebar}
              className="btn btn-ghost btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
              title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                {sidebarCollapsed ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {/* THE ASK-EXA EXPANDER (2026-09-18) — P2 of the box redesign. The
            sidebar is mounted ONCE by the shell, so a section here is
            reachable from every page and its thread survives a navigation,
            which the per-page header mount could never do. It sits at the
            TOP of the sidebar, above the nav list: unrolled, the box is the
            longest thing here, and the top is where it reads without
            scrolling past the nav to find it. Below it, the nav <ul> keeps
            `flex-1 min-h-0` and takes the remaining height — so the nav
            scrolls and the box keeps its own bounded height. It rides the
            sidebar's collapse as the rest of the contents do: the icon rail
            is 5rem, where no panel is readable. That mount point is also why
            the app-wide Cmd/Ctrl+K lives in the shell (NavSearchHotkey) and not
            in the box's own hook: while the rail is collapsed this line
            renders NOTHING, so the shell's listener is what expands the rail,
            unrolls the section and leaves the caret in its input. */}
        {!sidebarCollapsed && <NavSearchSection />}

        {/* Navigation Menu */}
        <ul className="menu menu-vertical flex-nowrap p-4 pt-0 flex-1 w-full min-h-0">
          <li>
            <Link
              to="/"
              className={`flex items-center ${isActive('/') ? 'active' : ''}`}
              title="Dashboard"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
              </svg>
              {!sidebarCollapsed && <span className="ml-2">Dashboard</span>}
            </Link>
          </li>

          {!sidebarCollapsed && (
            <li>
              <details open>
                <summary>Agents</summary>
                <ul>
                  <li>
                    <Link
                      to="/agent-interaction"
                      className={isActive('/agent-interaction') ? 'active' : ''}
                    >
                      Agent Chat
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/agent-profiles"
                      className={isActive('/agent-profiles') ? 'active' : ''}
                    >
                      Agent Profiles
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/teams"
                      className={isActive('/teams') ? 'active' : ''}
                    >
                      Collectives
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/exa"
                      className={isActive('/exa') ? 'active' : ''}
                    >
                      Exa Agent
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/agent-integration"
                      className={isActive('/agent-integration') ? 'active' : ''}
                    >
                      Exa Config
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/sessions"
                      className={isActive('/sessions') ? 'active' : ''}
                    >
                      Sessions
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/agents/templates"
                      className={isActive('/agents/templates') ? 'active' : ''}
                    >
                      Templates
                    </Link>
                  </li>
                </ul>
              </details>
            </li>
          )}

          {!sidebarCollapsed && (
            <li>
              <details open>
                <summary>Workflows</summary>
                <ul>
                  <li>
                    <Link
                      to="/workflow-automation"
                      className={isActive('/workflow-automation') ? 'active' : ''}
                    >
                      Automation
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/workflow-execution"
                      className={isActive('/workflow-execution') ? 'active' : ''}
                    >
                      Execution
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/workflow-products"
                      className={isActive('/workflow-products') ? 'active' : ''}
                    >
                      Products
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/workflow-templates"
                      className={isActive('/workflow-templates') ? 'active' : ''}
                    >
                      Workflows
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/workflow-kinds"
                      className={isActive('/workflow-kinds') ? 'active' : ''}
                    >
                      Templates
                    </Link>
                  </li>
                </ul>
              </details>
            </li>
          )}

          {!sidebarCollapsed && (
            <li>
              {/* THE CONFIGURATION SECTION (2026-08-31, the _28
                  build — the user's config-nav): the config pages'
                  home — Speech + Notifications (moved out of the
                  Assets) + the System's placeholder (the Phase-5
                  roundup page). */}
              <details>
                <summary>Configuration</summary>
                <ul>
                  <li>
                    <Link
                      to="/macros"
                      className={isActive('/macros') ? 'active' : ''}
                    >
                      Macros
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/notifications-config"
                      className={isActive('/notifications-config') ? 'active' : ''}
                    >
                      Notifications
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/cognitive-pipeline"
                      className={isActive('/cognitive-pipeline') ? 'active' : ''}
                    >
                      Pipeline Config
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/providers/cloud"
                      className={isActive('/providers/cloud') ? 'active' : ''}
                    >
                      Cloud Providers
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/providers/local"
                      className={isActive('/providers/local') ? 'active' : ''}
                    >
                      Local Providers
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/providers/capabilities"
                      className={isActive('/providers/capabilities') ? 'active' : ''}
                    >
                      Capabilities
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/settings"
                      className={isActive('/settings') ? 'active' : ''}
                    >
                      Settings
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/speech"
                      className={isActive('/speech') ? 'active' : ''}
                    >
                      Speech
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/local-services"
                      className={isActive('/local-services') ? 'active' : ''}
                    >
                      Local Services
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/system-configs"
                      className={isActive('/system-configs') ? 'active' : ''}
                    >
                      System Configs
                    </Link>
                  </li>
                </ul>
              </details>
            </li>
          )}

          {!sidebarCollapsed && (
            <li>
              <details>
                <summary>Utilities</summary>
                <ul>
                  <li>
                    <Link
                      to="/setup"
                      className={isActive('/setup') ? 'active' : ''}
                    >
                      Setup
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/tools"
                      className={isActive('/tools') ? 'active' : ''}
                    >
                      Tool Management
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/toolkits"
                      className={isActive('/toolkits') ? 'active' : ''}
                    >
                      Toolkits
                    </Link>
                  </li>
                </ul>
              </details>
            </li>
          )}

          {!sidebarCollapsed && (
            <li>
              <details>
                <summary>Assets</summary>
                <ul>
                  <li>
                    <Link
                      to="/images"
                      className={isActive('/images') ? 'active' : ''}
                    >
                      Images
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/skills"
                      className={isActive('/skills') ? 'active' : ''}
                    >
                      Skills
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/sounds"
                      className={isActive('/sounds') ? 'active' : ''}
                    >
                      Sounds
                    </Link>
                  </li>
                </ul>
              </details>
            </li>
          )}

          {!sidebarCollapsed && (
            <li>
              <details>
                <summary>Development</summary>
                <ul>
                  <li>
                    <Link
                      to="/components"
                      className={isActive('/components') ? 'active' : ''}
                    >
                      Gallery
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/debugging"
                      className={isActive('/debugging') ? 'active' : ''}
                    >
                      Debugging
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/testing-dashboard"
                      className={isActive('/testing-dashboard') ? 'active' : ''}
                    >
                      Testing Dashboard
                    </Link>
                  </li>
                </ul>
              </details>
            </li>
          )}

          {!sidebarCollapsed && (
            <li>
              <details>
                <summary>System</summary>
                <ul>
                  <li>
                    <Link
                      to="/analytics"
                      className={isActive('/analytics') ? 'active' : ''}
                    >
                      Analytics
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/messages"
                      className={isActive('/messages') ? 'active' : ''}
                    >
                      Messages
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/history"
                      className={isActive('/history') ? 'active' : ''}
                    >
                      History
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/logs"
                      className={isActive('/logs') ? 'active' : ''}
                    >
                      Logs
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/rag-index"
                      className={isActive('/rag-index') ? 'active' : ''}
                    >
                      RAG Index
                    </Link>
                  </li>
                  <li>
                    <Link
                      to="/trash"
                      className={isActive('/trash') ? 'active' : ''}
                    >
                      Trash
                    </Link>
                  </li>
                </ul>
              </details>
            </li>
          )}
          <li>
            <Link
              to="/wiki"
              className={`flex items-center ${isActive('/wiki') || location.pathname.startsWith('/wiki') ? 'active' : ''}`}
              title="Wiki"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              {!sidebarCollapsed && <span className="ml-2">Wiki</span>}
            </Link>
          </li>

        </ul>
      </aside>

      {/* Main Content */}
      <div className="flex flex-col flex-1 min-w-0 h-dvh overflow-y-auto">
        {/* Mobile hamburger button — visible only on small screens */}
        <div className="lg:hidden p-4 flex-shrink-0">
          <button
            ref={hamburgerRef}
            onClick={toggleSidebar}
            className="btn btn-ghost rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
            title="Open sidebar"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        </div>

        {/* (the command widget does NOT live here. It rides the page's OWN
            header row — PageBanner's right side — because "vertical space is
            at a premium. it goes on the same line as the header if there is
            one." A bar in this column cost a whole row for one button; the
            user called it on 2026-09-15.) */}

        {/* Main Content Area.

            `tabIndex={-1}` IS THE HANDOFF'S LANDING PLACE (2026-09-19): a page that
            declares no primary input of its own still has to be able to RECEIVE the
            caret after a navigation the reader asked for (`claimPageFocus`,
            services/focusContract) — otherwise "jump to the page I just went to" has
            nowhere to land and the caret stays in the nav panel. Not a tab stop:
            `-1` means focusable by code, never by Tab, so the keyboard order is
            unchanged. */}
        <main className="flex-1 bg-base-200" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  )
}
/** The QueryClient-bound sync bridge (2026-08-24): useAgentSync
 * needs useQueryClient — it can only run INSIDE the QueryProvider.
 * Rendered as a child of the provider (no output — pure wiring). */
function AppSyncBridge() {
  useAgentSync()
  // THE CROSS-WINDOW SESSION SYNC (2026-08-25): the session events
  // converge every open tab's shared store.
  useSessionSync()
  // THE CROSS-WINDOW MACRO SYNC (2026-08-25, the roadmap Phase 5):
  // the macro + meta-topic events reload the shared macro store.
  useMacroSync()
  return null
}

function App() {
  // For now, we'll use default values since we don't have auth system
  const userPermissions = ['admin', 'config_manager', 'developer'];
  const isAuthenticated = true;

  // App-wide workflow-product toasts (ToastDistributor queue drain)
  useWorkflowToasts();
  useNotifyBridge();
  useCancellingNotice();

  // THE CROSS-TAB NOTIFY-RECEIVER (2026-08-29): the local errors
  // reach EVERY tab's message center!
  useEffect(() => {
    return enableCrossTabNotifyReceiver()
  }, [])
  // Load settings on app mount
  const loadSettings = useSettingsStore((state) => state.loadSettings);

  useEffect(() => {
    loadSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <HelmetProvider>
      <QueryProvider>
        <Router>
          <GlobalTheme />
          {/* THE APP-WIDE Cmd/Ctrl+K (2026-09-18) — mounted by the SHELL and
              never unmounted, because the box it opens lives in the nav
              sidebar's section, which is not rendered while the rail is
              collapsed: a listener inside that section could not answer the
              one case the key exists for. One listener, no output. */}
          <NavSearchHotkey />
          <CognitiveHubProvider>  {/* ← Cognitive Hub wraps the app */}
            <AppSyncBridge />
            <ScrollToTop />
            <FirstRunRedirect />
            <Layout>
              <Suspense fallback={<PageLoader />}>
                <Routes>
                  {routes.map((route) => {
                    return (
                      <Route
                        key={route.path}
                        path={route.path}
                        element={
                          <RouteGuard
                            route={route}
                            userPermissions={userPermissions}
                            isAuthenticated={isAuthenticated}
                          >
                            <route.component />
                          </RouteGuard>
                        }
                      />
                    );
                  })}
                </Routes>
              </Suspense>
            </Layout>
            <NotificationContainer />
            <HelpModal />
            <AgentPanel />
          </CognitiveHubProvider>
        </Router>
      </QueryProvider>
    </HelmetProvider>
  )
}

export default App
