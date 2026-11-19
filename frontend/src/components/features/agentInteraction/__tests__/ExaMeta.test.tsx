/** The Exa bubble instrumentation (2026-08-22): the done event
 * carries usage/elapsed/model; the assistant bubble's footer
 * renders the meta — model badge, turn time, context usage.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ResponseStream from '../ResponseStream';

const baseMsg = {
  id: 'exa-reply-1',
  role: 'assistant',
  content: 'the answer',
  timestamp: new Date(),
};

describe('The Exa bubble meta (instrumentation)', () => {
  it('renders nothing extra without the meta', () => {
    render(<ResponseStream isStreaming={false} messages={[baseMsg as any]} />); // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
    expect(screen.queryByText(/deepseek|ox-alpha|nemotron/)).toBeNull();
  });

  it('renders ONE model badge (via the footer), turn time, and context usage', () => {
    const msg = {
      ...baseMsg,
      metadata: {
        exa_meta: true,
        model: 'deepseek/deepseek-v4-flash',
        elapsed_ms: 42300,
        ctx: { size: 65536, used: 18300 },
      },
    };
    render(<ResponseStream isStreaming={false} messages={[msg as any]} />); // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
    // the model badge appears EXACTLY once (the footer's
    // metadata.model path — the exa_meta block renders only
    // elapsed + ctx; the user caught the double badge). The
    // pre-existing badge shows the full model string.
    expect(screen.getAllByText('deepseek/deepseek-v4-flash')).toHaveLength(1);
    expect(screen.getByText('42.3s')).toBeTruthy();
    expect(screen.getByText('18k/66k')).toBeTruthy();
  });
});
