/**
 * navHistory — the shortcuts offered when the command box opens.
 *
 * The rules that matter: a repeat RAISES a count instead of duplicating the
 * row, the most-used destination leads (recency breaks ties), the list is
 * bounded, and a broken store degrades to "no history" — never to an
 * exception in the header of every page in the app.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { recordNav, navHistory, clearNavHistory } from '../navHistory';

describe('navHistory', () => {
  beforeEach(() => {
    clearNavHistory();
  });

  it('starts empty', () => {
    expect(navHistory()).toEqual([]);
  });

  it('records a destination and offers it back', () => {
    recordNav('/logs', 'Logs');
    const list = navHistory();
    expect(list.length).toBe(1);
    expect(list[0]).toMatchObject({ to: '/logs', label: 'Logs', count: 1 });
  });

  it('raises a COUNT on repeat instead of duplicating the row', () => {
    recordNav('/logs', 'Logs');
    recordNav('/logs', 'Logs');
    recordNav('/logs', 'Logs');
    const list = navHistory();
    expect(list.length).toBe(1);
    expect(list[0].count).toBe(3);
  });

  it('leads with the MOST USED, and uses recency to break a tie', () => {
    recordNav('/logs', 'Logs', 1000);
    recordNav('/sessions', 'Sessions', 2000);
    recordNav('/sessions', 'Sessions', 3000);
    recordNav('/workflows', 'Workflows', 4000);
    const list = navHistory();
    expect(list[0].to).toBe('/sessions');      // count 2 beats count 1
    expect(list[1].to).toBe('/workflows');     // both count 1 — newer first
    expect(list[2].to).toBe('/logs');
  });

  it('ignores an empty destination (a tab app has no path to store)', () => {
    recordNav('', 'Wiki');
    expect(navHistory()).toEqual([]);
  });

  it('is bounded — a shortcut list, not a log', () => {
    for (let i = 0; i < 80; i++) recordNav('/page-' + i, 'Page ' + i, i);
    const list = navHistory(100);
    expect(list.length).toBeLessThanOrEqual(40);
  });

  it('degrades to empty on a corrupt store rather than throwing', () => {
    localStorage.setItem('cog-nav-history', '{not json at all');
    expect(() => navHistory()).not.toThrow();
    expect(navHistory()).toEqual([]);
    // and still records afterwards
    recordNav('/logs', 'Logs');
    expect(navHistory()[0].to).toBe('/logs');
  });
});
