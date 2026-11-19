// THE OUTAGE EPISODE GATE (2026-09-04, the dedupe refinement)
//
// Several INDEPENDENT notifiers announce backend outages: the ONE
// apiClient's 3rd-failure gate, the BackendStatusIndicator's
// health-poll transitions, and the useSystemHealth hook. One
// outage used to land 3-4 near-identical message-center entries
// (the _34 probe: 3x 'Backend Unavailable' + 1x 'Health Check
// Failed'). The CENTER is the record — every firing lands (the
// Bob-errors dig, 2026-09-01) — so the collapse happens HERE, at
// the notifier edge: the FIRST down-detector of an episode
// announces, the FIRST recovery-detector announces, and every
// other notifier stays silent until the next episode.
//
// A leaf module (imports NOTHING — any module may import it).

type EpisodeState = 'idle' | 'down' | 'up'

let episode: EpisodeState = 'idle'

export const outageGate = {
  /** true = this notifier should announce the DOWN (the first of
      the episode); false = someone already announced it. */
  markDown(): boolean {
    if (episode === 'down') return false
    episode = 'down'
    return true
  },

  /** true = this notifier should announce the RECOVERY (the
      episode had a down announcement); false = there was nothing
      announced (or the recovery already was). */
  markUp(): boolean {
    if (episode !== 'down') return false
    episode = 'up'
    return true
  },

  /** THE TEST SEAM — reset the episode state. */
  reset(): void {
    episode = 'idle'
  },
}
