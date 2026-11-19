/**
 * Core TypeScript types for GenericApp Frontend
 *
 * This module exports all core type definitions used throughout the application,
 * organized by domain (authentication, system health, agents, workflows, etc.).
 */

/**
 * Represents a user in the system.
 *
 * @interface User
 * @property {string} id - Unique identifier for the user
 * @property {string} username - User's login username
 * @property {string} email - User's email address
 * @property {string} role - User's role (e.g., 'admin', 'user', 'viewer')
 * @property {string[]} permissions - Array of permission strings the user has
 * @property {string} createdAt - ISO 8601 timestamp of account creation
 * @property {string} [lastLogin] - ISO 8601 timestamp of last login
 */
export interface User {
  id: string;
  username: string;
  email: string;
  role: string;
  permissions: string[];
  createdAt: string;
  lastLogin?: string;
}

/**
 * Represents the current authentication state.
 *
 * @interface AuthState
 * @property {boolean} isAuthenticated - Whether a user is currently authenticated
 * @property {User | null} user - Current authenticated user or null
 * @property {string | null} token - Authentication token or null
 * @property {boolean} loading - Whether authentication is in progress
 */
export interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
  loading: boolean;
}

/**
 * Represents the overall system health status.
 *
 * @interface SystemHealth
 * @property {string} status - Overall system status: 'healthy', 'degraded', or 'unhealthy'
 * @property {string} timestamp - ISO 8601 timestamp of the health check
 * @property {ServiceStatus[]} services - Array of individual service statuses
 * @property {SystemMetrics} metrics - System resource metrics
 * @property {number} uptime - System uptime in seconds
 * @property {string} version - System version string
 */
export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  services: ServiceStatus[];
  metrics: SystemMetrics;
  uptime: number;
  version: string;
}

/**
 * Represents the status of a single service.
 *
 * @interface ServiceStatus
 * @property {string} name - Name of the service
 * @property {string} status - Service status: 'running', 'stopped', 'error', or 'unknown'
 * @property {string} health - Health level: 'healthy', 'warning', or 'critical'
 * @property {number} [uptime] - Service uptime in seconds
 * @property {string} [lastCheck] - ISO 8601 timestamp of last health check
 * @property {Record<string, unknown>} [details] - Additional service-specific details
 */
export interface ServiceStatus {
  name: string;
  status: 'running' | 'stopped' | 'error' | 'unknown';
  health: 'healthy' | 'warning' | 'critical';
  uptime?: number;
  lastCheck?: string;
  details?: Record<string, unknown>;
}

/**
 * Represents system resource metrics.
 *
 * @interface SystemMetrics
 * @property {Object} cpu - CPU metrics
 *   - usage: CPU usage percentage (0-100)
 *   - cores: Number of CPU cores
 *   - loadAverage: Load average over 1, 5, and 15 minutes
 * @property {Object} memory - Memory metrics
 *   - total: Total memory in bytes
 *   - used: Used memory in bytes
 *   - free: Free memory in bytes
 *   - usage: Memory usage percentage (0-100)
 * @property {Object} disk - Disk metrics
 *   - total: Total disk space in bytes
 *   - used: Used disk space in bytes
 *   - free: Free disk space in bytes
 *   - usage: Disk usage percentage (0-100)
 * @property {Object} network - Network metrics
 *   - bytesIn: Bytes received
 *   - bytesOut: Bytes sent
 *   - connections: Number of active connections
 */
export interface SystemMetrics {
  cpu: {
    usage: number;
    cores: number;
    loadAverage: number[];
  };
  memory: {
    total: number;
    used: number;
    free: number;
    usage: number;
  };
  disk: {
    total: number;
    used: number;
    free: number;
    usage: number;
  };
  network: {
    bytesIn: number;
    bytesOut: number;
    connections: number;
  };
}

// Logs and Events
export interface LogEntry {
  id: number | string;
  timestamp: string;
  level: LogLevel;
  source: string;
  message: string;
  context?: Record<string, unknown>;
  userId?: string;
  sessionId?: string;
  user_agent?: string;
  url?: string;
  trace_id?: string;
  log_type?: 'frontend' | 'backend';
  created_at?: string;
}

export type LogLevel = 'debug' | 'info' | 'warning' | 'error' | 'critical';

export interface LogFilter {
  level?: LogLevel | LogLevel[];
  source?: string | string[];
  sourceType?: string;
  startDate?: string;
  endDate?: string;
  from?: string;
  to?: string;
  search?: string;
  limit?: number;
  offset?: number;
  page?: number;
  page_size?: number;
  session_id?: string;
  user_id?: string;
}

/**
 * Represents information about an agent in the system.
 *
 * @interface AgentInfo
 * @property {string} id - Unique identifier for the agent
 * @property {string} name - Human-readable name of the agent
 * @property {string} type - Type of agent (e.g., 'llm', 'tool', 'workflow')
 * @property {string} status - Current status: 'active', 'inactive', or 'error'
 * @property {string[]} capabilities - Array of capabilities this agent provides
 * @property {Record<string, unknown>} configuration - Agent-specific configuration
 * @property {string} lastSeen - ISO 8601 timestamp of last activity
 * @property {AgentMetrics} [metrics] - Optional performance metrics
 */
