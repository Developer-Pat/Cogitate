/**
 * HelpModal wikilink conversion tests.
 *
 * The help surface has its own converter (processWikilinks), separate from the
 * wiki viewer's. Two real corpus forms used to render as literal [[...]] text
 * here: an aliased link ([[help/tools|Tool Management]] — six help pages use
 * this form) and any target with a space in it. Both are measured by
 * scripts/analysis/wiki_corpus_census.py.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { HelpModal } from '../HelpModal';

vi.mock('mermaid', () => ({
  default: { initialize: vi.fn().mockResolvedValue(undefined), render: vi.fn().mockResolvedValue({ svg: '' }) },
}));

const HELP_CONTENT = [
  '## Tools',
  '',
  'See [[help/tools|Tool Management]] and [[dev-notes/architecture/Paths and Path Resolution]].',
].join('\n');

function openModal(context = 'chat') {
  window.dispatchEvent(new CustomEvent('open-help-modal', {
    detail: { context, documentTitle: 'Test', timestamp: 0 },
  }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('HelpModal wikilink conversion', () => {
  it('converts an aliased wikilink and records its alias as the label', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/wiki') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ tree: [], pages: [] }) });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          pages: [{ slug: 'chat', title: 'Chat', category: 'chat', content: HELP_CONTENT }],
        }),
      });
    }));

    render(<HelpModal />);
    openModal('chat');

    const link = await screen.findByRole('link', { name: 'Tool Management' }, { timeout: 3000 });
    expect(link).toHaveAttribute('href', '/wiki/help/tools');
  });

  it('converts a wikilink whose path contains a space', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/wiki') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ tree: [], pages: [] }) });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          pages: [{ slug: 'chat', title: 'Chat', category: 'chat', content: HELP_CONTENT }],
        }),
      });
    }));

    render(<HelpModal />);
    openModal('chat');

    const link = await screen.findByRole('link', { name: 'Paths and Path Resolution' }, { timeout: 3000 });
    expect(link).toHaveAttribute('href', '/wiki/dev-notes/architecture/Paths%20and%20Path%20Resolution');
  });
});
