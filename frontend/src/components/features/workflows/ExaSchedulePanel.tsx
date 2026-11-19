/**
 * ExaSchedulePanel — the Exa-managed-ops experiment (2026-08-18).
 *
 * "Tell Exa to set a schedule" — natural language → the typed
 * set-trigger-schedule tool. The panel streams the ACP events and
 * SHOWS THE TOOL CALLS (the guard: the user sees exactly what Exa
 * did). The tool cannot write a bad cron — the guard at the tool.
 *
 * Uses the same /api/v1/external-agent/ws bridge as the Agent
 * Panel / ConsultComposer.
 */

import { useEffect, useRef, useState } from 'react';

interface EventLine {
  kind: 'tool' | 'text' | 'status';
  text: string;
}

export default function ExaSchedulePanel({ onScheduled }: { onScheduled?: () => void }) {
  const [prompt, setPrompt] = useState('');
  const [busy, setBusy] = useState(false);
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<EventLine[]>([]);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const doneRef = useRef(false);
  const answerRef = useRef('');
  const [answer, setAnswer] = useState('');

  const close = () => { try { wsRef.current?.close(); } catch { /* noop */ } wsRef.current = null; };

  useEffect(() => () => close(), []);

  // Phase-2 verify: read the DB truth after a run (the trigger
  // list API) and append a VERIFIED line — the honest surface.
  const verifyAfterRun = async () => {
    try {
      const resp = await fetch('/api/v1/triggers?include_inactive=true', { headers: { accept: 'application/json' } });
      const data = await resp.json();
      const triggers = Array.isArray(data) ? data : (data as { triggers?: unknown[] }).triggers ?? [];
      const sched = (triggers as Array<{ name?: string; config?: { cron?: string } }>)
        .filter((t) => t.config && typeof t.config.cron === 'string')
        .map((t) => `${t.name ?? '?'}=${t.config?.cron}`)
        .join(' · ');
      setEvents((prev) => [...prev, {
        kind: 'status',
        text: `✔ VERIFIED (read-back): ${sched || 'no schedule triggers found'}`,
      }]);
    } catch (err) {
      setEvents((prev) => [...prev, { kind: 'status', text: '⚠ VERIFY FAILED: could not read back the triggers (' + String(err) + ')' }]);
    }
  };

  const run = () => {
    if (!prompt.trim() || busy) return;
    setBusy(true);
    setError(null);
    doneRef.current = false;
    setEvents([]);
    answerRef.current = '';
    setAnswer('');
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${window.location.host}/api/v1/external-agent/ws`);
    wsRef.current = ws;
    ws.onopen = () => {
      setConnected(true);
      // the experiment's prompt contract (2026-08-18): direct Exa to
      // the existing typed API — its proven capability (probe 1/2:
      // it drives live APIs). The validation lives server-side in
      // the endpoint; a bad cron cannot be written either way.
      const directive = [
        'You are operating the Cogitate workflow-automation schedule panel.',
        'The user wants: ' + prompt,
        'To set a trigger schedule, call the HTTP API: PUT /api/v1/triggers/{trigger_id}',
        'with JSON body {"config": {"cron": "<5-field cron>", "timezone": "UTC"}}.',
        'The trigger ids are visible in the app (e.g. monitor-rss-hourly, monitor-market-5min).',
        'The cron must have exactly 5 fields (minute hour day month weekday).',
        'For system knowledge, query the RAG first: call search-knowledge',
        'with your question before reading source files (it returns the',
        'relevant wiki pages with scores).',
        'IMPORTANT: change ONLY the config.cron field. Do NOT change the',
        'trigger name, description, or active state — the name must stay',
        'as-is (it does not reflect the schedule).',
        'Call the API with curl, then confirm the resulting cron to the user.',
      ].join('\n');
      ws.send(JSON.stringify({ type: 'prompt', text: directive }));
    };
    ws.onmessage = (ev: MessageEvent) => {
      let m: { type: string; text?: string; status?: string; message?: string; update?: Record<string, unknown> };
      try { m = JSON.parse(String(ev.data)); } catch { return; }
      if (m.type === 'tool_call') {
        // the raw ACP session/update — the shape varies by the agent;
        // extract the name defensively (content.name / toolCall.name /
        // top-level name) and fall back to the raw JSON so the user
        // ALWAYS sees the tool activity (the panel's guard)
        const u = (m.update ?? {}) as Record<string, unknown>;
        const content = (u.content ?? {}) as Record<string, unknown>;
        const tc = (content.toolCall ?? content.tool_call ?? content) as Record<string, unknown>;
        const name = (tc.name as string) ?? (content.name as string) ?? (u.name as string) ?? 'tool';
        const args = tc.arguments ?? content.arguments ?? content.input ?? {};
        const argStr = typeof args === 'string' ? args : JSON.stringify(args);
        setEvents((prev) => [...prev, {
          kind: 'tool',
          text: `🔧 ${name}(${(argStr || '').slice(0, 120)})` + (name === 'tool' ? ' — ' + JSON.stringify(u).slice(0, 80) : ''),
        }]);
      } else if (m.type === 'message' && m.text) {
        // COALESCE the text chunks (2026-08-18): one live line, not a
        // div per chunk — 900 chunks = 900 DOM nodes + a stuck render
        answerRef.current += m.text;
        setAnswer(answerRef.current);
      } else if (m.type === 'status' && m.status === 'error') {
        setError(m.message || 'The agent reported an error');
        setBusy(false);
        close();
      } else if (m.type === 'done') {
        setBusy(false);
        doneRef.current = true;
        setConnected(false);
        // only bump the refresh when the turn actually ENDED (the
        // usage event follows a completed run) — a failed/aborted
        // turn also emits done but should not claim a schedule set
        onScheduled?.();
        // THE CLAIMED/VERIFIED PATTERN (Phase 2, 2026-08-18): after
        // Exa's run, READ BACK the DB truth and show it — the panel
        // displays "Exa claimed (above) — verified: the DB now shows"
        verifyAfterRun();
        close();
      }
    };
    ws.onerror = () => { setError('Connection error'); setBusy(false); };
    ws.onclose = () => { setConnected(false); if (!doneRef.current) setBusy(false); };
  };

  return (
    <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)] mt-6">
      <div className="card-body gap-3">
        <div className="flex items-center justify-between">
          <h3 className="card-title text-base">🤖 Exa — set a schedule</h3>
          <span className={`badge badge-sm ${connected ? 'badge-success badge-outline' : 'badge-ghost'}`}>
            {connected ? 'connected' : 'idle'}
          </span>
        </div>
        <p className="text-sm text-readout">
          Ask Exa to configure a trigger's schedule in plain language. Exa uses the
          typed schedule tool — a bad cron is rejected, and you can see its tool calls below.
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') run(); }}
            placeholder="e.g. Set the RSS monitor to run every day at 9am"
            className="input input-bordered input-sm flex-1"
          />
          <button className="btn btn-sm btn-primary" onClick={run} disabled={busy || !prompt.trim()}>
            {busy ? 'Running…' : 'Run'}
          </button>
        </div>
        {error && <div className="alert alert-error py-2 text-sm">{error}</div>}
        {(events.length > 0 || answer) && (
          <div className="rounded-md bg-base-100 p-3 text-xs font-mono max-h-48 overflow-y-auto space-y-1">
            {events.map((e, i) => (
              <div key={i} className={e.kind === 'tool' ? 'text-primary' : 'text-readout'}>{e.text}</div>
            ))}
            {answer && (
              <div className="text-readout whitespace-pre-wrap break-words">{answer}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
