/**
 * focusContract — who gets the caret.
 *
 * TWO HALVES, and the second one is what this file is mostly about (2026-09-19):
 *
 *  - THE DECLARATION: a page built around one field names it (`data-autofocus`),
 *    and a claimant that finds one yields. Verified live in the real app; here it
 *    is pinned as the DOM rule it is.
 *  - THE HANDOFF: a navigation the READER ASKED FOR hands them the destination —
 *    the declared field if there is one, else the `<main>` region. The user's
 *    report was being left in the nav panel after asking to go somewhere.
 *
 * The handoff is a ONE-SHOT token in `localStorage` (not a call), because half of
 * these arrivals are a NEW TAB — a document the opener cannot touch. So the rules
 * worth pinning are about the token's lifecycle: written, honoured once, dropped
 * when stale, and never honoured for an arrival nobody asked for.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  claimDeclaredPrimaryInput,
  claimPageFocus,
  declaredPrimaryInput,
  FOCUS_HANDOFF_KEY,
  pageFocusRequested,
  requestPageFocus,
} from '../focusContract';

/** A page that lands on main, and one that declares its own first field. */
const pageWithMain = () => {
  document.body.innerHTML = '<main tabindex="-1"><p>the page</p></main>';
  return document.querySelector('main')!;
};

const pageDeclaringAField = () => {
  document.body.innerHTML =
    '<main tabindex="-1"><input data-autofocus aria-label="the page\'s own field" /></main>';
  return document.body.querySelector('input')!;
};

describe('focusContract', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    localStorage.clear();
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('reads a page’s declared primary input, or nothing', () => {
    pageWithMain();
    expect(declaredPrimaryInput()).toBeNull();

    const field = pageDeclaringAField();
    expect(declaredPrimaryInput()).toBe(field);
  });

  it('sends the caret to <main> when the page declares no field of its own', () => {
    const main = pageWithMain();
    requestPageFocus();

    expect(pageFocusRequested()).toBe(true);
    expect(claimPageFocus()).toBe(true);
    expect(document.activeElement).toBe(main);
  });

  it('prefers the page’s declared field over <main>', () => {
    const field = pageDeclaringAField();
    requestPageFocus();

    expect(claimPageFocus()).toBe(true);
    expect(document.activeElement).toBe(field);
  });

  it('honours ONE arrival — a claim consumes the request', () => {
    pageWithMain();
    requestPageFocus();

    expect(claimPageFocus()).toBe(true);
    // nothing left for the next arrival: a second claim has nothing to honour
    expect(pageFocusRequested()).toBe(false);
    expect(claimPageFocus()).toBe(false);
  });

  it('does nothing at all for a COLD arrival — no request, no claim', () => {
    const main = pageWithMain();
    const somewhere = document.createElement('button');
    document.body.appendChild(somewhere);
    somewhere.focus();
    expect(document.activeElement).toBe(somewhere);

    // a typed URL, a bookmark, a reload: nobody asked, so the page keeps whatever
    // caret it has and the box keeps the one the reader gave it
    expect(pageFocusRequested()).toBe(false);
    expect(claimPageFocus()).toBe(false);
    expect(document.activeElement).toBe(somewhere);
    expect(main.contains(document.activeElement)).toBe(false);
  });

  it('DROPS a stale request rather than honouring it late', () => {
    const main = pageWithMain();
    // a token written long ago — the navigation it belonged to never arrived, or
    // arrived and was already answered
    localStorage.setItem(FOCUS_HANDOFF_KEY, String(Date.now() - 60_000));

    expect(pageFocusRequested()).toBe(false);
    expect(claimPageFocus()).toBe(false);
    expect(document.activeElement).not.toBe(main);
    // and it is cleared, not merely ignored — a stale token must not wait around
    // for the next arrival
    expect(localStorage.getItem(FOCUS_HANDOFF_KEY)).toBeNull();
  });

  it('YIELDS to a page that already took the caret for itself', () => {
    // The composition that matters: a page's own field effect runs BEFORE the
    // shell's (children before parents in one commit), so by the time the claim
    // runs the caret may already be where it belongs.
    document.body.innerHTML = '<main tabindex="-1"><input aria-label="grabbed by the page" /></main>';
    const grabbed = document.body.querySelector('input')!;
    grabbed.focus();

    requestPageFocus();
    expect(claimPageFocus()).toBe(true);
    // the page kept it — being "honoured" here means NOT stealing it back
    expect(document.activeElement).toBe(grabbed);
  });

  it('claims nothing when the page has neither a field nor a landmark', () => {
    // A defensive case: the shell always renders <main>, but a claim must not
    // throw (or focus <body>) if it ever is not there.
    requestPageFocus();
    expect(claimPageFocus()).toBe(false);
    expect(document.activeElement).toBe(document.body);
  });

  it('lets a declaring page take the caret for its own field', () => {
    // THE PAGE'S OWN HALF — the half that matters on a COLD load, where the
    // route's chunk lands after the shell's arrival effect has already run and
    // found no declaration to yield to.
    const field = pageDeclaringAField();

    claimDeclaredPrimaryInput();

    expect(document.activeElement).toBe(field);
  });

  it('is a no-op on a page that declares nothing', () => {
    pageWithMain();
    const somewhere = document.createElement('button');
    document.body.appendChild(somewhere);
    somewhere.focus();

    claimDeclaredPrimaryInput();

    expect(document.activeElement).toBe(somewhere);
  });
});
