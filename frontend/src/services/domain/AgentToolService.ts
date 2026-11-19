/**
 * AgentToolService - Manage agent-tool associations.
 * 
 * Provides API client for agent-tool management endpoints.
 */

import type {
  AgentToolUpdate,
  AgentToolResponse,
  AgentToolListResponse,
  AgentToolEnableRequest,
  AgentToolsFilters,
} from '@/types/tools';
import { apiClient } from '../apiClient';
import { frontendLoggingService } from '../frontendLoggingService';

/**
 * AgentToolService - Manage agent-tool associations
 */
export class AgentToolService {
  private basePath = '/api/v1/tools/agents';

  /**
   * List tools for an agent
   */
  async listAgentTools(agentId: string, filters: AgentToolsFilters = {}): Promise<AgentToolListResponse> {
    try {
      const params = new URLSearchParams();
      if (filters.is_enabled !== undefined) {
        params.append('is_enabled', filters.is_enabled.toString());
      }

      const queryString = params.toString();
      const endpoint = queryString 
        ? `${this.basePath}/${agentId}/tools?${queryString}`
        : `${this.basePath}/${agentId}/tools`;

      const response = await apiClient.get<AgentToolListResponse>(endpoint);
      
      if (!response.error && response.data) {
        return response.data;
      }

      throw new Error(response.error?.message || `Failed to fetch tools for agent: ${agentId}`);
    } catch (error) {
      frontendLoggingService.error('AgentToolService', `Failed to list tools for agent ${agentId}`, error);
      throw error;
    }
  }

  /**
   * Get agent-tool association
   */
  async getAgentTool(agentId: string, toolId: string): Promise<AgentToolResponse> {
    try {
      const response = await apiClient.get<AgentToolResponse>(`${this.basePath}/${agentId}/tools/${toolId}`);
      
      if (!response.error && response.data) {
        return response.data;
      }

      throw new Error(response.error?.message || `Tool ${toolId} not enabled for agent ${agentId}`);
    } catch (error) {
      frontendLoggingService.error('AgentToolService', `Failed to get agent-tool ${agentId}/${toolId}`, error);
      throw error;
    }
  }

  /**
   * Enable a tool for an agent
   */
  async enableToolForAgent(agentId: string, request: AgentToolEnableRequest): Promise<AgentToolResponse> {
    try {
      const response = await apiClient.post<AgentToolResponse>(
        `${this.basePath}/${agentId}/tools`,
        request
      );
      
      if (!response.error && response.data) {
        frontendLoggingService.info('AgentToolService', `Enabled tool ${request.tool_id} for agent ${agentId}`);
        return response.data;
      }

      throw new Error(response.error?.message || `Failed to enable tool for agent: ${agentId}`);
    } catch (error) {
      frontendLoggingService.error('AgentToolService', `Failed to enable tool for agent ${agentId}`, error);
      throw error;
    }
  }

  /**
   * Update agent-tool configuration
   */
  async updateAgentTool(
    agentId: string,
    toolId: string,
    updateData: AgentToolUpdate
  ): Promise<AgentToolResponse> {
    try {
      const response = await apiClient.put<AgentToolResponse>(
        `${this.basePath}/${agentId}/tools/${toolId}`,
        updateData
      );
      
      if (!response.error && response.data) {
        frontendLoggingService.info('AgentToolService', `Updated tool ${toolId} for agent ${agentId}`);
        return response.data;
      }

      throw new Error(response.error?.message || `Failed to update agent-tool: ${agentId}/${toolId}`);
    } catch (error) {
      frontendLoggingService.error('AgentToolService', `Failed to update agent-tool ${agentId}/${toolId}`, error);
      throw error;
    }
  }

  /**
   * Disable a tool for an agent (soft delete)
   */
  async disableToolForAgent(agentId: string, toolId: string): Promise<AgentToolResponse> {
    try {
      const response = await apiClient.post<AgentToolResponse>(
        `${this.basePath}/${agentId}/tools/${toolId}/disable`,
        {}
      );
      
      if (!response.error && response.data) {
        frontendLoggingService.info('AgentToolService', `Disabled tool ${toolId} for agent ${agentId}`);
        return response.data;
      }

      throw new Error(response.error?.message || `Failed to disable tool for agent: ${agentId}`);
    } catch (error) {
      frontendLoggingService.error('AgentToolService', `Failed to disable tool for agent ${agentId}`, error);
      throw error;
    }
  }

  /**
   * Remove tool from agent (hard delete)
   */
  async removeToolFromAgent(agentId: string, toolId: string): Promise<void> {
    try {
      const response = await apiClient.delete(`${this.basePath}/${agentId}/tools/${toolId}`);
      
      if (!response.error) {
        frontendLoggingService.info('AgentToolService', `Removed tool ${toolId} from agent ${agentId}`);
        return;
      }

      throw new Error(response.error?.message || `Failed to remove tool from agent: ${agentId}`);
    } catch (error) {
      frontendLoggingService.error('AgentToolService', `Failed to remove tool from agent ${agentId}`, error);
      throw error;
    }
  }

  /**
   * Get enabled tools for agent (convenience method)
   */
  async getEnabledTools(agentId: string): Promise<AgentToolResponse[]> {
    const response = await this.listAgentTools(agentId, { is_enabled: true });
    return response.tools;
  }

  /**
   * Get disabled tools for agent (convenience method)
   */
  async getDisabledTools(agentId: string): Promise<AgentToolResponse[]> {
    const response = await this.listAgentTools(agentId, { is_enabled: false });
    return response.tools;
  }

  /**
   * Check if tool is enabled for agent
   */
  async isToolEnabled(agentId: string, toolId: string): Promise<boolean> {
    try {
      const agentTool = await this.getAgentTool(agentId, toolId);
      return agentTool.is_enabled;
    } catch {
      return false;
    }
  }

  /**
   * Enable multiple tools for agent
   */
  async enableToolsForAgent(agentId: string, toolIds: string[], priority: number = 0): Promise<AgentToolResponse[]> {
    const results: AgentToolResponse[] = [];
    
    for (const toolId of toolIds) {
      try {
        const result = await this.enableToolForAgent(agentId, {
          tool_id: toolId,
          priority,
          config: {}
        });
        results.push(result);
      } catch (error) {
        frontendLoggingService.warning('AgentToolService', `Failed to enable tool ${toolId} for agent ${agentId}`, { error });
      }
    }
    
    return results;
  }

  /**
   * Disable all tools for agent
   */
  async disableAllToolsForAgent(agentId: string): Promise<void> {
    try {
      const enabledTools = await this.getEnabledTools(agentId);
      
      for (const agentTool of enabledTools) {
        await this.disableToolForAgent(agentId, agentTool.tool_id);
      }
      
      frontendLoggingService.info('AgentToolService', `Disabled all tools for agent ${agentId}`);
    } catch (error) {
      frontendLoggingService.error('AgentToolService', `Failed to disable all tools for agent ${agentId}`, error);
      throw error;
    }
  }
}

// Export singleton instance
export const agentToolService = new AgentToolService();