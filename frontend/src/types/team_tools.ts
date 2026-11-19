/**
 * Team Tools domain types.
 *
 * TypeScript interfaces for team-tool assignment management.
 */

import type { Collection, CollectionItem } from './collections';

/**
 * Source type for team tool assignments.
 * - 'direct': Tool was directly assigned to the team
 * - 'toolbox': Tool was assigned via a toolbox
 */
export type TeamToolSourceType = 'direct' | 'toolbox';

/**
 * Represents a tool assignment to a team.
 */
export interface TeamTool {
  id: string;
  team_id: string;
  tool_id: string;
  source_type: TeamToolSourceType;
  source_id: string | null; // toolbox_id if source_type is 'toolbox'
  priority: number;
  is_active: boolean;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  tool?: ToolSummary;
}

/**
 * Tool summary for team tool responses.
 */
export interface ToolSummary {
  id: string;
  name: string;
  slug: string;
  description: string;
  icon: string | null;
  color: string | null;
  is_active: boolean;
}

/**
 * Request payload for creating a team tool assignment.
 */
export interface TeamToolCreate {
  tool_id: string;
  source_type: TeamToolSourceType;
  source_id?: string | null;
  priority?: number;
  is_active?: boolean;
  config?: Record<string, unknown>;
}

/**
 * Request payload for updating a team tool assignment.
 */
export interface TeamToolUpdate {
  priority?: number;
  is_active?: boolean;
  config?: Record<string, unknown>;
}

/**
 * Response for listing team tools.
 */
export interface TeamToolListResponse {
  tools: TeamTool[];
  total: number;
}

/**
 * Request payload for assigning a toolbox to a team.
 */
export interface ToolboxAssignCreate {
  toolbox_id: string;
  priority?: number;
}

/**
 * Response for toolbox assignment.
 */
export interface ToolboxAssignResponse {
  id: string;
  team_id: string;
  toolbox_id: string;
  tool_count: number;
  tools_added: Array<{ tool_id: string; tool_name: string }>;
  created_at: string;
}

/**
 * Request payload for team sync.
 */
export interface TeamSyncRequest {
  agent_ids?: string[];
}

/**
 * Information about a tool assignment conflict.
 */
export interface ConflictInfo {
  agent_id: string;
  tool_id: string;
  tool_name: string;
  conflicting_teams: Array<{ team_id: string; team_name: string }>;
  resolution: 'last_team_wins';
  winning_team_id: string;
}

/**
 * Response for team sync operation.
 */
export interface TeamSyncResponse {
  synced_agents: string[];
  tools_assigned: number;
  tools_removed: number;
  conflicts_detected: number;
  conflicts: ConflictInfo[];
}

/**
 * Team detail with extended information.
 */
export interface Team extends Collection {
  members: CollectionItem[];
  tools: TeamTool[];
}
