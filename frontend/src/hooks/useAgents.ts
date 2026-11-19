import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentService } from '../services';
import { useSystemStore } from '../stores/systemStore';
import type { AgentConfig } from '../types';

/**
 * Hook for fetching and managing agents.
 *
 * Automatically updates the system store when data is fetched.
 * Refetches every 30 seconds to keep agent data current.
 *
 * @returns {UseQueryResult<AgentInfo[], Error>} Query object containing:
 *   - data: Array of agent information objects
 *   - isLoading: Whether the query is currently loading
 *   - error: Error object if the query failed
 *   - refetch: Function to manually refetch agents
 *
 * @throws {Error} If the API request fails
 *
 * @example
 * const { data: agents, isLoading, error } = useAgents();
 *
 * if (isLoading) return <div>Loading agents...</div>;
 * if (error) return <div>Error: {error.message}</div>;
 *
 * return (
 *   <ul>
 *     {agents?.map(agent => (
 *       <li key={agent.id}>{agent.name} - {agent.status}</li>
 *     ))}
 *   </ul>
 * );
 */
export function useAgents() {
  const setAgentConfigurations = useSystemStore((state) => state.setAgentConfigurations);

  const query = useQuery({
    queryKey: ['agents'],
    queryFn: async () => {
      const response = await agentService.getAgents();
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    refetchInterval: 30000, // Refetch every 30 seconds
  });

  // Update Zustand store when data is fetched
  // Note: AgentInfo[] needs to be converted to AgentConfig[] for the store
  if (query.data) {
    const agentConfigs: AgentConfig[] = query.data.map(agent => ({
      id: agent.id,
      name: agent.name,
      type: agent.type,
      parameters: agent.configuration || {},
      enabled: agent.status === 'active',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }));
    setAgentConfigurations(agentConfigs);
  }

  return query;
}

/**
 * Hook for fetching a specific agent by ID.
 *
 * Only fetches when an ID is provided. Useful for loading agent details
 * on a detail page or when selecting an agent.
 *
 * @param {string} id - The unique identifier of the agent to fetch
 * @returns {UseQueryResult<AgentInfo, Error>} Query object containing agent information
 * @throws {Error} If the API request fails or agent is not found
 *
 * @example
 * const { data: agent, isLoading } = useAgentById('agent-123');
 *
 * if (isLoading) return <div>Loading agent details...</div>;
 *
 * return <div>{agent?.name} ({agent?.type})</div>;
 */
export function useAgentById(id: string) {
  return useQuery({
    queryKey: ['agent', id],
    queryFn: async () => {
      const response = await agentService.getAgentById(id);
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    enabled: !!id, // Only fetch if ID is provided
  });
}

/**
 * Hook for fetching agent metrics.
 *
 * Retrieves real-time performance metrics for a specific agent.
 * Refetches every 10 seconds for real-time updates.
 * Only fetches when an ID is provided.
 *
 * @param {string} id - The unique identifier of the agent
 * @returns {UseQueryResult<AgentMetrics, Error>} Query object containing:
 *   - requestsProcessed: Number of requests handled
 *   - averageResponseTime: Average response time in milliseconds
 *   - errorRate: Percentage of failed requests
 *   - memoryUsage: Current memory usage in bytes
 * @throws {Error} If the API request fails
 *
 * @example
 * const { data: metrics } = useAgentMetrics('agent-123');
 *
 * return (
 *   <div>
 *     <p>Requests: {metrics?.requestsProcessed}</p>
 *     <p>Avg Response: {metrics?.averageResponseTime}ms</p>
 *     <p>Error Rate: {(metrics?.errorRate * 100).toFixed(2)}%</p>
 *   </div>
 * );
 */
export function useAgentMetrics(id: string) {
  return useQuery({
    queryKey: ['agent-metrics', id],
    queryFn: async () => {
      const response = await agentService.getAgentMetrics(id);
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    enabled: !!id, // Only fetch if ID is provided
    refetchInterval: 10000, // Refetch every 10 seconds for real-time metrics
  });
}

/**
 * Hook for creating a new agent.
 *
 * Provides a mutation function to create a new agent configuration.
 * Automatically invalidates the agents query after successful creation.
 *
 * @returns {UseMutationResult<AgentConfig, Error, Omit<AgentConfig, 'id' | 'createdAt' | 'updatedAt'>>} Mutation object with:
 *   - mutate: Function to trigger agent creation
 *   - isPending: Whether the mutation is in progress
 *   - error: Error object if mutation failed
 *   - data: Created agent configuration
 * @throws {Error} If the API request fails
 *
 * @example
 * const { mutate: createAgent, isPending } = useCreateAgent();
 *
 * const handleCreate = () => {
 *   createAgent({
 *     name: 'New Agent',
 *     type: 'llm',
 *     parameters: { model: 'gpt-4' },
 *     enabled: true,
 *   });
 * };
 */
export function useCreateAgent() {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async (config: Omit<AgentConfig, 'id' | 'createdAt' | 'updatedAt'>) => {
      const response = await agentService.createAgent(config);
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    onSuccess: () => {
      // Invalidate agents query to refetch the list
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });

  return mutation;
}

/**
 * Hook for updating an agent configuration.
 *
 * Provides a mutation function to update an existing agent.
 * Updates both the API and local Zustand store on success.
 * Invalidates related queries to keep data in sync.
 *
 * @returns {UseMutationResult<AgentConfig, Error, {id: string, config: Partial<AgentConfig>}>} Mutation object with:
 *   - mutate: Function to trigger agent update with {id, config} parameter
 *   - isPending: Whether the mutation is in progress
 *   - error: Error object if mutation failed
 * @throws {Error} If the API request fails
 *
 * @example
 * const { mutate: updateAgent } = useUpdateAgent();
 *
 * updateAgent({
 *   id: 'agent-123',
 *   config: { enabled: false, parameters: { model: 'gpt-3.5' } }
 * });
 */
export function useUpdateAgent() {
  const queryClient = useQueryClient();
  const updateAgentConfiguration = useSystemStore((state) => state.updateAgentConfiguration);

  const mutation = useMutation({
    mutationFn: async ({ id, config }: { id: string; config: Partial<AgentConfig> }) => {
      const response = await agentService.updateAgent(id, config);
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    onSuccess: (data) => {
      // Update Zustand store
      if (data) {
        updateAgentConfiguration(data);
        
        // Invalidate agent queries
        queryClient.invalidateQueries({ queryKey: ['agents'] });
        queryClient.invalidateQueries({ queryKey: ['agent', data.id] });
      }
    },
  });

  return mutation;
}

/**
 * Hook for deleting an agent.
 *
 * Provides a mutation function to delete an agent configuration.
 * Automatically invalidates the agents query after successful deletion.
 *
 * @returns {UseMutationResult<{message: string}, Error, string>} Mutation object with:
 *   - mutate: Function to trigger agent deletion with agent ID
 *   - isPending: Whether the mutation is in progress
 *   - error: Error object if mutation failed
 * @throws {Error} If the API request fails
 *
 * @example
 * const { mutate: deleteAgent } = useDeleteAgent();
 *
 * const handleDelete = (agentId: string) => {
 *   if (confirm('Are you sure?')) {
 *     deleteAgent(agentId);
 *   }
 * };
 */
export function useDeleteAgent() {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async (id: string) => {
      const response = await agentService.deleteAgent(id);
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    onSuccess: () => {
      // Invalidate agents query to refetch the list
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });

  return mutation;
}

/**
 * Hook for agent lifecycle actions (start, stop, restart, test).
 *
 * Provides mutation functions for controlling agent state and testing connectivity.
 * Each action automatically invalidates the agents query on success.
 *
 * @returns {Object} Object containing mutation functions:
 *   - startAgent: Mutation to start an agent (takes agent ID)
 *   - stopAgent: Mutation to stop an agent (takes agent ID)
 *   - restartAgent: Mutation to restart an agent (takes agent ID)
 *   - testAgent: Mutation to test agent connectivity (takes agent ID)
 * @throws {Error} If any API request fails
 *
 * @example
 * const { startAgent, stopAgent, restartAgent, testAgent } = useAgentActions();
 *
 * // Start an agent
 * startAgent.mutate('agent-123');
 *
 * // Test connectivity
 * testAgent.mutate('agent-123');
 *
 * // Check status
 * if (startAgent.isPending) return <div>Starting...</div>;
 * if (startAgent.error) return <div>Error: {startAgent.error.message}</div>;
 */
export function useAgentActions() {
  const queryClient = useQueryClient();

  const startAgent = useMutation({
    mutationFn: async (id: string) => {
      const response = await agentService.startAgent(id);
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });

  const stopAgent = useMutation({
    mutationFn: async (id: string) => {
      const response = await agentService.stopAgent(id);
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });

  const restartAgent = useMutation({
    mutationFn: async (id: string) => {
      const response = await agentService.restartAgent(id);
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });

  const testAgent = useMutation({
    mutationFn: async (id: string) => {
      const response = await agentService.testAgent(id);
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
  });

  return {
    startAgent,
    stopAgent,
    restartAgent,
    testAgent,
  };
}

/**
 * Hook for fetching available agent types.
 *
 * Retrieves the list of supported agent types in the system.
 * Data is cached for 5 minutes to reduce API calls.
 *
 * @returns {UseQueryResult<string[], Error>} Query object containing array of agent type names
 * @throws {Error} If the API request fails
 *
 * @example
 * const { data: agentTypes } = useAgentTypes();
 *
 * return (
 *   <select>
 *     {agentTypes?.map(type => (
 *       <option key={type} value={type}>{type}</option>
 *     ))}
 *   </select>
 * );
 */
export function useAgentTypes() {
  return useQuery({
    queryKey: ['agent-types'],
    queryFn: async () => {
      const response = await agentService.getAgentTypes();
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    staleTime: 300000, // Consider data stale after 5 minutes
  });
}

/**
 * Hook for fetching agent capabilities.
 *
 * Retrieves the capabilities available for each agent type.
 * Data is cached for 5 minutes to reduce API calls.
 *
 * @returns {UseQueryResult<Record<string, string[]>, Error>} Query object containing:
 *   - Object mapping agent types to their available capabilities
 *   - Example: { 'llm': ['chat', 'analysis'], 'tool': ['execute', 'schedule'] }
 * @throws {Error} If the API request fails
 *
 * @example
 * const { data: capabilities } = useAgentCapabilities();
 *
 * return (
 *   <div>
 *     {Object.entries(capabilities || {}).map(([type, caps]) => (
 *       <div key={type}>
 *         <h3>{type}</h3>
 *         <ul>
 *           {caps.map(cap => <li key={cap}>{cap}</li>)}
 *         </ul>
 *       </div>
 *     ))}
 *   </div>
 * );
 */
export function useAgentCapabilities() {
  return useQuery({
    queryKey: ['agent-capabilities'],
    queryFn: async () => {
      const response = await agentService.getAgentCapabilities();
      if (response.error) {
        throw new Error(response.error.message);
      }
      return response.data;
    },
    staleTime: 300000, // Consider data stale after 5 minutes
  });
}