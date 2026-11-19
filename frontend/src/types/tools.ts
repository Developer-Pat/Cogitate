/**
 * Tools Management TypeScript types.
 * 
 * Type definitions for the Agent Tools Management System.
 */

/**
 * Tool Category
 */
export interface ToolCategory {
  id: string;
  parent_id: string | null;
  name: string;
  slug: string;
  description: string | null;
  icon: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

/**
 * Tool Category for creation
 */
export interface ToolCategoryCreate {
  name: string;
  slug: string;
  description?: string | null;
  icon?: string | null;
  sort_order?: number;
  parent_id?: string | null;
}

/**
 * Tool Category for update
 */
export interface ToolCategoryUpdate {
  name?: string;
  slug?: string;
  description?: string | null;
  icon?: string | null;
  sort_order?: number;
}

/**
 * Tool Category response
 */
export type ToolCategoryResponse = ToolCategory;

/**
 * Tool Category list response
 */
export interface ToolCategoryListResponse {
  categories: ToolCategoryResponse[];
  total: number;
}

/**
 * Category summary (for nested references)
 */
export interface CategorySummary {
  id: string;
  name: string;
  slug: string;
  icon: string | null;
}

/**
 * Tool Definition
 */
export interface Tool {
  id: string;
  name: string;
  slug: string;
  description: string;
  version: string;
  category_id: string | null;
  provider: string | null;
  type: string | null;
  config_schema: Record<string, unknown>;
  endpoint: string | null;
  timeout_ms: number;
  requires_auth: boolean;
  icon: string | null;
  color: string | null;
  tags: string[] | null;
  is_active: boolean;
  is_builtin: boolean;
  capability: string | null;
  usage_count: number;
  created_at: string;
  updated_at: string;
}

/**
 * Tool for creation
 */
export interface ToolCreate {
  name: string;
  slug: string;
  description: string;
  version?: string;
  category_id?: string | null;
  provider?: string | null;
  type?: string | null;
  config_schema?: Record<string, unknown>;
  endpoint?: string | null;
  timeout_ms?: number;
  requires_auth?: boolean;
  icon?: string | null;
  color?: string | null;
  tags?: string[] | null;
  is_active?: boolean;
  is_builtin?: boolean;
}

/**
 * Tool for update
 */
export interface ToolUpdate {
  name?: string;
  slug?: string;
  description?: string;
  version?: string;
  category_id?: string | null;
  provider?: string | null;
  type?: string | null;
  config_schema?: Record<string, unknown>;
  endpoint?: string | null;
  timeout_ms?: number;
  requires_auth?: boolean;
  icon?: string | null;
  color?: string | null;
  tags?: string[] | null;
  is_active?: boolean;
  is_builtin?: boolean;
}

/**
 * Tool response with category info
 */
export interface ToolResponse extends Tool {
  category: CategorySummary | null;
}

/**
 * Tool list response
 */
export interface ToolListResponse {
  tools: ToolResponse[];
  total: number;
}

/**
 * Tool search response
 */
export interface ToolSearchResponse extends ToolListResponse {
  query: string;
  filters: Record<string, unknown> | null;
}

/**
 * Tool summary (for nested references)
 */
export interface ToolSummary {
  id: string;
  name: string;
  slug: string;
  description: string;
  icon: string | null;
  color: string | null;
  category: CategorySummary | null;
  config_schema: Record<string, unknown>;
}

/**
 * Agent-Tool Association
 */
export interface AgentTool {
  id: string;
  agent_id: string;
  tool_id: string;
  is_enabled: boolean;
  priority: number;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/**
 * Agent-Tool for creation
 */
export interface AgentToolCreate {
  tool_id: string;
  is_enabled?: boolean;
  priority?: number;
  config?: Record<string, unknown>;
}

/**
 * Agent-Tool for update
 */
export interface AgentToolUpdate {
  is_enabled?: boolean;
  priority?: number;
  config?: Record<string, unknown>;
}

/**
 * Agent-Tool response with tool info
 */
export interface AgentToolResponse extends AgentTool {
  tool: ToolSummary | null;
}

/**
 * Agent-Tool list response
 */
export interface AgentToolListResponse {
  tools: AgentToolResponse[];
  total: number;
}

/**
 * Agent-Tool enable request
 */
export interface AgentToolEnableRequest {
  tool_id: string;
  priority?: number;
  config?: Record<string, unknown>;
}

/**
 * Tool Usage Log
 */
export interface ToolUsageLog {
  id: string;
  tool_id: string;
  agent_id: string;
  session_id: string | null;
  success: boolean;
  execution_time_ms: number | null;
  error_message: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

/**
 * Tool Usage Log for creation
 */
export interface ToolUsageLogCreate {
  tool_id: string;
  agent_id: string;
  session_id?: string | null;
  success?: boolean;
  execution_time_ms?: number | null;
  error_message?: string | null;
  metadata?: Record<string, unknown> | null;
}

/**
 * Tool Usage Log response with tool name
 */
export interface ToolUsageLogResponse extends ToolUsageLog {
  tool_name: string | null;
}

/**
 * Tool Usage Log list response
 */
export interface ToolUsageLogListResponse {
  logs: ToolUsageLogResponse[];
  total: number;
}

/**
 * Tool Usage Statistics
 */
export interface ToolUsageStats {
  tool_id: string;
  tool_name: string;
  total_usage: number;
  success_rate: number;
  avg_execution_time_ms: number | null;
}

/**
 * Tool Usage Statistics response
 */
export interface ToolUsageStatsResponse {
  stats: ToolUsageStats[];
  period_start: string;
  period_end: string;
}

/**
 * Tool Registry (runtime)
 */
export interface ToolDefinition {
  name: string;
  slug: string;
  description: string;
  handler?: (...args: unknown[]) => unknown;
  config_schema: Record<string, unknown>;
  is_builtin: boolean;
  metadata: Record<string, unknown>;
}

/**
 * Tool search filters
 */
export interface ToolFilters {
  category_id?: string;
  is_active?: boolean;
  provider?: string;
  tags?: string[];
  query?: string;
  limit?: number;
  offset?: number;
}

/**
 * Agent tools filters
 */
export interface AgentToolsFilters {
  is_enabled?: boolean;
}

/**
 * Tool usage filters
 */
export interface ToolUsageFilters {
  tool_id?: string;
  agent_id?: string;
  session_id?: string;
  success?: boolean;
  limit?: number;
  offset?: number;
}

/**
 * Tool usage stats filters
 */
export interface ToolUsageStatsFilters {
  tool_id?: string;
  agent_id?: string;
  days?: number;
}