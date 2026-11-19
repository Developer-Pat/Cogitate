/**
 * AgentPanel — external agent (Hermes/OpenClaw) side panel.
 *
 * Help-style right-drawer (same pattern as HelpModal: fixed overlay,
 * slides in from the right, does NOT shrink the layout). Own chat
 * area — thin ACP client, NOT the agent-chat backend.
 *
 * Opens via the global event: window.dispatchEvent(new CustomEvent(
 * 'open-agent-panel')).
 */

import { memo, useCallback, useEffect, useRef, useState } from 'react';
import { useMessageStore } from '@/stores/messageStore';
import { MoreVertical } from 'lucide-react';
import { MarkdownText } from '@/components/ui/MarkdownText';
import { useNotificationStore } from '@/stores/notificationStore';
import { useCognitiveHubStore } from '@/stores/cognitiveHubStore';
import { SessionService } from '@/services/domain/SessionService';
import { addTopics, removeTopics } from '@/services/messagingFeed';
import { eventBus } from '@/services/eventBus';
import { backoffDelay, shouldReconnectOnClose } from '@/services/exaSocketPolicy';
import type { ConversationSession } from '@/types/agentInteraction';
import { frontendLoggingService } from '@/services/frontendLoggingService';

interface PanelMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  activity?: string[];  // tool_call titles (watchable workspace — FULL, not
                        // truncated: the copy button needs the complete
                        // picture even when lines scrolled off screen)
  activityDone?: boolean; // turn ended (done/cancelled) — render static
                          // markers instead of spinners
  pending?: boolean;    // queued hand-off awaiting explicit Send/Discard
  // THE BUILD FIX (2026-08-25, the tsc -b).
  _done?: boolean
}

/**
 * One message row, memoized on `m`.
 *
 * WHY IT IS MEMOIZED: this panel re-renders for two reasons — a WebSocket frame
 * per stream update, AND the one-second elapsed timer — so an unmemoized row
 * re-renders once a second whether or not anything changed. `setMessages`
 * spreads from `prev`, so untouched messages keep their object identity and the
 * memo bails on them; only the row that actually changed does work.
 *
 * The two handlers must stay `useCallback` — a fresh function prop on every
 * render would defeat the memo entirely.
 */
const MessageRow = memo(
  ({
    m,
    onConfirm,
    onDiscard,
  }: {
    m: PanelMessage;
    onConfirm: () => void;
    onDiscard: () => void;
  }) => (
    <div
      className={`max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
        m.role === 'user'
          ? 'ml-auto bg-primary text-primary-content'
          : 'mr-auto bg-base-300/60 text-base-content'
      }`}
    >
      {/* MARKDOWN RENDER: Exa's status reports came back as raw pipes, so
          the panel showed plain text. MarkdownText (the shared small-surface
          renderer) draws tables, headings and code inline — AND it cuts the
          text at block boundaries with each block memoized, so a growing
          reply does not re-parse its finished half. */}
      {m.text ? (
        <div className="not-prose">
          <MarkdownText>{m.text}</MarkdownText>
        </div>
      ) : null}
      {m.pending && (
        <div className="mt-2 pt-2 border-t border-base-content/20 flex gap-2">
          <div className="tooltip tooltip-top" data-tip="Send this queued prompt now">
            <button className="btn btn-primary btn-xs" onClick={onConfirm}>
              Send
            </button>
          </div>
          <div className="tooltip tooltip-top" data-tip="Discard the queued prompt">
            <button className="btn btn-neutral btn-ghost btn-xs" onClick={onDiscard}>
              Discard
            </button>
          </div>
        </div>
      )}
      {m.activity && m.activity.length > 0 && (
        <div className="mt-2 pt-2 border-t border-base-content/10 flex flex-col gap-1">
          {m.activity.map((a, i) => (
            // plain text while running — the single 'thinking…'
            // indicator below conveys activity; a spinner per
            // line is noise (user, 2026-08-13). Static marker
            // only after the turn ends.
            <div key={i} className="text-[11px] opacity-70 flex items-center gap-1 font-mono">
              {m.activityDone && <span className="opacity-60">▸</span>}
              {a}
            </div>
          ))}
        </div>
      )}
    </div>
  )
);

MessageRow.displayName = 'MessageRow';

interface WsMessage {
  type: 'status' | 'message' | 'thought' | 'tool_call' | 'done';
  status?: string;
  message?: string;
  text?: string;
  reply?: string;
  sessionId?: string;
  update?: { kind?: string; title?: string; locations?: { path?: string }[] };
  [key: string]: unknown;
}

