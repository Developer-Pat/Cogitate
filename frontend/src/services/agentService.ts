import { apiClient } from './apiClient';
import type { ApiResponse, AgentInfo, AgentConfig, AgentMetrics } from '../types';

/**
 * Agent Service - Handles all agent management and configuration API endpoints.
 *
 * Provides methods for:
 * - Fetching agent lists and details
 * - Creating, updating, and deleting agent configurations
 * - Managing agent lifecycle (start, stop, restart)
 * - Testing agent connectivity
 * - Retrieving agent types and capabilities
 *
 * All methods return ApiResponse objects that contain either data or error information.
 *
 * @example
 * // Fetch all agents
 * const response = await agentService.getAgents();
 * if (response.error) {
 *   console.error('Failed to fetch agents:', response.error.message);
 * } else {
 *   console.log('Agents:', response.data);
 * }
 */
export const agentService = {
  /**
   * Retrieves all available agents from the backend.
   *
   * @returns {Promise<ApiResponse<AgentInfo[]>>} Response containing array of agent information
   * @throws {Error} If the HTTP request fails
   *
   * @example
   * const response = await agentService.getAgents();
   * const agents = response.data || [];
   */
  async getAgents(): Promise<ApiResponse<AgentInfo[]>> {
    return apiClient.get<AgentInfo[]>('/api/v1/agents');
  },

  /**
   * Retrieves a specific agent by its unique identifier.
   *
   * @param {string} id - The unique identifier of the agent to retrieve
   * @returns {Promise<ApiResponse<AgentInfo>>} Response containing the agent information
   * @throws {Error} If the HTTP request fails
   *
   * @example
   * const response = await agentService.getAgentById('agent-123');
   * if (response.data) {
   *   console.log('Agent name:', response.data.name);
   * }
   */
  async getAgentById(id: string): Promise<ApiResponse<AgentInfo>> {
    return apiClient.get<AgentInfo>(`/api/v1/agents/${id}`);
  },

  /**
   * Retrieves performance metrics for a specific agent.
   *
   * @param {string} id - The unique identifier of the agent
   * @returns {Promise<ApiResponse<AgentMetrics>>} Response containing:
   *   - requestsProcessed: Total number of requests handled
   *   - averageResponseTime: Average response time in milliseconds
   *   - errorRate: Percentage of failed requests (0-1)
   *   - memoryUsage: Current memory usage in bytes
   * @throws {Error} If the HTTP request fails
   *
   * @example
   * const response = await agentService.getAgentMetrics('agent-123');
   * if (response.data) {
   *   console.log(`Error rate: ${(response.data.errorRate * 100).toFixed(2)}%`);
   * }
   */
  async getAgentMetrics(id: string): Promise<ApiResponse<AgentMetrics>> {
    return apiClient.get<AgentMetrics>(`/api/v1/agents/${id}/metrics`);
  },

  /**
   * Creates a new agent configuration.
   *
   * @param {Omit<AgentConfig, 'id' | 'createdAt' | 'updatedAt'>} config - Agent configuration
   *   - name: Human-readable name for the agent
   *   - type: Type of agent (e.g., 'llm', 'tool', 'workflow')
   *   - parameters: Configuration parameters specific to the agent type
   *   - enabled: Whether the agent should be enabled
   * @returns {Promise<ApiResponse<AgentConfig>>} Response containing the created agent with ID and timestamps
   * @throws {Error} If the HTTP request fails or validation fails
   *
   * @example
   * const response = await agentService.createAgent({
   *   name: 'Research Agent',
   *   type: 'llm',
   *   parameters: { model: 'gpt-4', temperature: 0.7 },
   *   enabled: true,
   * });
   */
  async createAgent(config: Omit<AgentConfig, 'id' | 'createdAt' | 'updatedAt'>): Promise<ApiResponse<AgentConfig>> {
    return apiClient.post<AgentConfig>('/api/v1/agents', config);
  },

  /**
   * Updates an existing agent configuration.
   *
   * @param {string} id - The unique identifier of the agent to update
   * @param {Partial<AgentConfig>} config - Partial agent configuration with fields to update
   * @returns {Promise<ApiResponse<AgentConfig>>} Response containing the updated agent configuration
   * @throws {Error} If the HTTP request fails or agent not found
   *
   * @example
   * const response = await agentService.updateAgent('agent-123', {
   *   enabled: false,
   *   parameters: { temperature: 0.5 }
   * });
   */
  async updateAgent(id: string, config: Partial<AgentConfig>): Promise<ApiResponse<AgentConfig>> {
    return apiClient.put<AgentConfig>(`/api/v1/agents/${id}`, config);
  },

  /**
   * Deletes an agent configuration.
   *
   * @param {string} id - The unique identifier of the agent to delete
   * @returns {Promise<ApiResponse<{message: string}>>} Response with confirmation message
   * @throws {Error} If the HTTP request fails or agent not found
   *
   * @example
   * const response = await agentService.deleteAgent('agent-123');
   * if (!response.error) {
   *   console.log('Agent deleted successfully');
   * }
   */
  async deleteAgent(id: string): Promise<ApiResponse<{ message: string }>> {
    return apiClient.delete<{ message: string }>(`/api/v1/agents/${id}`);
  },

  /**
   * Starts an agent, transitioning it to active state.
   *
   * @param {string} id - The unique identifier of the agent to start
   * @returns {Promise<ApiResponse<{message: string, agent: AgentInfo}>>} Response containing confirmation and updated agent info
   * @throws {Error} If the HTTP request fails or agent not found
   *
   * @example
   * const response = await agentService.startAgent('agent-123');
   * if (response.data) {
   *   console.log('Agent started:', response.data.agent.status);
   * }
   */
  async startAgent(id: string): Promise<ApiResponse<{ message: string; agent: AgentInfo }>> {
    return apiClient.post<{ message: string; agent: AgentInfo }>(`/api/v1/agents/${id}/start`);
  },

  /**
   * Stops an agent, transitioning it to inactive state.
   *
   * @param {string} id - The unique identifier of the agent to stop
   * @returns {Promise<ApiResponse<{message: string, agent: AgentInfo}>>} Response containing confirmation and updated agent info
   * @throws {Error} If the HTTP request fails or agent not found
   *
   * @example
   * const response = await agentService.stopAgent('agent-123');
   */
  async stopAgent(id: string): Promise<ApiResponse<{ message: string; agent: AgentInfo }>> {
    return apiClient.post<{ message: string; agent: AgentInfo }>(`/api/v1/agents/${id}/stop`);
  },

  /**
   * Restarts an agent, stopping and then starting it.
   *
   * @param {string} id - The unique identifier of the agent to restart
   * @returns {Promise<ApiResponse<{message: string, agent: AgentInfo}>>} Response containing confirmation and updated agent info
   * @throws {Error} If the HTTP request fails or agent not found
   *
   * @example
   * const response = await agentService.restartAgent('agent-123');
   */
  async restartAgent(id: string): Promise<ApiResponse<{ message: string; agent: AgentInfo }>> {
    return apiClient.post<{ message: string; agent: AgentInfo }>(`/api/v1/agents/${id}/restart`);
  },

  /**
   * Tests agent connectivity and responsiveness.
   *
   * @param {string} id - The unique identifier of the agent to test
   * @returns {Promise<ApiResponse<{connected: boolean, latency?: number}>>} Response containing:
   *   - connected: Whether the agent is reachable
   *   - latency: Response time in milliseconds (if connected)
   * @throws {Error} If the HTTP request fails
   *
   * @example
   * const response = await agentService.testAgent('agent-123');
   * if (response.data?.connected) {
   *   console.log(`Agent latency: ${response.data.latency}ms`);
   * }
   */
  async testAgent(id: string): Promise<ApiResponse<{ connected: boolean; latency?: number }>> {
    return apiClient.get<{ connected: boolean; latency?: number }>(`/api/v1/agents/${id}/test`);
  },

  /**
   * Retrieves the list of available agent types in the system.
   *
   * @returns {Promise<ApiResponse<string[]>>} Response containing array of agent type names
   * @throws {Error} If the HTTP request fails
   *
   * @example
   * const response = await agentService.getAgentTypes();
   * const types = response.data || [];
   * console.log('Available types:', types);
   */
  async getAgentTypes(): Promise<ApiResponse<string[]>> {
    return apiClient.get<string[]>('/api/v1/agents/types');
  },

  /**
   * Retrieves the capabilities available for each agent type.
   *
   * @returns {Promise<ApiResponse<Record<string, string[]>>>} Response containing object mapping:
   *   - Keys: Agent type names
   *   - Values: Array of capability names for that type
   * @throws {Error} If the HTTP request fails
   *
   * @example
   * const response = await agentService.getAgentCapabilities();
   * if (response.data) {
   *   const llmCapabilities = response.data['llm'] || [];
   *   console.log('LLM capabilities:', llmCapabilities);
   * }
   */
  async getAgentCapabilities(): Promise<ApiResponse<Record<string, string[]>>> {
    return apiClient.get<Record<string, string[]>>('/api/v1/agents/capabilities');
  },
};