/**
 * Workflow Template Management Types
 * 
 * Type definitions for the Workflow Template Management system in Phase 2
 */

import { z } from 'zod';

/**
 * Workflow Template Types
 */
export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  author: string;
  tags: string[];
  steps: WorkflowStep[];
  inputs: WorkflowInput[];
  outputs: WorkflowOutput[];
  metadata: WorkflowMetadata;
  createdAt: string;
  updatedAt: string;
  isPublic: boolean;
  isCustomizable: boolean;
  executionCount: number;
  successRate: number;
  averageExecutionTime: number;
  /** Workflow type (simple, advanced, agent, etc.) — used for filtering/sorting */
  workflowType?: string;
}

export interface WorkflowStep {
  id: string;
  name: string;
  type: 'agent' | 'condition' | 'loop' | 'input' | 'output' | 'transform';
  agentId?: string;
  parameters: Record<string, unknown>;
  conditions?: WorkflowCondition[];
  nextSteps: string[];
  errorHandling?: WorkflowErrorHandling;
  timeout?: number;
  retryCount?: number;
}

export interface WorkflowCondition {
  id: string;
  type: 'if' | 'else' | 'switch';
  condition: string;
  targetStep: string;
}

export interface WorkflowErrorHandling {
  retryOnError: boolean;
  maxRetries: number;
  fallbackStep?: string;
  errorMessage?: string;
}

export interface WorkflowInput {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
  required: boolean;
  description: string;
  defaultValue?: unknown;
  validation?: {
    min?: number;
    max?: number;
    pattern?: string;
    enum?: string[];
  };
}

export interface WorkflowOutput {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
  description: string;
  sourceStep: string;
}

export interface WorkflowMetadata {
  complexity: 'simple' | 'medium' | 'complex';
  estimatedDuration: number;
  requiredCapabilities: string[];
  dependencies: string[];
  supportedAgents: string[];
}

/**
 * Workflow Execution Types
 */
export interface WorkflowExecution {
  id: string;
  templateId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  inputs: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  startedAt?: string;
  completedAt?: string;
  error?: string;
  /** The ONE wording for a failed run — names the provider + model the run resolved. Absent
   *  when the run named nobody (a non-LLM failure, G4-F5); `error` above keeps the RAW
   *  exception so the cause stays recoverable. */
  failureStatement?: string;
  /** THE SECOND AXIS: the run COMPLETED with a failure absorbed inside it — `status` stays the
   *  execution outcome, and the message is in `error` / `failureStatement` beside it. */
  degraded?: boolean;
  executionTime?: number;
  stepExecutions: StepExecution[];
  logs: ExecutionLog[];
  /** Raw execution_result from the backend API (result, agent_name, completed_at, error_details, etc.) */
  executionResult?: Record<string, unknown>;
}

export interface StepExecution {
  stepId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  startedAt?: string;
  completedAt?: string;
  output?: unknown;
  error?: string;
  executionTime?: number;
  retryCount?: number;
}

export interface ExecutionLog {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  message: string;
  stepId?: string;
  data?: unknown;
}

/**
 * Workflow Template Filter Types
 */
export interface WorkflowTemplateFilters {
  search: string;
  category: string[];
  complexity: ('simple' | 'medium' | 'complex')[];
  tags: string[];
  isPublic: boolean | null;
  isCustomizable: boolean | null;
  sortBy: 'name' | 'category' | 'complexity' | 'executionCount' | 'successRate' | 'createdAt';
  sortOrder: 'asc' | 'desc';
}

/**
 * Workflow Template State
 */
export interface WorkflowTemplateState {
  templates: WorkflowTemplate[];
  filteredTemplates: WorkflowTemplate[];
  filters: WorkflowTemplateFilters;
  loading: boolean;
  error: string | null;
  selectedTemplate: WorkflowTemplate | null;
  categories: string[];
  tags: string[];
  /** Phase E: testing-namespace fixtures hidden by default; devs
   * toggle to see them. */
  includeTesting: boolean;
}

/**
 * Workflow Execution State
 */
export interface WorkflowExecutionState {
  executions: WorkflowExecution[];
  selectedExecution: WorkflowExecution | null;
  loading: boolean;
  error: string | null;
  polling: boolean;
}

/**
 * Workflow Import/Export Types
 */
export interface WorkflowImportData {
  template: WorkflowTemplate;
  includeExecutions?: boolean;
  overwriteExisting?: boolean;
}

export interface WorkflowExportData {
  template: WorkflowTemplate;
  includeExecutions?: boolean;
  format: 'json' | 'yaml';
}

