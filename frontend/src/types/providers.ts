/**
 * Provider Management Types
 * 
 * Type definitions for the Provider Management system in Phase 2
 */

/**
 * Provider Types
 */
export type ProviderType = 'llm' | 'embedding' | 'vector' | 'storage' | 'api' | 'custom';
export type ProviderStatus = 'active' | 'inactive' | 'error' | 'configuring' | 'testing';
export type ProviderHealthStatus = 'healthy' | 'degraded' | 'unhealthy' | 'unknown';

/**
 * Provider Information
 */
export interface ProviderInfo {
  id: string;
  name: string;
  type: ProviderType;
  status: ProviderStatus;
  description: string;
  version: string;
  capabilities: string[];
  configuration: ProviderConfiguration;
  health: ProviderHealth;
  lastSeen: string;
  createdAt: string;
  updatedAt: string;
  metadata?: Record<string, unknown>;
}

/**
 * Provider Configuration
 */
export interface ProviderConfiguration {
  apiKey?: string;
  baseUrl?: string;
  model?: string;
  timeout?: number;
  maxRetries?: number;
  rateLimit?: number;
  customParameters?: Record<string, unknown>;
  authentication?: {
    type: 'api_key' | 'oauth' | 'bearer' | 'none';
    credentials?: Record<string, unknown>;
  };
}

/**
 * Provider Health Information
 */
export interface ProviderHealth {
  status: ProviderHealthStatus;
  lastChecked: string;
  responseTime?: number;
  uptime?: number;
  errorRate?: number;
  metrics?: {
    requestsPerMinute?: number;
    averageResponseTime?: number;
    errorCount?: number;
    successRate?: number;
  };
  issues?: ProviderIssue[];
}

/**
 * Provider Issue
 */
export interface ProviderIssue {
  id: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  timestamp: string;
  resolved: boolean;
  resolution?: string;
}

/**
 * Provider Test Request/Response
 */
export interface ProviderTestRequest {
  providerId: string;
  testType: 'connection' | 'capability' | 'performance' | 'custom';
  parameters?: Record<string, unknown>;
  customTest?: {
    input: string;
    expectedOutput?: string;
  };
}

export interface ProviderTestResponse {
  success: boolean;
  testType: string;
  executionTime: number;
  output?: string;
  error?: string;
  metrics?: {
    latency?: number;
    throughput?: number;
    accuracy?: number;
  };
}

/**
 * Provider Discovery Filter Types
 */
export interface ProviderDiscoveryFilters {
  search: string;
  providerType: ProviderType[];
  status: ProviderStatus[];
  capabilities: string[];
  sortBy: 'name' | 'type' | 'status' | 'lastSeen' | 'health';
  sortOrder: 'asc' | 'desc';
}

/**
 * Provider Usage Statistics
 */
export interface ProviderUsageStats {
  providerId: string;
  totalRequests: number;
  successRate: number;
  averageResponseTime: number;
  peakUsage: {
    timestamp: string;
    requests: number;
  };
  dailyUsage: Array<{
    date: string;
    requests: number;
    errors: number;
  }>;
  capabilityUsage: Record<string, number>;
}

/**
 * Provider Capability Details
 */
export interface ProviderCapability {
  name: string;
  description: string;
  parameters: Array<{
    name: string;
    type: string;
    required: boolean;
    description: string;
    defaultValue?: unknown;
  }>;
  examples: string[];
  limitations?: string[];
}

/**
 * Form Validation Schemas (for React Hook Form + Zod)
 */
export interface ProviderConfigFormData {
  name: string;
  type: ProviderType;
  description?: string;
  configuration: {
    apiKey?: string;
    baseUrl?: string;
    model?: string;
    timeout?: number;
    maxRetries?: number;
    rateLimit?: number;
    customParameters?: Record<string, unknown>;
  };
}

export interface ProviderTestFormData {
  testType: 'connection' | 'capability' | 'performance' | 'custom';
  parameters?: Record<string, unknown>;
  customInput?: string;
  expectedOutput?: string;
}

