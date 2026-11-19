/**
 * The provider-health widget for the Basic Info tab.
 *
 * The two things worth pinning down:
 *  - BLANK when there is nothing to report. An unsaved profile has no
 *    usage_logs behind it, and a cheerful green badge for "we know nothing"
 *    would be a lie about state.
 *  - With room to spare, the error is READABLE in place (no click needed),
 *    while Copy still hands over the raw original.
 */

import { render, screen } from '@/test/test-utils';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import ProfileHealthWidget from '../ProfileHealthWidget';

const RAW =
  'MidStreamFallbackError: litellm.MidStreamFallbackError: litellm.APIError: ' +
  'APIError: OpenrouterException - Message: Upstream error from DeepInfra: ' +
  "Assistant tool call function.arguments must be valid JSON., Metadata: " +
  "{'error_type': 'provider_unavailable'}, User ID:  Original exception: " +
  'APIError: litellm.APIError: APIError: OpenrouterException - Message: ' +
  'Upstream error from DeepInfra: Assistant tool call function.arguments ' +
  'must be valid JSON.';

const mk = (over = {}) => ({
  status: 'ok' as 'ok' | 'warn' | 'fail',
  consecutive_failures: 0,
  last_error: null as string | null,
  last_failure_at: null as string | null,
  failures_7d: 0,
  ...over,
});

describe('ProfileHealthWidget', () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it('renders NOTHING when there is no health (an unsaved profile)', () => {
    const { container } = render(<ProfileHealthWidget health={undefined} />);
    expect(container.textContent).toBe('');
    expect(screen.queryByText('Provider health')).toBeNull();
  });

  it('treats a null health the same as absent', () => {
    const { container } = render(<ProfileHealthWidget health={null} />);
    expect(container.textContent).toBe('');
  });

  it('reports a healthy profile plainly, with no error to copy', () => {
    render(<ProfileHealthWidget health={mk()} />);
    expect(screen.getByText('Provider health')).toBeTruthy();
    expect(screen.getByText('Healthy')).toBeTruthy();
    expect(screen.getByText('0 failures in the last 7 days')).toBeTruthy();
    expect(screen.getByText('No provider failures in the last 7 days.')).toBeTruthy();
    expect(screen.queryByText('Copy error')).toBeNull();
  });

  it('shows the failure count, the time, and the error IN PLACE (no click)', () => {
    render(
      <ProfileHealthWidget
        health={mk({ status: 'warn', failures_7d: 4, last_error: RAW, last_failure_at: '2026-09-14 00:19:01' })}
      />,
    );
    expect(screen.getByText('Warnings')).toBeTruthy();
    expect(screen.getByText('4 failures in the last 7 days')).toBeTruthy();
    expect(screen.getByText('Last failure 2026-09-14 00:19:01')).toBeTruthy();
    // the whole reason there is room here: the error is readable without a click
    const shown = screen.getByText(/Assistant tool call function\.arguments must be valid JSON/);
    expect(shown.textContent).not.toContain('Original exception:');
    expect(shown.textContent).not.toContain('litellm.');
  });

  it('marks a failing profile distinctly', () => {
    render(<ProfileHealthWidget health={mk({ status: 'fail', failures_7d: 9, last_error: RAW })} />);
    expect(screen.getByText('Failing')).toBeTruthy();
  });

  it('copies the RAW error, not the tidied one', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    render(<ProfileHealthWidget health={mk({ status: 'fail', failures_7d: 9, last_error: RAW })} />);
    await userEvent.click(screen.getByText('Copy error'));

    expect(writeText).toHaveBeenCalledWith(RAW);
    expect(await screen.findByText('Copied to clipboard')).toBeTruthy();
  });
});