// THE CONTEXT HAND-OFF TEMPLATES (strategy: exa-roles-and-surfaces.md).
// Opening the panel from a page with a context payload seeds Exa's first
// prompt with where you are — one Exa, many surfaces.
//
// MODULE SCOPE, deliberately: this is pure static text, and the panel's `open`
// callback lists it as a dependency — an object literal recreated on every
// render would give that callback a new identity every render, re-subscribing
// its global event listener each time. Hoisting makes the stability real
// instead of memo-dependent.
// NOTE: the macros template embeds the macro-management skill (fetched async in
// `open`) — the user's ask is to GENERATE/MAINTAIN macros, not just discuss
// them (2026-08-13).
const contextTemplates: Record<string, string> = {
  macros:
    `The user opened you from the MACROS page. They want you to ` +
    `GENERATE and MAINTAIN macros — the facility is extensive and ` +
    `hand-editing every slot is tedious and error-prone. Use the ` +
    `cogitate-macro-management skill below: discover what exists ` +
    `(GET /api/v1/macros?all=true, /topics/list, /meta-topics), ` +
    `then create/update macro sets and meta-topics per their ` +
    `request. Show the resulting slot layout so they can verify.\n\n` +
    `[SKILL: cogitate-macro-management — see below if loaded]`,
  setup:
    `The user opened you from the SETUP page. They are setting up ` +
    `the app: providers, API keys, the default model, a starter ` +
    `agent. Guide them through the current setup state (what's ` +
    `configured, what's missing) and explain each choice in plain ` +
    `user language.`,
  execution:
    `The user opened you from the WORKFLOW EXECUTION page. They ` +
    `probably want to know why a workflow run failed or how to ` +
    `troubleshoot it. Investigate the execution logs / traces and ` +
    `report what you actually see.`,
  agents:
    `The user opened you from the PROFILES page. They want you to ` +
    `CREATE and CONFIGURE agents — a new agent for a job, or fix an ` +
    `existing one. Use the cogitate-create-agent skill below: ` +
    `discover what exists (GET /api/v1/agents, /providers, /tools), ` +
    `then create/update per their request with a REAL provider + ` +
    `model + system prompt, and enable the tools it needs. Show the ` +
    `resulting agent summary so they can verify.\n\n` +
    `[SKILL: cogitate-create-agent — see below if loaded]`,
  workflow:
    `The user opened you from the WORKFLOWS page. They ` +
    `want you to CREATE and MAINTAIN workflows — a template ` +
    `(kind) instantiated for a repeated task, or fix an existing ` +
    `one. Use the cogitate-create-workflow skill below: discover ` +
    `what exists (GET /api/v1/workflows/templates), then ` +
    `create/update per their request with a real description and ` +
    `a non-empty ` +
    `config (chain_steps / approval_required / inputs). Validate ` +
    `before saving. Show the template summary so they can ` +
    `verify.\n\n` +
    `[SKILL: cogitate-create-workflow — see below if loaded]`,
};

