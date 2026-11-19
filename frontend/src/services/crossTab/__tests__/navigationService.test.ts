/**
 * navigationService — ONE WINDOW PER DESTINATION (2026-09-19).
 *
 * THE USER'S RULE: *"we don't need or want two windows showing logs. If logs is
 * open we just switch to it."* Two properties make that true, and both are pinned
 * here because both were wrong in a way that only showed up when driven:
 *
 *  1. THE NAME: every destination is opened as `cog-<path>`, so a second request
 *     for the same place reaches the window that already has it. `_blank` (what
 *     the tab apps used) stacks a fresh duplicate every time.
 *  2. NO RELOAD WHEN SWITCHING: `window.open(url, name)` on an existing window
 *     focuses it AND re-navigates it — measured: a value set on that window did
 *     not survive. So the switch asks for the window with NO url
 *     (`window.open('', name)`) and only loads a destination into a window that
 *     is blank, i.e. the one the same call just created because none had the name.
 *
 * AGENT CHAT IS EXEMPT — a user may have more than one conversation going at a
 * time, so it keeps a fresh tab per request (one tab per conversation is its own
 * arc).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { navigateTo, openReusing, windowNameFor } from '../navigationService';

/** What `window.open` hands back for a window that already exists. */
const occupiedWindow = (href: string) => ({ location: { href }, focus: vi.fn() });

let openSpy: ReturnType<typeof vi.fn>;

describe('navigationService', () => {
  beforeEach(() => {
    openSpy = vi.fn();
    (window as unknown as { open: unknown }).open = openSpy;
  });

  it('names every destination the same way — one window per path', () => {
    expect(windowNameFor('/logs')).toBe('cog-/logs');
    expect(windowNameFor('/wiki/dev-notes/x')).toBe('cog-/wiki/dev-notes/x');
  });

  it('LOADS the destination into a window that did not exist', () => {
    // `window.open('', name)` had to create one, so what came back is blank and
    // is ours to fill.
    const fresh = occupiedWindow('about:blank');
    openSpy.mockReturnValueOnce(fresh);

    openReusing('/logs');

    expect(openSpy).toHaveBeenCalledWith('', 'cog-/logs');
    expect(fresh.location.href).toBe('/logs');
    expect(fresh.focus).not.toHaveBeenCalled(); // it is a new window: nothing to switch to
  });

  it('SWITCHES to the window that has it — and does NOT reload it', () => {
    const existing = occupiedWindow('/logs');
    openSpy.mockReturnValueOnce(existing);

    openReusing('/logs');

    expect(existing.focus).toHaveBeenCalled();
    // the whole point: the URL it already had is left alone, so nothing the tab
    // was holding (a draft, a session, a scroll position) is thrown away
    expect(existing.location.href).toBe('/logs');
  });

  it('falls back to the plain open when there is no handle at all', () => {
    // a blocked popup, or a browser that hands back nothing
    openSpy.mockReturnValueOnce(undefined);

    openReusing('/logs');

    expect(openSpy).toHaveBeenNthCalledWith(2, '/logs', 'cog-/logs');
  });

  it('treats an unreadable window as occupied — never navigates what it cannot see', () => {
    const opaque = {
      get location(): { href: string } {
        throw new Error('cross-origin');
      },
      focus: vi.fn(),
    };
    openSpy.mockReturnValueOnce(opaque);

    openReusing('/logs');

    expect(opaque.focus).toHaveBeenCalled();
    expect(openSpy).toHaveBeenCalledTimes(1);
  });

  it('takes the same named route for a tab app', () => {
    openSpy.mockReturnValueOnce(undefined);
    navigateTo('sessions');
    expect(openSpy).toHaveBeenCalledWith('/sessions', 'cog-/sessions');
  });

  it('keeps AGENT CHAT on a fresh tab per request — the exemption', () => {
    navigateTo('agent-chat');
    expect(openSpy).toHaveBeenCalledWith('/agent-interaction', '_blank');
  });
});
