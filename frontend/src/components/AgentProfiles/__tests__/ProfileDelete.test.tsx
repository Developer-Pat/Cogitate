/** The lifecycle UI (agent-lifecycle Phase D): the delete dialog
 * discloses the BOM, the delete reports the archive.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ProfileDetail from '../ProfileDetail';
import { MemoryRouter } from 'react-router-dom';

describe('The delete dialog (BOM disclosure)', () => {
  const profile = {
    id: '42',
    name: 'Probe Agent',
    description: 'd',
    provider: 'deepseek',
    model: 'deepseek-v4-flash',
    system_prompt: '',
    tools: ['web-search', 'file-read'],
    memory: true,
    workspace_key: 'probe-agent',
    cognitive_profile_name: 'chat-skill',
    cognitive_profile_depth: 'shallow',
  };

  const report = {
    deleted: true,
    agent_id: 42,
    agent_name: 'Probe Agent',
    bom: { tool_links: 2, grants: 0, collections: 1, chat_sessions: 0 },
    archived_path: '/home/user/Projects/cogitate/agents/.archived/probe-agent-20260816_000000',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('opens the BOM dialog with the footprint disclosed', async () => {
    const onDelete = vi.fn().mockResolvedValue(report);
    render(
      <MemoryRouter><ProfileDetail
        profile={profile as never}
        action="edit"
        onSave={vi.fn()}
        onCancel={vi.fn()}
        onDelete={onDelete}
        isSaving={false}
      /></MemoryRouter>
    );

    // the depth marker — the honest family readout (the hardcoded
    // 'deep' chip is gone; the chip now shows the derived family)
    expect(screen.getByText('shallow')).toBeTruthy();

    fireEvent.click(screen.getByText('Delete Profile'));

    // the dialog discloses what will be removed
    expect(await screen.findByText('Delete Probe Agent?')).toBeTruthy();
    expect(screen.getByText(/2 tool link\(s\)/)).toBeTruthy();
    expect(screen.getByText(/Workspace folder/)).toBeTruthy();
  });

  it('confirming deletes + shows the result report (the archive)', async () => {
    const onDelete = vi.fn().mockResolvedValue(report);
    render(
      <MemoryRouter><ProfileDetail
        profile={profile as never}
        action="edit"
        onSave={vi.fn()}
        onCancel={vi.fn()}
        onDelete={onDelete}
        isSaving={false}
      /></MemoryRouter>
    );

    fireEvent.click(screen.getByText('Delete Profile'));
    // the dialog's confirm — there are two "Delete Profile" buttons
    const dialog = await screen.findByText('Delete Probe Agent?');
    const dialogBtns = dialog.closest('.card');
    const confirm = [...(dialogBtns?.querySelectorAll('button') ?? [])].find(
      b => b.textContent?.includes('Delete Profile')
    );
    fireEvent.click(confirm!);

    await waitFor(() => expect(onDelete).toHaveBeenCalledWith('42'));

    // the result report: the archive path is shown
    expect(await screen.findByText('Profile deleted')).toBeTruthy();
    expect(screen.getByText(/Removed: 2 tool link\(s\), 1 collection\(s\)/)).toBeTruthy();
    expect(screen.getByText(/Archived at:/)).toBeTruthy();
  });
});
