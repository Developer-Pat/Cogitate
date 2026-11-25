import { useCallback, useMemo, useState, useEffect, useRef } from 'react'
import { ErrorBoundary } from '../components/ErrorBoundary'
import { HelpButton } from '../components/help'
import ResponseStream from '../components/features/agentInteraction/ResponseStream'
import ChatInterface from '../components/features/agentInteraction/ChatInterface'
import SessionManager from '../components/features/agentInteraction/SessionManager'
import CognitiveTraceDebugOverlay from '../components/features/agentInteraction/CognitiveTraceDebugOverlay'
import { usePageTitle } from '../hooks/usePageTitle'
import { uuidv4 } from '../utils/uuid'
import { useTracePanel } from '../hooks/useTracePanel'
import { useMessageStore, selectUnreadCount } from '../stores/messageStore'
import { useNotificationStore } from '../stores/notificationStore'
import { getExternalAgentConfig, getExternalAgentStatus, activateExa, updateExaModel, modelAskFrom } from '../services/externalAgentService'
import ExaModelAskDialog, { type ExaModelOffer } from '../components/features/exa/ExaModelAskDialog'
import { SessionService } from '../services/domain/SessionService'
import { SessionSource } from '../services/sessionSyncService'
import { navigateTo } from '../services/crossTab/navigationService'
import { addTopics, removeTopics } from '../services/messagingFeed'
import { eventBus } from '../services/eventBus'
import { titleService } from '../services/domain/TitleService'
import { resolveTitleModel } from '../utils/titleModelResolver'
import { EXA_SESSION_PLACEHOLDER } from '../utils/sessionTitles'
import { useSettingsStore } from '../stores/settingsStore'
import { consumeSwapRequest, peekSwapRequest } from '../services/domains/providers/swapHandoff'
import { frontendLoggingService } from '../services/frontendLoggingService'
import type { ConversationMessage, ConversationSession } from '../types/agentInteraction'
import { ttsService } from '../services/ttsService'
import { ttsConfigService } from '../services/domain/ttsConfigService'
import { backoffDelay, shouldReconnectOnClose } from '../services/exaSocketPolicy'

// THE WS-PROTOCOL (step 1.4 — the first-class stream): the
// /external-agent/ws events (the AgentPanel's protocol — the local
// copy of the WsMessage shape).
interface WsMessage {
  type: 'status' | 'message' | 'thought' | 'tool_call' | 'done'
  status?: string
  message?: string
  text?: string
  reply?: string
  sessionId?: string
  update?: { kind?: string; title?: string; locations?: { path?: string }[] }
  [key: string]: unknown
}