export interface AgentInfo {
  id: string;
  name: string;
  type: string;
  status: 'active' | 'inactive' | 'error';
  capabilities: string[];
  configuration: Record<string, unknown>;
  lastSeen: string;
  metrics?: AgentMetrics;
}

/**
 * Represents performance metrics for an agent.
 *
 * @interface AgentMetrics
 * @property {number} requestsProcessed - Total number of requests processed
 * @property {number} averageResponseTime - Average response time in milliseconds
 * @property {number} errorRate - Error rate as a decimal (0-1)
 * @property {number} memoryUsage - Current memory usage in bytes
 */
export interface AgentMetrics {
  requestsProcessed: number;
  averageResponseTime: number;
  errorRate: number;
  memoryUsage: number;
}

/**
 * Represents an agent configuration for creation and updates.
 *
 * @interface AgentConfig
 * @property {string} id - Unique identifier for the agent
 * @property {string} name - Human-readable name of the agent
 * @property {string} type - Type of agent (e.g., 'llm', 'tool', 'workflow')
 * @property {Record<string, unknown>} parameters - Configuration parameters specific to the agent type
 * @property {boolean} enabled - Whether the agent is currently enabled
 * @property {string} createdAt - ISO 8601 timestamp of creation
 * @property {string} updatedAt - ISO 8601 timestamp of last update
 */
export interface AgentConfig {
  id: string;
  name: string;
  type: string;
  parameters: Record<string, unknown>;
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
}

// Sessions and Workflows
export interface ActiveSession {
  id: string;
  userId: string;
  agentId: string;
  status: 'active' | 'paused' | 'completed' | 'error';
  startedAt: string;
  lastActivity: string;
  context: Record<string, unknown>;
  metrics?: SessionMetrics;
}

export interface SessionMetrics {
  messagesExchanged: number;
  tokensUsed: number;
  duration: number;
  averageResponseTime: number;
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  status: 'draft' | 'active' | 'paused' | 'archived';
  steps: WorkflowStep[];
  triggers: WorkflowTrigger[];
  createdAt: string;
  updatedAt: string;
}

export interface WorkflowStep {
  id: string;
  name: string;
  type: 'agent' | 'condition' | 'action' | 'wait';
  configuration: Record<string, unknown>;
  nextSteps: string[];
}

export interface WorkflowTrigger {
  type: 'manual' | 'schedule' | 'event';
  configuration: Record<string, unknown>;
}

/**
 * Represents an API error response.
 *
 * @interface ApiError
 * @property {string} code - Error code for programmatic handling
 * @property {string} message - Human-readable error message
 * @property {Record<string, unknown>} [details] - Additional error details
 * @property {string} [timestamp] - ISO 8601 timestamp of the error
 */
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  timestamp?: string;
}

/**
 * Represents a standardized API response.
 *
 * @interface ApiResponse
 * @template T - The type of data in the response
 * @property {T} [data] - Response data (present if successful)
 * @property {ApiError} [error] - Error information (present if failed)
 * @property {number} status - HTTP status code
 * @property {string} timestamp - ISO 8601 timestamp of the response
 *
 * @example
 * const response: ApiResponse<AgentInfo[]> = await agentService.getAgents();
 * if (response.error) {
 *   console.error('Error:', response.error.message);
 * } else {
 *   console.log('Agents:', response.data);
 * }
 */
export interface ApiResponse<T = unknown> {
  data?: T;
  error?: ApiError;
  status: number;
  timestamp: string;
}

// UI and Notifications
export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export interface Theme {
  name: string;
  colors: {
    primary: string;
    secondary: string;
    accent: string;
    neutral: string;
    base: string;
    info: string;
    success: string;
    warning: string;
    error: string;
  };
}

// Form and Validation
export interface FormField {
  name: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'checkbox' | 'textarea';
  required: boolean;
  placeholder?: string;
  options?: { label: string; value: string }[];
  validation?: {
    pattern?: RegExp;
    min?: number;
    max?: number;
    custom?: (value: unknown) => string | null;
  };
}

// Real-time Data
export interface RealTimeUpdate {
  type: 'log' | 'health' | 'session' | 'agent';
  data: unknown;
  timestamp: string;
}

// Pagination and Filtering
export interface PaginationParams {
  page: number;
  limit: number;
  total: number;
}

export interface FilterParams {
  [key: string]: unknown;
}

export interface PaginatedResponse<T> {
  logs?: T[];
  data?: T[];
  pagination?: PaginationParams;
  filters?: FilterParams;
  has_more?: boolean;
  total?: number;
  page?: number;
  pageSize?: number;
}

// Settings and Theme Types
export * from './settings';

// Provider Types
export * from './providers';

// Collections Types
export * from './collections';

// Documents Types
