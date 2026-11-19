/**
 * Tool Permissions TypeScript types.
 *
 * Type definitions for tool-collection permission management.
 */

/**
 * Valid permission levels for tool access
 */
export type PermissionLevel = 'read' | 'execute' | 'write' | 'admin' | 'deny';

/**
 * Permission level display metadata
 */
export interface PermissionLevelInfo {
  label: string;
  description: string;
  color: string;
}

/**
 * Collection summary for permission display
 */
export interface CollectionSummary {
  id: string;
  name: string;
  entity_type: string;
  icon: string | null;
  color: string | null;
}

/**
 * Tool collection permission
 */
export interface ToolCollectionPermission {
  id: string;
  tool_id: string;
  collection_id: string;
  permission_level: PermissionLevel;
  collection: CollectionSummary | null;
  created_at: string;
  updated_at: string;
}

/**
 * Permission summary for a tool
 */
export interface ToolPermissionSummary {
  collection_id: string;
  collection_name: string;
  permission_level: PermissionLevel;
  member_count: number;
  created_at: string;
  updated_at: string;
}

/**
 * Tool permissions response
 */
export interface ToolPermissionsResponse {
  tool_id: string;
  tool_name: string;
  default_access: PermissionLevel;
  permissions: ToolPermissionSummary[];
  total: number;
}

/**
 * Tool permissions update request
 */
export interface ToolPermissionsUpdateRequest {
  default_access?: PermissionLevel;
  permissions: Array<{
    collection_id: string;
    permission_level: PermissionLevel;
  }>;
}

/**
 * Permission check response
 */
export interface PermissionCheckResponse {
  has_permission: boolean;
  permission_level: PermissionLevel | null;
  required: string | null;
  source: string | null;
  message: string | null;
}

/**
 * Accessible tool summary
 */
export interface AccessibleToolSummary {
  id: string;
  name: string;
  slug: string;
  description: string;
  icon: string | null;
  color: string | null;
  type: string | null;
  provider: string | null;
  permission_level: PermissionLevel;
}

/**
 * Accessible tools response
 */
export interface AccessibleToolsResponse {
  tools: AccessibleToolSummary[];
  total: number;
  user_id: string | null;
  permission_filter: string | null;
}

/**
 * Permission filters
 */
export interface PermissionFilters {
  user_id?: string;
  permission?: PermissionLevel;
  limit?: number;
  offset?: number;
}

/**
 * Permission level metadata helper
 */
export const PERMISSION_LEVELS: Record<PermissionLevel, PermissionLevelInfo> = {
  read: {
    label: 'Read',
    description: 'Can view tool',
    color: 'badge-ghost',
  },
  execute: {
    label: 'Execute',
    description: 'Can use tool in Chat/Workflow',
    color: 'badge-primary',
  },
  write: {
    label: 'Write',
    description: 'Can modify tool settings',
    color: 'badge-secondary',
  },
  admin: {
    label: 'Admin',
    description: 'Full control including permissions',
    color: 'badge-accent',
  },
  deny: {
    label: 'Denied',
    description: 'No access',
    color: 'badge-error',
  },
};

/**
 * Get permission level info
 */
export function getPermissionLevelInfo(level: PermissionLevel): PermissionLevelInfo {
  return PERMISSION_LEVELS[level] || PERMISSION_LEVELS.read;
}

/**
 * Check if permission level meets requirement
 */
export function hasPermission(current: PermissionLevel, required: PermissionLevel): boolean {
  const hierarchy: Record<PermissionLevel, number> = {
    deny: -1,
    read: 0,
    execute: 1,
    write: 2,
    admin: 3,
  };
  
  return (hierarchy[current] || 0) >= (hierarchy[required] || 0);
}
