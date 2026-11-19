/** The 3-way permission tier (2026-08-21): chat / fix / yolo.
 *
 * The selector replaces the old binary fix_mode toggle:
 * 1. The Permission tier card shows the three buttons + the badge
 *    for the CURRENT tier (per-edit approval / fix granted /
 *    unrestricted).
 * 2. Clicking a tier updates the local state (the badge + the
 *    description change) — Save persists via updateExternalAgentConfig
 *    with permission_tier.
 * 3. The legacy fix_mode bool is still accepted on load (compat).
 */

import { render, screen, fireEvent, waitFor } from '@/test/test-utils';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import AgentIntegration from '../AgentIntegration';

vi.mock('@/services/externalAgentService', () => ({
  getExternalAgentConfig: vi.fn().mockResolvedValue({
    command: 'hermes acp', cwd: '', permission_tier: 'chat', max_turn_seconds: 300,
  }),
  getExternalAgentStatus: vi.fn().mockResolvedValue({
    connected: false, command: 'hermes acp', cwd: '', permission_tier: 'chat',
  }),
  updateExternalAgentConfig: vi.fn().mockImplementation(async (patch: Record<string, unknown>) => ({
    command: 'hermes acp', cwd: '', permission_tier: patch.permission_tier ?? 'chat',
    max_turn_seconds: 300,
  })),
  restartExternalAgent: vi.fn().mockResolvedValue({ status: 'restarted' }),
}));

import { updateExternalAgentConfig, getExternalAgentConfig } from '@/services/externalAgentService';

describe('The tested brains are CONFIG (2026-10-10, the service-literals arc)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('the quick-switch offers what the config serves, not a bundled list', async () => {
    // The four brains used to be a `const` in the page, so a new brain meant a rebuild.
    // The API is the list's home now: whatever it serves is what the dropdown offers.
    (getExternalAgentConfig as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      command: 'hermes acp', cwd: '', permission_tier: 'chat', max_turn_seconds: 300,
      brains: [
        { label: 'Only one', model: 'some-vendor/some-model', provider: 'openrouter',
          base_url: 'https://example.invalid/v1', vision: true },
      ],
    });

    render(<AgentIntegration />);

    // BOTH consumers read it: the brain quick-switch AND the vision picker (vision: true).
    expect((await screen.findAllByText('Only one')).length).toBe(2);
  });

  it('a served brain that is not vision-capable stays out of the vision picker', async () => {
    (getExternalAgentConfig as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      command: 'hermes acp', cwd: '', permission_tier: 'chat', max_turn_seconds: 300,
      brains: [
        { label: 'Text only', model: 'some-vendor/text', provider: 'openrouter',
          base_url: 'https://example.invalid/v1', vision: false },
      ],
    });

    render(<AgentIntegration />);

    expect((await screen.findAllByText('Text only')).length).toBe(1);
  });
});

describe('The permission tier (3-way selector)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows the three tiers + the chat badge by default', async () => {
    render(<AgentIntegration />);
    expect(await screen.findByText('Permission tier')).toBeTruthy();
    expect(screen.getByText('Chat approval')).toBeTruthy();
    expect(screen.getByText('Fix mode')).toBeTruthy();
    expect(screen.getByText('YOLO')).toBeTruthy();
    expect(screen.getByText('per-edit approval')).toBeTruthy();
  });

  it('clicking YOLO flips the badge + the description (local state)', async () => {
    render(<AgentIntegration />);
    fireEvent.click(await screen.findByText('YOLO'));
    expect(await screen.findByText('unrestricted')).toBeTruthy();
    // the risk framing is visible (the break button + the audit)
    expect(screen.getByText(/break button/)).toBeTruthy();
    expect(screen.getByText(/audited/)).toBeTruthy();
    // NOT persisted until Save
    expect(updateExternalAgentConfig).not.toHaveBeenCalled();
  });

  it('clicking Fix mode shows the scoped description', async () => {
    render(<AgentIntegration />);
    fireEvent.click(await screen.findByText('Fix mode'));
    expect(await screen.findByText('fix granted')).toBeTruthy();
    expect(screen.getByText(/workspace/)).toBeTruthy();
  });

  it('Save persists the selected tier', async () => {
    render(<AgentIntegration />);
    fireEvent.click(await screen.findByText('YOLO'));
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => {
      expect(updateExternalAgentConfig).toHaveBeenCalledWith(
        expect.objectContaining({ permission_tier: 'yolo' })
      );
    });
  });

  it('accepts the legacy fix_mode bool on load (compat)', async () => {
    const { getExternalAgentConfig } = await import('@/services/externalAgentService');
    (getExternalAgentConfig as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      command: 'hermes acp', cwd: '', fix_mode: true, max_turn_seconds: 300,
    });
    render(<AgentIntegration />);
    expect(await screen.findByText('fix granted')).toBeTruthy();
  });
});
