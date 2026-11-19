/**
 * TeamToolService - Manage team-tool assignments.
 *
 * Provides API client for team tool management endpoints.
 */

import type {
  TeamTool,
  TeamToolCreate,
  TeamToolUpdate,
  TeamToolListResponse,
  TeamSyncRequest,
  TeamSyncResponse,
  Team,
} from '@/types/team_tools';
import type { Collection, CollectionItem, CollectionCreate, CollectionUpdate, CollectionItemCreate } from '@/types/collections';
import { apiClient } from '../apiClient';
import { frontendLoggingService } from '../frontendLoggingService';

/**
 * TeamToolService - Manage team tools and team members
 */
export class TeamToolService {
  private teamsPath = '/api/v1/teams';
  private teamsCache: Collection[] | null = null;
  private cacheTimestamp: number | null = null;
  private readonly CACHE_TTL = 2 * 60 * 1000; // 2 minutes

  // =========================================================================
  // Team Management
  // =========================================================================

  /**
   * List all teams.
   */
  async listTeams(): Promise<Collection[]> {
    const useCache = true;

    if (useCache && this.teamsCache && this.cacheTimestamp) {
      const now = Date.now();
      if (now - this.cacheTimestamp < this.CACHE_TTL) {
        frontendLoggingService.debug('TeamToolService', 'Returning cached teams', {
          count: this.teamsCache.length
        });
        return this.teamsCache;
      }
    }

    try {
      const response = await apiClient.get<Collection[]>(this.teamsPath);

      if (response.error) {
        frontendLoggingService.error('TeamToolService', 'Failed to list teams', response.error);
        throw new Error(response.error.message);
      }

      const result = response.data!;

      // Update cache
      this.teamsCache = result;
      this.cacheTimestamp = Date.now();

      frontendLoggingService.debug('TeamToolService', `Listed ${result.length} teams`);
      return result;
    } catch (error) {
      frontendLoggingService.error('TeamToolService', 'Failed to list teams', error);
      throw error;
    }
  }

  /**
   * Get a single team by ID with members and tools.
   */
  async getTeam(teamId: string): Promise<Team> {
    try {
      const [teamResponse, membersResponse, toolsResponse] = await Promise.all([
        apiClient.get<Collection>(`${this.teamsPath}/${teamId}`),
        apiClient.get<CollectionItem[]>(`${this.teamsPath}/${teamId}/members`),
        apiClient.get<TeamToolListResponse>(`${this.teamsPath}/${teamId}/tools`),
      ]);

      if (teamResponse.error) {
        frontendLoggingService.error('TeamToolService', 'Failed to get team', teamResponse.error);
        throw new Error(teamResponse.error.message);
      }

      if (membersResponse.error) {
        frontendLoggingService.error('TeamToolService', 'Failed to get team members', membersResponse.error);
        throw new Error(membersResponse.error.message);
      }

      if (toolsResponse.error) {
        frontendLoggingService.error('TeamToolService', 'Failed to get team tools', toolsResponse.error);
        throw new Error(toolsResponse.error.message);
      }

      const team: Team = {
        ...teamResponse.data!,
        members: membersResponse.data! || [],
        tools: toolsResponse.data?.tools || [],
      };

      frontendLoggingService.debug('TeamToolService', 'Got team', {
        teamId,
        name: team.name,
        membersCount: team.members.length,
        toolsCount: team.tools.length
      });

      return team;
    } catch (error) {
      frontendLoggingService.error('TeamToolService', 'Failed to get team', error);
      throw error;
    }
  }

  /**
   * Create a new team.
   */
  async createTeam(teamData: CollectionCreate): Promise<Collection> {
    try {
      const response = await apiClient.post<Collection>(this.teamsPath, {
        ...teamData,
        entity_type: 'agent' as const,
      });

      if (response.error) {
        frontendLoggingService.error('TeamToolService', 'Failed to create team', response.error);
        throw new Error(response.error.message);
      }

      // Invalidate cache
      this.invalidateCache();

      frontendLoggingService.info('TeamToolService', 'Created team', {
        teamId: response.data?.id,
        name: response.data?.name
      });

      return response.data!;
    } catch (error) {
      frontendLoggingService.error('TeamToolService', 'Failed to create team', error);
      throw error;
    }
  }

