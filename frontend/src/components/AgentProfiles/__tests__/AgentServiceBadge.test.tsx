/**
 * The current-availability badge on /agent-profiles (phase 6, G5-F2's agent half).
 *
 * The tests pin the two things the ruling asks for and the one thing it forbids:
 *
 *  - an agent whose service cannot answer is REPORTED (the plan's requirement);
 *  - the copy keeps the CURRENT question apart from the HISTORY badge's — "cannot run now" is not
 *    "failing lately", and a reader must be able to tell which badge says which;
 *  - and the readout NEVER invents a verdict: `available === null` ("not checked") draws nothing,
 *    because calling a working agent broken is the failure mode this whole arc exists to remove.
 */

import { render, screen } from '@/test/test-utils';
import { describe, it, expect } from 'vitest';
import AgentServiceBadge from '../AgentServiceBadge';

const down = (over: Partial<NonNullable<Parameters<typeof AgentServiceBadge>[0]['availability']>> = {}) => ({
  state: 'down' as const,
  available: false as boolean | null,
  reason: 'the local server is not running and no local server answers',
  checked_at: '2026-10-05T12:23:06.609Z',
  provider: 'llama',
  model: 'Bonsai-27B-Q1_0.gguf',
  ...over,
});

describe('AgentServiceBadge', () => {
  it('draws nothing when the response carried no availability', () => {
    const { container } = render(<AgentServiceBadge />);
    expect(container).toBeEmptyDOMElement();
  });

  it('draws NOTHING when nothing was checked — a readout never invents a verdict', () => {
    const { container } = render(
      <AgentServiceBadge availability={down({ state: 'unknown', available: null, reason: 'not checked' })} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('draws nothing on a healthy row in the sidebar — the norm is not a badge', () => {
    const { container } = render(
      <AgentServiceBadge availability={down({ state: 'available', available: true })} compact />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('reports an agent that cannot run, VISIBLY (never hover-only)', () => {
    render(<AgentServiceBadge availability={down()} agentName="Lois" compact />);

    expect(screen.getByText('Cannot run')).toBeInTheDocument();
    // The words are on the element, not only in a tooltip.
    expect(screen.getByLabelText(/Lois: cannot run now/)).toBeInTheDocument();
  });

  it('keeps the CURRENT question apart from the HISTORY badge', () => {
    render(<AgentServiceBadge availability={down()} agentName="Lois" compact />);

    // The health cell's vocabulary must NOT be what this badge says.
    expect(screen.queryByText('Failing')).not.toBeInTheDocument();
    expect(screen.queryByText('Warnings')).not.toBeInTheDocument();
    expect(screen.queryByText('OK')).not.toBeInTheDocument();
    // …and its own copy says WHEN the reading is from, which a history badge cannot.
    expect(screen.getByLabelText(/Checked 2026-10-05T12:23:06.609Z/)).toBeInTheDocument();
  });

  it('carries the service, the reason and the check time in the detail form', () => {
    render(<AgentServiceBadge availability={down()} agentName="Lois" />);

    expect(screen.getByText('Service availability')).toBeInTheDocument();
    expect(screen.getByText('Cannot run')).toBeInTheDocument();
    expect(screen.getByText('llama/Bonsai-27B-Q1_0.gguf')).toBeInTheDocument();
    expect(screen.getByText(/the local server is not running/)).toBeInTheDocument();
    expect(screen.getByText(/Checked 2026-10-05T12:23:06.609Z/)).toBeInTheDocument();
  });

  it('says so when the service can run', () => {
    render(<AgentServiceBadge availability={down({ state: 'available', available: true, reason: 'it answers' })} />);

    expect(screen.getByText('Can run')).toBeInTheDocument();
    expect(screen.getByText(/can run now/)).toBeInTheDocument();
  });

  it('reports a switched-off capability in its own words', () => {
    render(
      <AgentServiceBadge
        availability={down({ state: 'disabled', available: false, reason: "the 'chat' capability is switched off" })}
      />
    );

    expect(screen.getByText(/the chat capability is switched off/)).toBeInTheDocument();
  });
});
