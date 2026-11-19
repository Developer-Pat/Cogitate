/**
 * AgentPanel halt path (INCIDENT 2026-08-13):
 * 1. The Stop button is NOT disabled by the busy/input-freeze state —
 *    it replaces Send while busy, has no disabled prop, and stays
 *    clickable even though the input textarea is disabled.
 * 2. Clicking Stop sends {"type":"cancel"} over the WS.
 * 3. The "cancelled" status clears busy and appends "⏹ Stopped.".
 */

import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AgentPanel } from '../AgentPanel';

class FakeWebSocket {  url: string;

  static instances: FakeWebSocket[] = [];
  static OPEN = 1;
  static CLOSED = 3;
  sent: string[] = [];
  readyState: number = FakeWebSocket.OPEN;
  onopen: (() => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onclose: (() => void) | null = null;
  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.readyState = FakeWebSocket.CLOSED;
  }
  // test helpers
  open() {
    act(() => this.onopen?.());
  }
  emit(msg: unknown) {
    act(() => this.onmessage?.({ data: JSON.stringify(msg) } as MessageEvent));
  }
}

describe('AgentPanel halt path', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('Stop button is clickable while busy even though the input is frozen', async () => {
    render(<AgentPanel />);
    act(() => window.dispatchEvent(new CustomEvent('open-agent-panel')));
    const ws = FakeWebSocket.instances[0];
    ws.open(); // connected
    ws.emit({ type: 'status', status: 'ready', sessionId: 's1' });

    // type + send a prompt -> busy
    const textbox = screen.getByPlaceholderText(/Ask Exa|Connecting/);
    fireEvent.change(textbox, { target: { value: 'hello' } });
    fireEvent.click(screen.getByText('Send'));

    // busy: Send is replaced by Stop; input is DISABLED (frozen)
    expect(screen.getByText('Stop')).toBeTruthy();
    expect((screen.getByPlaceholderText(/Ask Exa|Connecting/) as HTMLInputElement).disabled).toBe(true);

    // the Stop button itself must NOT be disabled — this is the whole point
    const stopBtn = screen.getByText('Stop').closest('button') as HTMLButtonElement;
    expect(stopBtn.disabled).toBe(false);

    // click Stop -> cancel message sent
    fireEvent.click(stopBtn);
    expect(ws.sent).toContain(JSON.stringify({ type: 'cancel' }));

    // server confirms cancelled -> busy clears, note appears
    ws.emit({ type: 'status', status: 'cancelled' });
    await waitFor(() => expect(screen.getByText(/⏹ Stopped/)).toBeTruthy());
    expect(screen.getByText('Send')).toBeTruthy();
  });

  it('Force Kill is available while busy (not frozen) and sends nuke with two-click confirm', async () => {
    render(<AgentPanel />);
    act(() => window.dispatchEvent(new CustomEvent('open-agent-panel')));
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.emit({ type: 'status', status: 'ready', sessionId: 's1' });

    // type + send -> busy (input frozen, Stop shown)
    const textbox = screen.getByPlaceholderText(/Ask Exa|Connecting/);
    fireEvent.change(textbox, { target: { value: 'hello' } });
    fireEvent.click(screen.getByText('Send'));
    expect(screen.getByText('Stop')).toBeTruthy();

    // Force Kill is present and clickable — never disabled by busy
    const nukeBtn = screen.getByText('⚠ Force Kill').closest('button') as HTMLButtonElement;
    expect(nukeBtn.disabled).toBe(false);
    // two-click confirm: first click asks, does NOT send
    fireEvent.click(nukeBtn);
    expect(screen.getByText('Yes, kill')).toBeTruthy();
    expect(ws.sent.some((s) => s.includes('nuke'))).toBe(false);
    // confirm -> nuke sent
    fireEvent.click(screen.getByText('Yes, kill'));
    expect(ws.sent.some((s) => s.includes('nuke'))).toBe(true);
  });

  it('Copy captures the full transcript including tool activity', async () => {
    render(<AgentPanel />);
    act(() => window.dispatchEvent(new CustomEvent('open-agent-panel')));
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.emit({ type: 'status', status: 'ready', sessionId: 's1' });

    // user message + assistant text + tool activity + done
    act(() => {
      ws.onmessage?.({ data: JSON.stringify({ type: 'message', text: 'investigating…' }) } as MessageEvent);
    });
    act(() => {
      ws.onmessage?.({ data: JSON.stringify({ type: 'tool_call', update: { kind: 'terminal', title: 'grep logs' } }) } as MessageEvent);
    });
    act(() => {
      ws.onmessage?.({ data: JSON.stringify({ type: 'tool_call', update: { kind: 'terminal', title: 'sqlite query' } }) } as MessageEvent);
    });
    act(() => {
      ws.onmessage?.({ data: JSON.stringify({ type: 'message', text: ' all done' }) } as MessageEvent);
    });
    act(() => {
      ws.onmessage?.({ data: JSON.stringify({ type: 'done', reply: 'investigating… all done' }) } as MessageEvent);
    });

    // stub clipboard
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    fireEvent.click(screen.getByText('Copy'));
    await waitFor(() => expect(writeText).toHaveBeenCalled());
    const copied = writeText.mock.calls[0][0] as string;
    expect(copied).toContain('investigating…');
    expect(copied).toContain('grep logs');
    expect(copied).toContain('sqlite query');
    expect(copied).toContain('all done');
  });

  it('Diagnose is hidden when the panel opens with a context hand-off', async () => {
    // opened from Macros -> the situation is the hand-off; Diagnose
    // (a Chat-situation button) must not be shown
    render(<AgentPanel />);
    act(() => window.dispatchEvent(new CustomEvent('open-agent-panel', { detail: { context: 'macros' } })));
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.emit({ type: 'status', status: 'ready', sessionId: 's1' });
    await waitFor(() => expect(screen.getByText(/Ask Exa: Macros/)).toBeTruthy());
    expect(screen.queryByText('Diagnose')).toBeNull();
  });

  it('Diagnose is available on a plain (no-context) open and supersedes nothing — ONE prompt', async () => {
    render(<AgentPanel />);
    act(() => window.dispatchEvent(new CustomEvent('open-agent-panel')));
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.emit({ type: 'status', status: 'ready', sessionId: 's1' });
    await waitFor(() => expect(screen.getByText('Diagnose')).toBeTruthy());
    // Diagnose then Send in the same tick — busyRef blocks the second
    fireEvent.click(screen.getByText('Diagnose'));
    expect(screen.queryAllByText('Send').length).toBe(0); // busy -> Stop
    await waitFor(() => expect(ws.sent.filter((m) => m.includes('"type":"prompt"')).length).toBe(1));
    expect(ws.sent.find((m) => m.includes('"type":"prompt"'))!).toContain('DIAGNOSTIC HANDOFF');
  });

  it('macros hand-off embeds the macro-management skill', async () => {
    // stub the skill endpoint
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ name: 'cogitate-macro-management', body: 'SKILL BODY: macro system' }),
    }));
    render(<AgentPanel />);
    act(() => window.dispatchEvent(new CustomEvent('open-agent-panel', { detail: { context: 'macros' } })));
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.emit({ type: 'status', status: 'ready', sessionId: 's1' });
    // the pending hand-off appears; its Send carries the skill
    await waitFor(() => expect(screen.getByText(/Ask Exa: Macros/)).toBeTruthy());
    await new Promise((r) => setTimeout(r, 50)); // let the fetch resolve
    expect(ws.sent.filter((m) => m.includes('"type":"prompt"')).length).toBe(0); // still no auto-fire
    // confirm: the sent prompt includes the skill body
    fireEvent.click(screen.getAllByText('Send')[0]); // the hand-off's inline Send
    await waitFor(() => expect(ws.sent.filter((m) => m.includes('"type":"prompt"')).length).toBe(1));
    const sent = ws.sent.find((m) => m.includes('"type":"prompt"'))!;
    expect(sent).toContain('cogitate-macro-management');
    expect(sent).toContain('SKILL BODY: macro system');
    vi.unstubAllGlobals();
  });

  it.each([
    // label matches the panel's ternary: macros→Macros, setup→Setup,
    // execution→Workflow Execution, else the raw ctx ('agents'→'Agents'
    // via the capitalized label helper, 'workflow' stays lowercase)
    ['agents', 'cogitate-create-agent', /Ask Exa: agents/, 'SKILL BODY: agent creation'],
    ['workflow', 'cogitate-create-workflow', /Ask Exa: workflow/, 'SKILL BODY: workflow creation'],
  ])('context hand-off embeds its skill (%s)', async (ctx, skillName, label, body) => {
    try {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ name: skillName, body }),
      }));
      render(<AgentPanel />);
      act(() => window.dispatchEvent(new CustomEvent('open-agent-panel', { detail: { context: ctx } })));
      const ws = FakeWebSocket.instances[0];
      ws.open();
      ws.emit({ type: 'status', status: 'ready', sessionId: 's1' });
      await waitFor(() => expect(screen.getByText(label)).toBeTruthy());
      await new Promise((r) => setTimeout(r, 50)); // let the fetch resolve
      expect(ws.sent.filter((m) => m.includes('"type":"prompt"')).length).toBe(0); // no auto-fire
      fireEvent.click(screen.getAllByText('Send')[0]); // the hand-off's inline Send
      await waitFor(() => expect(ws.sent.filter((m) => m.includes('"type":"prompt"')).length).toBe(1));
      const sent = ws.sent.find((m) => m.includes('"type":"prompt"'))!;
      expect(sent).toContain(skillName);
      expect(sent).toContain(body);
    } finally {
      vi.unstubAllGlobals(); // always restore — a leaked fetch mock
      // breaks later tests (the Save report test stubs its own fetch)
    }
  });

  it('typed prompt auto-discards pending hand-off — ONE send only (no queue)', async () => {
    render(<AgentPanel />);
    act(() => window.dispatchEvent(new CustomEvent('open-agent-panel', { detail: { context: 'macros' } })));
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.emit({ type: 'status', status: 'ready', sessionId: 's1' });
    // pending hand-off is surfaced
    expect(screen.getByText(/Ask Exa: Macros/)).toBeTruthy();
    expect(ws.sent.filter((m) => m.includes('"type":"prompt"')).length).toBe(0); // NO auto-fire
    // user types their own prompt and sends
    const input = screen.getByPlaceholderText(/Ask Exa/);
    fireEvent.change(input, { target: { value: 'system status please' } });
    // Enter in the input fires the MAIN send path
    fireEvent.keyDown(input, { key: 'Enter' });
    // exactly ONE prompt sent (the typed one), hand-off discarded
    const prompts = ws.sent.filter((m) => m.includes('"type":"prompt"'));
    expect(prompts.length).toBe(1);
    expect(prompts[0]).toContain('system status please');
    expect(prompts[0]).not.toContain('MACROS');
  });

  it('renders assistant markdown as a table (not raw pipes)', async () => {
    render(<AgentPanel />);
    act(() => window.dispatchEvent(new CustomEvent('open-agent-panel')));
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.emit({ type: 'status', status: 'ready', sessionId: 's1' });
    act(() => {
      ws.onmessage?.({
        data: JSON.stringify({
          type: 'message',
          text: '| Call | latency |\n|---|---|\n| #1 | 4.4s |',
        }),
      } as MessageEvent);
    });
    // the markdown table renders as an actual <table>, not raw pipe text
    const table = document.querySelector('.not-prose table');
    expect(table).toBeTruthy();
    expect(table?.textContent).toContain('4.4s');
    expect(screen.queryByText('| Call | latency |')).toBeNull();
  });

  it('Save persists the last assistant report (not the transcript)', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
    vi.stubGlobal('fetch', fetchMock);
    render(<AgentPanel />);
    act(() => window.dispatchEvent(new CustomEvent('open-agent-panel')));
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.emit({ type: 'status', status: 'ready', sessionId: 's1' });
    // assistant report + a stopped marker AFTER it
    act(() => {
      ws.onmessage?.({ data: JSON.stringify({ type: 'message', text: '# Status\n\nAll healthy.' }) } as MessageEvent);
    });
    act(() => {
      ws.onmessage?.({ data: JSON.stringify({ type: 'status', status: 'cancelled' }) } as MessageEvent);
    });
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([u]) => String(u).includes('/report'))).toBe(true)
    );
    const [url, init] = fetchMock.mock.calls.find(([u]) => String(u).includes('/report'))!;
    expect(url).toBe('/api/v1/external-agent/report');
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.title).toContain('Exa Report');
    expect(body.body).toContain('All healthy.');
    expect(body.body).not.toContain('⏹');
    // the '✓ Saved' indicator re-renders after the report POST
    // resolves — waitFor it (the POST promise resolves on a later
    // microtask; racing it is what made this test flaky in full runs)
    await waitFor(() => expect(screen.getByText('✓ Saved')).toBeTruthy());
    vi.unstubAllGlobals();
  });

  it('time_limit status shows WHY the run stopped (not just Stopped)', async () => {
    render(<AgentPanel />);
    act(() => window.dispatchEvent(new CustomEvent('open-agent-panel')));
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.emit({ type: 'status', status: 'ready', sessionId: 's1' });
    act(() => {
      ws.onmessage?.({ data: JSON.stringify({ type: 'message', text: 'working…' }) } as MessageEvent);
    });
    // the backend auto-stops the run at the cap
    act(() => {
      ws.onmessage?.({ data: JSON.stringify({ type: 'status', status: 'time_limit', message: 'Reached the 300s time limit — the run was stopped.' }) } as MessageEvent);
    });
    expect(screen.getByText(/Time limit reached/)).toBeTruthy();
    expect(screen.getByText(/300s time limit/)).toBeTruthy();
    expect(screen.queryByText('⏹ Stopped.')).toBeNull(); // NOT a user stop
  });

  it('shows the elapsed timer while busy', async () => {
    vi.useFakeTimers();
    render(<AgentPanel />);
    act(() => window.dispatchEvent(new CustomEvent('open-agent-panel')));
    const ws = FakeWebSocket.instances[0];
    ws.open();
    ws.emit({ type: 'status', status: 'ready', sessionId: 's1' });
    // send a real prompt → busy becomes true → timer starts
    fireEvent.change(screen.getByPlaceholderText('Ask Exa…'), { target: { value: 'hi' } });
    fireEvent.click(screen.getByText('Send'));
    const spinner = screen.getByText(/thinking/);
    expect(spinner.textContent).toMatch(/0m 0\d?s/);
    act(() => { vi.advanceTimersByTime(65000); });
    expect(spinner.textContent).toMatch(/1m 05s/);
    vi.useRealTimers();
  });

  it('auto-reconnects after the WS closes', async () => {
    render(<AgentPanel />);
    act(() => window.dispatchEvent(new CustomEvent('open-agent-panel')));
    const ws1 = FakeWebSocket.instances[0];
    ws1.open();
    // the socket dies (backend restart): readyState -> CLOSED, then
    // onclose fires. The panel's guard checks readyState > OPEN, so
    // the close MUST set readyState first (real browser behavior).
    ws1.close();
    act(() => {
      ws1.onclose?.();
    });
    // backoff: first retry after ~1s
    await new Promise((r) => setTimeout(r, 1200));
    const ws2 = FakeWebSocket.instances[1];
    expect(ws2).toBeTruthy(); // a NEW WebSocket was created
  });

  it('pending hand-off requires explicit Send — no auto-fire', async () => {
    render(<AgentPanel />);
    act(() => window.dispatchEvent(new CustomEvent('open-agent-panel')));
    const ws = FakeWebSocket.instances[0];
    ws.open();
    // open with a macros context (already open; re-dispatch with context)
    act(() => window.dispatchEvent(new CustomEvent('open-agent-panel', { detail: { context: 'macros' } })));
    ws.emit({ type: 'status', status: 'ready', sessionId: 's1' });

    // the pending prompt is surfaced, NOT sent automatically
    await waitFor(() => expect(screen.getByText('🔍 Ask Exa: Macros')).toBeTruthy());
    expect(ws.sent.length).toBe(0); // nothing auto-fired

    // discard it — nothing is sent
    fireEvent.click(screen.getByText('Discard'));
    expect(ws.sent.length).toBe(0);
  });
});
