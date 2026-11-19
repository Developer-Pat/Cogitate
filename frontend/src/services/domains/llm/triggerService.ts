/**
 * Trigger Service — Workflow Triggers
 *
 * Control surface for workflow triggers: list, activate, deactivate,
 * and view schedule info. Backs the trigger control panel.
 *
 * Backend: /api/v1/triggers (triggers_router.py)
 */

import { apiClient } from '@/services/apiClient';
import type { ApiResponse } from '@/types';
import type {
  TriggerInfoResponse,
  ScheduleListResponse
} from '@/types/workflows';

export interface ITriggerService {
  getTriggers(): Promise<ApiResponse<TriggerInfoResponse[]>>;
  activateTrigger(id: string): Promise<ApiResponse<TriggerInfoResponse>>;
  deactivateTrigger(id: string): Promise<ApiResponse<TriggerInfoResponse>>;
  getSchedules(): Promise<ApiResponse<ScheduleListResponse[]>>;
  updateTrigger(
    id: string,
    body: { config?: Record<string, unknown>; name?: string; is_active?: boolean }
  ): Promise<ApiResponse<TriggerInfoResponse>>;
}

class TriggerService implements ITriggerService {
  private readonly basePath = '/api/v1/triggers';

  async getTriggers(): Promise<ApiResponse<TriggerInfoResponse[]>> {
    // include_inactive: a control panel must show ALL triggers
    return apiClient.get<TriggerInfoResponse[]>(`${this.basePath}?include_inactive=true`);
  }

  async activateTrigger(id: string): Promise<ApiResponse<TriggerInfoResponse>> {
    return apiClient.post<TriggerInfoResponse>(`${this.basePath}/${id}/activate`);
  }

  async deactivateTrigger(id: string): Promise<ApiResponse<TriggerInfoResponse>> {
    return apiClient.post<TriggerInfoResponse>(`${this.basePath}/${id}/deactivate`);
  }

  async getSchedules(): Promise<ApiResponse<ScheduleListResponse[]>> {
    return apiClient.get<ScheduleListResponse[]>(`${this.basePath}/schedules/list`);
  }

  /** Update a trigger's config (the scheduler modal: cron + timezone). */
  async updateTrigger(
    id: string,
    body: { config?: Record<string, unknown>; name?: string; is_active?: boolean }
  ): Promise<ApiResponse<TriggerInfoResponse>> {
    return apiClient.put<TriggerInfoResponse>(`${this.basePath}/${id}`, body);
  }
}

export const triggerService = new TriggerService();
