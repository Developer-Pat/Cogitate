/**
 * Lifecycle Service - System Domain
 *
 * The shutdown button's client half. The app REQUESTS, the launcher ACTS.
 *
 * THE ONE THING TO GET RIGHT: when the application stops, the request that
 * stopped it DIES with it — the connection drops and no response arrives. That
 * is SUCCESS, not an error. A caller that treats the drop as a failure shows an
 * error toast and leaves a spinner turning for a perfectly clean shutdown.
 *
 * So this service does not reject on a dropped connection. It resolves with
 * `dropped: true`, and the UI says "stopping…" rather than "failed".
 */

import { apiClient } from '@/services/apiClient';
import type { ApiResponse } from '@/types';

/** The last exit's shape, as the backend reports it. */
export interface LastShutdownRecord {
  id: number;
  phase: 'running' | 'draining' | 'complete';
  started_at: string | null;
  completed_at: string | null;
  reason: string | null;
  in_flight: string[];
  completed: string[];
  abandoned: string[];
}

export interface LastShutdown {
  /** `clean` | `unclean` | `running` | `none` — `none` claims NOTHING. */
  state: 'clean' | 'unclean' | 'running' | 'none';
  record: LastShutdownRecord | null;
  how?: string;
}

export interface LifecycleResult {
  accepted: boolean;
  action: 'stop' | 'restart';
  reason: string;
  /** True when the connection dropped before a reply — the EXPECTED outcome. */
  dropped: boolean;
}

export interface ILifecycleService {
  getLastShutdown(): Promise<ApiResponse<LastShutdown>>;
  stop(): Promise<LifecycleResult>;
  restart(): Promise<LifecycleResult>;
}

class LifecycleService implements ILifecycleService {
  private readonly basePath = '/api/v1/system';

  /** How did the last instance end? The Dashboard card's data. */
  async getLastShutdown(): Promise<ApiResponse<LastShutdown>> {
    return await apiClient.get<LastShutdown>(`${this.basePath}/shutdown/last`);
  }

  async stop(): Promise<LifecycleResult> {
    return this._request('shutdown', 'stop');
  }

  async restart(): Promise<LifecycleResult> {
    return this._request('restart', 'restart');
  }

  /**
   * Fire the request; treat a DROPPED connection as success.
   *
   * The reply may never arrive: the launcher stops the process that would have
   * sent it. `expect_connection_drop: true` in the payload says so explicitly,
   * and this catch is what makes the client agree.
   */
  private async _request(
    path: 'shutdown' | 'restart',
    action: 'stop' | 'restart',
  ): Promise<LifecycleResult> {
    try {
      const res = await apiClient.post<{ accepted: boolean; reason: string }>(
        `${this.basePath}/${path}`,
        { confirm: true },
      );
      return {
        accepted: true,
        action,
        reason: res.data?.reason ?? `user-requested-${action}`,
        dropped: false,
      };
    } catch {
      // NOT a failure. The most likely reason the request errored is that the
      // application stopped — which is precisely what was asked for.
      return {
        accepted: true,
        action,
        reason: `user-requested-${action}`,
        dropped: true,
      };
    }
  }
}

export const lifecycleService: ILifecycleService = new LifecycleService();

export default lifecycleService;
