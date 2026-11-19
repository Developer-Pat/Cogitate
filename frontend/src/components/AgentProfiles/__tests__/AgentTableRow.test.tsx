/**
 * The sidebar table row.
 *
 * The contract worth pinning: the description is a HOVER TOOLTIP, not visible
 * text. Rendering it inline made the row wide enough to push the Actions column
 * behind a horizontal scrollbar, so it must never come back as a text node.
 */

import { render, screen } from '@/test/test-utils';
import { describe, it, expect, vi } from 'vitest';
import AgentTableRow from '../AgentTableRow';
import type { Profile } from '@/services/domain/ProfileService';

const DESC = "Bob, a news scout and reporter — the user's eyes on the world.";

const mkProfile = (over: Partial<Profile> = {}): Profile =>
  ({
    id: '19',
    name: 'Bob',
    description: DESC,
    image_url: null,
    provider: 'openrouter',
    model: 'inclusionai/ling-3.0-flash',
    ...over,
  }) as Profile;

const renderRow = (profile: Profile) =>
  render(
    <table>
      <tbody>
        <AgentTableRow
          profile={profile}
          isSelected={false}
          isRowSelected={false}
          onSelect={vi.fn()}
          onSelectProfile={vi.fn()}
          onDuplicate={vi.fn()}
          isLoading={false}
        />
      </tbody>
    </table>,
  );

// The row also contains AgentTableActions, which has its OWN tooltip
// (data-tip="Actions"). Scope every query to the name cell so a neighbour's
// tooltip can never satisfy these assertions.
const nameCell = (container: HTMLElement) =>
  container.querySelector('tbody td:nth-child(2)');

describe('AgentTableRow', () => {
  it('shows the agent name', () => {
    renderRow(mkProfile());
    expect(screen.getByText('Bob')).toBeTruthy();
  });

  it('carries the description as a data-tip tooltip', () => {
    const { container } = renderRow(mkProfile());
    const tip = nameCell(container)?.querySelector('[data-tip]');
    expect(tip?.getAttribute('data-tip')).toBe(DESC);
  });

  it('uses the DaisyUI tooltip classes, opening upward', () => {
    const { container } = renderRow(mkProfile());
    const tip = nameCell(container)?.querySelector('[data-tip]');
    expect(tip?.className).toContain('tooltip');
    expect(tip?.className).toContain('tooltip-top');
  });

  it('stacks above the table header, which is sticky z-10 with an opaque background', () => {
    // Without an explicit z-index the header paints over the tooltip's first
    // line: a two-line tip then reads as its tail ("eyes on the world.").
    const { container } = renderRow(mkProfile());
    const tip = nameCell(container)?.querySelector('[data-tip]');
    const z = Number((tip?.className.match(/\bz-(\d+)\b/) || [])[1] || 0);
    expect(z).toBeGreaterThan(10);
  });

  it('constrains the bubble width so a long tip wraps instead of running off', () => {
    const { container } = renderRow(mkProfile());
    const tip = nameCell(container)?.querySelector('[data-tip]');
    // an arbitrary value, not a named token: `xs` is a 4px spacing token here
    expect(tip?.className).toContain('before:max-w-[20rem]');
    expect(tip?.className).not.toContain('max-w-xs');
  });

  it('does NOT render the description as visible text', () => {
    // the whole point: inline text widened the row and hid Actions
    renderRow(mkProfile());
    expect(screen.queryByText(DESC, { exact: false })).toBeNull();
  });

  it('omits the tooltip entirely when there is no description', () => {
    const { container } = renderRow(mkProfile({ description: '' }));
    expect(nameCell(container)?.querySelector('[data-tip]')).toBeNull();
    expect(nameCell(container)?.querySelector('.tooltip')).toBeNull();
    // and the name still renders
    expect(screen.getByText('Bob')).toBeTruthy();
  });

  it('puts the tooltip on a wrapping element, not on the truncating child', () => {
    // `truncate` is overflow:hidden, which would clip the bubble
    const { container } = renderRow(mkProfile());
    const tip = nameCell(container)?.querySelector('[data-tip]');
    expect(tip?.className).not.toContain('truncate');
    expect(tip?.querySelector('.truncate')).toBeTruthy();
  });
});
