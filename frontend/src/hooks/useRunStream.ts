/**
 * useRunStream — follow a run's live event stream, folded into a `RunFeed`.
 *
 * THE USER-TESTING PAGE, Phase C2. The endpoint is `/testing/runs/{id}/events`:
 * the run's own `events.jsonl`, replayed from the start and then followed, closing
 * itself when the run ends (C0 built it; this is the consumer).
 *
 * WHY A RAW `EventSource` AND NOT `SSEClient`. The house client retries on its own
 * and then GIVES UP after `maxRetries` — fine for a stream that is always short,
 * wrong for a test run that takes half an hour: a blip at minute twenty would end
 * the feed permanently. The browser's own reconnect is better here, and it is what
 * the stream was built for: every frame carries its byte offset as its `id:`, so a
 * reconnecting EventSource sends `Last-Event-ID` by itself and resumes exactly
 * where it stopped instead of replaying the run. So this hook opens the stream,
 * listens, and stays out of the way — except for the one case the browser cannot
 * know about, below.
 *
 * THE STREAM ENDS ITSELF when the run does, and that is not an error: the event
 * source fires `onerror` with `readyState === CLOSED` when the server closes the
 * response. That state is the honest end of a watched run, and it is reported as
 * `closed` rather than as a failure.
 *
 * ONE HOOK PER PAGE, not per tab: the live feed must survive a nav within the page
 * — switching to Runnable to read a row must not tear down a running run's feed.
 */

import { useEffect, useState } from 'react';
import { testingService, type RunEvent } from '../services/domain/TestingService';
import {
  emptyFeed,
  reduceRunEvent,
  type RunFeed,
} from '../utils/runFeed';
import { frontendLoggingService } from '../services/frontendLoggingService';

export type StreamStatus = 'idle' | 'connecting' | 'open' | 'closed' | 'error';

export interface UseRunStreamReturn {
  feed: RunFeed;
  status: StreamStatus;
}

/** The known event kinds. A frame with an unknown `t` is not reduced — a newer
 *  plugin can add a kind, and a page that guessed at it would be inventing. */
const KNOWN = new Set([
  'run_start', 'session_start', 'collect', 'test', 'summary', 'run_end',
  'stream_end', 'error',
]);

/**
 * The frames that mean THE STREAM IS OVER.
 *
 * `run_end` is the run's own end; `stream_end` is the stream saying it has
 * nothing more and closing; `error` is an endpoint with nothing to follow. Once
 * one of these has arrived there is nothing left to wait for — and waiting is not
 * harmless: the browser treats the server's close as a dropped connection and
 * RECONNECTS (measured: the loop replays the run's tail every few seconds and the
 * tab sits on "stream interrupted — reconnecting" over a run that finished
 * minutes ago). The browser cannot know the stream was finished on purpose; the
 * page can, so it closes the stream itself.
 */
const TERMINAL = new Set(['run_end', 'stream_end', 'error']);

function parseFrame(raw: string): RunEvent | null {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;                       // a frame this page cannot read is skipped
  }
  if (typeof data !== 'object' || data === null) return null;
  const t = (data as { t?: unknown }).t;
  if (typeof t !== 'string' || !KNOWN.has(t)) return null;
  // The single unchecked step: the wire says its shape through `t`, and the
  // reducer reads only fields it has a `typeof` guard for.
  return data as RunEvent;
}

export function useRunStream(runId: string | null): UseRunStreamReturn {
  const [feed, setFeed] = useState<RunFeed>(() => emptyFeed(runId));
  const [status, setStatus] = useState<StreamStatus>(runId ? 'connecting' : 'idle');

  useEffect(() => {
    if (!runId) {
      setFeed(emptyFeed(null));
      setStatus('idle');
      return;
    }

    // A new run, or a reload: start the fold over. Without this reset, a previous
    // run's lines would still be on screen under the new run's counts.
    setFeed(emptyFeed(runId));
    setStatus('connecting');

    const source = new EventSource(testingService.runEventsUrl(runId));

    source.onopen = () => setStatus('open');

    source.onmessage = (message: MessageEvent<string>) => {
      const event = parseFrame(message.data);
      if (!event) return;
      setFeed((current) => reduceRunEvent(current, event));
      if (TERMINAL.has(event.t)) {
        // The end, declared by the stream — stop here rather than letting the
        // browser reconnect into a run that is over.
        source.close();
        setStatus('closed');
        return;
      }
      setStatus('open');
    };

    source.onerror = () => {
      // An error while the stream is still open is a real connection problem, and
      // the browser is already retrying. An error AFTER a terminal frame is the
      // close the page itself asked for — not a failure, and not reported as one.
      if (source.readyState === EventSource.CLOSED) {
        setStatus('closed');
      } else {
        setStatus('error');
        frontendLoggingService.warning('useRunStream', 'run stream interrupted (reconnecting)', {
          runId,
        });
      }
    };

    return () => {
      source.close();
    };
  }, [runId]);

  return { feed, status };
}

export default useRunStream;