export function AgentPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const isOpenRef = useRef(false);
  const [messages, setMessages] = useState<PanelMessage[]>([]);
  const [input, setInput] = useState('');
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  // WHOLE-TURN TIMER (2026-08-14): elapsed seconds while busy, so the
  // user can tell 'working' from 'hung' and gauge the configured cap.
  const [elapsedSec, setElapsedSec] = useState(0);
  // THE EXA-HISTORY LOAD (2026-08-27): the panel was live-stream-only
  // — the existing exa-session's messages never rendered (the empty
  // dialog, the missing bubbles). On mount, load the latest exa-session
  // (the null-agentId = the external surface) + its messages as the
  // initial bubbles; the live-ask appends on top.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const service = new SessionService();
        const sessions = await service.loadSessions();
        const latestExa = [...sessions]
          .filter((s) => !s.agentId)
          .sort((a, b) => {
            // the backend's updated_at can arrive as a non-Date (the
            // {}-conversion) — the id-fallback (the auto-increment IS
            // the recency order)
            const recency = (x: ConversationSession) =>
              x.updatedAt instanceof Date ? x.updatedAt.getTime() : Number(x.id) || 0;
            return recency(b) - recency(a);
          })[0];
        if (!latestExa?.id || cancelled) return;
        const full = await service.loadSession(latestExa.id);
        const history: PanelMessage[] = (full.messages ?? []).map((m) => ({
          id: String(m.id),
          role: m.role === 'tool' || m.role === 'system' ? 'assistant' : m.role,
          text: m.content,
          pending: false,
        }));
        if (!cancelled && history.length) {
          // THE RACE-FIX (2026-08-27): the load can resolve AFTER the
          // user's send — the functional-merge never clobbers an
          // active conversation (the fresh bubbles survive).
          setMessages((prev) => (prev.length ? prev : history));
          frontendLoggingService.info(
            'AgentPanel',
            `exa history loaded: ${history.length} messages`,
            { sessionId: latestExa.id },
          );
        }
      } catch (e) {
        frontendLoggingService.error('AgentPanel', 'exa history load failed', e);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // THE TIMER-PICKUP (2026-08-28, the EXA-TIMER): hear the
  // timer:{id}:fired bus-events (the backend's timer-service) and
  // surface a CONFIRMABLE pickup — the 08-13 doctrine (NO auto-fire):
  // the user sends or discards it; the next-ask also carries the
  // context via the pending-ref.
  useEffect(() => {
    addTopics('timer:*');
    const unsub = eventBus.subscribe('timer:*', (payload) => {
      const p = (payload ?? {}) as { timer_id?: string; context?: string };
      if (!p.timer_id) return;
      const id = crypto.randomUUID();
      const ctx = p.context || 'the long-running job finished';
      pendingPromptRef.current = {
        id,
        label: 'timer-fired',
        text: `The timer fired. Pick up where you left off: ${ctx}. Read the results, give me the digest, and clean up the working copy.`,
      };
      setMessages((prev) => [
        ...prev,
        { id, role: 'user', text: `⏰ The timer fired — ${ctx}`, pending: true },
      ]);
      frontendLoggingService.info('AgentPanel', 'timer-fired pickup surfaced', { timer_id: p.timer_id });
    });
    return () => {
      unsub();
      removeTopics('timer:*');
    };
  }, []);

  useEffect(() => {
    if (!busy) {
      setElapsedSec(0);
      return;
    }
    const started = Date.now();
    const iv = setInterval(() => setElapsedSec(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(iv);
  }, [busy]);
  const [fixMode, setFixMode] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  // SYNCHRONOUS in-flight guard (2026-08-13, Exa_dialog_04): React
  // state updates are async — two sends in the same tick (a pending
  // hand-off Send + a typed prompt Send) both read busy=false and
  // both fire, so Hermes queues one ("Queued for the next turn").
  // The ref is set BEFORE the WS write, so the second send sees it.
  const busyRef = useRef(false);
  // single choke point for clearing the busy state (state + ref)
  const clearBusy = useCallback(() => {
    busyRef.current = false;
    setBusy(false);
  }, []);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { addError } = useNotificationStore();

  // THE INACTIVE GATE (2026-11-19): a switched-off Exa answers `inactive` and
  // closes. Reconnecting against that gate repeats the same sentence every
  // second (the backoff was reset on open), so the panel says it once and stops.
  const inactiveRef = useRef(false);
  const inactiveNotifiedRef = useRef(false);

  const close = useCallback(() => {
    setIsOpen(false);
    isOpenRef.current = false;
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    // THE CONNECTION DISCIPLINE (2026-08-25, the user's question):
    // closing the drawer used to leave the WS OPEN (the 'always
    // on' lingering connection) — the connection lives with the
    // panel's visibility.
    wsRef.current?.close();
    wsRef.current = null;
    setConnected(false);
  }, []);

  const pendingContextRef = useRef<string | null>(null);
  // a surfaced (non-auto-fired) hand-off awaiting explicit user action
  const pendingPromptRef = useRef<{ id: string; label: string; text: string } | null>(null);

  // THE RECONNECT (2026-08-13): the WS dying (backend reload, network blip,
  // server restart) reconnects with exponential backoff. It calls `open`
  // through a REF: `open` lists THIS callback as a dependency (its ws.onclose
  // schedules the reconnect) and this callback needs `open` — two dependency
  // arrays pointing at each other would be a cycle, and a ref is the standard
  // break. It is declared ABOVE `open` for the same reason (a dep array is
  // evaluated during render, so a later declaration would be a TDZ error).
  const openRef = useRef<((context?: string) => void) | null>(null)
  const scheduleReconnect = useCallback(() => {
    if (reconnectTimerRef.current !== null) return; // already scheduled
    const attempt = reconnectAttemptRef.current;
    // exponential backoff: 1s, 2s, 4s... capped at 15s
    const delay = backoffDelay(attempt, 15000);
    reconnectTimerRef.current = window.setTimeout(() => {
      reconnectTimerRef.current = null;
      reconnectAttemptRef.current += 1;
      openRef.current?.();
    }, delay);
  }, []);

  const open = useCallback((context?: string) => {
    setIsOpen(true);
    // THE MESSAGE READ (2026-08-25, the Message Center): opening
    // the Exa panel means the exa messages are seen — the queue
    // marks them read (the unread count drops).
    useMessageStore.getState().markAllRead()
    isOpenRef.current = true;
    setOpenContext(context || null);
    pendingContextRef.current = context || null;
    // (the backoff counter is NOT reset here: this runs for the user's open AND
    // for every scheduled reconnect, so resetting here pinned the delay at 1s —
    // it resets on the server's `ready` instead)
    // A user open is a fresh attempt at the gate, so the inactive latch lifts
    // here and the one-note budget refills.
    inactiveRef.current = false;
    inactiveNotifiedRef.current = false;
    // reflect the persisted fix-mode grant (the explicit grant lives
    // on the Exa Agent page; the panel shows it)
    fetch('/api/v1/external-agent/config')
      .then((r) => (r.ok ? r.json() : null))
      .then((cfg) => { if (cfg) setFixMode(!!cfg.fix_mode); })
      .catch(() => {});
    // (re)connect lazily on open
    if (!wsRef.current || wsRef.current.readyState > WebSocket.OPEN) {
      setConnected(false);
      try {
        const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const ws = new WebSocket(`${proto}://${window.location.host}/api/v1/external-agent/ws`);
        wsRef.current = ws;
        ws.onopen = () => setConnected(true);
        ws.onmessage = (ev: MessageEvent) => {
          let msg: WsMessage;
          try {
            msg = JSON.parse(String(ev.data));
          } catch {
            return;
          }
          if (msg.type === 'status' && msg.status === 'ready') {
            setConnected(true);
            // the server is answering a live Exa: the blips are over
            inactiveRef.current = false;
            inactiveNotifiedRef.current = false;
            reconnectAttemptRef.current = 0;
            // Pending hand-off — NO auto-fire (2026-08-13 incident: a
            // queued prompt that executed on reconnect ran away with no
            // halt path). Surface it as a confirmable message instead;
            // the user explicitly sends or discards it.
            const ctx = pendingContextRef.current;
            pendingContextRef.current = null;
            if (ctx && !pendingPromptRef.current) {
              const tpl = contextTemplates[ctx];
              if (tpl) {
                const label = ctx === 'macros' ? 'Macros' : ctx === 'setup' ? 'Setup' : ctx === 'execution' ? 'Workflow Execution' : ctx;
                const id = crypto.randomUUID();
                // embed the context's skill (consult-tool-injected
                // delivery — same pattern as the Diagnose button):
                // macros → macro-management; agents → create-agent;
                // workflow → create-workflow
                const skillByCtx: Record<string, string> = {
                  macros: 'cogitate-macro-management',
                  agents: 'cogitate-create-agent',
                  workflow: 'cogitate-create-workflow',
                };
                const skillName = skillByCtx[ctx];
                if (skillName) {
                  fetch(`/api/v1/external-agent/skills/${skillName}`)
                    .then((r) => (r.ok ? r.json() : null))
                    .then((sk) => {
                      if (!sk || pendingPromptRef.current?.id !== id) return;
                      pendingPromptRef.current = {
                        ...pendingPromptRef.current!,
                        text: `${tpl}\n\n[SKILL: ${skillName}]\n${sk.body}`,
                      };
                    })
                    .catch(() => {});
                }
                pendingPromptRef.current = { id, label, text: tpl };
                setMessages((prev) => [...prev, { id, role: 'user', text: `🔍 Ask Exa: ${label}`, pending: true }]);
              }
            }
          } else if (msg.type === 'status' && msg.status === 'cancelled') {
            // halt path (2026-08-13): backend killed the agent subprocess
            clearBusy();
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              // stop the activity spinners — the turn is over
              if (last && last.role === 'assistant' && last.activity?.length) {
                next[next.length - 1] = { ...last, activityDone: true };
              }
              return [...next, { id: crypto.randomUUID(), role: 'assistant', text: '⏹ Stopped.' }];
            });
          } else if (msg.type === 'status' && msg.status === 'time_limit') {
            // whole-turn cap (2026-08-14): the backend auto-stopped the
            // run because it exceeded the configured time limit — say
            // WHY (not a user stop), with the remedy
            clearBusy();
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last && last.role === 'assistant' && last.activity?.length) {
                next[next.length - 1] = { ...last, activityDone: true };
              }
              return [
                ...next,
                {
                  id: crypto.randomUUID(),
                  role: 'assistant',
                  text: '⏱ Time limit reached — the run was stopped automatically. '
                    + (msg.message || 'You can re-ask with more detail, or raise the limit on the Exa Agent page.'),
                },
              ];
            });
          } else if (msg.type === 'status' && msg.status === 'working') {
            // THE TOOL-CALL CHECK-IN (2026-09-08):
            // the beacon note rides the activity line of the current
            // assistant message (one at a time — the latest replaces)
            if (msg.message) {
              setMessages((prev) => {
                const last = prev[prev.length - 1]
                if (last?.role !== 'assistant') return prev
                const rest = (last.activity || []).filter((a) => !a.startsWith('⏳'))
                return [...prev.slice(0, -1), { ...last, activity: [...rest, `⏳ ${msg.message}`] }]
              })
            }
          } else if (msg.type === 'status' && msg.status === 'tool_call_limit') {
            // THE TOOL-CALL CAP (2026-09-08): the
            // backend auto-stopped the runaway turn — say WHY
            clearBusy();
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last && last.role === 'assistant' && last.activity?.length) {
                next[next.length - 1] = { ...last, activityDone: true };
              }
              return [...next, { id: crypto.randomUUID(), role: 'assistant', text: '⏱ Tool-call limit reached — the run was stopped automatically. ' + (msg.message || 'You can re-ask with more detail, or raise the limit on the Exa Agent page.') }];
            });
          } else if (msg.type === 'tool_call') {
            const title = msg.update?.title || msg.update?.kind || 'tool';
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              // attach to the current assistant message if it's the
              // latest (text may be empty while thoughts stream, or
              // partial while the reply streams — activity shows
              // regardless, like a live workspace). FULL list (capped
              // at 200 defensively) — the copy button captures the
              // complete picture even when lines scrolled off screen.
              if (last && last.role === 'assistant') {
                next[next.length - 1] = { ...last, activity: [...(last.activity || []), title].slice(-200) };
              } else {
                next.push({ id: crypto.randomUUID(), role: 'assistant', text: '', activity: [title] });
              }
              return next;
            });
          } else if (msg.type === 'status' && msg.status === 'inactive') {
            // THE GATE (2026-11-18): Exa ships switched off — say so plainly
            // and stop the spinner, instead of an input that waits forever.
            // ONCE, and the socket stops (2026-11-19): the gate refuses every
            // reconnect, so repeating the note is only noise.
            inactiveRef.current = true;
            if (!inactiveNotifiedRef.current) {
              inactiveNotifiedRef.current = true;
              addError('Exa', String(msg.message || 'Exa is not active — activate it on the Exa page.'));
            }
            clearBusy();
          } else if (msg.type === 'status' && msg.status === 'error') {
            addError('Agent Panel', String(msg.message || 'connection error'));
            clearBusy();
          } else if (msg.type === 'message') {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last && last.role === 'assistant' && !last._done) {
                next[next.length - 1] = { ...last, text: last.text + String(msg.text || '') };
              } else {
                next.push({ id: crypto.randomUUID(), role: 'assistant', text: String(msg.text || '') });
              }
              return next;
            });
          } else if (msg.type === 'done') {
            clearBusy();
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              if (last && last.role === 'assistant') {
                next[next.length - 1] = { ...last, _done: true, activityDone: last.activity?.length ? true : last.activityDone } as PanelMessage;
              }
              return next;
            });
            // THE DB-RECONCILIATION (2026-08-27): the panel's live view
            // can lose bubbles (the session-churn, the stream hiccups —
            // the user's "the bubble died" twice). After a turn, the
            // DB is the authority: re-fetch the session's messages and
            // replace the view — the conversation CANNOT vanish.
            if (msg.sessionId) {
              const sid = String(msg.sessionId);
              const service = new SessionService();
              service
                .loadSession(sid)
                .then((full) => {
                  const reconciled = (full.messages ?? []).map((m) => ({
                    id: String(m.id),
                    role: m.role === 'tool' || m.role === 'system' ? 'assistant' : m.role,
                    text: m.content,
                    pending: false,
                  }));
                  if (reconciled.length) {
                    setMessages(reconciled);
                    frontendLoggingService.info(
                      'AgentPanel',
                      `db-reconciled: ${reconciled.length} messages`,
                      { sessionId: sid },
                    );
                  }
                })
                .catch(() => {
                  frontendLoggingService.error('AgentPanel', 'db-reconciliation failed', { sessionId: sid });
                });
            }
          }
        };
        ws.onclose = () => {
          setConnected(false);
          clearBusy();
          // AUTO-RECONNECT (2026-08-13): the WS dying (backend reload,
          // network blip, server restart) used to leave the panel
          // 'offline' until manually reopened. Keep the drawer open and
          // reconnect with exponential backoff — the panel is a
          // persistent workspace, not a one-shot chat.
          if (isOpenRef.current && shouldReconnectOnClose({ disposed: false, inactive: inactiveRef.current })) {
            scheduleReconnect();
          }
        };
        ws.onerror = () => {
          // THE SILENT-RECOVERY (2026-08-25, the user's report:
          // 'Agent Panel / WebSocket error' — the toast on every
          // transient!). The reconnect below is automatic + infinite
          // (the persistent-workspace design), so a drop is ALWAYS
          // recovered — the 'offline' badge is the honest state
          // signal, and the toast was pure noise. The sustained
          // failure surfaces via the badge staying offline.
          setConnected(false);
          clearBusy();
        };
      } catch (err) {
        addError('Agent Panel', String(err));
      }
    }
  }, [addError, clearBusy, scheduleReconnect]);

  // keep the ref pointing at the CURRENT `open` — an effect rather than a
  // render-time write (the strict-mode-safe way), and early enough: the
  // reconnect timer only fires a second or more later.
  useEffect(() => {
    openRef.current = open;
  }, [open]);

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as { context?: string } | undefined;
      open(detail?.context);
    };
    window.addEventListener('open-agent-panel', handler);
    return () => window.removeEventListener('open-agent-panel', handler);
  }, [open]);

  // close WS + clear the reconnect timer on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close();
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
    };
  }, []);

  // auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const send = useCallback(() => {
    const text = input.trim();
    if (!text || busyRef.current || !connected) return;
    // the user typed their OWN prompt — the contextual hand-off (if
    // any) is superseded; discard it so it can't double-send later
    if (pendingPromptRef.current) {
      pendingPromptRef.current = null;
      setMessages((prev) => prev.map((m) => ({ ...m, pending: false })));
    }
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', text }]);
    setInput('');
    busyRef.current = true;
    setBusy(true);
    wsRef.current?.send(JSON.stringify({ type: 'prompt', text }));
  }, [input, connected]);

  // explicitly send a surfaced pending hand-off (no auto-fire)
  const confirmPending = useCallback(() => {
    const pending = pendingPromptRef.current;
    if (!pending || busyRef.current || !connected) return;
    pendingPromptRef.current = null;
    setMessages((prev) => prev.map((m) => (m.id === pending.id ? { ...m, pending: false } : m)));
    busyRef.current = true;
    setBusy(true);
    wsRef.current?.send(JSON.stringify({ type: 'prompt', text: pending.text }));
  }, [connected]);

  const discardPending = useCallback(() => {
    const pending = pendingPromptRef.current;
    if (!pending) return;
    pendingPromptRef.current = null;
    setMessages((prev) => prev.filter((m) => m.id !== pending.id));
  }, []);

  // HALT PATH (2026-08-13): ask the backend to kill the agent subprocess
  const stop = useCallback(() => {
    if (!busyRef.current || !connected) return;
    wsRef.current?.send(JSON.stringify({ type: 'cancel' }));
  }, [connected]);

  const [confirmNuke, setConfirmNuke] = useState(false);

  // NUKE (2026-08-13): force-kill the agent subprocess AND its whole
  // process tree (process-group SIGKILL — targeted by ownership, can
  // never touch the backend / VS Code / CLI). For when the gentle
  // Stop failed and Exa ignores everything. Always available while
  // connected — never disabled by the busy/freeze state. Two-click
  // confirm so a stray click can't nuke a working agent.
  const nuke = useCallback(() => {
    if (!connected) return;
    wsRef.current?.send(JSON.stringify({ type: 'nuke' }));
    setConfirmNuke(false);
  }, [connected]);

  const [copied, setCopied] = useState(false);
  // situation-aware header (2026-08-13): Diagnose is the CHAT-situation
  // button (hands the active session to Exa). When the panel opens from
  // another surface (Macros/Setup/Execution) the situation is the
  // hand-off — show Diagnose only for a plain (no-context) open so no
  // one presses a button meant for a situation they don't know about.
  const [openContext, setOpenContext] = useState<string | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<number | null>(null);
  // COPY (2026-08-13): the FULL transcript — user messages, assistant
  // text, AND every tool-call activity line (even ones scrolled off
  // screen — activity is captured in full, not truncated). Clipboard
  // write is fire-and-forget; if it fails (permissions), we still
  // surface the text in a prompt-style fallback... actually keep it
  // simple: navigator.clipboard with a visual 'Copied!' state.
  const copyTranscript = useCallback(async () => {
    const lines: string[] = [];
    for (const m of messages) {
      if (m.role === 'user') {
        lines.push(`🧑 You: ${m.text}`);
      } else {
        if (m.activity?.length) {
          lines.push('🛠 Exa tools:');
          for (const a of m.activity) lines.push(`   ${a}`);
        }
        if (m.text) lines.push(`🤖 Exa: ${m.text}`);
      }
    }
    if (lines.length === 0) return;
    const text = lines.join('\n');
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      // clipboard blocked (permissions) — fall back to a textarea
      // select-and-copy so the user still gets the output
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand('copy');
        setCopied(true);
      } catch {
        /* give up silently */
      }
      document.body.removeChild(ta);
    }
  }, [messages]);

  // THE CONFIRMATION REVERTS ON A TIMER AN EFFECT OWNS. A bare `setTimeout` in the handler
  // outlives the component — and its TEST environment: one fired after teardown and threw
  // `ReferenceError: window is not defined`, turning a fully-green ui gate into EXIT 1 with all
  // 983 tests passing (measured 2026-09-28). The cleanup clears it on unmount, and a second copy
  // restarts it rather than racing the first.
  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(timer);
  }, [copied]);

  // SAVE AS REPORT (Option B, 2026-08-13): persist the last assistant
  // reply (the report) into the workflow-product flow — it shows on
  // the Workflow Products page with the report-viewer modal and
  // survives the ephemeral panel chat. Deliberately saves the last
  // assistant message (the deliverable), not the whole transcript.
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const saveReport = useCallback(async () => {
    // find the LAST assistant message with real text (skip 'Stopped.')
    const last = [...messages].reverse().find(
      (m) => m.role === 'assistant' && m.text && !m.text.startsWith('⏹')
    );
    if (!last || !last.text) return;
    setSaveState('saving');
    try {
      const r = await fetch('/api/v1/external-agent/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: `Exa Report — ${new Date().toLocaleDateString()}`,
          body: last.text,
        }),
      });
      if (!r.ok) throw new Error(`save failed: ${r.status}`);
      setSaveState('saved');
      setTimeout(() => setSaveState('idle'), 2000);
    } catch {
      setSaveState('error');
      setTimeout(() => setSaveState('idle'), 2500);
    }
  }, [messages]);

  const clear = useCallback(() => {
    pendingPromptRef.current = null;
    setMessages([]);
  }, []);

  // Keyboard-takeover: hand the ACTIVE session to the consultant.
  // The Cogitate skills (orientation + analyze-logs) are EMBEDDED in
  // the prompt (consult-tool-injected delivery — Hermes' own skill
  // loader cannot see repo skills; we read them and include them).
  const diagnose = useCallback(async () => {
    if (!connected || busyRef.current) return;
    // Diagnose + a pending hand-off Send in the same tick would
    // double-send (the dialog_04 race) — the sync ref guards it, and
    // an explicit diagnose supersedes any contextual hand-off.
    if (pendingPromptRef.current) {
      pendingPromptRef.current = null;
      setMessages((prev) => prev.map((m) => ({ ...m, pending: false })));
    }
    const { activeSession, activeAgent } = useCognitiveHubStore.getState();
    const sessionLabel = activeSession?.title || activeSession?.id || 'the current session';
    const agentLabel = activeAgent?.name || 'the active agent';
    busyRef.current = true;
    setBusy(true);
    try {
      // fetch the skills to embed (best-effort; degrade to directives)
      const [orientation, analyzeLogs] = await Promise.all([
        fetch(`/api/v1/external-agent/skills/cogitate-orientation`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
        fetch(`/api/v1/external-agent/skills/cogitate-analyze-logs`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
      ]);
      const skillsBlock = [
        orientation ? `[SKILL: cogitate-orientation]\n${orientation.body}` : '[SKILL: cogitate-orientation — unavailable]',
        analyzeLogs ? `[SKILL: cogitate-analyze-logs]\n${analyzeLogs.body}` : '[SKILL: cogitate-analyze-logs — unavailable]',
      ].join('\n\n');

      const prompt =
        `You are consulting on the Cogitate codebase. Here are the ` +
        `Cogitate skills you must follow:\n\n${skillsBlock}\n\n` +
        `DIAGNOSTIC HANDOFF (read-only): the user is working with ` +
        `${agentLabel} in session "${sessionLabel}". They encountered a ` +
        `problem and handed you the keyboard to diagnose it.\n\n` +
        `Investigate using your tools: tail backend/logs/app.log, follow ` +
        `the analyze-logs triage method, check wiki/dev-notes/known-issues.md, ` +
        `query the session trace if useful. Work read-only — do NOT write, ` +
        `patch, or modify anything. Form a hypothesis, verify it against the ` +
        `actual evidence, and report: what you observed (with evidence), ` +
        `the likely root cause, and a proposed fix for the user to apply.`;
      setMessages((prev) => [...prev, {
        id: crypto.randomUUID(),
        role: 'user',
        text: `🔍 Diagnose: ${agentLabel} / ${sessionLabel}`,
      }]);
      wsRef.current?.send(JSON.stringify({ type: 'prompt', text: prompt }));
    } catch {
      clearBusy();
    }
  }, [connected, clearBusy]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50">
      {/* Drawer — overlay style: no mask, page stays interactive */}
      <div
        className="relative bg-base-100 shadow-xl w-[560px] max-w-[90vw] h-full overflow-hidden flex flex-col border-l border-base-300"
        role="dialog"
        aria-modal="false"
        aria-labelledby="agent-panel-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-base-300 flex-shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <h2 id="agent-panel-title" className="text-xl font-semibold text-base-content truncate">
              Exa
            </h2>
            <div
              className={`tooltip tooltip-bottom`}
              data-tip={connected ? 'Exa is ready' : 'Exa is not connected'}
            >
              <span className={`badge badge-sm ${connected ? 'badge-success' : 'badge-ghost'}`}>
                {connected ? 'connected' : 'offline'}
              </span>
            </div>
            <div
              className="tooltip tooltip-bottom"
              data-tip={fixMode ? 'Fix mode GRANTED — the consultant may write/patch/run modifying commands' : 'Read-only mode — the consultant diagnoses and proposes fixes'}
            >
              {/* THE MODE INDICATOR (2026-08-25, the user's ask): the
                  ghost badge read as plain text — the dot + label
                  reads as a status indicator. */}
              <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${fixMode ? 'text-warning' : 'text-readout'}`}>
                <span className={`w-2 h-2 rounded-full ${fixMode ? 'bg-warning animate-pulse' : 'bg-base-content/40'}`} />
                {fixMode ? 'fix granted' : 'read-only'}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {!openContext && (
              <div className="tooltip tooltip-bottom" data-tip="Hand the active session to Exa — read-only diagnosis">
                <button
                  className="btn btn-primary btn-sm"
                  onClick={diagnose}
                  disabled={!connected || busy}
                >
                  Diagnose
                </button>
              </div>
            )}
            {/* THE THREE-DOT ACTION MENU (2026-08-25, the user's
                call): the Copy/Save/Clear buttons move behind the
                ⋮ — the usual UI hack, the header de-clutters. */}
            <div className="dropdown dropdown-end">
              <div className="tooltip tooltip-bottom" data-tip="More actions">
                <button
                  tabIndex={0}
                  type="button"
                  className="btn btn-ghost btn-sm btn-circle"
                  aria-label="More actions"
                >
                  <MoreVertical className="w-4 h-4" />
                </button>
              </div>
              <ul tabIndex={0} className="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-44 text-xs">
                <li>
                  <button onClick={copyTranscript} disabled={messages.length === 0}>
                    {copied ? '✓ Copied' : 'Copy'}
                  </button>
                </li>
                <li>
                  <button
                    onClick={saveReport}
                    disabled={saveState === 'saving' || messages.length === 0}
                  >
                    {saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? '✓ Saved' : saveState === 'error' ? '✗ Failed' : 'Save'}
                  </button>
                </li>
                <li>
                  <button onClick={clear}>Clear</button>
                </li>
              </ul>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={close} aria-label="Close agent panel">
              ✕
            </button>
          </div>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 ? (
            <div className="text-center py-10 opacity-60 text-sm">
              <p>Exa — the external consulting agent.</p>
              <p className="text-xs mt-1">Ask it to investigate a problem — it checks the logs, traces, and system state.</p>
            </div>
          ) : (
            messages.map((m) => (
              <MessageRow
                key={m.id}
                m={m}
                onConfirm={confirmPending}
                onDiscard={discardPending}
              />
            ))
          )}
          {busy && (
            <div className="flex items-center gap-2 text-xs opacity-60">
              <span className="loading loading-spinner loading-xs" />
              thinking… · {Math.floor(elapsedSec / 60)}m {String(elapsedSec % 60).padStart(2, '0')}s
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t border-base-300 p-3 flex gap-2 flex-shrink-0">
          {/* THE MULTILINE INPUT (2026-08-25, the user's feedback):
              Enter sends, Shift+Enter inserts a newline — the
              textarea replaces the single-line input. */}
          <textarea
            className="textarea textarea-bordered textarea-sm flex-1 font-inherit resize-y min-h-[2.5rem] max-h-32"
            placeholder={connected ? 'Ask Exa…' : 'Connecting…'}
            value={input}
            disabled={!connected || busy}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          {busy ? (
            <div className="tooltip tooltip-top" data-tip="Stop Exa — gentle interrupt (any in-flight reply is lost if it escalates)">
              <button className="btn btn-error btn-sm" onClick={stop}>
                Stop
              </button>
            </div>
          ) : (
            <button className="btn btn-primary btn-sm" onClick={send} disabled={!connected || !input.trim()}>
              Send
            </button>
          )}
        </div>
        {/* Danger zone — Force Kill (never disabled by busy/freeze) */}
        {connected && (
          <div className="flex items-center justify-end px-3 pb-2">
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
                  ⚠ Force Kill
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default AgentPanel;
