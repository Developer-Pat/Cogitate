/**
 * The swap handoff (A3, the write side — 2026-09-09).
 *
 * The local page asks, the SYSTEM AGENT runs. The swap is a
 * conversation with a button: the user authorizes the tradeoff on
 * the local page, the page queues the request, and the Exa chat
 * tab surfaces it as a confirmable pickup (no auto-fire — the
 * user sends it to Exa themselves).
 *
 * Transport: localStorage + the storage event. The Exa chat lives
 * in its own browser tab, so the in-memory event bus cannot reach
 * it. A queued request is a single-use localStorage value; the
 * Exa tab reads it on mount AND listens for the cross-tab storage
 * event (fires in every OTHER tab when this one writes).
 */
const SWAP_KEY = 'cogitate-swap-request'

export interface SwapRequest {
  text: string
  label: string
  queuedAt: number
}

/** Queue a swap request (the local page, after the user authorizes). */
export function queueSwapRequest(req: SwapRequest): void {
  try {
    localStorage.setItem(SWAP_KEY, JSON.stringify(req))
  } catch {
    // storage full/blocked — the user can still ask Exa by hand
  }
}

/** Read + clear the queued request (the Exa tab, on mount). */
export function consumeSwapRequest(): SwapRequest | null {
  try {
    const raw = localStorage.getItem(SWAP_KEY)
    if (!raw) return null
    const req = JSON.parse(raw) as SwapRequest
    localStorage.removeItem(SWAP_KEY)
    return req
  } catch {
    localStorage.removeItem(SWAP_KEY)
    return null
  }
}

/** Peek without clearing (the Exa tab's storage-event handler). */
export function peekSwapRequest(): SwapRequest | null {
  try {
    const raw = localStorage.getItem(SWAP_KEY)
    if (!raw) return null
    return JSON.parse(raw) as SwapRequest
  } catch {
    return null
  }
}

/** The swap request the Exa chat should send (the runbook shape). */
export function composeSwapRequestText(daemonName: string, runningOwner: string[]): string {
  if (runningOwner.length > 0) {
    return (
      `Please swap the local LLM daemon: stop ${runningOwner.join(
        ', '
      )} and start ${daemonName} instead, then verify with the provider occupancy endpoint and report the new state.`
    )
  }
  return (
    `Please start the ${daemonName} daemon, then verify with the provider occupancy endpoint and report the new state.`
  )
}
