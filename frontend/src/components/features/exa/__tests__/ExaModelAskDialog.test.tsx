/**
 * The activation ask renders ONE question with this install's chat model already named, and its
 * press is the accept. The markup lives in one component because the Exa chat page and the
 * integrations page both ask it — the v0.1.1 release run found the chat page not asking at all.
 */

import { render, screen, fireEvent } from '@/test/test-utils';
import { describe, expect, it, vi } from 'vitest';

import ExaModelAskDialog from '../ExaModelAskDialog';

const offer = { provider: 'deepseek', model: 'deepseek/deepseek-flash', base_url: 'https://api.deepseek.com' };

const dialog = () => document.querySelector<HTMLDialogElement>('dialog.modal');

describe('ExaModelAskDialog', () => {
  it('is closed when there is nothing to ask', () => {
    render(<ExaModelAskDialog offer={null} onAccept={vi.fn()} onDismiss={vi.fn()} />);
    expect(dialog()?.open).toBe(false);
  });

  it('names the offered model and provider', () => {
    render(<ExaModelAskDialog offer={offer} onAccept={vi.fn()} onDismiss={vi.fn()} />);
    expect(dialog()?.open).toBe(true);
    expect(screen.getByText('deepseek/deepseek-flash')).toBeTruthy();
    expect(screen.getByText('deepseek')).toBeTruthy();
  });

  it('the press is the accept', () => {
    const onAccept = vi.fn();
    render(<ExaModelAskDialog offer={offer} onAccept={onAccept} onDismiss={vi.fn()} />);
    fireEvent.click(screen.getByText('Use this model'));
    expect(onAccept).toHaveBeenCalledTimes(1);
  });

  it('can be declined without writing anything', () => {
    const onAccept = vi.fn();
    const onDismiss = vi.fn();
    render(<ExaModelAskDialog offer={offer} onAccept={onAccept} onDismiss={onDismiss} />);
    fireEvent.click(screen.getByText('Choose on the card'));
    expect(onDismiss).toHaveBeenCalledTimes(1);
    expect(onAccept).not.toHaveBeenCalled();
  });
});
