/**
 * Mode Service - System Domain
 *
 * The mode switch's client half: which BUILD the frontend serves, and the
 * request to change it. The same contract as the shutdown button — the app
 * REQUESTS, the launcher ACTS — with one deliberate difference:
 *
 *   THE CONNECTION DOES NOT DROP. A shutdown asks for the process that would
 *   send the reply to die, so losing the connection is the expected outcome.
 *   A mode switch cycles only the FRONTEND; this backend answers normally. A
 *   client that carried the shutdown's "dropped = success" rule over here
 *   would report success for a switch that never happened.
 *
 * The mode itself is persisted by the LAUNCHER (`.pids/frontend.mode`) — this
 * service reads it, never writes it. One writer, so the record cannot disagree
 * with what is actually serving.
 */

import { apiClient } from '@/services/apiClient';
import type { ApiResponse } from '@/types';

export type FrontendMode = 'development' | 'production';

export interface ModeState {
  /** `null` when the launcher never recorded one — claims nothing. */
  mode: FrontendMode | null;
  available: FrontendMode[];
}

export interface ModeSwitchResult {
  accepted: boolean;
  mode: FrontendMode;
  /** Always false here — see the note above. */
  expect_connection_drop: boolean;
  note: string;
}

export interface IModeService {
  get(): Promise<ApiResponse<ModeState>>;
  switchTo(mode: FrontendMode): Promise<ApiResponse<ModeSwitchResult>>;
}

class ModeService implements IModeService {
  private readonly basePath = '/api/v1/system';

  /** Which build is serving, as the launcher recorded it. */
  async get(): Promise<ApiResponse<ModeState>> {
    return await apiClient.get<ModeState>(`${this.basePath}/mode`);
  }

  /**
   * Ask the launcher to switch. Detached on the server side: switching TO
   * production rebuilds first (over a minute), so this returns as soon as the
   * launcher has been asked — not when the switch is done.
   */
  async switchTo(mode: FrontendMode): Promise<ApiResponse<ModeSwitchResult>> {
    return await apiClient.post<ModeSwitchResult>(`${this.basePath}/mode`, {
      mode,
      confirm: true,
    });
  }
}

export const modeService: IModeService = new ModeService();

export default modeService;
