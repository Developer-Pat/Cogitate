/** THE ACTIVATION ASK (2026-11-20).
 *
 * Activating provisions Exa's home — its skills and the provider keys — and flips the
 * switch. It does NOT choose a model: a home with no model answers as plain Hermes,
 * which is the failure the provisioning fixed. So the answer says `needs_model`, and
 * the page asks ONE question with this install's chat model already named. The press
 * is the accept; nothing is written without it.
 *
 * A `<dialog>` keeps its content in the DOM when closed, so these tests read the
 * element's `open` flag rather than looking for the text.
 */

import { render, screen, fireEvent, waitFor } from '@/test/test-utils';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// The offer helper (`seededFileCount`) is real — only the network calls are mocked.
vi.mock('@/services/externalAgentService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/externalAgentService')>();
  return {
    ...actual,
    getExternalAgentConfig: vi.fn().mockResolvedValue({
      command: 'hermes acp', cwd: '', permission_tier: 'chat', max_turn_seconds: 300,
    }),
    getExternalAgentStatus: vi.fn().mockResolvedValue({
      connected: false, enabled: false, command: 'hermes acp', cwd: '', permission_tier: 'chat',
    }),
    getExaModel: vi.fn().mockResolvedValue({ model: '', provider: '', offer: null }),
    updateExaModel: vi.fn().mockResolvedValue({ model: 'deepseek-flash', provider: 'deepseek' }),
    updateExternalAgentConfig: vi.fn(),
    restartExternalAgent: vi.fn(),
    activateExa: vi.fn(),
    deactivateExa: vi.fn(),
  };
});

import AgentIntegration from '../AgentIntegration';
import { activateExa, updateExaModel } from '@/services/externalAgentService';

const ask = () => document.querySelector<HTMLDialogElement>('dialog.modal');

const activation = (over: Record<string, unknown>) => ({
  enabled: true,
  runnable: true,
  blocked_reason: null,
  provisioned: ['skills seeded into .hermes/skills/cogitate (3 file(s) added)'],
  model: null,
  provider: null,
  needs_model: true,
  offer: { provider: 'deepseek', model: 'deepseek-flash', base_url: null },
  ...over,
});

describe('the activation ask', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('a home with no model is asked about, with this install’s chat model named', async () => {
    (activateExa as ReturnType<typeof vi.fn>).mockResolvedValue(activation({}));

    render(<AgentIntegration />);
    fireEvent.click(await screen.findByText('Activate Exa'));

    await waitFor(() => expect(ask()?.open).toBe(true));
    expect(screen.getByText(/Exa is on — it has no model yet/)).toBeTruthy();
    expect(screen.getByText('deepseek-flash')).toBeTruthy();
  });

  it('the press writes exactly the offered model — the one accept', async () => {
    (activateExa as ReturnType<typeof vi.fn>).mockResolvedValue(activation({}));

    render(<AgentIntegration />);
    fireEvent.click(await screen.findByText('Activate Exa'));
    await waitFor(() => expect(ask()?.open).toBe(true));

    fireEvent.click(screen.getByText('Use this model'));

    await waitFor(() =>
      expect(updateExaModel).toHaveBeenCalledWith(
        expect.objectContaining({ model: 'deepseek-flash', provider: 'deepseek' })
      )
    );
    expect(ask()?.open).toBe(false);
  });

  it('a home that already has a model is not asked — and nothing is overwritten', async () => {
    (activateExa as ReturnType<typeof vi.fn>).mockResolvedValue(
      activation({ needs_model: false, model: 'deepseek/x', provider: 'deepseek' })
    );

    render(<AgentIntegration />);
    fireEvent.click(await screen.findByText('Activate Exa'));

    await waitFor(() => expect(ask()).toBeTruthy());
    expect(ask()?.open).toBe(false);
    expect(updateExaModel).not.toHaveBeenCalled();
  });

  it('with nothing on the install to offer, it says so instead of asking', async () => {
    (activateExa as ReturnType<typeof vi.fn>).mockResolvedValue(
      activation({ offer: null, provisioned: [] })
    );

    render(<AgentIntegration />);
    fireEvent.click(await screen.findByText('Activate Exa'));

    await waitFor(() => expect(screen.getByText(/it has no model/)).toBeTruthy());
    expect(ask()?.open).toBe(false);
  });
});