/**
 * Form Validation Schemas (for React Hook Form + Zod)
 */
export const workflowTemplateFormSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100, 'Name too long'),
  description: z.string().min(1, 'Description is required').max(500, 'Description too long'),
  category: z.string().min(1, 'Category is required'),
  tags: z.array(z.string()).optional(),
  isPublic: z.boolean().default(false),
  isCustomizable: z.boolean().default(true),
});

export const workflowExecutionFormSchema = z.object({
  templateId: z.string().min(1, 'Template ID is required'),
  inputs: z.record(z.string(), z.any()),
});

export const workflowImportFormSchema = z.object({
  file: z.any(),
  overwriteExisting: z.boolean().default(false),
  includeExecutions: z.boolean().default(false),
});

export type WorkflowTemplateFormData = z.infer<typeof workflowTemplateFormSchema>;
export type WorkflowExecutionFormData = z.infer<typeof workflowExecutionFormSchema>;
export type WorkflowImportFormData = z.infer<typeof workflowImportFormSchema>;

/**
 * Workflow API Responses
 */
export interface WorkflowTemplatesResponse {
  templates: WorkflowTemplate[];
  total: number;
  page: number;
  limit: number;
  filters: WorkflowTemplateFilters;
}

export interface WorkflowTemplateResponse {
  template: WorkflowTemplate;
}

export interface WorkflowExecutionsResponse {
  executions: WorkflowExecution[];
  total: number;
  page: number;
  limit: number;
}

export interface WorkflowExecutionResponse {
  execution: WorkflowExecution;
}

export interface WorkflowCategoriesResponse {
  categories: string[];
  tags: string[];
}

export interface WorkflowImportResponse {
  importedTemplate: WorkflowTemplate;
  message: string;
  warnings?: string[];
}

export interface WorkflowExportResponse {
  data: string;
  filename: string;
  format: 'json' | 'yaml';
}

/**
 * Workflow List Types
 */
export interface WorkflowList {
  id: string;
  name: string;
  description?: string;
  user_key: string;
  workflow_ids: string[];
  workflow_count: number;
  is_default: boolean;
  tags?: string[];
  created_at: string;
  updated_at: string;
}

export interface WorkflowListCreate {
  name: string;
  description?: string;
  user_key?: string;
  workflow_ids?: string[];
  is_default?: boolean;
  tags?: string[];
}

export interface WorkflowListUpdate {
  name?: string;
  description?: string;
  workflow_ids?: string[];
  is_default?: boolean;
  tags?: string[];
}

export interface WorkflowInList {
  template_id: string;
  name: string;
  description?: string;
  version: string;
  tags?: string[];
}

export interface WorkflowListListResponse {
  workflow_lists: WorkflowList[];
  total: number;
}

export interface WorkflowListResponse {
  workflow_list: WorkflowList;
}

export interface WorkflowListWorkflowsResponse {
  workflows: WorkflowInList[];
  total: number;
}

/**
 * Component Props
 */
export interface WorkflowCardProps {
  template: WorkflowTemplate;
  onSelect: (template: WorkflowTemplate) => void;
  onExecute: (templateId: string, inputs?: Record<string, unknown>) => void;
  onEdit: (template: WorkflowTemplate) => void;
  onExport: (template: WorkflowTemplate) => void;
  isSelected?: boolean;
  className?: string;
}

export interface WorkflowEditorProps {
  template: WorkflowTemplate;
  onSave: (template: WorkflowTemplate) => void;
  onCancel: () => void;
  onValidate: (template: WorkflowTemplate) => Promise<boolean>;
  className?: string;
}

export interface WorkflowPreviewProps {
  template: WorkflowTemplate;
  onClose: () => void;
  onExecute: (templateId: string, inputs?: Record<string, unknown>) => void;
  onEdit: (template: WorkflowTemplate) => void;
  className?: string;
}

export interface WorkflowImportProps {
  onImport: (data: WorkflowImportData) => Promise<void>;
  onCancel: () => void;
  className?: string;
}

export interface WorkflowExecutionViewerProps {
  execution: WorkflowExecution;
  onClose: () => void;
  onRetry?: (executionId: string) => void;
  className?: string;
}

/**
 * Hook Return Types
 */
