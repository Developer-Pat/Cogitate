import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@/test/test-utils';
import WorkflowProducts from '../WorkflowProducts';

// stub the products fetch — the page loads products.json via the API
const product = {
  product_type: 'exa_report',
  title: 'Exa Report — test',
  body: '# Report\n\nSome **markdown** content.',
  source_template: 'exa-panel',
  created_at: '2026-08-14T06:00:00.000Z',
  delivered_at: '2026-08-14T06:00:00.000Z',
};

describe('WorkflowProducts modals', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ products: [product], total: 1 }),
    }));
  });

  it('renders the report viewer WITHOUT the DaisyUI modal-box trap (opacity-0 class)', async () => {
    render(<WorkflowProducts />);
    const viewBtn = await screen.findByText('View');
    fireEvent.click(viewBtn);
    await waitFor(() => expect(screen.getByText('markdown')).toBeTruthy());
    // the fixed container must NOT carry the modal-box class (it is
    // opacity:0 by DaisyUI default — the mask-without-box bug)
    const box = document.querySelector('.max-w-3xl');
    expect(box).toBeTruthy();
    expect(box!.className).not.toContain('modal-box');
  });

  it('shows "Exa Report" in the type filter', async () => {
    render(<WorkflowProducts />);
    await screen.findByText('View');
    const option = document.querySelector('option[value="exa_report"]');
    expect(option).toBeTruthy();
    expect(option!.textContent).toBe('Exa Report');
  });
});
