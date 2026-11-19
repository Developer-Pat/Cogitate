/**
 * The provider-health cell on /agent-profiles.
 *
 * The point of this surface is that the chat badge only ever showed a
 * truncated tooltip. So the tests assert the thing that was missing: the
 * error is READABLE, and it can be COPIED — the raw string, not the
 * tidied one, because the raw string is the evidence.
 */

import { render, screen } from '@/test/test-utils';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import AgentHealthCell from '../AgentHealthCell';
import { cleanErrorMessage } from '@/utils/cleanErrorMessage';

const RAW =
  'MidStreamFallbackError: litellm.MidStreamFallbackError: litellm.APIError: ' +
  'APIError: OpenrouterException - Message: Upstream error from DeepInfra: ' +
  "Assistant tool call function.arguments must be valid JSON., Metadata: " +
  "{'error_type': 'provider_unavailable'}, User ID:  Original exception: " +
  'APIError: litellm.APIError: APIError: OpenrouterException - Message: ' +
  'Upstream error from DeepInfra: Assistant tool call function.arguments ' +
  'must be valid JSON.';

const mk = (over: Partial<Parameters<typeof AgentHealthCell>[0]['health'] & object> = {}) => ({
  status: 'ok' as const,
  consecutive_failures: 0,
  last_error: null as string | null,
  last_failure_at: null as string | null,
  failures_7d: 0,
  ...over,
});

describe('cleanErrorMessage', () => {
  it('drops the duplicated tail litellm appends', () => {
    const out = cleanErrorMessage(RAW);
    expect(out).not.toContain('Original exception:');
    // the same failure said once, not twice
    expect(out.match(/must be valid JSON/g)?.length).toBe(1);
  });

  it('strips the litellm prefix chain so a non-expert can read it', () => {
    const out = cleanErrorMessage(RAW);
    expect(out).not.toContain('litellm.');
    expect(out).toContain('Assistant tool call function.arguments must be valid JSON');
  });

  it('keeps the actual upstream reason', () => {
    expect(cleanErrorMessage(RAW)).toContain('Upstream error from DeepInfra');
  });
});

describe('AgentHealthCell', () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it('says so when the response carried no health at all', () => {
    render(<AgentHealthCell health={undefined} agentName="Probe" />);
    expect(screen.getByText('—')).toBeTruthy();
  });

  it('shows OK for a healthy agent and offers nothing to copy', () => {
    render(<AgentHealthCell health={mk()} agentName="Healthy" />);
    expect(screen.getByText('OK')).toBeTruthy();
    expect(screen.queryByText('Copy error')).toBeNull();
  });

  it('shows the failure count for a warned agent', () => {
    render(
      <AgentHealthCell
        health={mk({ status: 'warn', failures_7d: 4, last_error: RAW, last_failure_at: '2026-09-14 00:19:01' })}
        agentName="Bob"
      />,
    );
    expect(screen.getByText('Warnings')).toBeTruthy();
    expect(screen.getByText('4/7d')).toBeTruthy();
  });

  it('makes the error READABLE — the whole reason this surface exists', () => {
    render(
      <AgentHealthCell
        health={mk({ status: 'warn', failures_7d: 4, last_error: RAW, last_failure_at: '2026-09-14 00:19:01' })}
        agentName="Bob"
      />,
    );
    // rendered cleaned, not the raw wall
    const shown = screen.getByText(/Assistant tool call function\.arguments must be valid JSON/);
    expect(shown.textContent).not.toContain('Original exception:');
    // and the failure time is visible for context
    expect(screen.getByText('2026-09-14 00:19:01')).toBeTruthy();
  });

  it('copies the RAW error, not the tidied one', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    render(
      <AgentHealthCell
        health={mk({ status: 'fail', failures_7d: 9, last_error: RAW })}
        agentName="Bob"
      />,
    );
    await userEvent.click(screen.getByText('Copy error'));

    expect(writeText).toHaveBeenCalledWith(RAW);
    expect(await screen.findByText('Copied to clipboard')).toBeTruthy();
  });

  it('keeps the trigger visible rather than hover-only', () => {
    // The house rule: no hover-hidden controls. A failure badge that only
    // appears on hover is a failure nobody sees.
    const { container } = render(
      <AgentHealthCell health={mk({ status: 'fail', failures_7d: 9, last_error: RAW })} agentName="Bob" />,
    );
    const hidden = container.querySelector('.opacity-0');
    expect(hidden).toBeNull();
  });

  describe('compact (the sidebar list form)', () => {
    it('renders a quiet dot for a healthy agent instead of the word OK', () => {
      render(<AgentHealthCell health={mk()} agentName="Healthy" compact />);
      expect(screen.queryByText('OK')).toBeNull();
      // still VISIBLE — a marker, not a hover-only affordance
      expect(screen.getByLabelText('Provider health: OK')).toBeTruthy();
    });

    it('does NOT suppress a problem — trouble still shows a marker and the count', () => {
      render(
        <AgentHealthCell
          health={mk({ status: 'warn', failures_7d: 4, last_error: RAW, last_failure_at: '2026-09-14 00:19:01' })}
          agentName="Bob"
          compact
        />,
      );
      // compact drops the WORDS (they do not fit the sidebar) but keeps the
      // signal: the marker, the count, and the full error behind a click.
      expect(screen.getByText('4')).toBeTruthy();
      expect(screen.queryByText('Warnings')).toBeNull();
      expect(screen.queryByText('4/7d')).toBeNull();
      expect(screen.getByText('Copy error')).toBeTruthy();
    });

    it('carries the full meaning in its accessible name, since the words are gone', () => {
      render(
        <AgentHealthCell
          health={mk({ status: 'warn', failures_7d: 4, last_error: RAW })}
          agentName="Bob"
          compact
        />,
      );
      const el = screen.getByLabelText(/Provider health: Warnings, 4 failures/);
      expect(el).toBeTruthy();
    });

    it('keeps the full wording where there IS room (the table column)', () => {
      render(
        <AgentHealthCell
          health={mk({ status: 'warn', failures_7d: 4, last_error: RAW })}
          agentName="Bob"
        />,
      );
      expect(screen.getByText('Warnings')).toBeTruthy();
      expect(screen.getByText('4/7d')).toBeTruthy();
    });

    it('still says so when the response carried no health', () => {
      render(<AgentHealthCell health={undefined} agentName="Probe" compact />);
      expect(screen.getByText('—')).toBeTruthy();
    });
  });
});
