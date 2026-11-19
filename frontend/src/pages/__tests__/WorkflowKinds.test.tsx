import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@/test/test-utils';
import WorkflowKinds from '../WorkflowKinds';

const kinds = [
  {
    name: 'monitor',
    description: 'Watches something on a schedule, analyzes what changed, and delivers a report.',
    builder_key: 'monitor_graph',
    product_type: 'report',
    inputs: [{ name: 'source_kind', type: 'string', description: '', required: false }],
  },
  {
    name: 'file-processing',
    description: 'Organizes and summarizes files.',
    builder_key: 'file_clerk_graph',
    product_type: 'file',
    inputs: [],
  },
];

describe('WorkflowKinds (Phase A)', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      const u = String(url);
      const filtered = u.includes('product_type=file')
        ? kinds.filter((k) => k.product_type === 'file')
        : u.includes('q=monitor')
          ? kinds.filter((k) => k.name.includes('monitor'))
          : kinds;
      return Promise.resolve({
        ok: true,
        json: async () => ({ kinds: filtered, total: filtered.length }),
      });
    }));
  });

  afterEach(() => vi.unstubAllGlobals());

  it('renders all kinds with their product badges', async () => {
    render(<WorkflowKinds />);
    expect(await screen.findByText('monitor')).toBeTruthy();
    expect(screen.getByText('file-processing')).toBeTruthy();
    // product badges (the filter dropdown also shows 'Report' — the
    // badge is the one inside the card)
    const monitorCard = screen.getByText('monitor').closest('.card')!;
    expect(monitorCard.textContent).toContain('Report');
    const fileCard = screen.getByText('file-processing').closest('.card')!;
    expect(fileCard.textContent).toContain('File');
  });

  it('shows the input declaration for kinds that have them', async () => {
    render(<WorkflowKinds />);
    await screen.findByText('monitor');
    expect(screen.getByText(/source_kind \(string/)).toBeTruthy();
  });

  it('filters by product type', async () => {
    render(<WorkflowKinds />);
    await screen.findByText('monitor');
    fireEvent.change(screen.getByLabelText('Product type'), { target: { value: 'file' } });
    await waitFor(() => expect(screen.queryByText('monitor')).toBeNull());
    // WAIT for the survivor too. The filtered list does not necessarily commit
    // on the same render that removed 'monitor' — an intermediate empty-list
    // render satisfies the wait above — so asserting immediately afterwards
    // races the second render. That race is what made this test flaky.
    expect(await screen.findByText('file-processing')).toBeTruthy();
  });
});
