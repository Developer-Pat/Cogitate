import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import QuickStats from '../QuickStats';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});
const wrap = (ui: React.ReactElement) => (
  <QueryClientProvider client={queryClient}>
    <MemoryRouter>{ui}</MemoryRouter>
  </QueryClientProvider>
);

// the hooks hit backend endpoints — stub fetch for all three
describe('QuickStats', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    }));
  });

  afterEach(() => vi.unstubAllGlobals());

  it('renders the four stat tiles', async () => {
    render(wrap(<QuickStats />));
    expect(await screen.findByText('System Status')).toBeTruthy();
    expect(screen.getByText('CPU Usage')).toBeTruthy();
    expect(screen.getByText('Memory Usage')).toBeTruthy();
    expect(screen.getByText('Recent Logs')).toBeTruthy();
  });

  it('tiles are summary-only (the System Info page was removed — no link)', async () => {
    render(wrap(<QuickStats />));
    await screen.findByText('System Status');
    // no links: the monitoring page is gone, the tiles are pure summary
    const links = screen.queryAllByRole('link');
    expect(links.length).toBe(0);
  });
});
