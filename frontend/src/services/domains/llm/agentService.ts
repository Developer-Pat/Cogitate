/**
 * Enhanced Agent Service - LLM Domain
 *
 * Service abstraction layer for agent management with proper domain boundaries,
 * error handling, and request/response transformation.
 */

import { apiClient } from '@/services/apiClient';
import type { ApiResponse, AgentInfo, AgentConfig, AgentMetrics } from '@/types';

/**
 * Agent Service Interface
 */
export interface IAgentService {
  getAgents(): Promise<ApiResponse<AgentInfo[]>>;
  getAgentById(id: string): Promise<ApiResponse<AgentInfo>>;
  getAgentMetrics(id: string): Promise<ApiResponse<AgentMetrics>>;
  createAgent(config: Omit<AgentConfig, 'id' | 'createdAt' | 'updatedAt'>): Promise<ApiResponse<AgentConfig>>;
  updateAgent(id: string, config: Partial<AgentConfig>): Promise<ApiResponse<AgentConfig>>;
  deleteAgent(id: string): Promise<ApiResponse<{ message: string }>>;
  startAgent(id: string): Promise<ApiResponse<{ message: string; agent: AgentInfo }>>;
  stopAgent(id: string): Promise<ApiResponse<{ message: string; agent: AgentInfo }>>;
  restartAgent(id: string): Promise<ApiResponse<{ message: string; agent: AgentInfo }>>;
  testAgent(id: string): Promise<ApiResponse<{ connected: boolean; latency?: number }>>;
  getAgentTypes(): Promise<ApiResponse<string[]>>;
  getAgentCapabilities(): Promise<ApiResponse<Record<string, string[]>>>;
}

/**
 * Agent Service Implementation
 */
class AgentService implements IAgentService {
  private readonly basePath = '/api/v1/agents';

  /**
   * Get all available agents
   */
  async getAgents(): Promise<ApiResponse<AgentInfo[]>> {
    return await apiClient.get<AgentInfo[]>(this.basePath);
  }

  /**
   * Get a specific agent by ID
   */
  async getAgentById(id: string): Promise<ApiResponse<AgentInfo>> {
    return await apiClient.get<AgentInfo>(`${this.basePath}/${id}`);
  }

  /**
   * Get agent metrics
   */
  async getAgentMetrics(id: string): Promise<ApiResponse<AgentMetrics>> {
    return await apiClient.get<AgentMetrics>(`${this.basePath}/${id}/metrics`);
  }

  /**
   * Create a new agent configuration
   */
  async createAgent(config: Omit<AgentConfig, 'id' | 'createdAt' | 'updatedAt'>): Promise<ApiResponse<AgentConfig>> {
    return await apiClient.post<AgentConfig>(this.basePath, config);
  }

  /**
   * Update an existing agent configuration
   */
  async updateAgent(id: string, config: Partial<AgentConfig>): Promise<ApiResponse<AgentConfig>> {
    return await apiClient.put<AgentConfig>(`${this.basePath}/${id}`, config);
  }

  /**
   * Delete an agent configuration
   */
  async deleteAgent(id: string): Promise<ApiResponse<{ message: string }>> {
    return await apiClient.delete<{ message: string }>(`${this.basePath}/${id}`);
  }

  /**
   * Start an agent
   */
  async startAgent(id: string): Promise<ApiResponse<{ message: string; agent: AgentInfo }>> {
    return await apiClient.post<{ message: string; agent: AgentInfo }>(`${this.basePath}/${id}/start`);
  }

  /**
   * Stop an agent
   */
  async stopAgent(id: string): Promise<ApiResponse<{ message: string; agent: AgentInfo }>> {
    return await apiClient.post<{ message: string; agent: AgentInfo }>(`${this.basePath}/${id}/stop`);
  }

  /**
   * Restart an agent
   */
  async restartAgent(id: string): Promise<ApiResponse<{ message: string; agent: AgentInfo }>> {
    return await apiClient.post<{ message: string; agent: AgentInfo }>(`${this.basePath}/${id}/restart`);
  }

  /**
   * Test agent connectivity
   */
  async testAgent(id: string): Promise<ApiResponse<{ connected: boolean; latency?: number }>> {
    return await apiClient.get<{ connected: boolean; latency?: number }>(`${this.basePath}/${id}/test`);
  }

  /**
   * Get available agent types
   */
  async getAgentTypes(): Promise<ApiResponse<string[]>> {
    return await apiClient.get<string[]>(`${this.basePath}/types`);
  }

  /**
   * Get agent capabilities
   */
  async getAgentCapabilities(): Promise<ApiResponse<Record<string, string[]>>> {
    return await apiClient.get<Record<string, string[]>>(`${this.basePath}/capabilities`);
  }
}

// Create and export singleton instance
export const agentService: IAgentService = new AgentService();

// Export for dependency injection
export default agentService;