import { apiClient } from '../apiClient';
import { frontendLoggingService } from '../frontendLoggingService';

export interface KitSummary {
  id: string;
  name: string;
  description?: string | null;
  color: string;
  icon: string;
}

export interface AgentOwnerSummary {
  id: number;
  name: string;
}

export interface AgentKitsResponse {
  agent_id: number;
  kits: KitSummary[];
}

export interface AgentOwnersResponse {
  kit_id: string;
  agents: AgentOwnerSummary[];
}

/**
 * THE AGENT KITS (2026-09-04, the agent-kits build P4): the
 * frontend side of the agent_kits JOIN — kits-for-agent +
 * attach/detach on the agents router, and the agent-owners read
 * on the collections router.
 */
export class AgentKitService {
  private readonly agentsPath = '/api/v1/agents';
  private readonly collectionsPath = '/api/v1/collections';

  /** The toolkits an agent owns. */
  async getAgentKits(agentId: number): Promise<KitSummary[]> {
    try {
      const response = await apiClient.get<AgentKitsResponse>(
        `${this.agentsPath}/${agentId}/kits`
      );
      if (response.error) {
        frontendLoggingService.error('AgentKitService', 'Failed to get agent kits', response.error);
        throw new Error(response.error.message);
      }
      return response.data?.kits ?? [];
    } catch (error) {
      frontendLoggingService.error('AgentKitService', 'Failed to get agent kits', error);
      throw error;
    }
  }

  /** Attach a toolkit to an agent (idempotent). Returns the refreshed list. */
  async attachKit(agentId: number, kitId: string): Promise<KitSummary[]> {
    try {
      const response = await apiClient.post<AgentKitsResponse>(
        `${this.agentsPath}/${agentId}/kits`,
        { kit_id: kitId }
      );
      if (response.error) {
        frontendLoggingService.error('AgentKitService', 'Failed to attach kit', response.error);
        throw new Error(response.error.message);
      }
      return response.data?.kits ?? [];
    } catch (error) {
      frontendLoggingService.error('AgentKitService', 'Failed to attach kit', error);
      throw error;
    }
  }

  /** Detach a toolkit from an agent. */
  async detachKit(agentId: number, kitId: string): Promise<void> {
    try {
      const response = await apiClient.delete(`${this.agentsPath}/${agentId}/kits/${kitId}`);
      if (response.error) {
        frontendLoggingService.error('AgentKitService', 'Failed to detach kit', response.error);
        throw new Error(response.error.message);
      }
    } catch (error) {
      frontendLoggingService.error('AgentKitService', 'Failed to detach kit', error);
      throw error;
    }
  }

  /** The agents that own a kit (tool-typed collections only). */
  async getKitOwners(kitId: string): Promise<AgentOwnerSummary[]> {
    try {
      const response = await apiClient.get<AgentOwnersResponse>(
        `${this.collectionsPath}/${kitId}/agent-owners`
      );
      if (response.error) {
        frontendLoggingService.error('AgentKitService', 'Failed to get kit owners', response.error);
        throw new Error(response.error.message);
      }
      return response.data?.agents ?? [];
    } catch (error) {
      frontendLoggingService.error('AgentKitService', 'Failed to get kit owners', error);
      throw error;
    }
  }
}

export const agentKitService = new AgentKitService();