  /**
   * Update an existing team.
   */
  async updateTeam(
    teamId: string,
    teamData: CollectionUpdate
  ): Promise<Collection> {
    try {
      const response = await apiClient.put<Collection>(`${this.teamsPath}/${teamId}`, teamData);

      if (response.error) {
        frontendLoggingService.error('TeamToolService', 'Failed to update team', response.error);
        throw new Error(response.error.message);
      }

      // Invalidate cache
      this.invalidateCache();

      frontendLoggingService.info('TeamToolService', 'Updated team', {
        teamId,
        ...teamData
      });

      return response.data!;
    } catch (error) {
      frontendLoggingService.error('TeamToolService', 'Failed to update team', error);
      throw error;
    }
  }

  /**
   * Delete a team.
   */
  async deleteTeam(teamId: string): Promise<void> {
    try {
      const response = await apiClient.delete(`${this.teamsPath}/${teamId}`);

      if (response.error) {
        frontendLoggingService.error('TeamToolService', 'Failed to delete team', response.error);
        throw new Error(response.error.message);
      }

      // Invalidate cache
      this.invalidateCache();

      frontendLoggingService.info('TeamToolService', 'Deleted team', {
        teamId
      });
    } catch (error) {
      frontendLoggingService.error('TeamToolService', 'Failed to delete team', error);
      throw error;
    }
  }

  // =========================================================================
  // Team Member Management
  // =========================================================================

  /**
   * Add a member (agent) to a team.
   */
  async addMemberToTeam(
    teamId: string,
    memberData: CollectionItemCreate
  ): Promise<CollectionItem> {
    try {
      const response = await apiClient.post<CollectionItem>(
        `${this.teamsPath}/${teamId}/members`,
        {
          ...memberData,
          entity_type: 'agent' as const,
        }
      );

      if (response.error) {
        frontendLoggingService.error('TeamToolService', 'Failed to add member to team', response.error);
        throw new Error(response.error.message);
      }

      frontendLoggingService.info('TeamToolService', 'Added member to team', {
        teamId,
        agentId: memberData.entity_id,
        agentName: memberData.entity_name
      });

      return response.data!;
    } catch (error) {
      frontendLoggingService.error('TeamToolService', 'Failed to add member to team', error);
      throw error;
    }
  }

  /**
   * Remove a member from a team.
   */
  async removeMemberFromTeam(
    teamId: string,
    memberId: string
  ): Promise<void> {
    try {
      const response = await apiClient.delete(`${this.teamsPath}/${teamId}/members/${memberId}`);

      if (response.error) {
        frontendLoggingService.error('TeamToolService', 'Failed to remove member from team', response.error);
        throw new Error(response.error.message);
      }

      frontendLoggingService.info('TeamToolService', 'Removed member from team', {
        teamId,
        memberId
      });
    } catch (error) {
      frontendLoggingService.error('TeamToolService', 'Failed to remove member from team', error);
      throw error;
    }
  }

  /**
   * Get all members of a team.
   */
  async getTeamMembers(teamId: string): Promise<CollectionItem[]> {
    try {
      const response = await apiClient.get<CollectionItem[]>(`${this.teamsPath}/${teamId}/members`);

      if (response.error) {
        frontendLoggingService.error('TeamToolService', 'Failed to get team members', response.error);
        throw new Error(response.error.message);
      }

      frontendLoggingService.debug('TeamToolService', 'Got team members', {
        teamId,
        count: response.data?.length
      });

      return response.data!;
    } catch (error) {
      frontendLoggingService.error('TeamToolService', 'Failed to get team members', error);
      throw error;
    }
  }

  // =========================================================================
  // Team Tools Management
  // =========================================================================

  /**
   * Get all tools assigned to a team.
   */
  async getTeamTools(teamId: string): Promise<TeamTool[]> {
    try {
      const response = await apiClient.get<TeamToolListResponse>(`${this.teamsPath}/${teamId}/tools`);

      if (response.error) {
        frontendLoggingService.error('TeamToolService', 'Failed to get team tools', response.error);
        throw new Error(response.error.message);
      }

      frontendLoggingService.debug('TeamToolService', 'Got team tools', {
        teamId,
        count: response.data?.total
      });

      return response.data?.tools || [];
    } catch (error) {
      frontendLoggingService.error('TeamToolService', 'Failed to get team tools', error);
      throw error;
    }
  }