export interface UseWorkflowTemplatesReturn {
  templates: WorkflowTemplate[];
  filteredTemplates: WorkflowTemplate[];
  filters: WorkflowTemplateFilters;
  loading: boolean;
  error: string | null;
  categories: string[];
  tags: string[];
  includeTesting: boolean;
  setIncludeTesting: (v: boolean) => void;
  setFilters: (filters: WorkflowTemplateFilters) => void;
  refreshTemplates: () => Promise<void>;
  selectedTemplate: WorkflowTemplate | null;
  setSelectedTemplate: (template: WorkflowTemplate | null) => void;
  createTemplate: (template: Omit<WorkflowTemplate, 'id' | 'createdAt' | 'updatedAt'>) => Promise<void>;
  updateTemplate: (id: string, template: Partial<WorkflowTemplate>) => Promise<void>;
  deleteTemplate: (id: string) => Promise<void>;
  form: unknown; // UseFormReturn<WorkflowTemplateFormData>
}

export interface UseWorkflowExecutionReturn {
  executions: WorkflowExecution[];
  selectedExecution: WorkflowExecution | null;
  loading: boolean;
  error: string | null;
  polling: boolean;
  executeWorkflow: (templateId: string, inputs: Record<string, unknown>, workflowType?: 'simple' | 'multi_agent') => Promise<void>;
  getExecution: (executionId: string) => Promise<void>;
  cancelExecution: (executionId: string) => Promise<void>;
  retryExecution: (executionId: string) => Promise<void>;
  startPolling: (executionId: string) => void;
  stopPolling: () => void;
  setSSEDisconnect: (disconnectFn: () => void) => void;
  disconnectSSE: () => void;
  form: unknown; // UseFormReturn<WorkflowExecutionFormData>
}

export interface UseWorkflowValidationReturn {
  validateTemplate: (template: WorkflowTemplate) => Promise<{
    isValid: boolean;
    errors: string[];
    warnings: string[];
  }>;
  validateExecution: (templateId: string, inputs: Record<string, unknown>) => Promise<{
    isValid: boolean;
    errors: string[];
    warnings: string[];
  }>;
  validateStep: (step: WorkflowStep) => Promise<{
    isValid: boolean;
    errors: string[];
    warnings: string[];
  }>;
}


// ---------------------------------------------------------------------------
// Workflow Triggers
// ---------------------------------------------------------------------------

export interface WorkflowTrigger {
  id: string;
  workflowId: string;
  triggerType: 'schedule' | 'webhook' | 'database';
  config: Record<string, unknown>;
  isActive: boolean;
  name?: string;
  description?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface ScheduleInfo {
  triggerId: string;
  workflowId?: string;
  cron?: string;
  timezone?: string;
  nextRunTime?: string;
  enabled?: boolean;
}

export interface TriggerInfoResponse {
  id: string;
  workflow_id: string;
  trigger_type: string;
  config: Record<string, unknown>;
  is_active: boolean;
  name?: string;
  description?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ScheduleListResponse {
  trigger_id: string;
  workflow_id?: string;
  cron?: string;
  timezone?: string;
  next_run_time?: string;
  enabled?: boolean;
}


export interface WorkflowProductInfo {
  product_type: string;
  title: string;
  source_template: string;
  created_at: string;
  path?: string;
  meta?: Record<string, unknown>;
  body?: string;
}

export interface WorkflowProductsResponse {
  products: WorkflowProductInfo[];
  total: number;
}

/**
 * Run retention — the windows for workflow runs.
 *
 * THE POLICY IS CONFIG: it lives in the app settings and is resolved there, so the UI edits
 * values rather than relying on anything compiled in. `stats` describes what the store holds now;
 * a `RetentionReport` describes what a prune did (or, with `dry_run`, would do).
 */
export interface RetentionPolicy {
  /** Prune automatically on the schedule. A fresh install prunes nothing until asked. */
  enabled: boolean;
  snapshot_days: number;
  /** The identity row AND its checkpoint thread: the two are paired, on purpose. */
  run_days: number;
  abandoned_hours: number;
  schedule_hour: number;
}

export interface RetentionStats {
  rows: number;
  metadata_bytes: number;
  snapshot_bytes: number;
  oldest: string | null;
  newest: string | null;
  by_status: Record<string, number>;
}

export interface RetentionState {
  policy: RetentionPolicy;
  /** The SHIPPED defaults — so a surface showing a number can say whether it is somebody's choice. */
  defaults: RetentionPolicy;
  configured: boolean;
  stats: RetentionStats;
}

export interface RetentionReport {
  dry_run: boolean;
  enabled: boolean;
  policy: RetentionPolicy;
  rows_pruned: number;
  threads_pruned: number;
  snapshots_stripped: number;
  snapshot_bytes_freed: number;
  abandoned_marked: number;
  abandoned_ids: string[];
  pruned_ids: string[];
  errors: string[];
  generated_at: string;
}
