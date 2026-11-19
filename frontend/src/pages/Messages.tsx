/**
 * Messages — the Message Center page (2026-08-25, the roadmap's
 * Phase 2). The collections-style table against the message store:
 * sortable columns (time / source / type / title / read), a filter
 * row, the checkbox bulk-select + the bulk delete.
 *
 * The Exa surface lives on its own page (/exa — the ported
 * Diagnose / timer-pickup / Force-Kill / activity-fold); this page
 * is the queue alone.
 */
import { useMemo, useRef, useState, useEffect } from 'react'
import {
  useMessageStore,
  selectUnreadCount,
  type SystemMessage,
} from '../stores/messageStore'
import { Trash2 } from 'lucide-react'
import { usePageTitle } from '../hooks/usePageTitle'
import { notificationConfigService } from '../services/domain/notificationConfigService'
import { claimDeclaredPrimaryInput } from '../services/focusContract'
import { frontendLoggingService } from '../services/frontendLoggingService'
import { PageBanner } from '../components/ui/PageBanner'
import { PageContainer } from '../components/ui/PageContainer'

// THE CLEAR-ALL EMPHASIS (2026-09-05, the ui-loudness pilot): the
// destructive-but-recoverable act — FILLED (solid caution) or
// QUIET (bordered caution). THE USER'S VERDICT: BORDERED (the
// page keeps ONE solid fill — Full Test; Clear all reads as
// amber-outlined). A future 'high-contrast controls' user
// preference would drive this from the Settings schema instead
// of this constant.
const CLEAR_ALL_STYLE = 'btn btn-caution btn-outline btn-sm rounded-full'
import { HelpButton } from '../components/help/HelpButton'
import { ExaPromptFlyout } from '../components/features/agentInteraction/ExaPromptFlyout'

type SortKey = 'timestamp' | 'source' | 'type' | 'title' | 'read'
type TypeFilter = 'all' | 'info' | 'success' | 'warning' | 'error'

function fmtTime(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit', // 2026-09-05: the center test's messages land
    // seconds apart — minute-resolution made them indistinguishable
    hour12: true,
  })
}

const TYPE_BADGE: Record<string, string> = {
  info: 'badge-info',
  success: 'badge-success',
  warning: 'badge-warning',
  error: 'badge-error',
}

