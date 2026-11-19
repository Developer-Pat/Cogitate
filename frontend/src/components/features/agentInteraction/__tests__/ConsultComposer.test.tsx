/** ConsultComposer — renders, opens, and streams into the session. */

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ConsultComposer } from '../ConsultComposer';

class MockWebSocket {  url: string;

  static instances: MockWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  sent: string[] = [];
  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this);
  }
  send(data: string) { this.sent.push(data); }
  close() {}
  // test helpers
  static openAll() { MockWebSocket.instances.forEach((i) => i.onopen?.()); }
  static emitAll(data: string) { MockWebSocket.instances.forEach((i) => i.onmessage?.({ data })); }
}

describe('ConsultComposer', () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    (global as unknown as { WebSocket: unknown }).WebSocket = MockWebSocket;
  });

  it('renders the consult button and opens the composer', () => {
    render(<ConsultComposer sessionId="s1" onAddMessage={vi.fn()} onUpdateMessage={vi.fn()} />);
    const btn = screen.getByLabelText('Ask Exa');
    expect(btn).toBeTruthy();
    fireEvent.click(btn);
    expect(screen.getByText('Ask Exa')).toBeTruthy();
  });

  it('asks, streams into the session, and closes on done', async () => {
    const add = vi.fn();
    const update = vi.fn();
    render(<ConsultComposer sessionId="s1" onAddMessage={add} onUpdateMessage={update} />);
    fireEvent.click(screen.getByLabelText('Ask Exa'));

    fireEvent.change(screen.getByLabelText(/Context/i), { target: { value: 'agent sees X' } });
    fireEvent.change(screen.getByLabelText(/Question/i), { target: { value: 'why?' } });
    fireEvent.click(screen.getByText('Ask'));

    // the user-visible consult message is added to the session
    expect(add).toHaveBeenCalledWith('s1', expect.objectContaining({ role: 'tool', tool_name: 'consult' }));

    act(() => { MockWebSocket.openAll(); });
    // stream a chunk then done — content accumulates the ask + answer
    act(() => { MockWebSocket.emitAll(JSON.stringify({ type: 'message', text: 'because' })); });
    expect(update).toHaveBeenCalledWith(
      's1',
      expect.any(String),
      expect.stringContaining('**Answer:** because')
    );

    act(() => { MockWebSocket.emitAll(JSON.stringify({ type: 'done', reply: 'because the file is missing' })); });
    await waitFor(() =>
      expect(update).toHaveBeenCalledWith(
        's1',
        expect.any(String),
        expect.stringContaining('because the file is missing')
      )
    );
    // the ask (context + question) stays visible in the final content
    const finalCall = update.mock.calls[update.mock.calls.length - 1][2] as string;
    expect(finalCall).toContain('**Question:** why?');
    expect(finalCall).toContain('**Context:** agent sees X');
  });
});

it('closes the popover on the Escape key (the 2026-08-25 cancel)', () => {
  render(<ConsultComposer sessionId="s1" onAddMessage={vi.fn()} onUpdateMessage={vi.fn()} />);
  fireEvent.click(screen.getByLabelText('Ask Exa'));
  // the popover is open (the header is visible)
  expect(screen.getByText('Ask Exa')).toBeTruthy();
  fireEvent.keyDown(window, { key: 'Escape' });
  // the popover closes — the header is gone
  expect(screen.queryByText(/Context/i)).toBeNull();
});
