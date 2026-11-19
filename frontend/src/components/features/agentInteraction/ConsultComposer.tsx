/**
 * ConsultComposer — user-askable Consulting Agent surface.
 *
 * A popover in the chat input row: the user passes context (what
 * the agent observes) + a question; the external agent's answer
 * streams into the SESSION THREAD as a tool-role message (the
 * 'watch the dialog' part of the Consulting Agent design —
 * display-only, no session-store access).
 *
 * Uses the same /api/v1/external-agent/ws bridge as the Agent
 * Panel; Phase-1 per-prompt queueing means concurrent panel +
 * consult conversations serialize cleanly.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { ConversationMessage } from '@/types/agentInteraction'
import { BadgeButton } from '@/components/ui/BadgeButton';

interface ConsultComposerProps {
  sessionId?: string;
  onAddMessage: (sessionId: string, message: ConversationMessage) => void;
  onUpdateMessage: (sessionId: string, messageId: string, content: string) => void;
}

interface WsMsg {
  type: 'status' | 'message' | 'thought' | 'done';
  text?: string;
  status?: string;
  message?: string;
  reply?: string;
}

function askPrefix(context: string, question: string): string {
  return `🔍 **Consulting the external agent**\n\n**Context:** ${context || '*(none provided)*'}\n\n**Question:** ${question}`;
}

export function ConsultComposer({ sessionId, onAddMessage, onUpdateMessage }: ConsultComposerProps) {
  const [open, setOpen] = useState(false);
  const [context, setContext] = useState('');
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const msgIdRef = useRef<string | null>(null);
  const answerRef = useRef('');

  const close = useCallback(() => {
    setOpen(false);
    setContext('');
    setQuestion('');
  }, []);

  const ask = useCallback(() => {
    const q = question.trim();
    const c = context.trim();
    if (!q || busy) return;
    if (!sessionId) return;

    setBusy(true);
    const msgId = `consult-${Date.now()}`;
    msgIdRef.current = msgId;
    answerRef.current = '';

    // the consult request stays visible: the ask (context + question)
    // AND the streamed answer accumulate in one tool-role message so
    // the dialog is watchable in-session (the 'watch the dialog' goal)
    onAddMessage(sessionId, {
      id: msgId,
      role: 'tool',
      content: `🔍 **Consulting the external agent**\n\n**Context:** ${c || '*(none provided)*'}\n\n**Question:** ${q}\n\n**Answer:** `,
      timestamp: new Date(),
      tool_name: 'consult',
    });

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${window.location.host}/api/v1/external-agent/ws`);
    wsRef.current = ws;
    ws.onopen = () => {
      setConnected(true);
      ws.send(JSON.stringify({ type: 'prompt', text: `[Context]\n${c || '(none)'}\n\n[Question]\n${q}` }));
    };
    ws.onmessage = (ev: MessageEvent) => {
      let m: WsMsg;
      try { m = JSON.parse(String(ev.data)); } catch { return; }
      if (m.type === 'message') {
        answerRef.current += m.text || '';
        onUpdateMessage(sessionId, msgId, `${askPrefix(c, q)}\n\n**Answer:** ${answerRef.current}`);
      } else if (m.type === 'status' && m.status === 'inactive') {
        // THE GATE (2026-11-18): an inactive Exa answers with its state — the
        // consult bubble says why instead of spinning until the socket closes.
        onUpdateMessage(
          sessionId,
          msgId,
          `${askPrefix(c, q)}\n\n**Answer:** *(Exa is not active — ${m.message || 'activate it on the Exa page.'})*`
        );
        setBusy(false);
      } else if (m.type === 'status' && m.status === 'error') {
        onUpdateMessage(sessionId, msgId, `${askPrefix(c, q)}\n\n**Answer:** *(consult failed: ${m.message || 'unknown error'})*`);
        setBusy(false);
      } else if (m.type === 'done') {
        // prefer the backend's full reply (it includes any chunks the
        // browser may have missed); fall back to accumulated chunks
        const finalAnswer = (m.reply || answerRef.current || '');
        onUpdateMessage(sessionId, msgId, `${askPrefix(c, q)}\n\n**Answer:** ${finalAnswer}`);
        setBusy(false);
        close();
      }
    };
    ws.onerror = () => {
      onUpdateMessage(sessionId, msgId, '**Consult failed:** connection error');
      setBusy(false);
    };
    ws.onclose = () => {
      setConnected(false);
      setBusy(false);
    };
  }, [question, context, busy, sessionId, onAddMessage, onUpdateMessage, close]);

  useEffect(() => () => wsRef.current?.close(), []);

  // THE ESCAPE CANCEL (2026-08-25, the user's ask): Escape closes
  // the popover (and aborts an in-flight ask — the WS closes, the
  // busy flag clears).
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        close()
        setBusy(false)
        wsRef.current?.close()
        wsRef.current = null
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, close]);

  return (
    <div className="relative">
      {/* THE TOOLTIP: 'Ask Exa', opening ABOVE the button (the
          user's spec, 2026-08-25). The glyph: the chat-bubble icon
          (the emoji habit is banned in the UI). */}
      <div className="tooltip tooltip-top" data-tip="Ask Exa">
        <BadgeButton
          size="sm"
          onClick={() => setOpen((o) => !o)}
          aria-label="Ask Exa"
          className={open ? 'text-primary' : ''}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
        </BadgeButton>
      </div>

      {open && (
        <div className="absolute bottom-full left-0 mb-2 w-[380px] max-w-[85vw] bg-base-200 border border-base-300 rounded-lg shadow-xl p-3 z-50">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold">Ask Exa</span>
            <button className="btn btn-ghost btn-xs" onClick={close} aria-label="Close consult composer">✕</button>
          </div>

          <label className="label label-text text-xs" htmlFor="consult-context">Context (what the agent observes)</label>
          <textarea
            id="consult-context"
            className="textarea textarea-bordered textarea-sm w-full mb-2 font-mono text-xs"
            rows={3}
            value={context}
            placeholder="e.g. RSS digest workflow failed: file-not-found for outputs/report.md"
            onChange={(e) => setContext(e.target.value)}
          />

          <label className="label label-text text-xs" htmlFor="consult-question">Question</label>
          <textarea
            id="consult-question"
            className="textarea textarea-bordered textarea-sm w-full mb-2 font-mono text-xs"
            rows={2}
            value={question}
            placeholder="What could cause this and what should I check first?"
            onChange={(e) => setQuestion(e.target.value)}
          />

          <div className="flex items-center justify-end gap-2">
            {busy && <span className="text-xs opacity-60 flex items-center gap-1"><span className="loading loading-spinner loading-xs" /> consulting…</span>}
            {!busy && !connected && question.trim() && (
              <span className="text-xs opacity-50">connects when you ask</span>
            )}
            <button className="btn btn-primary btn-sm" onClick={ask} disabled={busy || !question.trim() || !sessionId}>
              Ask
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default ConsultComposer;
