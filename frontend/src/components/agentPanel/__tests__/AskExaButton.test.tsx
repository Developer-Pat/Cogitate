/** AskExaButton — dispatches open-agent-panel with the context payload. */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AskExaButton } from '../AskExaButton';

describe('AskExaButton', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the button with label', () => {
    render(<AskExaButton context="macros" />);
    expect(screen.getByText('Ask Exa')).toBeTruthy();
  });

  it('dispatches open-agent-panel with the context in detail', () => {
    const dispatched: CustomEvent[] = [];
    const spy = vi.spyOn(window, 'dispatchEvent').mockImplementation((e: Event) => {
      dispatched.push(e as CustomEvent);
      return true;
    });
    render(<AskExaButton context="macros" />);
    fireEvent.click(screen.getByText('Ask Exa'));
    expect(spy).toHaveBeenCalled();
    const ev = dispatched.find((e) => e.type === 'open-agent-panel');
    expect(ev).toBeTruthy();
    expect((ev!.detail as { context: string }).context).toBe('macros');
  });
});
