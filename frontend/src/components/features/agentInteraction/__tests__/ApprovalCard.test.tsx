/** The ApprovalCard resolved states (2026-08-21): after a
 * decision, the card collapses to ONE line — "Permission granted"
 * (green ✓) or "Permission denied" (red ✕) — with the title kept
 * and the buttons gone.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ResponseStream from '../ResponseStream';

const pendingMsg = {
  id: 'exa-approval-1',
  role: 'tool',
  tool_name: 'approval',
  content: '**Exa requests permission to edit:**\n\n`Approve edit: /tmp/x.py`',
  timestamp: new Date(),
  metadata: {
    request_id: '999',
    request: {
      request_id: '999',
      title: 'Approve edit: /tmp/x.py',
      options: [{ option_id: 'allow_once', name: 'Allow edit' }, { option_id: 'deny', name: 'Deny' }],
      content: [{ type: 'text', text: 'old -> new' }],
    },
  },
};

function makeMessages(overrides: Record<string, unknown>) {
  return [{
    ...pendingMsg,
    metadata: { ...pendingMsg.metadata, ...overrides },
  } as any]; // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
}

describe('The ApprovalCard', () => {
  it('shows the pending card with the buttons + the diff', () => {
    render(<ResponseStream isStreaming={false} messages={makeMessages({})} />);
    expect(screen.getByText('Allow edit')).toBeTruthy();
    expect(screen.getByText('Deny')).toBeTruthy();
    expect(screen.getByText('old -> new')).toBeTruthy();
  });

  it('collapses to ONE line "Permission granted" (green) after approval', () => {
    render(<ResponseStream isStreaming={false} messages={makeMessages({ resolved: true })} />);
    expect(screen.getByText('Permission granted')).toBeTruthy();
    expect(screen.queryByText('Allow edit')).toBeNull();
    expect(screen.queryByText('old -> new')).toBeNull();
    // the title is kept (the audit trail)
    expect(screen.getByText(/Approve edit/)).toBeTruthy();
  });

  it('collapses to ONE line "Permission denied" (red) after denial', () => {
    render(<ResponseStream isStreaming={false} messages={makeMessages({ resolved: false })} />);
    expect(screen.getByText('Permission denied')).toBeTruthy();
    expect(screen.queryByText('Allow edit')).toBeNull();
    expect(screen.queryByText('Deny')).toBeNull();
  });

  it('the pending card still calls onApprove with the option', () => {
    const onApprove = vi.fn();
    render(<ResponseStream isStreaming={false} messages={makeMessages({})} onExaApproval={onApprove} />);
    fireEvent.click(screen.getByText('Allow edit'));
    expect(onApprove).toHaveBeenCalledWith('999', 'allow_once');
  });
});
