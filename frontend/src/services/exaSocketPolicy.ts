/**
 * The socket policy the Exa surfaces share.
 *
 * WHY THIS EXISTS (2026-11-19, the user's "loop of messaging" report): the
 * backend answers a switched-off Exa with `{type:'status', status:'inactive'}`
 * and then CLOSES the socket. A reconnect-on-close handler therefore talks to a
 * gate that will refuse it every time — one sentence became a toast per attempt,
 * and because `onopen` reset the backoff counter the attempts came every second.
 *
 * The rule this module pins:
 *   - `inactive` is a STATE, not a blip. The socket stops for good; the surface
 *     renders the state (banner / card) and may say it once.
 *   - the backoff counter resets only when the server says `ready`. A socket
 *     that opens and immediately dies must still back off.
 */

/** How long a surface waits before the next reconnect attempt. */
export function backoffDelay(attempt: number, capMs = 30000): number {
  return Math.min(capMs, 1000 * 2 ** attempt)
}

/**
 * Whether a closed socket should be reopened.
 *
 * `disposed` — the component unmounted (or the effect re-ran).
 * `inactive` — the server's last word was `inactive`; it will say the same
 * again, so a reconnect is pure noise.
 */
export function shouldReconnectOnClose(facts: { disposed: boolean; inactive: boolean }): boolean {
  return !facts.disposed && !facts.inactive
}
