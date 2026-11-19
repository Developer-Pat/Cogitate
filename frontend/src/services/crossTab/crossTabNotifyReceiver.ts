/**
 * crossTabNotifyReceiver - the cross-tab message-sync's receiver
 * (2026-08-29).
 *
 * The notification-store broadcasts the local notifications (the
 * app-notify's!) over the tab-services channel; EVERY tab's
 * receiver adds them to ITS message-store — so the message center
 * in any tab shows every tab's errors.
 *
 * THE DEDUPE IS BY EVENT ID, NOT BY CONTENT (corrected 2026-09-15).
 * This comment used to claim "addMessage is content-keyed — the same
 * title/message won't double-add". That is NO LONGER TRUE and has not
 * been since 2026-09-05: the content-key skip was deliberately removed
 * at the user's instruction ("the center is the RECORD — every firing
 * lands"), because it ate the repeats and left only the first instance
 * of each repeated warning. addMessage now suppresses ONLY:
 *   - the same eventId (one record per EVENT, not one per delivery path
 *     — the cross-tab triples fix), and
 *   - content that was explicitly deleted and is still inside the
 *     tombstone TTL.
 * Everything else records, every time. So a repeat that carries no
 * eventId WILL add a new row — that is the intent, not a leak.
 */

import { crossTab } from './crossTab'
import { useMessageStore } from '@/stores/messageStore'

/** wire ONCE at the app-boot. */
export function enableCrossTabNotifyReceiver(): () => void {
  return crossTab.subscribe((msg) => {
    if (msg.type !== 'notify') return
    try {
      useMessageStore.getState().addMessage({
        eventId: msg.eventId,
        kind: msg.kind,
        source: msg.source,
        type: msg.messageType as 'info' | 'success' | 'warning' | 'error',
        title: msg.title,
        message: msg.message,
      })
    } catch {
      // the center must never break the pump
    }
  })
}
