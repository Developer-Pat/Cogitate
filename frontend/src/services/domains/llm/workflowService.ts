/**
 * Workflow Service - LLM Domain
 *
 * Service abstraction layer for workflow management with proper domain boundaries.
 */

import { apiClient } from '@/services/apiClient';
import type { ApiResponse } from '@/types/index'
import type { WorkflowProductsResponse } from '@/types/workflows';
import type {
  WorkflowTemplate,
  WorkflowExecution,
  WorkflowTemplatesResponse,
  WorkflowExecutionsResponse,
  WorkflowCategoriesResponse,
  WorkflowImportResponse,
  WorkflowExportResponse,
  WorkflowImportData,
  RetentionPolicy,
  RetentionReport,
  RetentionState
} from '@/types/workflows';

/**
 * Workflow Service Interface
 */
export interface IWorkflowService {
  // Template Management
  getTemplates(): Promise<ApiResponse<WorkflowTemplate[]>>;
  getTemplateById(id: string): Promise<ApiResponse<WorkflowTemplate>>;
  createTemplate(template: Omit<WorkflowTemplate, 'id' | 'createdAt' | 'updatedAt'>): Promise<ApiResponse<WorkflowTemplate>>;
  updateTemplate(id: string, template: Partial<WorkflowTemplate>): Promise<ApiResponse<WorkflowTemplate>>;
  deleteTemplate(id: string): Promise<ApiResponse<{ message: string }>>;
  
  // Template Discovery & Filtering
  getTemplateCategories(): Promise<ApiResponse<WorkflowCategoriesResponse>>;
  searchTemplates(query: string, filters?: Record<string, unknown>): Promise<ApiResponse<WorkflowTemplatesResponse>>;
  
  // Execution Management
  executeTemplate(id: string, inputs: Record<string, unknown>, workflowType?: 'simple' | 'multi_agent'): Promise<ApiResponse<WorkflowExecution>>;
  getExecution(executionId: string): Promise<ApiResponse<WorkflowExecution>>;
  getExecutions(templateId?: string, triggerId?: string): Promise<ApiResponse<WorkflowExecutionsResponse>>;
  // Run retention — the windows are config, so the surface reads and writes them here
  getRetention(): Promise<ApiResponse<RetentionState>>;
  updateRetention(policy: Partial<RetentionPolicy>): Promise<ApiResponse<{ policy: RetentionPolicy }>>;
  pruneRetention(dryRun?: boolean): Promise<ApiResponse<RetentionReport>>;
  cancelExecution(executionId: string): Promise<ApiResponse<{ message: string }>>;
  retryExecution(executionId: string): Promise<ApiResponse<WorkflowExecution>>;
  
  // Import/Export
  importTemplate(data: WorkflowImportData): Promise<ApiResponse<WorkflowImportResponse>>;
  exportTemplate(id: string, format: 'json' | 'yaml', includeExecutions?: boolean): Promise<ApiResponse<WorkflowExportResponse>>;
  
  // Validation
  validateTemplate(template: WorkflowTemplate): Promise<ApiResponse<{ isValid: boolean; errors: string[]; warnings: string[] }>>;
  validateExecution(templateId: string, inputs: Record<string, unknown>): Promise<ApiResponse<{ isValid: boolean; errors: string[]; warnings: string[] }>>;

  // THE BUILD FIX (2026-08-26, the tsc -b tail — the pages read
  // these; the interface lagged the implementation).
  getWorkflowToasts(since?: string): Promise<ApiResponse<{ toasts: unknown[]; total: number }>>;
  getWorkflowProducts(limit?: number): Promise<ApiResponse<WorkflowProductsResponse>>;
  clearWorkflowProducts(): Promise<ApiResponse<{ cleared: number }>>;
  deleteWorkflowProduct(productId: string): Promise<ApiResponse<{ deleted: string }>>;
  resetMonitorCheckpoint(templateId: string): Promise<ApiResponse<{ reset: string; cleared_feeds: string[]; cleared_count: number }>>;
}

/**
 * Workflow Service Implementation
 */
class WorkflowService implements IWorkflowService {
  private readonly basePath = '/api/v1/workflows';