export default function Messages() {
  usePageTitle('Messages', 'The system message queue — view, filter, and manage the notifications')
  const messages = useMessageStore((s) => s.messages)
  const unreadCount = useMessageStore(selectUnreadCount)
  const markAllRead = useMessageStore((s) => s.markAllRead)
  const deleteMessages = useMessageStore((s) => s.deleteMessages)
  const clearAll = useMessageStore((s) => s.clearAll)
  const [sortKey, setSortKey] = useState<SortKey>('timestamp')
  const [sortDesc, setSortDesc] = useState(true)
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all')
  const [sourceFilter, setSourceFilter] = useState<string>('all')
  // THE TIME-RANGE FILTER (2026-09-05, the user's ask): last hour /
  // 6 hours / day / week / month — the table narrows to that window.
  type TimeRange = 'all' | '5m' | '20m' | '1h' | '6h' | '24h'
  const [timeRange, setTimeRange] = useState<TimeRange>('all')
  // THE READ-STATE FILTER (2026-09-05, the user's ask): All /
  // Unread / Read — gives the read state a job in the table.
  type ReadFilter = 'all' | 'unread' | 'read'
  const [readFilter, setReadFilter] = useState<ReadFilter>('all')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  // THE VIEW MODAL (2026-08-25, the user's ask): the truncated
  // rows can't show the full message — the row click opens the
  // modal (the sessions-modal pattern).
  const [viewing, setViewing] = useState<SystemMessage | null>(null)
  // THE MODAL COPY (2026-08-25, the user's ask): copy the message
  // info to the clipboard — the title, the meta, the full text.
  const [copied, setCopied] = useState(false)
  const handleCopyMessage = async (m: SystemMessage) => {
    try {
      // THE IDS (2026-08-29, the user's ask): the copied text opens
      // with the message id + the bus event id — unambiguous which
      // message is being referenced.
      const ids = [m.id, m.eventId ? `event: ${m.eventId}` : null].filter(Boolean).join(' · ')
      await navigator.clipboard.writeText(
        `${ids}\n${m.title}\n${m.type} | source: ${m.source} | ${fmtTime(m.timestamp)}\n\n${m.message}`,
      )
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1200)
    } catch {
      // the clipboard can be denied — no fuss
    }
  }
  const sources = useMemo(
    () => Array.from(new Set(messages.map((m) => m.source))).sort(),
    [messages],
  )
  // THE TEST BUTTON (2026-09-05, the user's ask): fire the REAL
  // notification chain — the SSE carries the event to every open
  // tab; the bridge toasts it + the center records it. The type
  // picker exercises the filters + the toast styling.
  // THE DELIVERY ECHO (2026-09-05, the user's 'nope not working'):
  // the POST returning ok only proves the SEND side — the button now
  // watches for the event to COME BACK (the center record) and names
  // the broken link when it doesn't. No silent failures in the test
  // itself either.
  const [testType, setTestType] = useState<TypeFilter>('warning')
  const [sendingTest, setSendingTest] = useState(false)
  const [testError, setTestError] = useState<string | null>(null)
  const [testEcho, setTestEcho] = useState<'delivered' | 'undelivered' | null>(null)
  const [hiddenWarn, setHiddenWarn] = useState(false)
  const testWatchRef = useRef<number | null>(null)
  const testTitleRef = useRef('')
  // THE RACE FIX (2026-09-05): the SSE delivery can BEAT the POST's
  // HTTP response back to the tab (the persistent stream vs a fresh
  // round-trip) — a watch armed only AFTER the await misses the
  // landing. The pending flag arms BEFORE the send + the listener
  // accepts a landing whenever the flag is set.
  const testPendingRef = useRef(false)

  /**
   * THE PAGE'S OWN HALF OF THE FOCUS CONTRACT (2026-09-19). The search field below
   * declares itself the primary input (`data-autofocus`), and a declaration nobody
   * ACTS on leaves the caret wherever the standing Search box put it — which is
   * what a cold load of this page did: the route is lazy, so this page mounts
   * AFTER the shell's arrival effect has already run and found no declaration to
   * yield to. See services/focusContract.
   */
  useEffect(() => {
    claimDeclaredPrimaryInput();
  }, []);

  useEffect(() => {
    // the delivery watch: the arriving center entry (matched by the
    // exact sent title) proves the round-trip — bus → this tab
    const unsubscribe = useMessageStore.subscribe((state, prev) => {
      if (testTitleRef.current && testPendingRef.current && state.messages !== prev.messages) {
        const landed = state.messages.some((m) => m.title === testTitleRef.current)
        if (landed) {
          testPendingRef.current = false
          if (testWatchRef.current !== null) {
            window.clearTimeout(testWatchRef.current)
            testWatchRef.current = null
          }
          setTestEcho('delivered')
        }
      }
    })
    return unsubscribe
  }, [])

  const handleSendTest = async () => {
    try {
      setSendingTest(true)
      setTestError(null)
      setTestEcho(null)
      setHiddenWarn(document.visibilityState === 'hidden')
      const title = `Test ${testType} — ${fmtTime(Date.now())}`
      testTitleRef.current = title
      // the watch arms BEFORE the send — the delivery may arrive
      // before the POST's response does
      testPendingRef.current = true
      // THE VISIBLE-TIME WINDOW (2026-09-05): a hidden tab's stream
      // throttles — the watch must not expire while hidden. Only
      // visible milliseconds count toward the 5s budget.
      const echoStart = performance.now()
      let echoVisibleMs = 0
      let echoLastTick = echoStart
      const echoInterval = window.setInterval(() => {
        const now = performance.now()
        if (document.visibilityState === 'visible') {
          echoVisibleMs += now - echoLastTick
        }
        echoLastTick = now
        if (echoVisibleMs >= 5000) {
          window.clearInterval(echoInterval)
          testWatchRef.current = null
          testPendingRef.current = false
          // THE FINAL RE-CHECK: a LATE arrival is delivered, not failed
          const landed = useMessageStore
            .getState()
            .messages.some((m) => m.title === testTitleRef.current)
          setTestEcho(landed ? 'delivered' : 'undelivered')
        }
      }, 200)
      testWatchRef.current = echoInterval as unknown as number
      await notificationConfigService.sendTest({
        title,
        message:
          'The message-center test button — if you can read this in the center, the whole chain works (bus → SSE → bridge → toast + record).',
        type: testType === 'all' ? 'info' : testType,
      })
    } catch {
      // the chain under test may be what's broken — an INLINE note,
      // not a toast (a toast about the toasts would confuse)
      testPendingRef.current = false
      if (testWatchRef.current !== null) {
        window.clearTimeout(testWatchRef.current)
        testWatchRef.current = null
      }
      setTestError('Send failed — is the backend reachable?')
    } finally {
      setSendingTest(false)
    }
  }

  // ==== THE FULL CENTER TEST (2026-09-05, the user's ask) ====
  // Starting warning → one message per class (~1.5s apart) → every
  // arrival verified against the center → a PASSED/FAILED verdict
  // message → every step logged through the funnel (the Logs page).
  const TEST_CLASSES = ['info', 'success', 'warning', 'error'] as const

  interface TestStep {
    type: string
    title: string
    ok: boolean
    delayMs: number | null
  }

  const [centerTest, setCenterTest] = useState<{
    status: 'idle' | 'running' | 'passed' | 'failed'
    steps: TestStep[]
  }>({ status: 'idle', steps: [] })
  const runIdRef = useRef('')
  const testRunRef = useRef<boolean>(false)

  // THE VISIBLE-TIME WINDOW (2026-09-05, the backgrounded-tab
  // false-failure): a hidden tab's event stream is browser-throttled
  // — deliveries can stall for minutes. The arrival window must NOT
  // burn down while the tab is hidden: only visible milliseconds
  // count toward the budget. The moment the user returns, the stream
  // catches up + the delivery lands (or the budget finishes).
  const waitForArrival = (title: string, visibleBudgetMs: number) =>
    new Promise<boolean>((resolve) => {
      if (useMessageStore.getState().messages.some((m) => m.title === title)) {
        resolve(true)
        return
      }
      let done = false
      let visibleMs = 0
      let lastTick = performance.now()
      const finish = (ok: boolean) => {
        if (done) return
        done = true
        window.clearInterval(interval)
        unsub()
        resolve(ok)
      }
      const unsub = useMessageStore.subscribe((state) => {
        if (state.messages.some((m) => m.title === title)) finish(true)
      })
      const interval = window.setInterval(() => {
        const now = performance.now()
        if (document.visibilityState === 'visible') {
          visibleMs += now - lastTick
        }
        lastTick = now
        if (visibleMs >= visibleBudgetMs) finish(false)
      }, 200)
    })

  const runCenterTest = async () => {
    if (testRunRef.current) return
    testRunRef.current = true
    setTestEcho(null)
    setTestError(null)
    setHiddenWarn(document.visibilityState === 'hidden')
    const runId = Date.now().toString(36).slice(-5)
    runIdRef.current = runId
    const steps: TestStep[] = []
    const push = (step: TestStep) => {
      steps.push(step)
      setCenterTest({ status: 'running', steps: [...steps] })
    }
    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))
    const sendAndVerify = async (
      type: 'info' | 'success' | 'warning' | 'error',
      label: string,
      message: string,
    ): Promise<TestStep> => {
      const title = `${label} — ${runId}`
      const t0 = performance.now()
      try {
        await notificationConfigService.sendTest({ title, message, type })
      } catch {
        const step: TestStep = { type, title, ok: false, delayMs: null }
        push(step)
        frontendLoggingService.error('message-center-test', `SEND FAILED — ${type}: ${title}`, { runId })
        return step
      }
      const ok = await waitForArrival(title, 4000)
      const step: TestStep = { type, title, ok, delayMs: Math.round(performance.now() - t0) }
      push(step)
      if (ok) {
        frontendLoggingService.info('message-center-test', `delivered ${type}: ${title} (${step.delayMs}ms round-trip)`, { runId })
      } else {
        frontendLoggingService.error('message-center-test', `NOT DELIVERED — ${type}: ${title} (the send-side ok, no center record)`, { runId })
      }
      return step
    }

    // 1. the starting warning
    await sendAndVerify(
      'warning',
      'Starting message center test',
      'The full center test is starting — every class goes over the real bus and must arrive in the center.',
    )
    await sleep(1500)
    // 2. one per class
    for (const cls of TEST_CLASSES) {
      await sendAndVerify(cls, `Test ${cls} message`, `The ${cls} class over the real bus — watch for its toast.`)
      await sleep(1500)
    }
    // 3. the verdict
    const missing = steps.filter((s) => !s.ok)
    if (missing.length === 0) {
      await sendAndVerify(
        'success',
        'Message center test PASSED',
        `All ${steps.length} messages arrived in the center. The full chain works.`,
      )
      frontendLoggingService.info('message-center-test', `VERDICT: PASSED — all ${steps.length} messages delivered`, { runId })
      setCenterTest({ status: 'passed', steps: [...steps] })
    } else {
      const list = missing.map((s) => `${s.type} ("${s.title}")`).join(', ')
      await sendAndVerify(
        'error',
        'Message center test FAILED',
        `${missing.length} of ${steps.length} messages never arrived: ${list}.`,
      )
      frontendLoggingService.error('message-center-test', `VERDICT: FAILED — missing ${missing.length}/${steps.length}: ${list}`, { runId })
      setCenterTest({ status: 'failed', steps: [...steps] })
    }
    testRunRef.current = false
  }

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    const rangeMs: Record<TimeRange, number> = {
      all: 0,
      '5m': 5 * 60e3,
      '20m': 20 * 60e3,
      '1h': 60 * 60e3,
      '6h': 6 * 60 * 60e3,
      '24h': 24 * 60 * 60e3,
    }
    const cutoff = rangeMs[timeRange] ? Date.now() - rangeMs[timeRange] : 0
    let rows = messages.filter((m) => {
      if (typeFilter !== 'all' && m.type !== typeFilter) return false
      if (sourceFilter !== 'all' && m.source !== sourceFilter) return false
      if (readFilter === 'unread' && m.read) return false
      if (readFilter === 'read' && !m.read) return false
      if (cutoff && m.timestamp < cutoff) return false
      if (q && !(m.title.toLowerCase().includes(q) || m.message.toLowerCase().includes(q))) return false
      return true
    })
    rows = [...rows].sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      const cmp = typeof av === 'string' && typeof bv === 'string'
        ? av.localeCompare(bv)
        : (av as number) - (bv as number)
      return sortDesc ? -cmp : cmp
    })
    return rows
  }, [messages, typeFilter, sourceFilter, timeRange, readFilter, search, sortKey, sortDesc])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDesc((d) => !d)
    } else {
      setSortKey(key)
      setSortDesc(key === 'timestamp' ? true : false)
    }
  }

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    setSelected((prev) =>
      prev.size === filtered.length && filtered.length > 0
        ? new Set()
        : new Set(filtered.map((m) => m.id)),
    )
  }

  const handleBulkDelete = () => {
    deleteMessages(Array.from(selected))
    setSelected(new Set())
  }

  const sortArrow = (key: SortKey) =>
    sortKey === key ? (sortDesc ? ' ↓' : ' ↑') : ''

  return (
    <PageContainer className="msg-center-surface space-y-4">
      {/* THE HEADER (2026-09-05, the user's ask): the banner + the
           Help button ONLY — every other control moved out (the test
           controls into the expander below; the table controls into
           the row under it). */}
      <div className="flex items-center justify-between mb-1">
        {/* hideCommand + a page-seated pill: inside this justify-between row
            PageBanner shrinks to its content, which lands the pill beside the
            TITLE at the page's left edge — and the flyout panel opens leftward
            (absolute right-0, 440px), so it would run under the nav panel. */}
        <PageBanner
          title="Message Center"
          tooltip="The system message queue — the notifications from the bus and the local errors"
          hideCommand
        />
        <div className="flex items-center gap-2">
          <ExaPromptFlyout />
          <HelpButton context="messages" tooltipPosition="bottom" />
        </div>
      </div>

      {/* THE TEST SECTION (2026-09-05, the user's ask): the
          test-related controls live in an expander — out of the
          header, collapsed by default. */}
      <div className="collapse collapse-arrow bg-base-200/60 rounded-box">
        <input type="checkbox" className="min-h-0" aria-label="Toggle the messaging test center" />
        <div className="collapse-title text-sm font-medium min-h-0 py-2.5">
          Messaging Test Center
        </div>
        <div className="collapse-content">
          <div className="flex items-center gap-2 flex-wrap pt-1 pb-4">
            <div className="tooltip tooltip-top" data-tip="Run the full message-center test"><button
              className="btn btn-primary btn-sm rounded-full"
              onClick={runCenterTest}
              disabled={testRunRef.current}
            >
              {testRunRef.current
                ? `Running… ${centerTest.steps.length}/6`
                : 'Full Test'}
            </button></div>
            <div className="tooltip tooltip-top" data-tip="Send one message of the chosen type"><button
              className="btn btn-outline btn-sm rounded-full"
              onClick={handleSendTest}
              disabled={sendingTest}
            >
              {sendingTest ? 'Sending…' : 'Single message'}
            </button></div>
            {/* THE TYPE PICKER (2026-09-05, the user's ask): AFTER the
                Single message button. */}
            <div className="tooltip tooltip-top" data-tip="Type of the single test message"><select
              className="select select-sm select-bordered max-w-[6.5rem]"
              value={testType}
              onChange={(e) => setTestType(e.target.value as TypeFilter)}
              aria-label="Single message type"
            >
              <option value="info">Info</option>
              <option value="success">Success</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
            </select></div>
          </div>
          {(testError || testEcho || hiddenWarn) && (
            <div className="flex items-center gap-3 flex-wrap text-xs px-1 pb-1">
              {testError && <span className="text-error">{testError}</span>}
              {testEcho === 'delivered' && (
                <span className="text-success flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Delivered — the chain works
                </span>
              )}
              {testEcho === 'undelivered' && (
                <span className="text-error">
                  Sent, but nothing came back — this tab's event stream
                  (SSE) is disconnected. A page reload re-establishes it.
                  (The sidebar's bridge dot is a DIFFERENT channel — it
                  can be green while the event stream is down.)
                </span>
              )}
              {hiddenWarn && (
                <span className="text-warning">
                  ⚠ The tab was hidden when the message was sent —
                  background tabs throttle the event stream. Keep this
                  tab visible, or the arrival may stall.
                </span>
              )}
            </div>
          )}
          {/* THE CENTER-TEST RUN PANEL (2026-09-05): the live step
              chips + the verdict — INSIDE the test expander (the
              user's ask). The full per-step detail lives in the
              Logs page (the funnel — every step is logged). */}
          {centerTest.status !== 'idle' && (
            <div
              className={`alert ${
                centerTest.status === 'failed'
                  ? 'alert-error'
                  : centerTest.status === 'passed'
                    ? 'alert-success'
                    : 'alert-info'
              } py-2 px-3 shadow-none`}
            >
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-3 flex-wrap text-sm">
            <span className="font-medium">
              {centerTest.status === 'running' && `Center test running — ${centerTest.steps.length}/6`}
              {centerTest.status === 'passed' && `PASSED — all ${centerTest.steps.length} messages delivered`}
              {centerTest.status === 'failed' && (
                <>FAILED — {centerTest.steps.filter((s) => !s.ok).length} message(s) never arrived</>
              )}
            </span>
            <span className="flex items-center gap-1.5 flex-wrap">
              {centerTest.steps.map((s, i) => (
                <span
                  key={`${s.title}-${i}`}
                  className={`badge badge-sm gap-1 ${s.ok ? 'badge-success' : 'badge-error'}`}
                >
                  {s.ok ? '✓' : '✗'} {s.type}
                </span>
              ))}
            </span>
            {centerTest.status !== 'running' && (
              <div className="tooltip tooltip-top" data-tip="Dismiss this result panel"><button
                className="btn btn-outline btn-xs rounded-full"
                onClick={() => setCenterTest({ status: 'idle', steps: [] })}
              >
                Dismiss
              </button></div>
            )}
            </div>
            {/* THE FILTER-HIDDEN NOTE (2026-09-05, the user's filter
                discovery): the messages may have ARRIVED while the
                page filters hide them from the table — the panel
                says so instead of leaving the user confused. */}
            {centerTest.status !== 'running' && (() => {
              const q = search.trim().toLowerCase()
              const hidden = centerTest.steps.filter((s) => {
                if (typeFilter !== 'all' && s.type !== typeFilter) return true
                if (q && !s.title.toLowerCase().includes(q)) return true
                return false
              })
              if (hidden.length === 0) return null
              return (
                <span className="text-warning text-xs w-full">
                  Note: {hidden.length} of the test messages ({hidden.map((s) => s.type).join(', ')}) are
                  hidden by the current filters — set the type filter
                  to All types or clear the search to see them.
                </span>
              )
            })()}
          </div>
            </div>
          )}
        </div>
      </div>

      {/* THE TABLE CONTROLS ROW (2026-09-05, the user's ask): the
          filters + the table-level actions on ONE row — below the
          test expander. */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="tooltip tooltip-bottom" data-tip="Search the titles and messages"><input
          data-autofocus
          className="input input-bordered input-sm w-56"
          placeholder="Search title or message..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search messages"
        /></div>
        <div className="tooltip tooltip-bottom" data-tip="Filter the table by message type"><select
          className="select select-bordered select-sm max-w-[7.5rem]"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as TypeFilter)}
          aria-label="Filter by type"
        >
          <option value="all">All types</option>
          <option value="info">Info</option>
          <option value="success">Success</option>
          <option value="warning">Warning</option>
          <option value="error">Error</option>
        </select></div>
        <div className="tooltip tooltip-bottom" data-tip="Filter by source (who sent it)">
          <select
            className="select select-bordered select-sm max-w-[8rem]"
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            aria-label="Filter by source"
          >
            <option value="all">All sources</option>
            {sources.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        {/* THE TIME RANGE (2026-09-05, the user's ask): the table
            narrows to the window. */}
        <div className="tooltip tooltip-bottom" data-tip="Show messages from the last…"><select
          className="select select-bordered select-sm"
          value={timeRange}
          onChange={(e) => setTimeRange(e.target.value as TimeRange)}
          aria-label="Filter by time range"
        >
          <option value="all">All time</option>
          <option value="5m">Last 5 minutes</option>
          <option value="20m">Last 20 minutes</option>
          <option value="1h">Last hour</option>
          <option value="6h">Last 6 hours</option>
          <option value="24h">Last day</option>
        </select></div>
        <div className="tooltip tooltip-bottom" data-tip="Show only unread or read messages"><select
          className="select select-bordered select-sm max-w-[7rem]"
          value={readFilter}
          onChange={(e) => setReadFilter(e.target.value as ReadFilter)}
          aria-label="Filter by read state"
        >
          <option value="all">All states</option>
          <option value="unread">Unread</option>
          <option value="read">Read</option>
        </select></div>
        {/* THE COUNTS (2026-09-05): moved off the banner; badges now
            (the user's ask — the unread badge matches the app's
            badge-error convention, the total rides an outline). */}
        <div className="ml-3 flex items-center gap-1.5 whitespace-nowrap">
          {unreadCount > 0 && (
            <span className="badge badge-error badge-sm">{unreadCount} unread</span>
          )}
          <span className={`badge badge-sm ${unreadCount > 0 ? 'badge-outline' : 'badge-ghost'}`}>
            {messages.length} {messages.length === 1 ? 'message' : 'messages'}
          </span>
        </div>
        <div className="flex-1" />
        <div className="tooltip tooltip-bottom" data-tip="Mark every message as read"><button
          className="btn btn-primary btn-outline btn-sm rounded-full"
          onClick={markAllRead}
          disabled={unreadCount === 0}
        >
          Mark all read
        </button></div>
        <div className="tooltip tooltip-bottom" data-tip="Clear all messages from the center"><button
          className={CLEAR_ALL_STYLE}
          onClick={clearAll}
          disabled={messages.length === 0}
        >
          <Trash2 className="w-3.5 h-3.5" />
          Clear all
        </button></div>
        {selected.size > 0 && (
          <div className="tooltip tooltip-bottom" data-tip="Delete the selected messages"><button
            className="btn btn-error btn-sm rounded-full"
            onClick={handleBulkDelete}
          >
            Delete {selected.size} selected
          </button></div>
        )}
      </div>

      {/* The table */}
      <div className="card bg-base-200 shadow-sm">
        <div className="card-body p-3">
          {filtered.length === 0 ? (
            <div className="text-center py-8 text-readout text-sm">
              {messages.length === 0
                ? 'No messages yet — the system notifications land here.'
                : 'No messages match the filters.'}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="table table-sm">
                <thead>
                  <tr className="text-xs">
                    <th className="w-8">
                      <div className="tooltip tooltip-bottom" data-tip="Select all visible messages"><input
                        type="checkbox"
                        className="checkbox checkbox-sm checkbox-primary"
                        checked={selected.size === filtered.length && filtered.length > 0}
                        onChange={toggleSelectAll}
                        aria-label="Select all"
                      /></div>
                    </th>
                    <th>
                      <div className="tooltip tooltip-bottom" data-tip="Sort by title"><button className="btn btn-ghost btn-xs" onClick={() => toggleSort('title')}>
                        Title{sortArrow('title')}
                      </button></div>
                    </th>
                    <th>
                      <div className="tooltip tooltip-bottom" data-tip="Sort by type"><button className="btn btn-ghost btn-xs" onClick={() => toggleSort('type')}>
                        Type{sortArrow('type')}
                      </button></div>
                    </th>
                    <th>
                      <div className="tooltip tooltip-bottom" data-tip="Sort by time (newest first)"><button className="btn btn-ghost btn-xs" onClick={() => toggleSort('timestamp')}>
                        Time{sortArrow('timestamp')}
                      </button></div>
                    </th>
                    <th>
                      <div className="tooltip tooltip-bottom" data-tip="Sort by source"><button className="btn btn-ghost btn-xs" onClick={() => toggleSort('source')}>
                        Source{sortArrow('source')}
                      </button></div>
                    </th>

                    <th>
                      <div className="tooltip tooltip-bottom" data-tip="Sort by read state"><button className="btn btn-ghost btn-xs" onClick={() => toggleSort('read')}>
                        Read{sortArrow('read')}
                      </button></div>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((m: SystemMessage) => (
                    <tr key={m.id} className={m.read ? 'opacity-60' : ''}>
                      <td>
                        <div className="tooltip tooltip-bottom" data-tip="Select this message"><input
                          type="checkbox"
                          className="checkbox checkbox-sm checkbox-primary"
                          checked={selected.has(m.id)}
                          onChange={() => toggleSelect(m.id)}
                          aria-label={`Select ${m.title}`}
                        /></div>
                      </td>
                      <td className="text-sm font-medium">{m.title}</td>
                      <td>
                        <span className={`badge badge-xs ${TYPE_BADGE[m.type] ?? 'badge-ghost'}`}>
                          {m.type}
                        </span>
                      </td>
                      <td className="text-xs whitespace-nowrap">{fmtTime(m.timestamp)}</td>
                      <td className="text-xs">{m.source}</td>

                      <td>
                        {/* THE VIEW BADGE (2026-09-05, the user's ask):
                            the 'new'/'read' texts are gone — the row
                            dimming + the time tell the story. */}
                        <div className="tooltip tooltip-bottom" data-tip="Open the full message"><button
                          className="badge badge-ghost badge-sm gap-1 cursor-pointer hover:bg-base-300 transition-colors"
                          onClick={() => setViewing(m)}
                          aria-label={`View ${m.title}`}
                        >
                          View
                        </button></div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* THE VIEW MODAL (the sessions-modal pattern) */}
      {viewing && (
        <div className="modal modal-open" onClick={() => setViewing(null)}>
          <div className="modal-box max-w-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-semibold">{viewing.title}</h3>
              <div className="tooltip tooltip-bottom" data-tip="Close"><button className="btn btn-ghost btn-sm" onClick={() => setViewing(null)} aria-label="Close message">
                ✕
              </button></div>
            </div>
            <div className="flex items-center gap-2 text-xs text-readout mb-3 flex-wrap">
              <span className="font-mono">{viewing.id}</span>
              {viewing.eventId && <span className="font-mono">event: {viewing.eventId}</span>}
              <span className={`badge badge-xs ${TYPE_BADGE[viewing.type] ?? 'badge-ghost'}`}>{viewing.type}</span>
              <span>source: {viewing.source}</span>
              <span>{fmtTime(viewing.timestamp)}</span>
            </div>
            <p className="text-sm whitespace-pre-wrap">{viewing.message}</p>
            <div className="modal-action">
              <div className="tooltip tooltip-bottom" data-tip="Copy the message text">
                <button className="btn btn-ghost btn-sm" onClick={() => handleCopyMessage(viewing)}>
                  {copied ? '✓ Copied' : 'Copy'}
                </button>
              </div>
              <div className="tooltip tooltip-bottom" data-tip="Close without copying">
                <button className="btn btn-ghost btn-sm" onClick={() => setViewing(null)}>Close</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  )
}
