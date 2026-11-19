/** MarkdownText — markdown for the small surfaces, and the TWO link rules.
 *
 * The rules pinned here:
 *  - markdown is actually rendered (a link is a link, not characters)
 *  - an INTERNAL path rides the router, so the app navigates in place
 *  - anything else opens a new tab with `noopener noreferrer`, so a
 *    model-written link can never navigate the SPA away from the user's page
 *    nor reach window.opener
 *  - raw HTML is NOT rendered (react-markdown escapes it)
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { MarkdownText } from '../MarkdownText';

const renderMd = (md: string) =>
  render(
    <MemoryRouter>
      <MarkdownText>{md}</MarkdownText>
    </MemoryRouter>
  );

describe('MarkdownText', () => {
  it('renders markdown, not the literal punctuation', () => {
    renderMd('**bold** and a list:\n\n- one\n- two');
    expect(screen.getByText('bold').tagName).toBe('STRONG');
    expect(screen.getAllByRole('listitem').length).toBe(2);
  });

  it('renders an internal path as a router link (in place, no target)', () => {
    renderMd('See [the logs](/logs).');
    const a = screen.getByRole('link', { name: 'the logs' });
    expect(a.getAttribute('href')).toBe('/logs');
    // internal links must NOT open a new tab — the app navigates in place
    expect(a.getAttribute('target')).toBeNull();
  });

  it('renders an external URL in a new tab, with noopener', () => {
    renderMd('Read [the docs](https://example.com/x).');
    const a = screen.getByRole('link', { name: 'the docs' });
    expect(a.getAttribute('href')).toBe('https://example.com/x');
    expect(a.getAttribute('target')).toBe('_blank');
    expect(a.getAttribute('rel')).toContain('noopener');
    expect(a.getAttribute('rel')).toContain('noreferrer');
  });

  it('does NOT render raw HTML from the text', () => {
    const { container } = renderMd('<script>window.__pwned = 1</script>plain');
    expect(container.querySelector('script')).toBeNull();
    expect((window as unknown as { __pwned?: number }).__pwned).toBeUndefined();
  });

  it('renders a table (gfm) — the shape a report arrives in', () => {
    renderMd('| a | b |\n|---|---|\n| 1 | 2 |');
    expect(screen.getByRole('table')).toBeTruthy();
  });
});
