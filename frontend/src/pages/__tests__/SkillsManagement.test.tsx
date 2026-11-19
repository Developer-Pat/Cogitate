import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@/test/test-utils';
import SkillsManagement from '../SkillsManagement';

const curatedSkill = {
  name: 'cogitate-create-agent',
  description: 'Create and configure agents',
  category: 'cogitate',
  tags: ['agents', 'creation'],
  version: '1.0.0',
  author: 'Cogitate Team',
  related_skills: [],
  curated: true,
  valid: true,
  errors: [],
  warnings: [],
  path: '/skills/cogitate/create-agent/SKILL.md',
};

const agentSkill = {
  name: 'troubleshooting.skill',
  description: '',
  category: 'system-manager',
  tags: [],
  version: '',
  author: '',
  related_skills: [],
  curated: false,
  valid: true,
  errors: [],
  warnings: [],
  path: '/agents/system-manager/skills/troubleshooting.skill.md',
};

describe('SkillsManagement', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (String(url).includes('/api/v1/skills/in-use')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignments: [
              { skill: 'troubleshooting.skill', agents: ['system-manager'], sources: { file: ['system-manager'], derived: [] } },
            ],
            total: 1,
          }),
        });
      }
      if (String(url).includes('/api/v1/skills')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ skills: [curatedSkill, agentSkill], total: 2 }),
        });
      }
      return Promise.resolve({ ok: false, json: async () => ({}) });
    }));
  });

  afterEach(() => vi.unstubAllGlobals());

  it('renders both curated and agent-local skills with their badges', async () => {
    render(<SkillsManagement />);
    await screen.findByText('cogitate-create-agent');
    expect(screen.getByText('troubleshooting.skill')).toBeTruthy();
    // curated badge + agent badge both present
    expect(screen.getByText('curated')).toBeTruthy();
    expect(screen.getByText('agent')).toBeTruthy();
  });

  it('shows the in-use badge for skills assigned to an agent', async () => {
    render(<SkillsManagement />);
    await screen.findByText('troubleshooting.skill');
    expect(screen.getByText(/agent system-manager/)).toBeTruthy();
  });

  it('filters by curated status', async () => {
    render(<SkillsManagement />);
    await screen.findByText('cogitate-create-agent');
    // select "Curated" -> only the curated skill remains
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'true' } });
    await waitFor(() => expect(screen.queryByText('troubleshooting.skill')).toBeNull());
    expect(screen.getByText('cogitate-create-agent')).toBeTruthy();
  });

  it('searches by name', async () => {
    render(<SkillsManagement />);
    await screen.findByText('cogitate-create-agent');
    fireEvent.change(screen.getByPlaceholderText(/Search name/), { target: { value: 'troubleshooting' } });
    await waitFor(() => expect(screen.queryByText('cogitate-create-agent')).toBeNull());
    expect(screen.getByText('troubleshooting.skill')).toBeTruthy();
  });
});