export default function ExaChat() {
  usePageTitle('Exa Agent', 'Chat with Exa — the system agent')

  const sessionService = useMemo(() => new SessionService(), [])

  const unreadCount = useMessageStore(selectUnreadCount)

  // THE EXA FACE: the config's image-setting (the Exa Config page!)
  const [exaImage, setExaImage] = useState('')
  // THE ACTIVATION (2026-11-18): null = not asked yet. `false` = the backend
  // says Exa is switched off, and NOTHING typed here may reach it.
  const [exaActive, setExaActive] = useState<boolean | null>(null)
  const [exaBlockedReason, setExaBlockedReason] = useState<string | null>(null)
  const [activating, setActivating] = useState(false)
  // THE MODEL ASK (2026-11-22, measured on the release run): activation provisions Exa's home, and a
  // home with NO model does not answer at all — the first turn came back as an opaque
  // `RequestError: Internal error` while the toast said "say something to wake it up". The
  // integrations page asked this question; this page did not, and this page is the door the
  // readiness verdict links to. One dialog component, both doors.
  const [modelAsk, setModelAsk] = useState<ExaModelOffer | null>(null)
  const [savingModel, setSavingModel] = useState(false)
  useEffect(() => {
    getExternalAgentConfig()
      .then(cfg => setExaImage(cfg.image || ''))
      .catch(() => setExaImage(''))
    getExternalAgentStatus()
      .then((st) => {
        setExaActive(st.enabled)
        setExaBlockedReason(st.blocked_reason ?? null)
      })
      .catch(() => setExaActive(null))
  }, [])

  // THE PAGE'S OWN SESSION-STATE (step 1.4 — the first-class!):
  // the page owns its session + messages — the store's OUT (no
  // agent-chat's churn!). The backend's the source-of-truth.


  const [exaSessionId, setExaSessionId] = useState<string | null>(null)
  // THE SESSION REF (2026-09-04, the S1 review fix): persistMessage
  // reads the id from a REF so its identity stays STABLE — the ws
  // effect (deps [persistMessage]) binds ONCE instead of closing +
  // reconnecting on every session switch (the old behavior dropped
  // the socket and disabled the input for the reconnect gap).
  const exaSessionIdRef = useRef<string | null>(null)
  useEffect(() => {
    exaSessionIdRef.current = exaSessionId
  }, [exaSessionId])
  // THE SESSIONS PANEL (2026-09-04, the Exa-panel B — P2): the
  // collapsible right sidebar mirrors the agent page's; the list
  // holds the source='exa' sessions (the agent page's are filtered
  // out server-side).
  const [exaSidebarOpen, setExaSidebarOpen] = useState(false)
  const [exaSessions, setExaSessions] = useState<ConversationSession[]>([])
  const [isLoadingExaSessions, setIsLoadingExaSessions] = useState(false)
  // THE SESSION LIST LOADER: refresh the panel's list from the
  // server (source-scoped to the exa surface).
  const refreshExaSessions = useCallback(async () => {
    try {
      setIsLoadingExaSessions(true)
      const list = await sessionService.loadSessions(SessionSource.EXA)
      setExaSessions(list)
    } catch (e) {
      frontendLoggingService.error('ExaChat', 'Failed to load exa sessions', e)
    } finally {
      setIsLoadingExaSessions(false)
    }
  }, [sessionService])

  // THE BUBBLE PERSISTENCE (2026-08-30, the user's reload-clears-
  // the-bubbles): the page's OWN localStorage — the same-tab reload
  // restores the conversation. The page never saved its messages
  // (the backend session stayed empty!) — the bubbles now ride the
  // localStorage; the backend's session messages only FILL THE VOID
  // (the local state is the truth — no clobbering). The last-writer
  // wins across tabs (the tabs are independent per the doctrine).
  const BUBBLES_KEY = 'exa-chat-bubbles'
  const [exaMessages, setExaMessages] = useState<ConversationMessage[]>(() => {
    try {
      const raw = sessionStorage.getItem(BUBBLES_KEY)
      return raw ? (JSON.parse(raw) as ConversationMessage[]) : []
    } catch {
      return []
    }
  })
  useEffect(() => {
    try {
      sessionStorage.setItem(BUBBLES_KEY, JSON.stringify(exaMessages))
    } catch {
      // the storage quota — the conversation stays in-memory
    }
  }, [exaMessages])
  // THE MESSAGES REF (2026-09-04, the chat-audio rework P3): the ws
  // effect binds ONCE (a stale exaMessages closure!) — the auto-read
  // needs the reply's bubble id, so a ref mirrors the messages.
  const exaMessagesRef = useRef<ConversationMessage[]>(exaMessages)
  useEffect(() => {
    exaMessagesRef.current = exaMessages
  }, [exaMessages])
  // THE TIMER PICKUP (the panel-port): a confirmable hand-off — the
  // timer fired; the user sends or discards it (NO auto-fire!).
  const [pendingPickup, setPendingPickup] = useState<{ id: string; text: string; label: string } | null>(null)
  // THE FORCE-KILL CONFIRM (the panel-port): two-click — a stray
  // click can't nuke a working agent.
  const [confirmNuke, setConfirmNuke] = useState(false)
  const autoSessionDoneRef = useRef(false)
  // THE AUTO-TITLE GUARD (2026-09-04, P1): one title per session —
  // the first user message names it; the ref resets on a session
  // change (the effect below clears it when a NEW session opens).
  const autoTitledRef = useRef(false)
  const busCognitiveState = useTracePanel(exaSessionId || undefined)
  // the overlay's getter: the LATEST bus state (the ref pattern —
  // the getter must not go stale across renders)
  const busStateRef = useRef(busCognitiveState)
  busStateRef.current = busCognitiveState

  // THE TITLE-GUARD RESET (2026-09-04, P1): a NEW session id means
  // a NEW conversation — the first message may title it again.
  useEffect(() => {
    autoTitledRef.current = false
  }, [exaSessionId])

  // THE PANEL'S LIST REFRESH: load when the panel opens (fresh
  // data) + when the active session changes (new/renamed/deleted
  // rows stay current).
  useEffect(() => {
    if (exaSidebarOpen) {
      void refreshExaSessions()
    }
  }, [exaSidebarOpen, exaSessionId, refreshExaSessions])

  // THE AUTO-SESSION (step 1.3 + the once-guard!): open the latest
  // source='exa' session — or create the fresh ONE (the ref-guard
  // stops the double-creates!).
  useEffect(() => {
    if (autoSessionDoneRef.current) return
    let cancelled = false
    const openOrCreate = async () => {
      try {
        // THE SOURCE-SCOPED LOAD (2026-09-04, the exa-leak dig):
        // ask the server for the exa surface's sessions only — the
        // agent page no longer sees them, and this page skips the
        // client-side filter (the SessionSource constant keeps the
        // category rename-safe).
        const sessionList = await sessionService.loadSessions(SessionSource.EXA)
        if (cancelled) return
        // THE CONTINUITY (the step-1.5 fix): the page REMEMBERS its
        // session (the localStorage!) — the reload reopens the SAME
        // conversation, not a fresh one! The fallbacks: the stored
        // → the latest-exa → the create (stored!)
        const storedId = sessionStorage.getItem('exa-session-id')
        const stored = sessionList.find((s) => s.id === storedId)
        const latest = sessionList[sessionList.length - 1]
        const target = stored || latest
        if (target) {
          setExaSessionId(target.id)
          sessionStorage.setItem('exa-session-id', target.id)
          // the titles-list carries no messages — load them!
          try {
            const full = await sessionService.loadSession(target.id)
            if (!cancelled) {
              setExaMessages((prev) => (prev.length ? prev : full.messages || []))
            }
          } catch {
            // the load failed — the local bubbles stay (the truth)
          }
        } else if (!sessionStorage.getItem('exa-session-created')) {
          // THE CREATE: the FIRST-EVER only (the localStorage's
          // flag!) — the user's deletes are the intent, NOT
          // something to refill! (The 2026-08-29 fix: the old
          // fallback re-created a session on EVERY remount — the
          // deletes came right back!)
          const created = await sessionService.createSession(EXA_SESSION_PLACEHOLDER, SessionSource.EXA, '')
          if (cancelled) return
          sessionStorage.setItem('exa-session-created', '1')
          setExaSessionId(created.id)
          sessionStorage.setItem('exa-session-id', created.id)
          setExaMessages([])
        }
        // else: the sessionless — the deletes were the user's
        // intent; the page waits for the next engagement!
      } catch {
        // the backend's down — the page stays session-less; the
        // send-guard surfaces the offline-state
      }
      // the once-guard AFTER the attempt (the StrictMode's
      // double-mount cancels the first — the second runs fresh!)
      autoSessionDoneRef.current = true
    }
    openOrCreate()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ===== THE SESSIONS PANEL HANDLERS (2026-09-04, the Exa-panel B
  // — P2): select = load the session's messages into the view (the
  // true-resume context handoff lands in P3); delete = remove the
  // session row; the current session object = the panel's highlight.
  // =====
  const selectExaSession = useCallback(async (session: ConversationSession) => {
    // THE VIEW-CHANGE SUPERSEDES THE IN-FLIGHT TURN (2026-09-04, the
    // blocked-input dig — issue #2): switching sessions while a
    // response streams must not strand exaBusy=true (the input + the
    // macros disable on it). Clear it on the deliberate switch; the
    // stray ws events for the old turn are dropped with the messages.
    setExaBusy(false)
    try {
      const full = await sessionService.loadSession(session.id)
      setExaSessionId(session.id)
      sessionStorage.setItem('exa-session-id', session.id)
      setExaMessages(full.messages || [])
      setPendingPickup(null)
    } catch (e) {
      frontendLoggingService.error('ExaChat', 'Failed to open session', e)
    }
  }, [sessionService])

  const deleteExaSession = useCallback(async (sessionId: string) => {
    try {
      await sessionService.deleteSession(sessionId)
      // the deleted session was the active one -> start clean
      if (sessionId === exaSessionId) {
        sessionStorage.removeItem('exa-session-id')
        sessionStorage.removeItem('exa-session-created')
        setExaSessionId(null)
        setExaMessages([])
      }
      await refreshExaSessions()
    } catch (e) {
      frontendLoggingService.error('ExaChat', 'Failed to delete session', e)
    }
  }, [exaSessionId, refreshExaSessions, sessionService])

  // the current-session object for the panel highlight (the session
  // list carries no messages — the titles + the ids suffice)
  const currentExaSession = useMemo(
    () => exaSessions.find((s) => s.id === exaSessionId) ?? null,
    [exaSessions, exaSessionId]
  )

  // THE SMART RENAME (2026-09-04, the user-testing catch — "the exa
  // side panel rename… we want the same rename from the conversation
  // we have on the sessions page"): the SessionManager row's ✨
  // falls back to the MANUAL inline rename when the host provides no
  // onSessionSmartRename. The Sessions page instead POSTs to the
  // title endpoint and lets the BACKEND derive the title from the
  // conversation. Wired here the same way — the backend resolves
  // the title model (Exa has no agent row; the resolver's
  // backend_default covers it).
  const smartRenameExaSession = useCallback(async (session: ConversationSession) => {
    try {
      const res = await fetch(`/api/v1/sessions/${session.id}/title`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}), // no model -> the backend default
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error((body as { detail?: string }).detail || 'Title generation failed')
      }
      const data = (await res.json()) as { title?: string }
      if (data.title) {
        await sessionService.updateSessionTitle(session.id, data.title)
        await refreshExaSessions()
      }
    } catch (e) {
      frontendLoggingService.error('ExaChat', 'Smart rename failed', e)
    }
  }, [refreshExaSessions, sessionService])

  // THE PANEL'S NEW-CHAT (THE FULL ROTATION, 2026-09-04 — P3):
  // ONE mental model, both layers: (1) tell the RUNTIME to reset
  // its context (the /new ACP command — the external agent starts
  // fresh); (2) rotate the DB session — create the fresh row NOW
  // (the agent chat's New does the same), close the old view; the
  // first message titles the new session (the P1 auto-title).
  const newExaChat = useCallback(async () => {
    // THE BUSY-CLEAR (2026-09-04, the blocked-input dig): the New
    // rotation while a turn streams must not strand the busy flag.
    setExaBusy(false)
    // 1. the runtime reset (fire-and-forget; the offline is fine —
    //    the local rotation still happens)
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'prompt', text: '/new' }))
    }
    // 2. the DB rotation: create the fresh exa session immediately
    try {
      const created = await sessionService.createSession(EXA_SESSION_PLACEHOLDER, SessionSource.EXA, '')
      sessionStorage.setItem('exa-session-id', created.id)
      sessionStorage.setItem('exa-session-created', '1')
      setExaSessionId(created.id)
      setExaMessages([])
      setPendingPickup(null)
      setConfirmNewChat(false)
      autoTitledRef.current = false // the fresh session takes a new title
      await refreshExaSessions()
    } catch (e) {
      // the backend's down — fall back to the clear-only (the next
      // message's engage-path creates the session when it recovers)
      frontendLoggingService.error('ExaChat', 'New-chat rotation failed (backend down?)', e)
      sessionStorage.removeItem(BUBBLES_KEY)
      sessionStorage.removeItem('exa-session-id')
      setExaMessages([])
      setPendingPickup(null)
      setConfirmNewChat(false)
    }
  }, [sessionService, refreshExaSessions])

  // THE TIMER-FIRED PICKUP (the panel-port, 2026-08-29): hear the
  // timer:{id}:fired bus-events and surface a CONFIRMABLE pickup —
  // the 08-13 doctrine (NO auto-fire): the user sends or discards
  // it. The banner sits above the input until acted on.
  useEffect(() => {
    addTopics('timer:*')
    const unsub = eventBus.subscribe('timer:*', (payload) => {
      const p = (payload ?? {}) as { timer_id?: string; context?: string }
      if (!p.timer_id) return
      const ctx = p.context || 'the long-running job finished'
      setPendingPickup({
        id: uuidv4(),
        label: ctx,
        text: `The timer fired. Pick up where you left off: ${ctx}. Read the results, give me the digest, and clean up the working copy.`,
      })
      frontendLoggingService.info('ExaChat', 'timer-fired pickup surfaced', { timer_id: p.timer_id })
    })
    return () => {
      unsub()
      removeTopics('timer:*')
    }
  }, [])

  // THE SWAP PICKUP (A3, the write side — 2026-09-09): the local
  // providers page queues a swap request and opens this tab. The
  // request is single-use localStorage; hear it on mount (a cold
  // open) and via the cross-tab storage event (a warm tab — the
  // event fires in every OTHER tab when the page writes). Surface
  // it as the same confirmable pickup — NO auto-fire.
  useEffect(() => {
    const surfaceSwap = () => {
      const req = peekSwapRequest()
      if (!req) return
      consumeSwapRequest()
      setPendingPickup({
        id: uuidv4(),
        label: req.label,
        text: req.text,
      })
      frontendLoggingService.info('ExaChat', 'swap request pickup surfaced', {
        label: req.label,
      })
    }
    surfaceSwap()
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'cogitate-swap-request' && e.newValue) surfaceSwap()
    }
    window.addEventListener('storage', onStorage)
    return () => {
      window.removeEventListener('storage', onStorage)
    }
  }, [])

  // THE PERSIST (the step-1.5 continuity): the backend's
  // messages-endpoint (the Exa-bridge's save path!) — the
  // messages survive the reloads!
  const persistMessage = useCallback(
    async (role: 'user' | 'assistant', content: string) => {
      const sessionId = exaSessionIdRef.current
      if (!sessionId) return
      try {
        await fetch(`/api/v1/sessions/${sessionId}/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role, content }),
        })
      } catch {
        // the offline — the local-state's the view; the next
        // reload's the backend's truth
      }
    },
    [] // the ref keeps the identity stable — the ws binds once
  )


  // ===== THE FIRST-CLASS STREAM (step 1.4): the page's OWN
  // /external-agent/ws — the ACP-direct channel (NO agent-chat's
  // run-bridge!). The message-STORE stays the shared (the backend's
  // the source-of-truth); the RUN rides Exa's own channel. =====
  const wsRef = useRef<WebSocket | null>(null)
  const [exaConnected, setExaConnected] = useState(false)
  const [exaBusy, setExaBusy] = useState(false)
  // THE AUTO-RECONNECT (2026-08-30, the user's offline class — the
  // reload-only socket): the exp-backoff (1s -> 30s cap); the page
  // heals itself instead of dying until the reload.
  const reconnectAttemptRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // THE INACTIVE GATE (2026-11-19, the user's "loop of messaging" report): an
  // `inactive` frame is a STATE, not a blip — the socket stops for good and the
  // page says it ONCE. Reconnecting against a switched-off Exa produced a toast
  // per attempt, every second, because `onopen` also reset the backoff.
  const exaInactiveRef = useRef(false)
  const inactiveNotifiedRef = useRef(false)
  // the connect closure, so activation can reopen the socket by hand
  const connectRef = useRef<(() => void) | null>(null)
  // THE AUTO-VOICE (2026-08-30, the _25 P2 build; 2026-09-04, the
  // chat-audio rework P2 — the LIVE read): the tts config's enabled
  // flag — new responses read themselves aloud. The REF (the handler
  // closure pattern — the ws effect's deps stay stable). THE LIVE
  // FIX: the Speech page and this page are SEPARATE tabs — a
  // mount-time read went stale the moment the user toggled the
  // switch there. The config re-reads when the page gains focus or
  // becomes visible again (the user returning from the Speech tab
  // picks up the new setting — no reload needed).
  const autoVoiceRef = useRef(false)
  useEffect(() => {
    const refresh = () => {
      ttsConfigService
        .getConfig()
        .then((cfg) => {
          autoVoiceRef.current = cfg.enabled
        })
        .catch(() => {})
    }
    refresh()
    const onShow = () => refresh()
    document.addEventListener('visibilitychange', onShow)
    window.addEventListener('focus', onShow)
    return () => {
      document.removeEventListener('visibilitychange', onShow)
      window.removeEventListener('focus', onShow)
    }
  }, [])

  // THE AUTO-SPEAK OFF-SWITCH (2026-09-08, the user's ask): the
  // page's own pref — AUTO-reads off while the bubble PLAY buttons
  // still speak on demand (the tts config's enabled flag stays the
  // service master for manual speech; this pref gates ONLY the
  // auto-read branch). localStorage-backed (per-browser, no backend
  // churn); the ref mirrors the state for the ws closure.
  // OFF unless this browser has switched it on (2026-11-25): a shipped install must
  // not start reading replies aloud — the old default was 'true', so a fresh browser
  // began voicing every answer and, where TTS is unconfigured, raising an error the
  // user never asked for.
  const autoSpeakRef = useRef(
    (localStorage.getItem('exa-auto-speak') ?? 'false') !== 'false'
  )
  const [autoSpeak, setAutoSpeak] = useState(autoSpeakRef.current)
  const toggleAutoSpeak = () => {
    const next = !autoSpeakRef.current
    autoSpeakRef.current = next
    setAutoSpeak(next)
    localStorage.setItem('exa-auto-speak', String(next))
  }

  useEffect(() => {
    // (the sessionless connect — 2026-08-29: the ws is the
    // backend's handshake, NOT session-bound on the frontend! The
    // deletes left the page 'offline' because the guard skipped
    // the connect — the session's the page's state only!)
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    let disposed = false
    const connect = () => {
      if (disposed) return
      const ws = new WebSocket(`${proto}://${window.location.host}/api/v1/external-agent/ws`)
      wsRef.current = ws
      ws.onopen = () => {
        // the backoff resets on `ready`, never on open — a socket that opens
        // and immediately closes must still back off (the toast loop's second half)
        setExaConnected(true)
      }
      ws.onmessage = (ev: MessageEvent) => {
      let msg: WsMessage
      try {
        msg = JSON.parse(String(ev.data))
      } catch {
        return
      }
      if (msg.type === 'status' && msg.status === 'inactive') {
        // the gate's answer (2026-11-18): a switched-off Exa is a STATE, so the
        // page says it ONCE and the socket stops for good — the reconnect in
        // onclose is what turned that one sentence into a toast per second
        // (2026-11-19, the user's "loop of messaging").
        exaInactiveRef.current = true
        setExaActive(false)
        setExaBusy(false)
        if (!inactiveNotifiedRef.current) {
          inactiveNotifiedRef.current = true
          useNotificationStore.getState().addNotification({
            type: 'info',
            title: 'Exa is not active',
            message: msg.message || 'Activate it on the Exa page when you want it to answer.',
          })
        }
      } else if (msg.type === 'status' && msg.status === 'ready') {
        // a live Exa is answering: the blips are over, so the blip-detection
        // resets here rather than on every socket open
        exaInactiveRef.current = false
        inactiveNotifiedRef.current = false
        reconnectAttemptRef.current = 0
        setExaConnected(true)
      } else if (msg.type === 'message' && msg.text) {
        // THE STREAMING-CHUNKS (the protocol: {type:'message',
        // text: '<chunk>'}!): accumulate into the last-assistant
        // message (the isStreaming-flag!)
        setExaMessages((prev) => {
          const last = prev[prev.length - 1]
          if (last?.role === 'assistant' && last.isStreaming) {
            return [...prev.slice(0, -1), { ...last, content: last.content + (msg.text || '') }]
          }
          return [
            ...prev,
            {
              id: uuidv4(),
              role: 'assistant',
              content: msg.text || '',
              isStreaming: true,
              timestamp: new Date(),
            },
          ]
        })
      } else if (msg.type === 'thought' && msg.text) {
        // THE THOUGHT STREAM (the thinking-fold completion): the
        // ACP adapter's agent_thought_chunk events arrive as
        // {type:'thought', text:'<chunk>'} — accumulated into the
        // current assistant message's reasoning metadata;
        // ResponseStream renders it behind the collapsible Thinking
        // fold (the answer stays readable).
        setExaMessages((prev) => {
          const last = prev[prev.length - 1]
          if (last?.role === 'assistant') {
            const reasoning = (last.metadata?.reasoning || '') + (msg.text || '')
            return [
              ...prev.slice(0, -1),
              { ...last, metadata: { ...(last.metadata || {}), reasoning } },
            ]
          }
          return [
            ...prev,
            {
              id: uuidv4(),
              role: 'assistant',
              content: '',
              metadata: { reasoning: msg.text || '' },
              timestamp: new Date(),
            },
          ]
        })
      } else if (msg.type === 'tool_call') {
        // THE ACTIVITY (the panel-port): the tool-call titles attach
        // to the current assistant message — the fold renders them
        // collapsed, the answer is never pushed off-screen.
        const title = msg.update?.title || msg.update?.kind || 'tool'
        setExaMessages((prev) => {
          const last = prev[prev.length - 1]
          if (last?.role === 'assistant') {
            return [...prev.slice(0, -1), { ...last, activity: [...(last.activity || []), title].slice(-200) }]
          }
          return [
            ...prev,
            { id: uuidv4(), role: 'assistant', content: '', activity: [title], timestamp: new Date() },
          ]
        })
      } else if (msg.type === 'status' && msg.status === 'working') {
        // THE TOOL-CALL CHECK-IN (2026-09-08): the
        // backend's per-turn beacon — the last assistant bubble's
        // activity shows the live count (the runaway is visible
        // while it builds, not discovered at the crash). One note
        // at a time — the latest replaces the last.
        const note = msg.message || 'still working'
        setExaMessages((prev) => {
          const last = prev[prev.length - 1]
          if (last?.role !== 'assistant') return prev
          const rest = (last.activity || []).filter((a) => !a.startsWith('⏳'))
          return [...prev.slice(0, -1), { ...last, activity: [...rest, `⏳ ${note}`] }]
        })
      } else if (msg.type === 'status' && msg.status === 'tool_call_limit') {
        // THE TOOL-CALL CAP (2026-09-08): the backend
        // auto-stopped the runaway turn — say WHY (not a user stop)
        setExaBusy(false)
        setExaMessages((prev) => {
          const last = prev[prev.length - 1]
          const next =
            last?.role === 'assistant' && last.activity?.length && !last.activityDone
              ? [...prev.slice(0, -1), { ...last, activityDone: true }]
              : prev
          return [
            ...next,
            {
              id: uuidv4(),
              role: 'assistant',
              content: msg.message || 'Tool-call limit reached — the run was stopped.',
              timestamp: new Date(),
            },
          ]
        })
      } else if (msg.type === 'done' && msg.reply) {
        // THE FULL-REPLY rides the done-event! (the protocol:
        // {type:'done', reply: '<full text>'}!)
        setExaMessages((prev) => {
          const last = prev[prev.length - 1]
          if (last?.role === 'assistant') {
            return [
              ...prev.slice(0, -1),
              {
                ...last,
                content: msg.reply || last.content,
                isStreaming: false,
                activityDone: last.activity?.length ? true : last.activityDone,
              },
            ]
          }
          return [
            ...prev,
            { id: uuidv4(), role: 'assistant', content: msg.reply || '', timestamp: new Date() },
          ]
        })
        persistMessage('assistant', msg.reply)
        setExaBusy(false)
        // THE AUTO-VOICE (2026-08-30, the _25 P2 build; 2026-09-04,
        // the chat-audio rework P3 — the SPEAK KEY): when the tts
        // config's enabled, the finished response reads itself
        // aloud. The speech KEYS to the bubble that received the
        // reply (the last assistant message — its id survives the
        // content swap) — the bubble shows the pause/stop controls,
        // so an auto-read is never unstoppable.
        if (autoSpeakRef.current && autoVoiceRef.current && msg.reply) {
          const lastAssistant = [...exaMessagesRef.current].reverse().find((m) => m.role === 'assistant')
          ttsService.speak(msg.reply, { key: lastAssistant?.id })
        }
      } else if (msg.type === 'done' || (msg.type === 'status' && (msg.status === 'cancelled' || msg.status === 'error' || msg.status === 'time_limit'))) {
        setExaBusy(false)
        // the turn ended without a reply — mark the activity static
        setExaMessages((prev) => {
          const last = prev[prev.length - 1]
          if (last?.role === 'assistant' && last.activity?.length && !last.activityDone) {
            return [...prev.slice(0, -1), { ...last, activityDone: true }]
          }
          return prev
        })
      }
    }
      ws.onclose = () => {
        setExaConnected(false)
        setExaBusy(false)
        // THE RECONNECT (2026-08-30): the exp-backoff — 1s, 2s, 4s…
        // capped at 30s — the page comes back on its own; the ring
        // catch-up + the bubble-persistence make the recovery whole.
        // NOT after an `inactive` answer: the gate refuses every attempt,
        // so a reconnect only repeats the sentence (2026-11-19).
        if (shouldReconnectOnClose({ disposed, inactive: exaInactiveRef.current })) {
          const delay = backoffDelay(reconnectAttemptRef.current)
          reconnectAttemptRef.current += 1
          reconnectTimerRef.current = setTimeout(connect, delay)
        }
      }
      ws.onerror = () => {
        // the onclose follows the error — the reconnect there
      }
    }
    connectRef.current = connect
    connect()
    return () => {
      disposed = true
      connectRef.current = null
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [persistMessage])

  // THE EXA-STOP (the step-1.5 cleanup): the page's own halt —
  // the ws-cancel (the agent-chat's stop-paths are OUT!)
  const exaStop = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: 'cancel' }))
    setExaBusy(false)
  }, [])

  // THE PROMPT-HISTORY (the user's ask!): the past user-prompts —
  // the flyout's picker (the click re-sends the prompt!); the
  // ACP-actions' presets live in the ChatInterface (the toolbar!)
  const promptHistory = useMemo(
    () => exaMessages.filter((m) => m.role === 'user').map((m) => m.content).slice(-8),
    [exaMessages]
  )

  // THE EXA-SEND: the ws-drive (NOT the agent-chat's handleSendMessage!)
  const exaSend = useCallback(
    async (text: string) => {
      // THE GATE (2026-11-18): a switched-off Exa answers with its state, so a
      // typed prompt becomes a toast — never a socket message to nothing.
      if (exaActive === false) {
        useNotificationStore.getState().addNotification({
          type: 'info',
          title: 'Exa is not active',
          message: 'Activate it on the Exa page first — nothing is running to answer.',
        })
        return
      }
      // the user typed their OWN prompt — the timer pickup (if any)
      // is superseded; discard it so it can't double-send later
      if (pendingPickup) setPendingPickup(null)
      // THE ENGAGE-ON-DEMAND (2026-08-29): the sessionless page
      // (the deletes!) — the first ask CREATES the session + waits
      // for the ws (the session-bound connect)!
      if (!exaSessionIdRef.current) {
        const created = await sessionService.createSession(EXA_SESSION_PLACEHOLDER, SessionSource.EXA, '')
        sessionStorage.setItem('exa-session-created', '1')
        sessionStorage.setItem('exa-session-id', created.id)
        exaSessionIdRef.current = created.id
        setExaSessionId(created.id)
        // the ws-effect re-runs on the session-set — wait for the open!
        const deadline = Date.now() + 5000
        while ((!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) && Date.now() < deadline) {
          await new Promise((r) => setTimeout(r, 100))
        }
      }
      if (!wsRef.current || wsRef.current.readyState > WebSocket.OPEN) return
      setExaMessages((prev) => [
        ...prev,
        { id: uuidv4(), role: 'user', content: text, timestamp: new Date() },
      ])
      persistMessage('user', text)
      // THE AUTO-TITLE (2026-09-04, the Exa-panel P1 — REPLACED 2026-09-26).
      // The session used to be named from a 60-character SLICE of the first
      // user message, which is how session 141 came to be called
      // "Hi exa. I would like to add a new mystery LLM to the openrou". It now
      // goes through the SAME background service the chat page uses, so the
      // two surfaces title sessions one way: the service owns the model choice,
      // the anti-reasoning override for a short task, the retry, the rename and
      // the store update — and it honours `enableAutoTitle`, which the slice
      // never did. There is no agent here (Exa sessions carry source='exa'), so
      // the resolver's 'agent' preference yields null = the backend default.
      const titleSessionId = exaSessionIdRef.current
      if (titleSessionId && !autoTitledRef.current) {
        autoTitledRef.current = true
        const general = useSettingsStore.getState().settings.general
        titleService.generateTitleInBackground(
          titleSessionId,
          text,
          resolveTitleModel(null, general),
          general?.enableAutoTitle ?? true
        )
      }
      wsRef.current.send(JSON.stringify({ type: 'prompt', text }))
      setExaBusy(true)
    },
    [persistMessage, sessionService, pendingPickup]
  )

  // THE TIMER PICKUP CONFIRM (the panel-port): the user explicitly
  // sends the queued hand-off — NO auto-fire.
  const confirmPickup = useCallback(() => {
    const p = pendingPickup
    if (!p || exaBusy || !exaConnected) return
    setPendingPickup(null)
    setExaMessages((prev) => [
      ...prev,
      { id: uuidv4(), role: 'user', content: p.text, timestamp: new Date() },
    ])
    persistMessage('user', p.text)
    wsRef.current?.send(JSON.stringify({ type: 'prompt', text: p.text }))
    setExaBusy(true)
  }, [pendingPickup, exaBusy, exaConnected, exaActive, persistMessage])

  const discardPickup = useCallback(() => setPendingPickup(null), [])

  // THE NEW-CHAT CONFIRM (2026-08-30, the user's ask): the Reset
  // button's two-click confirm — like the Force Kill. Confirming
  // runs newExaChat (the FULL rotation: the runtime /new + the
  // fresh DB session). The agent can't clear its own chat (the
  // bubbles are the PAGE's localStorage).
  const [confirmNewChat, setConfirmNewChat] = useState(false)

  // THE NUKE (the panel-port): process-group SIGKILL — for when the
  // gentle Stop failed. Two-click confirm.
  const nuke = useCallback(() => {
    if (!exaConnected) return
    wsRef.current?.send(JSON.stringify({ type: 'nuke' }))
    setConfirmNuke(false)
  }, [exaConnected])

  // THE ACTIVATION (2026-11-18): one press, and the answer says what the box
  // can actually do — "activated" and "able to answer" are two different facts.
  // THE RE-PROBE (2026-11-19): activation happens on the SERVER, so the page's
  // stopped socket is reopened by hand — the gate is lifted, the toast may speak
  // again, and the backoff starts fresh.
  const reconnectNow = useCallback(() => {
    exaInactiveRef.current = false
    inactiveNotifiedRef.current = false
    reconnectAttemptRef.current = 0
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) wsRef.current.close()
    connectRef.current?.()
  }, [])

  const activate = useCallback(async () => {
    setActivating(true)
    try {
      const res = await activateExa()
      setExaActive(res.enabled)
      setExaBlockedReason(res.blocked_reason ?? null)
      if (res.enabled) reconnectNow()
      // THE ANSWER'S SECOND FACT (2026-11-22): "activated" and "able to answer" are different, and
      // on a home with no model the difference is total. Ask the one question activation cannot
      // decide, with this install's model already named.
      const { needsModel, offer } = modelAskFrom(res)
      if (needsModel) {
        if (offer) {
          setModelAsk(offer)
          useNotificationStore.getState().addNotification({
            type: 'warning',
            title: 'Exa activated — it needs a model',
            message: 'One press on the card and it can answer.',
          })
        } else {
          useNotificationStore.getState().addNotification({
            type: 'warning',
            title: 'Exa activated — but it has no model',
            message: 'Nothing on this install answers chat yet. Set a provider and model first.',
          })
        }
      } else {
        useNotificationStore.getState().addNotification({
          type: res.runnable ? 'success' : 'warning',
          title: res.runnable ? 'Exa activated' : 'Exa activated — but it cannot run here yet',
          message: res.runnable
            ? 'Say something to wake it up.'
            : (res.blocked_reason ?? 'The runtime it needs is missing from this machine.'),
        })
      }
    } catch (err) {
      useNotificationStore.getState().addNotification({ type: 'error', title: 'Exa', message: String(err) })
    } finally {
      setActivating(false)
    }
  }, [reconnectNow])

  // THE ASK'S ACCEPT: the same write the integrations page's Model card makes, so the two doors can
  // never disagree about what "use this model" means.
  const acceptOfferedModel = useCallback(async () => {
    if (!modelAsk) return
    const chosen = modelAsk
    setSavingModel(true)
    try {
      const updated = await updateExaModel({
        model: chosen.model,
        provider: chosen.provider,
        base_url: chosen.base_url ?? '',
      })
      setModelAsk(null)
      useNotificationStore.getState().addNotification({
        type: 'success',
        title: 'Exa Agent',
        message: `Model set to ${updated.model} (${updated.provider})`,
      })
      reconnectNow()
    } catch (err) {
      useNotificationStore.getState().addNotification({ type: 'error', title: 'Exa Agent', message: String(err) })
    } finally {
      setSavingModel(false)
    }
  }, [modelAsk, reconnectNow])

  return (
    <ErrorBoundary>
      <div className="flex h-dvh overflow-hidden bg-base-100">
        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Header */}
          <div className="border-b border-base-300 flex-shrink-0 bg-base-100 flex items-center justify-between h-auto py-4 px-6">
            {/* THE EXA HEADER (step 1.2 — the pickers deleted!): the
                real Exa image (the config's face) + the name + the
                status. The system agent needs no picker. */}
            <div className="flex items-center gap-3">
              <div className="avatar">
                <div className="w-10 h-10 rounded-full bg-base-200 flex items-center justify-center overflow-hidden ring-1 ring-base-300">
                  {exaImage ? (
                    <img src={exaImage} alt="Exa" className="w-full h-full object-cover" />
                  ) : (
                    <span className="text-lg text-readout">🤖</span>
                  )}
                </div>
              </div>
              <div>
                <div className="font-semibold text-base-content leading-tight flex items-center gap-2">
                  Exa
                  {/* THE EXA RUNTIME DOT (2026-09-04, the user's
                      check): the native title -> a proper DAISYUI
                      tooltip (the dot = the runtime-ws state; the
                      short label rides data-tip). */}
                  <span
                    className={`tooltip tooltip-bottom w-2 h-2 rounded-full cursor-help ${exaConnected ? 'bg-success' : 'bg-error'}`}
                    data-tip={exaConnected ? 'Connected' : 'Offline'}
                  />
                </div>
                <div className="text-xs text-readout">
                  {exaActive === false
                    ? 'inactive'
                    : exaBusy
                      ? 'working…'
                      : exaConnected
                        ? 'the system agent'
                        : 'offline'}
                </div>
              </div>
            </div>

            {/* Header Buttons */}
            <div className="flex gap-2 items-center">
              {/* THE AUTO-SPEAK OFF-SWITCH (2026-09-08, the user's
                  ask): AUTO-reads off while the bubble play buttons
                  still speak on demand. The tooltip rides the label
                  wrapper (never the checkbox input). */}
              <label
                className="tooltip tooltip-bottom flex items-center gap-1.5 cursor-pointer select-none"
                data-tip={autoSpeak ? 'Auto-speak on — replies read aloud. The play buttons still speak on demand.' : 'Auto-speak off — replies stay silent; the play buttons still speak on demand.'}
              >
                <span className="text-xs text-readout">Auto-speak</span>
                <input
                  type="checkbox"
                  className="toggle toggle-primary toggle-sm"
                  checked={autoSpeak}
                  onChange={toggleAutoSpeak}
                  aria-label="Toggle auto-speak"
                />
              </label>
              {/* THE SESSIONS-PANEL TOGGLE (2026-09-04, the Exa-panel
                  B): the collapsible right sidebar — same pattern as
                  the agent page's. */}
              <div className="tooltip tooltip-bottom" data-tip={exaSidebarOpen ? 'Close the session list' : 'Session list'}>
                <button
                  type="button"
                  onClick={() => setExaSidebarOpen(!exaSidebarOpen)}
                  className={`rounded-full p-1.5 border transition-all ${
                    exaSidebarOpen
                      ? 'border-primary/50 bg-primary/10 text-primary'
                      : 'border-base-300 hover:border-primary/50'
                  }`}
                  aria-label={exaSidebarOpen ? 'Close the session list' : 'Open the session list'}
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
                  </svg>
                </button>
              </div>
              {/* THE MESSAGES WIDGET (2026-08-25): the bell + the
                  count — just LEFT of the Exa button; navigates to
                  the Message Center page. */}
              <div className="tooltip tooltip-bottom" data-tip="Go to message center">
                <button
                  type="button"
                  onClick={() => navigateTo('messages')}
                  className="rounded-full p-1.5 border border-base-300 hover:border-primary/50 relative"
                  aria-label={`Go to message center (${unreadCount} unread)`}
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                  </svg>
                  {unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1 badge badge-primary badge-xs text-[10px]">
                      {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                  )}
                </button>
              </div>
              {/* THE NEW CHAT (2026-08-30, the user's ask): the
                  two-click confirm — clear the conversation + the
                  session keys; the next message starts fresh. */}
              {confirmNewChat ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-warning">Clear this conversation?</span>
                  <button className="btn btn-error btn-xs" onClick={() => void newExaChat()}>
                    Yes, clear
                  </button>
                  <button className="btn btn-neutral btn-ghost btn-xs" onClick={() => setConfirmNewChat(false)}>
                    Cancel
                  </button>
                </div>
              ) : (
                <div
                  className="tooltip tooltip-bottom"
                  data-tip="Reset — clear this conversation and start a fresh chat (the persistent memory survives)"
                >
                  <button
                    type="button"
                    onClick={() => setConfirmNewChat(true)}
                    className="pill-button pill-button--normal"
                    aria-label="Reset chat"
                  >
                    Reset
                  </button>
                </div>
              )}
              {/* Help Button */}
              <HelpButton
                context="exa-agent"
                size="sm"
                showIcon={false}
                showLabel={true}
                label="Help"
                tooltipPosition="bottom"
                className="pill-button pill-button--normal"
              />

            </div>
          </div>

          {/* THE INACTIVE STATE (2026-11-18): Exa ships switched off, so the
              chat says so and offers the one decision that changes it —
              instead of an input box that fails on send. */}
          {exaActive === false && (
            <div className="flex-shrink-0 px-6 py-3 border-b border-base-300 bg-base-200/60">
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-base-content">Exa is not active</div>
                  <div className="text-xs text-readout mt-0.5">
                    It is included but switched off — nothing runs until you turn it on.
                    {exaBlockedReason ? ` ${exaBlockedReason}` : ''}
                  </div>
                </div>
                <div
                  className="tooltip tooltip-bottom"
                  data-tip="Turn Exa on. It needs an agent runtime and a model to answer."
                >
                  <button className="btn btn-primary btn-sm" onClick={activate} disabled={activating}>
                    {activating ? '…' : 'Activate Exa'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Main Chat Area */}
          <div className="flex-1 overflow-hidden min-h-0 h-full">
            <ResponseStream
              messages={exaMessages}
              isStreaming={exaBusy}
              cognitiveState={busCognitiveState}
            />
          </div>

          {/* THE TIMER PICKUP (the panel-port): a confirmable banner —
              the user sends or discards the queued hand-off. */}
          {pendingPickup && (
            <div className="flex-shrink-0 px-6 py-2 bg-warning/5 border-t border-warning/20 flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium text-warning">The timer fired</div>
                <div className="text-xs text-readout truncate">{pendingPickup.label}</div>
              </div>
              <button className="btn btn-primary btn-xs" onClick={confirmPickup}>
                Send
              </button>
              <button className="btn btn-ghost btn-xs" onClick={discardPickup}>
                Discard
              </button>
            </div>
          )}

          {/* Chat Input */}
          <div className="flex-shrink-0 px-6 bg-base-100 border-t border-base-300 py-1">
            <ChatInterface
              onSendMessage={(msg) => exaSend(msg)}
              isStreaming={exaBusy}
              disabled={!exaConnected || exaActive === false}
              onStopStreaming={exaStop}
              placeholder={
                exaActive === false
                  ? 'Exa is not active — activate it to chat'
                  : !exaConnected
                    ? 'Connecting to Exa...'
                    : 'Message Exa...'
              }
              agentId="exa"
              exaConnected={exaConnected}
              onExaAction={exaSend}
              exaPromptHistory={promptHistory}
              onToggleRightPanel={() => setExaSidebarOpen((open) => !open)}
            />
          </div>

          {/* THE DANGER ZONE (the panel-port): Force Kill — the
              two-click confirm; never disabled by the busy state. */}
          {exaConnected && (
            <div className="flex items-center justify-end px-6 pb-1">
              {confirmNuke ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-error">Kill Exa and its processes?</span>
                  <button className="btn btn-error btn-xs" onClick={nuke}>
                    Yes, kill
                  </button>
                  <button className="btn btn-neutral btn-ghost btn-xs" onClick={() => setConfirmNuke(false)}>
                    Cancel
                  </button>
                </div>
              ) : (
                <div
                  className="tooltip tooltip-top"
                  data-tip="Force-kill Exa and everything it spawned (process-group SIGKILL). Use only if Stop doesn't work."
                >
                  <button
                    className="btn btn-ghost btn-xs text-error/70 hover:text-error"
                    onClick={() => setConfirmNuke(true)}
                  >
                    Force Kill
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* THE SESSIONS PANEL (2026-09-04, the Exa-panel B — P2):
            the collapsible right sidebar — the SHARED SessionManager
            widget (variant='exa'): no agent filter, no settings tab,
            the New button creates the exa session directly. The
            list refreshes when the panel opens. */}
        <div
          key={`exa-sidebar-${exaSidebarOpen}`}
          className={`border-l border-base-300 bg-base-100 transition-all duration-300 ease-in-out overflow-y-auto flex flex-col ${
            exaSidebarOpen ? 'w-80' : 'w-0'
          }`}
        >
          {exaSidebarOpen && (
            <div className="h-full flex flex-col">
              <div className="flex-1 overflow-y-auto">
                <SessionManager
                  variant="exa"
                  sessions={exaSessions}
                  currentSession={currentExaSession}
                  onSessionSelect={selectExaSession}
                  onSessionDelete={deleteExaSession}
                  onSessionRename={async (id, title) => {
                    await sessionService.updateSessionTitle(id, title)
                    await refreshExaSessions()
                  }}
                  onSessionSmartRename={smartRenameExaSession}
                  onNewSession={newExaChat}
                  onReloadSessions={refreshExaSessions}
                  isReloadingSessions={isLoadingExaSessions}
                />
              </div>
            </div>
          )}
        </div>

        {/* Cognitive Trace Debug Overlay (development only, Ctrl+Shift+D) */}
        <CognitiveTraceDebugOverlay
          cognitiveState={busCognitiveState}
          getCognitiveState={() => busStateRef.current}
        />

        {/* THE ACTIVATION ASK: asked here as well as on the integrations page, because this page
            hosts the Activate button the readiness verdict links to. */}
        <ExaModelAskDialog
          offer={modelAsk}
          saving={savingModel}
          onAccept={acceptOfferedModel}
          onDismiss={() => setModelAsk(null)}
        />
      </div>
    </ErrorBoundary>
  )
}