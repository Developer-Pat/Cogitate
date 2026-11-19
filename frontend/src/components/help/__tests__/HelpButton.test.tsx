/**
 * HelpButton component tests.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HelpButton } from '../HelpButton';

describe('HelpButton', () => {
  it('renders with default props', () => {
    render(<HelpButton />);
    expect(screen.getByLabelText('Help')).toBeDefined();
  });

  it('renders with context prop', () => {
    render(<HelpButton context="chat" />);
    expect(screen.getByLabelText('Help')).toBeDefined();
  });

  it('dispatches open-help-modal event on click', () => {
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent');
    render(<HelpButton context="chat" />);
    fireEvent.click(screen.getByLabelText('Help'));
    expect(dispatchSpy).toHaveBeenCalled();
    const event = dispatchSpy.mock.calls[0][0] as CustomEvent;
    expect(event.detail.context).toBe('chat');
    dispatchSpy.mockRestore();
  });

  it('uses help_page default context when none provided', () => {
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent');
    render(<HelpButton />);
    fireEvent.click(screen.getByLabelText('Help'));
    const event = dispatchSpy.mock.calls[0][0] as CustomEvent;
    expect(event.detail.context).toBe('help_page');
    dispatchSpy.mockRestore();
  });
});
