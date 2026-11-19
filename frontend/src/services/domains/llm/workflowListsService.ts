/**
 * Workflow Lists Service - LLM Domain
 *
 * Service abstraction layer for workflow list management.
 */

import { apiClient } from '@/services/apiClient';
import type { ApiResponse } from '@/types/index';
import type {
  WorkflowList,
  WorkflowListCreate,
  WorkflowListUpdate,
  WorkflowInList,
  WorkflowListListResponse,
  WorkflowListResponse,
  WorkflowListWorkflowsResponse
} from '@/types/workflows';

/**
 * Workflow Lists Service Interface
 */
export interface IWorkflowListsService {
  getLists(params?: { user_key?: string; tags?: string }): Promise<ApiResponse<WorkflowList[]>>;
  getListById(id: string): Promise<ApiResponse<WorkflowList>>;
  createList(data: WorkflowListCreate): Promise<ApiResponse<WorkflowList>>;
  updateList(id: string, data: WorkflowListUpdate): Promise<ApiResponse<WorkflowList>>;
  deleteList(id: string): Promise<ApiResponse<{ message: string }>>;
  getWorkflowsInList(id: string): Promise<ApiResponse<WorkflowInList[]>>;
  addWorkflowToList(listId: string, workflowId: string): Promise<ApiResponse<WorkflowList>>;
  removeWorkflowFromList(listId: string, workflowId: string): Promise<ApiResponse<WorkflowList>>;
}

/**
 * Workflow Lists Service Implementation
 */
class WorkflowListsService implements IWorkflowListsService {
  private readonly basePath = '/api/v1/workflow-lists';

  /**
   * Get all workflow lists
   */
  async getLists(params?: { user_key?: string; tags?: string }): Promise<ApiResponse<WorkflowList[]>> {
    const queryParams = new URLSearchParams();
    if (params?.user_key) queryParams.set('user_key', params.user_key);
    if (params?.tags) queryParams.set('tags', params.tags);

    const response = await apiClient.get<WorkflowListListResponse>(
      `${this.basePath}?${queryParams.toString()}`
    );

    // Extract workflow_lists array from response
    if (response.data && 'workflow_lists' in response.data) {
      return {
        ...response,
        data: response.data.workflow_lists || []
      };
    }

    return { ...response, data: [] };
  }

  /**
   * Get a specific workflow list by ID
   */
  async getListById(id: string): Promise<ApiResponse<WorkflowList>> {
    const response = await apiClient.get<WorkflowListResponse>(`${this.basePath}/${id}`);

    // Extract workflow_list from response
    if (response.data && 'workflow_list' in response.data) {
      return {
        ...response,
        data: response.data.workflow_list
      };
    }

    return response as unknown as ApiResponse<WorkflowList>;
  }

  /**
   * Create a new workflow list
   */
  async createList(data: WorkflowListCreate): Promise<ApiResponse<WorkflowList>> {
    const response = await apiClient.post<WorkflowListResponse>(this.basePath, data);

    // Extract workflow_list from response
    if (response.data && 'workflow_list' in response.data) {
      return {
        ...response,
        data: response.data.workflow_list
      };
    }

    return response as unknown as ApiResponse<WorkflowList>;
  }

  /**
   * Update an existing workflow list
   */
  async updateList(id: string, data: WorkflowListUpdate): Promise<ApiResponse<WorkflowList>> {
    const response = await apiClient.put<WorkflowListResponse>(`${this.basePath}/${id}`, data);

    // Extract workflow_list from response
    if (response.data && 'workflow_list' in response.data) {
      return {
        ...response,
        data: response.data.workflow_list
      };
    }

    return response as unknown as ApiResponse<WorkflowList>;
  }

  /**
   * Delete a workflow list
   */
  async deleteList(id: string): Promise<ApiResponse<{ message: string }>> {
    return apiClient.delete<{ message: string }>(`${this.basePath}/${id}`);
  }

  /**
   * Get all workflows in a list
   */
  async getWorkflowsInList(id: string): Promise<ApiResponse<WorkflowInList[]>> {
    const response = await apiClient.get<WorkflowListWorkflowsResponse>(
      `${this.basePath}/${id}/workflows`
    );

    // Extract workflows array from response
    if (response.data && 'workflows' in response.data) {
      return {
        ...response,
        data: response.data.workflows || []
      };
    }

    return { ...response, data: [] };
  }

  /**
   * Add a workflow to a list
   */
  async addWorkflowToList(listId: string, workflowId: string): Promise<ApiResponse<WorkflowList>> {
    const response = await apiClient.post<WorkflowListResponse>(`${this.basePath}/${listId}/workflows/${workflowId}`, {});

    // Extract workflow_list from response
    if (response.data && 'workflow_list' in response.data) {
      return {
        ...response,
        data: response.data.workflow_list
      };
    }

    return response as unknown as ApiResponse<WorkflowList>;
  }

  /**
   * Remove a workflow from a list
   */
  async removeWorkflowFromList(listId: string, workflowId: string): Promise<ApiResponse<WorkflowList>> {
    const response = await apiClient.delete<WorkflowListResponse>(`${this.basePath}/${listId}/workflows/${workflowId}`);

    // Extract workflow_list from response
    if (response.data && 'workflow_list' in response.data) {
      return {
        ...response,
        data: response.data.workflow_list
      };
    }

    return response as unknown as ApiResponse<WorkflowList>;
  }
}

// Export singleton instance
export const workflowListsService = new WorkflowListsService();