  /**
   * Get all available workflow templates (simple and multi-agent)
   */
  async getTemplates(): Promise<ApiResponse<WorkflowTemplate[]>> {
    // Fetch both simple and multi-agent templates
    const [simpleResponse, multiAgentResponse] = await Promise.all([
      apiClient.get<WorkflowTemplatesResponse>(`${this.basePath}/templates`),
      apiClient.get<Record<string, unknown>[]>('/api/v1/multi-agent/templates')
    ]);

    const templates: WorkflowTemplate[] = [];

    // Process simple templates
    if (simpleResponse.data && 'templates' in simpleResponse.data) {
      templates.push(...(simpleResponse.data.templates || []));
    }

    // Process multi-agent templates
    if (multiAgentResponse.data && Array.isArray(multiAgentResponse.data)) {
      const multiAgentTemplates: WorkflowTemplate[] = (multiAgentResponse.data as unknown[]).map(
        (mt: unknown) => {
          const ma = mt as {
            id: string; name: string; description?: string; tags?: string[];
            workflow_type?: string
          }
          return {
            id: ma.id,
            name: ma.name,
            description: ma.description || '',
            category: 'Multi-Agent',
            version: '1.0.0',
            author: 'System',
            tags: ma.tags || [],
            steps: [],
            inputs: [],
            outputs: [],
            metadata: {
              complexity: 'complex' as const,
              estimatedDuration: 0,
              requiredCapabilities: [],
              dependencies: [],
              supportedAgents: []
            },
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            isPublic: true,
            isCustomizable: false,
            executionCount: 0,
            successRate: 0,
            averageExecutionTime: 0,
            workflowType: ma.workflow_type || 'multi_agent'
          }
        }
      );
      templates.push(...multiAgentTemplates);
    }

    // Deduplicate by ID — multi-agent templates exist in both endpoints
    const seen = new Map<string, WorkflowTemplate>();
    templates.forEach(t => {
      if (!seen.has(t.id)) seen.set(t.id, t);
    });

    return {
      data: Array.from(seen.values()),
      status: 200,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Get a specific workflow template by ID (supports both simple and multi-agent)
   */
  async getTemplateById(id: string): Promise<ApiResponse<WorkflowTemplate>> {
    // Try simple templates first
    const simpleResponse = await apiClient.get<WorkflowTemplate>(`${this.basePath}/templates/${id}`);
    
    if (simpleResponse.data) {
      return simpleResponse;
    }

    // If not found, try multi-agent templates
    const multiAgentResponse = await apiClient.get<unknown>(`/api/v1/multi-agent/templates/${id}`);
    
    if (multiAgentResponse.data) {
      const mt = multiAgentResponse.data as {
        id: string;
        name: string;
        description?: string;
        tags?: string[];
        workflow_type?: string;
      };
      return {
        ...multiAgentResponse,
        data: {
          id: mt.id,
          name: mt.name,
          description: mt.description || '',
          category: 'Multi-Agent',
          version: '1.0.0',
          author: 'System',
          tags: mt.tags || [],
          steps: [],
          inputs: [],
          outputs: [],
          metadata: {
            complexity: 'complex',
            estimatedDuration: 0,
            requiredCapabilities: [],
            dependencies: [],
            supportedAgents: []
          },
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          isPublic: true,
          isCustomizable: false,
          executionCount: 0,
          successRate: 0,
          averageExecutionTime: 0,
          workflowType: mt.workflow_type || 'multi_agent'
        }
      };
    }

    return simpleResponse;
  }

  /**
   * Create a new workflow template
   */
  async createTemplate(template: Omit<WorkflowTemplate, 'id' | 'createdAt' | 'updatedAt'>): Promise<ApiResponse<WorkflowTemplate>> {
    return apiClient.post<WorkflowTemplate>(`${this.basePath}/templates`, template);
  }

  /**
   * Update an existing workflow template
   */
  async updateTemplate(id: string, template: Partial<WorkflowTemplate>): Promise<ApiResponse<WorkflowTemplate>> {
    return apiClient.put<WorkflowTemplate>(`${this.basePath}/templates/${id}`, template);
  }

  /**
   * Delete a workflow template
   */
  async deleteTemplate(id: string): Promise<ApiResponse<{ message: string }>> {
    return apiClient.delete<{ message: string }>(`${this.basePath}/templates/${id}`);
  }

  /**
   * Get template categories and tags
   */
  async getTemplateCategories(): Promise<ApiResponse<WorkflowCategoriesResponse>> {
    const response = await apiClient.get<unknown>(`${this.basePath}/templates/categories`);
    
    // Backend returns { categories: [{id, name, ...}], tags: [{name, count}] }.
    // Normalize to string arrays for the frontend.
    if (response.data && typeof response.data === 'object' && !Array.isArray(response.data)) {
      const raw = response.data as {
        categories?: Array<{ id?: string; name?: string }>;
        tags?: Array<{ name?: string }>;
      };
      return {
        ...response,
        data: {
          categories: (raw.categories ?? []).map(c => c.name ?? c.id ?? '').filter(Boolean),
          tags: (raw.tags ?? []).map(t => t.name ?? '').filter(Boolean)
        }
      };
    }
    
    // Legacy array response — nothing to extract
    return {
      ...response,
      data: {
        categories: [],
        tags: []
      }
    };
  }

  /**
   * Search templates with filters
   */
  async searchTemplates(query: string, filters?: Record<string, unknown>): Promise<ApiResponse<WorkflowTemplatesResponse>> {
    const params = new URLSearchParams();
    if (query) params.append('q', query);
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          params.append(key, String(value));
        }
      });
    }
    
    return apiClient.get<WorkflowTemplatesResponse>(`${this.basePath}/templates/search?${params}`);
  }

  /**
   * Execute a workflow template
   */
  async executeTemplate(id: string, inputs: Record<string, unknown>, workflowType?: 'simple' | 'multi_agent'): Promise<ApiResponse<WorkflowExecution>> {
    // Determine endpoint based on workflow type
    const endpoint = workflowType === 'multi_agent'
      ? '/api/v1/multi-agent/execute'
      : `${this.basePath}/execute`;

    const response = await apiClient.post<unknown>(endpoint, {
      template_id: id,
      initial_message: inputs.initial_message || 'Workflow execution started from UI',
      inputs
    }, {
      timeout: 120000  // Increase timeout for workflow execution (especially multi-agent)
    });

    // Transform backend response to frontend format
    if (response.data) {
      const data = response.data as {
        status: string;
        started_at?: string;
        completed_at?: string;
        workflow_id: string;
        template_id: string;
        degraded?: boolean;
      };
      // Normalize status: backend uses 'started', frontend expects 'running'
      const normalizedStatus = data.status === 'started' ? 'running' : data.status;
      
      // Calculate execution time from started_at and completed_at
      let executionTime: number | undefined = undefined;
      if (data.started_at && data.completed_at) {
        const started = new Date(data.started_at).getTime();
        const completed = new Date(data.completed_at).getTime();
        executionTime = Math.round((completed - started) / 1000); // Convert to seconds
      }

      response.data = {
        id: data.workflow_id,
        templateId: data.template_id,
        status: normalizedStatus,
        // the second axis, straight off the run's own record (/status serves it)
        degraded: Boolean(data.degraded),
        inputs: inputs || {},
        outputs: undefined,
        startedAt: data.started_at,
        completedAt: undefined,
        error: undefined,
        executionTime: executionTime,
        // Create initial step execution for single-step workflows
        stepExecutions: [{
          stepId: data.template_id || 'workflow',
          status: normalizedStatus as unknown,
          startedAt: data.started_at,
          completedAt: undefined,
          output: undefined,
          error: undefined,
          executionTime: undefined,
          retryCount: 0
        }],
        // Initial log entry
        logs: [{
          timestamp: data.started_at || new Date().toISOString(),
          level: 'info',
          message: `Workflow execution started`,
          stepId: data.template_id
        }]
      };
    }

    return response as ApiResponse<WorkflowExecution>;
  }

  /**
   * Get workflow execution by ID
   */
  async getExecution(executionId: string): Promise<ApiResponse<WorkflowExecution>> {
    const response = await apiClient.get<unknown>(`${this.basePath}/${executionId}/status`);

    // Transform backend response to frontend format
    if (response.data) {
      const data = response.data as {
        status: string;
        error?: string;
        failure_statement?: string;
        degraded?: boolean;
        execution_result?: {
          error_details?: { message?: string };
          error?: string;
          retry_attempts?: number;
          result?: string;
        };
        started_at?: string;
        completed_at?: string;
        workflow_id: string;
        template_id: string;
        outputs?: unknown;
      };
      // Normalize status: backend may use 'started', frontend expects 'running' — and the
      // backend records a failed run as 'error', which every `=== 'failed'` branch in the UI
      // (the runner's completion effect, ResultViewer, the list badge) keys on.
      const normalizedStatus = data.status === 'started' ? 'running'
        : data.status === 'error' ? 'failed'
        : data.status;

      // Extract error information - check for detailed error structure
      let errorMessage = data.error || undefined;

      // If error is an object with error_details, use the user-friendly message
      if (data.execution_result?.error_details?.message) {
        errorMessage = data.execution_result.error_details.message;
      } else if (data.execution_result?.error) {
        errorMessage = data.execution_result.error;
      }

      // Calculate execution time from started_at and completed_at
      let executionTime: number | undefined = undefined;
      if (data.started_at && data.completed_at) {
        const started = new Date(data.started_at).getTime();
        const completed = new Date(data.completed_at).getTime();
        executionTime = Math.round((completed - started) / 1000); // Convert to seconds
      }

      response.data = {
        id: data.workflow_id,
        templateId: data.template_id,
        status: normalizedStatus as 'pending' | 'running' | 'completed' | 'failed' | 'cancelled',
        // THE SECOND AXIS (the run's own record): `status` is the execution outcome, and this is
        // whether the run was worse for it. Never derived from the status word.
        degraded: Boolean(data.degraded),
        inputs: {},
        // Use the dedicated outputs field from API, not execution_result
        outputs: data.outputs || undefined,
        startedAt: data.started_at,
        completedAt: data.completed_at,
        error: errorMessage,
        // The ONE wording (the panel's primary text) — the raw exception stays in `error`.
        failureStatement: data.failure_statement || undefined,
        executionTime: executionTime,
        // Map execution_result to stepExecutions for single-step workflows
        stepExecutions: data.execution_result ? [{
          stepId: data.template_id || 'workflow',
          status: normalizedStatus as unknown,
          startedAt: data.started_at,
          completedAt: data.completed_at,
          output: data.outputs,
          error: errorMessage,
          executionTime: executionTime,
          retryCount: data.execution_result.retry_attempts || 0
        }] : [],
        // Generate logs from execution result
        logs: data.execution_result ? [{
          timestamp: data.completed_at || data.started_at || new Date().toISOString(),
          level: normalizedStatus === 'failed' ? 'error' : 'info',
          message: data.execution_result.result || `Workflow ${normalizedStatus}`,
          stepId: data.template_id
        }] : []
      };
    }

    return response as ApiResponse<WorkflowExecution>;
  }

  /**
   * Get workflow executions (optionally filtered by template)
   */
  /**
   * List workflow products (the display index — digests, alerts,
   * reports delivered by the distribution layer).
   */
  async getWorkflowProducts(limit = 50): Promise<ApiResponse<WorkflowProductsResponse>> {
    return apiClient.get<WorkflowProductsResponse>(`${this.basePath}/products?limit=${limit}`);
  }

  /** List unread product toasts (the ToastDistributor queue) since a cursor. */
  async getWorkflowToasts(since = ''): Promise<ApiResponse<{ toasts: unknown[]; total: number }>> {
    const qs = since ? `?since=${encodeURIComponent(since)}` : '';
    return apiClient.get<{ toasts: unknown[]; total: number }>(`${this.basePath}/toasts${qs}`);
  }

  /** Delete all workflow product files + the display index (stale-data reset). */
  async clearWorkflowProducts(): Promise<ApiResponse<{ cleared: number }>> {
    return apiClient.delete<{ cleared: number }>(`${this.basePath}/products`);
  }

  /** Delete ONE workflow product (file + index entry) by its created_at id. */
  async deleteWorkflowProduct(productId: string): Promise<ApiResponse<{ deleted: string }>> {
    return apiClient.delete<{ deleted: string }>(`${this.basePath}/products/${encodeURIComponent(productId)}`);
  }

  /** Reset a monitor's dedup checkpoint — the next run treats every item as new (a full run). */
  async resetMonitorCheckpoint(templateId: string): Promise<ApiResponse<{ reset: string; cleared_feeds: string[]; cleared_count: number }>> {
    return apiClient.post<{ reset: string; cleared_feeds: string[]; cleared_count: number }>(
      `${this.basePath}/monitors/reset`,
      { template_id: templateId }
    );
  }

  /** The effective retention policy, the defaults behind it, and what the store holds. */
  async getRetention(): Promise<ApiResponse<RetentionState>> {
    return apiClient.get<RetentionState>(`${this.basePath}/retention`);
  }

  /** Change the windows. Values are validated server-side — a nonsense window is refused. */
  async updateRetention(policy: Partial<RetentionPolicy>): Promise<ApiResponse<{ policy: RetentionPolicy }>> {
    return apiClient.put<{ policy: RetentionPolicy }>(`${this.basePath}/retention`, policy);
  }

  /**
   * Preview (`dryRun = true`, the default) or apply the prune.
   *
   * A preview measures exactly what the act would — rows, bytes, threads — and changes nothing,
   * so a person can see the cost before deciding.
   */
  async pruneRetention(dryRun = true): Promise<ApiResponse<RetentionReport>> {
    // `confirm=true` always travels with an APPLY: the endpoint refuses an apply without it, so a
    // request that merely arrived (a retry, a stray call) can never be the one that pruned.
    const confirmed = dryRun ? '' : '&confirm=true';
    return apiClient.post<RetentionReport>(
      `${this.basePath}/retention/prune?dry_run=${dryRun ? 'true' : 'false'}${confirmed}`
    );
  }

  async getExecutions(templateId?: string, triggerId?: string): Promise<ApiResponse<WorkflowExecutionsResponse>> {
    const params = new URLSearchParams();
    if (templateId) params.set('template_id', templateId);
    if (triggerId) params.set('trigger_id', triggerId);
    const qs = params.toString();
    return apiClient.get<WorkflowExecutionsResponse>(`${this.basePath}/executions${qs ? `?${qs}` : ''}`);
  }

  /**
   * Cancel a workflow execution
   */
  async cancelExecution(executionId: string): Promise<ApiResponse<{ message: string }>> {
    return apiClient.post<{ message: string }>(`${this.basePath}/executions/${executionId}/cancel`);
  }

  /**
   * Retry a failed workflow execution
   */
  async retryExecution(executionId: string): Promise<ApiResponse<WorkflowExecution>> {
    return apiClient.post<WorkflowExecution>(`${this.basePath}/executions/${executionId}/retry`);
  }

  /**
   * Import a workflow template
   */
  async importTemplate(data: WorkflowImportData): Promise<ApiResponse<WorkflowImportResponse>> {
    return apiClient.post<WorkflowImportResponse>(`${this.basePath}/templates/import`, data);
  }

  /**
   * Export a workflow template
   */
  async exportTemplate(id: string, format: 'json' | 'yaml', includeExecutions?: boolean): Promise<ApiResponse<WorkflowExportResponse>> {
    const params = new URLSearchParams();
    params.append('format', format);
    if (includeExecutions) {
      params.append('includeExecutions', 'true');
    }
    
    return apiClient.get<WorkflowExportResponse>(`${this.basePath}/templates/${id}/export?${params}`);
  }

  /**
   * Validate a workflow template
   */
  async validateTemplate(template: WorkflowTemplate): Promise<ApiResponse<{ isValid: boolean; errors: string[]; warnings: string[] }>> {
    return apiClient.post<{ isValid: boolean; errors: string[]; warnings: string[] }>(`${this.basePath}/templates/validate`, template);
  }

  /**
   * Validate workflow execution inputs
   */
  async validateExecution(templateId: string, inputs: Record<string, unknown>): Promise<ApiResponse<{ isValid: boolean; errors: string[]; warnings: string[] }>> {
    return apiClient.post<{ isValid: boolean; errors: string[]; warnings: string[] }>(`${this.basePath}/templates/${templateId}/validate-execution`, { inputs });
  }
}

// Create and export singleton instance
export const workflowService: IWorkflowService = new WorkflowService();

// Export for dependency injection
export default workflowService;