  /**
   * Assign a tool to a team.
   */
  async assignToolToTeam(
    teamId: string,
    toolData: TeamToolCreate
  ): Promise<TeamTool> {
    try {
      const response = await apiClient.post<TeamTool>(
        `${this.teamsPath}/${teamId}/tools`,
        toolData
      );

      if (response.error) {
        frontendLoggingService.error('TeamToolService', 'Failed to assign tool to team', response.error);
        throw new Error(response.error.message);
      }

      frontendLoggingService.info('TeamToolService', 'Assigned tool to team', {
        teamId,
        toolId: toolData.tool_id
      });

      return response.data!;
    } catch (error) {
      frontendLoggingService.error('TeamToolService', 'Failed to assign tool to team', error);
      throw error;
    }
  }

  /**
   * Update team tool configuration.
   */
  async updateTeamTool(
    teamId: string,
    toolId: string,
    updateData: TeamToolUpdate
  ): Promise<TeamTool> {
    try {
      const response = await apiClient.put<TeamTool>(
        `${this.teamsPath}/${teamId}/tools/${toolId}`,
        updateData
      );

      if (response.error) {
        frontendLoggingService.error('TeamToolService', 'Failed to update team tool', response.error);
        throw new Error(response.error.message);
      }

      frontendLoggingService.info('TeamToolService', 'Updated team tool', {
        teamId,
        toolId
      });

      return response.data!;
    } catch (error) {
      frontendLoggingService.error('TeamToolService', 'Failed to update team tool', error);
      throw error;
    }
  }

  /**
   * Remove a tool from a team.
   */
  async removeToolFromTeam(
    teamId: string,
    toolId: string,
    sourceType?: 'direct' | 'toolbox'
  ): Promise<void> {
    try {
      const params = sourceType ? `?source_type=${sourceType}` : '';
      const response = await apiClient.delete(`${this.teamsPath}/${teamId}/tools/${toolId}${params}`);

      if (response.error) {
        frontendLoggingService.error('TeamToolService', 'Failed to remove tool from team', response.error);
        throw new Error(response.error.message);
      }

      frontendLoggingService.info('TeamToolService', 'Removed tool from team', {
        teamId,
        toolId
      });
    } catch (error) {
      frontendLoggingService.error('TeamToolService', 'Failed to remove tool from team', error);
      throw error;
    }
  }

  // =========================================================================
  // Team Toolbox Management
  // =========================================================================



  // =========================================================================
  // Team Sync
  // =========================================================================

  /**
   * Sync team tools to team members.
   */
  async syncTeamTools(
    teamId: string,
    agentIds?: string[]
  ): Promise<TeamSyncResponse> {
    try {
      const syncRequest: TeamSyncRequest = agentIds ? { agent_ids: agentIds } : {};
      
      const response = await apiClient.post<TeamSyncResponse>(
        `${this.teamsPath}/${teamId}/sync`,
        syncRequest
      );

      if (response.error) {
        frontendLoggingService.error('TeamToolService', 'Failed to sync team tools', response.error);
        throw new Error(response.error.message);
      }

      frontendLoggingService.info('TeamToolService', 'Synced team tools', {
        teamId,
        syncedAgents: response.data?.synced_agents?.length,
        toolsAssigned: response.data?.tools_assigned,
        conflictsDetected: response.data?.conflicts_detected
      });

      return response.data!;
    } catch (error) {
      frontendLoggingService.error('TeamToolService', 'Failed to sync team tools', error);
      throw error;
    }
  }

  // =========================================================================
  // Cache Management
  // =========================================================================

  /**
   * Invalidate the teams cache.
   */
  private invalidateCache(): void {
    this.teamsCache = null;
    this.cacheTimestamp = null;
    frontendLoggingService.debug('TeamToolService', 'Cache invalidated');
  }

  /**
   * Clear the teams cache.
   */
  clearCache(): void {
    this.invalidateCache();
  }
}

// Create and export a singleton instance
export const teamToolService = new TeamToolService();

export default teamToolService;