export interface ProviderFilterFormData {
  search?: string;
  providerType?: ProviderType[];
  status?: ProviderStatus[];
  capabilities?: string[];
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

/**
 * Provider Management API Responses
 */
export interface ProviderDiscoveryResponse {
  providers: ProviderInfo[];
  total: number;
  page: number;
  limit: number;
  filters: ProviderDiscoveryFilters;
}

export interface ProviderCapabilitiesResponse {
  capabilities: Record<string, string[]>;
  providerTypes: ProviderType[];
}

export interface ProviderTestResults {
  [providerId: string]: ProviderTestResponse;
}

/**
 * Component Props
 */
export interface ProviderCardProps {
  provider: ProviderInfo;
  onSelect: (provider: ProviderInfo) => void;
  onTest: (providerId: string) => void;
  onConfigure: (providerId: string) => void;
  onViewModels?: (providerId: string) => void;
  isSelected?: boolean;
  className?: string;
}

export interface ProviderGridProps {
  providers: ProviderInfo[];
  selectedProvider: ProviderInfo | null;
  onProviderSelect: (provider: ProviderInfo) => void;
  onProviderTest: (providerId: string) => void;
  onProviderConfigure: (providerId: string) => void;
  loading?: boolean;
}

export interface ProviderFiltersProps {
  filters: ProviderDiscoveryFilters;
  onFiltersChange: (filters: ProviderDiscoveryFilters) => void;
  capabilities: Record<string, string[]>;
  providerTypes: ProviderType[];
  className?: string;
}

export interface ProviderConfigProps {
  provider: ProviderInfo;
  onSave: (providerId: string, config: ProviderConfiguration) => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
  className?: string;
}

export interface ProviderStatusProps {
  provider: ProviderInfo;
  onRefresh: (providerId: string) => Promise<void>;
  className?: string;
}

export interface ProviderTestProps {
  provider: ProviderInfo;
  onTest: (providerId: string, testRequest: ProviderTestRequest) => Promise<void>;
  testResults?: ProviderTestResponse;
  loading?: boolean;
  className?: string;
}

export interface ProviderDetailsProps {
  provider: ProviderInfo;
  onClose: () => void;
  onTest: (providerId: string, testRequest: ProviderTestRequest) => Promise<void>;
  onConfigure: (providerId: string, config: ProviderConfiguration) => Promise<void>;
  usageStats?: ProviderUsageStats;
  health?: ProviderHealth;
  className?: string;
}

/**
 * Hook Return Types
 */
export interface UseProvidersReturn {
  providers: ProviderInfo[];
  filteredProviders: ProviderInfo[];
  filters: ProviderDiscoveryFilters;
  loading: boolean;
  error: string | null;
  setFilters: (filters: ProviderDiscoveryFilters) => void;
  refreshProviders: () => Promise<void>;
  selectedProvider: ProviderInfo | null;
  setSelectedProvider: (provider: ProviderInfo | null) => void;
  createProvider: (provider: Omit<ProviderInfo, 'id' | 'createdAt' | 'updatedAt'>) => Promise<void>;
  updateProvider: (providerId: string, updates: Partial<ProviderInfo>) => Promise<void>;
  deleteProvider: (providerId: string) => Promise<void>;
}

export interface UseProviderHealthReturn {
  health: Record<string, ProviderHealth>;
  loading: boolean;
  error: string | null;
  refreshHealth: (providerId?: string) => Promise<void>;
  getHealth: (providerId: string) => ProviderHealth | undefined;
}

export interface UseProviderTestingReturn {
  testResults: ProviderTestResults;
  testing: boolean;
  error: string | null;
  testProvider: (providerId: string, testRequest: ProviderTestRequest) => Promise<void>;
  clearTestResults: (providerId?: string) => void;
  getTestResult: (providerId: string) => ProviderTestResponse | undefined;
}

// ============================================
// Phase 4: Provider Management Types
// ============================================

/**
 * Provider Configuration (Phase 4)
 */
export interface ProviderConfig {
  id: number;
  name: string;
  display_name: string | null;
  provider_type: string;
  base_url: string | null;
  is_active: boolean;
  priority: number;
  config: Record<string, unknown> | null;
  has_api_key: boolean;
  created_at: string;
  updated_at: string;
  /** The class seam (2026-09-08, the A1 split): 'cloud' or 'local',
   * derived from the provider_type by the backend. */
  location?: 'cloud' | 'local';
}

/**
 * Provider Config List Response
 */
export interface ProviderConfigListResponse {
  providers: ProviderConfig[];
  total: number;
}

/**
 * Provider Config Create Request
 */
export interface ProviderConfigCreate {
  name: string;
  display_name?: string;
  provider_type: string;
  base_url?: string;
  api_key?: string;
  is_active?: boolean;
  priority?: number;
  config?: Record<string, unknown>;
}

/**
 * Provider Config Update Request
 */
export interface ProviderConfigUpdate {
  display_name?: string;
  base_url?: string;
  api_key?: string;
  is_active?: boolean;
  priority?: number;
  config?: Record<string, unknown>;
}

/**
 * API Key Status Response
 */
export interface ApiKeyStatusResponse {
  provider_id: number;
  provider_name: string;
  api_key_configured: boolean;
}

/**
 * Provider Test Response
 */
export interface ProviderTestResponse {
  status: string;
  message: string;
  latency_ms?: number;
  models_available?: number;
}

/**
 * Usage Period Type
 */
export type UsagePeriod = 'daily' | 'weekly' | 'monthly' | 'all_time';

/**
 * Usage Summary Response
 */
export interface UsageSummaryResponse {
  period: string;
  total_tokens: number;
  total_cost_usd: number;
  total_requests: number;
  prompt_tokens: number;
  completion_tokens: number;
  success_count: number;
  error_count: number;
  avg_response_time_ms: number | null;
  period_start: string | null;
  period_end: string | null;
}

/**
 * Usage By Provider Response
 */
export interface UsageByProviderResponse {
  period: string;
  by_provider: Record<string, UsageSummaryResponse>;
}

/**
 * Model Usage Response
 */
export interface ModelUsageResponse {
  model: string;
  total_tokens: number;
  total_cost_usd: number;
  total_requests: number;
  prompt_tokens: number;
  completion_tokens: number;
}

/**
 * Usage Trend Response
 */
export interface UsageTrendResponse {
  date: string;
  total_tokens: number;
  total_cost_usd: number;
  total_requests: number;
}

/**
 * Cost Breakdown Response
 */
export interface CostBreakdownResponse {
  period: string;
  by_provider: Record<string, number>;
  total_cost_usd: number;
}

/**
 * Sync Schedule Response
 */
export interface SyncScheduleResponse {
  provider_id: number;
  sync_interval_hours: number;
  last_sync_at: string | null;
  next_sync_at: string | null;
  sync_enabled: boolean;
  last_sync_status: string;
}

/**
 * Sync Status Response
 */
export interface SyncStatusResponse {
  provider_id: number;
  status: string;
  message: string;
  models_synced: number;
  last_sync_at: string | null;
  next_sync_at: string | null;
}

/**
 * Sync Schedule Request
 */
export interface SyncScheduleRequest {
  sync_interval_hours: number;
}

/**
 * Provider Config Service Interface
 */
export interface IProviderConfigService {
  getProviders(includeInactive?: boolean): Promise<ProviderConfigListResponse>;
  getProvider(id: number): Promise<ProviderConfig>;
  createProvider(config: ProviderConfigCreate): Promise<ProviderConfig>;
  updateProvider(id: number, config: ProviderConfigUpdate): Promise<ProviderConfig>;
  deleteProvider(id: number): Promise<void>;
  setApiKey(id: number, apiKey: string): Promise<void>;
  getApiKeyStatus(id: number): Promise<ApiKeyStatusResponse>;
  testProvider(id: number): Promise<ProviderTestResponse>;
  syncModels(id: number, forceRefresh?: boolean): Promise<unknown>;
}

/**
 * Usage Service Interface
 */
export interface IUsageService {
  getUsageSummary(period: UsagePeriod): Promise<UsageSummaryResponse>;
  getUsageByProvider(period: UsagePeriod): Promise<UsageByProviderResponse>;
  getUsageByModel(period: UsagePeriod): Promise<ModelUsageResponse[]>;
  getUsageTrend(days: number): Promise<UsageTrendResponse[]>;
  getCostBreakdown(period: UsagePeriod): Promise<CostBreakdownResponse>;
  resetUsage(providerId: number): Promise<void>;
}

/**
 * Scheduler Service Interface
 */
export interface ISchedulerService {
  getSyncSchedule(providerId: number): Promise<SyncScheduleResponse>;
  setSyncSchedule(providerId: number, intervalHours: number): Promise<SyncScheduleResponse>;
  disableSync(providerId: number): Promise<void>;
  runSync(providerId: number): Promise<SyncStatusResponse>;
  getSyncStatus(providerId: number): Promise<SyncStatusResponse>;
}

/**
 * Hook Return Types for Phase 4
 */
export interface UseProviderConfigReturn {
  providers: ProviderConfig[];
  loading: boolean;
  error: string | null;
  refreshProviders: () => Promise<void>;
  createProvider: (config: ProviderConfigCreate) => Promise<void>;
  updateProvider: (id: number, config: ProviderConfigUpdate) => Promise<void>;
  deleteProvider: (id: number) => Promise<void>;
  setApiKey: (id: number, apiKey: string) => Promise<void>;
  testProvider: (id: number) => Promise<ProviderTestResponse | null>;
}

export interface UseUsageReturn {
  usage: UsageSummaryResponse | null;
  usageByProvider: UsageByProviderResponse | null;
  usageByModel: ModelUsageResponse[];
  usageTrend: UsageTrendResponse[];
  costBreakdown: CostBreakdownResponse | null;
  loading: boolean;
  error: string | null;
  refreshUsage: () => Promise<void>;
}

export interface UseSyncScheduleReturn {
  schedule: SyncScheduleResponse | null;
  syncStatus: SyncStatusResponse | null;
  loading: boolean;
  error: string | null;
  setSchedule: (intervalHours: number) => Promise<void>;
  disableSchedule: () => Promise<void>;
  runSync: () => Promise<SyncStatusResponse | null>;
  getSyncStatus: () => Promise<void>;
}