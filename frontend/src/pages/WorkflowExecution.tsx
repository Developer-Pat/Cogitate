import { useState, useEffect } from 'react';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { usePageTitle } from '../hooks/usePageTitle';
import { PageBanner } from '../components/ui/PageBanner';
import { ClipboardList, ChartColumn } from 'lucide-react';
import WorkflowRunner from '../components/features/workflowExecution/WorkflowRunner';
import { useWorkflowTemplates } from '../hooks/useWorkflowTemplates';
import { useWorkflowLists } from '../hooks/useWorkflowLists';
import { useWorkflowExecution } from '../hooks/useWorkflowExecution';
import { workflowListsService } from '../services/domains/llm/workflowListsService';
import { frontendLoggingService } from '../services/frontendLoggingService';
import type { WorkflowTemplate, WorkflowInList, WorkflowExecution } from '../types/workflows';
import { HelpButton } from '../components/help';
import { AskExaButton } from '../components/agentPanel/AskExaButton'


// Session storage keys for persistence
const STORAGE_KEY_LIST_ID = 'workflow_execution_selected_list_id';
const STORAGE_KEY_WORKFLOW_ID = 'workflow_execution_selected_workflow_id';
const STORAGE_KEY_TAB = 'workflow_execution_selected_tab';

type SelectionMode = 'template' | 'list';

export default function WorkflowExecution() {
  usePageTitle('Workflow Execution', 'Execute and monitor workflows with progress tracking')

  // Selection mode: direct template vs list-based
  const [selectionMode, setSelectionMode] = useState<SelectionMode>(() => {
    return (sessionStorage.getItem(STORAGE_KEY_TAB) as SelectionMode) || 'template';
  });

  // Template search filter
  const [templateFilter, setTemplateFilter] = useState('');

  // List-based selection (secondary path)
  const [selectedListId, setSelectedListId] = useState<string>(() => {
    return sessionStorage.getItem(STORAGE_KEY_LIST_ID) || '';
  });
  const [listWorkflows, setListWorkflows] = useState<WorkflowInList[]>([]);
  const [workflowsLoading, setWorkflowsLoading] = useState(false);

  // Direct template selection (primary path)
  const { templates, loading: templatesLoading, error: templatesError } = useWorkflowTemplates();

  // Shared state
  const [selectedTemplate, setSelectedTemplate] = useState<WorkflowTemplate | null>(() => {
    const savedWorkflowId = sessionStorage.getItem(STORAGE_KEY_WORKFLOW_ID);
    if (savedWorkflowId) {
      return { id: savedWorkflowId } as WorkflowTemplate;
    }
    return null;
  });
  const { executions } = useWorkflowExecution();
  const { workflowLists } = useWorkflowLists();

  // Load workflows when list is selected (list-based mode only)
  useEffect(() => {
    if (selectionMode !== 'list') return;

    const loadWorkflows = async () => {
      if (!selectedListId) {
        setListWorkflows([]);
        if (selectedTemplate?.id) {
          sessionStorage.removeItem(STORAGE_KEY_WORKFLOW_ID);
          setSelectedTemplate(null);
        }
        return;
      }

      try {
        setWorkflowsLoading(true);
        const response = await workflowListsService.getWorkflowsInList(selectedListId);
        if (response.data) {
          setListWorkflows(response.data);

          const savedWorkflowId = sessionStorage.getItem(STORAGE_KEY_WORKFLOW_ID);
          if (savedWorkflowId) {
            const workflow = response.data.find(wf => wf.template_id === savedWorkflowId);
            if (workflow) {
              const template: WorkflowTemplate = {
                id: workflow.template_id,
                name: workflow.name,
                description: workflow.description || '',
                category: 'Custom',
                version: workflow.version,
                author: 'System',
                tags: workflow.tags || [],
                steps: [],
                inputs: [],
                outputs: [],
                metadata: {
                  complexity: 'simple',
                  estimatedDuration: 0,
                  requiredCapabilities: [],
                  dependencies: [],
                  supportedAgents: []
                },
                createdAt: new Date().toISOString(),
                updatedAt: new Date().toISOString(),
                isPublic: false,
                isCustomizable: true,
                executionCount: 0,
                successRate: 0,
                averageExecutionTime: 0
              };
              setSelectedTemplate(template);
            } else {
              sessionStorage.removeItem(STORAGE_KEY_WORKFLOW_ID);
              setSelectedTemplate(null);
            }
          }
        }
      } catch (error) {
        frontendLoggingService.error('WorkflowExecution', 'Failed to load list workflows', error as Error);
        setListWorkflows([]);
      } finally {
        setWorkflowsLoading(false);
      }
    };

    loadWorkflows();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedListId, selectionMode]);

  // Persist state
  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY_TAB, selectionMode);
  }, [selectionMode]);

  useEffect(() => {
    if (selectedListId) {
      sessionStorage.setItem(STORAGE_KEY_LIST_ID, selectedListId);
    } else {
      sessionStorage.removeItem(STORAGE_KEY_LIST_ID);
    }
  }, [selectedListId]);

  useEffect(() => {
    if (selectedTemplate?.id) {
      sessionStorage.setItem(STORAGE_KEY_WORKFLOW_ID, selectedTemplate.id);
    } else {
      sessionStorage.removeItem(STORAGE_KEY_WORKFLOW_ID);
    }
  }, [selectedTemplate]);

  const handleTemplateSelect = (template: WorkflowTemplate) => {
    setSelectedTemplate(template);
  };

  const handleListSelect = (listId: string) => {
    setSelectedListId(listId);
    setSelectedTemplate(null);
  };

  const handleWorkflowSelect = (workflowId: string) => {
    const workflow = listWorkflows.find(wf => wf.template_id === workflowId);
    if (workflow) {
      const template: WorkflowTemplate = {
        id: workflow.template_id,
        name: workflow.name,
        description: workflow.description || '',
        category: 'Custom',
        version: workflow.version,
        author: 'System',
        tags: workflow.tags || [],
        steps: [],
        inputs: [],
        outputs: [],
        metadata: {
          complexity: 'simple',
          estimatedDuration: 0,
          requiredCapabilities: [],
          dependencies: [],
          supportedAgents: []
        },
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        isPublic: false,
        isCustomizable: true,
        executionCount: 0,
        successRate: 0,
        averageExecutionTime: 0
      };
      setSelectedTemplate(template);
    } else {
      sessionStorage.removeItem(STORAGE_KEY_WORKFLOW_ID);
      setSelectedTemplate(null);
    }
  };

  const handleExecutionComplete = (execution: WorkflowExecution) => {
    frontendLoggingService.info('WorkflowExecution', 'Workflow execution completed', execution as unknown as Record<string, unknown>);
  };

  const handleExecutionError = (error: string) => {
    frontendLoggingService.error('WorkflowExecution', 'Workflow execution error', new Error(error));
  };

  return (
    <ErrorBoundary>
      <div className="p-6 max-w-7xl mx-auto">
        <PageBanner
          title="Workflow Execution"
          className="mb-8"
          tooltip="Execute and monitor workflows with real-time progress tracking. Start, pause, stop, and resume workflows with detailed execution logs."
          action={
            <div className="flex items-center gap-2">
              <AskExaButton context="execution" tooltip="Ask Exa why a workflow run failed" />
              <HelpButton context="workflows" tooltipPosition="bottom" />
            </div>
          }
        />

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Workflow Selection Panel */}
          <div className="card bg-base-200 shadow-xl lg:col-span-1 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
            <div className="card-body gap-[var(--card-gap)]">
              <h2 className="card-title">Workflow Selection</h2>

              {templatesError && (
                <div className="alert alert-error">
                  <div>
                    <span>Failed to load templates: {templatesError}</span>
                  </div>
                </div>
              )}

              {/* Mode Tabs */}
              <div role="tablist" className="tabs tabs-bordered tabs-sm">
                <a
                  role="tab"
                  className={`tab ${selectionMode === 'template' ? 'tab-active' : ''}`}
                  onClick={() => { setSelectionMode('template'); setSelectedListId(''); setSelectedTemplate(null); }}
                >
                  All Templates
                </a>
                <a
                  role="tab"
                  className={`tab ${selectionMode === 'list' ? 'tab-active' : ''}`}
                  onClick={() => { setSelectionMode('list'); setSelectedTemplate(null); }}
                >
                  From List
                </a>
              </div>

              {/* Direct Template Selector (Primary) */}
              {selectionMode === 'template' && (
                <div className="space-y-4">
                  {templatesLoading ? (
                    <div className="text-center py-4">
                      <span className="loading loading-spinner loading-sm"></span>
                      <div className="mt-2 text-sm opacity-70">Loading templates...</div>
                    </div>
                  ) : templates.length === 0 ? (
                    <div className="text-center py-4 opacity-70">
                      <div className="text-4xl mb-2 text-readout">
                        <ClipboardList className="h-10 w-10 mx-auto" />
                      </div>
                      <div>No templates available</div>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {/* Search Filter */}
                      <div>
                        <label className="block text-sm font-medium mb-1.5">
                          Search Templates
                        </label>
                        <input
                          type="text"
                          placeholder="Filter by name or type..."
                          value={templateFilter}
                          onChange={(e) => setTemplateFilter(e.target.value)}
                          className="input input-bordered input-sm w-full"
                        />
                      </div>

                      {/* Grouped Select */}
                      <div>
                        <label className="block text-sm font-medium mb-1.5">
                          Select Template ({templates.length} total)
                        </label>
                        <select
                          value={selectedTemplate?.id || ''}
                          onChange={(e) => {
                            const tpl = templates.find(t => t.id === e.target.value);
                            if (tpl) handleTemplateSelect(tpl);
                          }}
                          className="select select-bordered w-full"
                          size={Math.min(templates.length, 8)}
                        >
                          <option value="">-- Select a Workflow --</option>
                          {(() => {
                            const filter = templateFilter.toLowerCase();
                            const filtered = templates.filter(t =>
                              t.name.toLowerCase().includes(filter) ||
                              (t.workflowType || '').toLowerCase().includes(filter) ||
                              t.category.toLowerCase().includes(filter)
                            );
                            // Group by category
                            const groups = new Map<string, typeof templates>();
                            filtered.forEach(t => {
                              const cat = t.category || 'Other';
                              if (!groups.has(cat)) groups.set(cat, []);
                              groups.get(cat)!.push(t);
                            });
                            return Array.from(groups.entries())
                              .sort(([a], [b]) => a.localeCompare(b))
                              .map(([category, items]) => (
                                <optgroup key={category} label={`${category} (${items.length})`}>
                                  {items.map(tpl => (
                                    <option key={tpl.id} value={tpl.id}>
                                      {tpl.name} ({tpl.workflowType || 'simple'})
                                    </option>
                                  ))}
                                </optgroup>
                              ));
                          })()}
                        </select>
                      </div>
                    </div>
                  )}

                  {/* Selected Template Info */}
                  {selectedTemplate && (
                    <div className="p-3 bg-base-100 rounded-lg border border-primary">
                      <div className="font-semibold text-sm">{selectedTemplate.name}</div>
                      <div className="text-xs opacity-70 mt-1 line-clamp-2">
                        {selectedTemplate.description}
                      </div>
                      <div className="flex flex-wrap gap-2 mt-2">
                        <span className="badge badge-outline badge-xs">
                          {selectedTemplate.category}
                        </span>
                        <span className="badge badge-ghost badge-xs">
                          {selectedTemplate.workflowType || 'simple'}
                        </span>
                        <span className="badge badge-ghost badge-xs">
                          v{selectedTemplate.version}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* List-Based Selector (Secondary) */}
              {selectionMode === 'list' && (
                <div className="space-y-4">
                  {workflowLists.length === 0 ? (
                    <div className="text-center py-4 opacity-70">
                      <div className="text-4xl mb-2 text-readout">
                        <ClipboardList className="h-10 w-10 mx-auto" />
                      </div>
                      <div>No workflow lists</div>
                      <div className="text-sm mt-1">Create lists on the Templates page</div>
                    </div>
                  ) : (
                    <>
                      <div>
                        <label className="block text-sm font-medium mb-2">Workflow List</label>
                        <select
                          value={selectedListId}
                          onChange={(e) => handleListSelect(e.target.value)}
                          className="select select-bordered w-full"
                        >
                          <option value="">-- Select a List --</option>
                          {workflowLists.map(list => (
                            <option key={list.id} value={list.id}>
                              {list.name} ({list.workflow_count} workflows)
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-2">Workflow</label>
                        {workflowsLoading ? (
                          <div className="text-center py-4">
                            <span className="loading loading-spinner loading-sm"></span>
                          </div>
                        ) : listWorkflows.length === 0 ? (
                          <select disabled className="select select-bordered w-full">
                            <option>{selectedListId ? 'No workflows in this list' : 'Select a list first'}</option>
                          </select>
                        ) : (
                          <select
                            value={selectedTemplate?.id || ''}
                            onChange={(e) => handleWorkflowSelect(e.target.value)}
                            className="select select-bordered w-full"
                          >
                            <option value="">-- Select a Workflow --</option>
                            {listWorkflows.map(wf => (
                              <option key={wf.template_id} value={wf.template_id}>
                                {wf.name} (v{wf.version})
                              </option>
                            ))}
                          </select>
                        )}
                      </div>
                    </>
                  )}
                </div>
              )}

              <div className="card-actions justify-end mt-4">
                <button
                  className="btn btn-primary btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                  onClick={() => { window.location.href = '/workflow-templates'; }}
                >
                  Manage Workflows
                </button>
              </div>
            </div>
          </div>

          {/* Workflow Execution Panel */}
          <div className="lg:col-span-3">
            {selectedTemplate ? (
              <WorkflowRunner
                template={selectedTemplate}
                onExecutionComplete={handleExecutionComplete}
                onExecutionError={handleExecutionError}
              />
            ) : (
              <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
                <div className="card-body gap-[var(--card-gap)]">
                  <h2 className="card-title">Workflow Execution</h2>
                  <div className="text-center py-8">
                    <div className="text-6xl mb-4 opacity-50">⚡</div>
                    <h3 className="text-xl font-semibold mb-2">Select a Workflow Template</h3>
                    <p className="opacity-70 mb-4">
                      Choose a template from the left panel to start execution
                    </p>
                    <div className="stats shadow">
                      <div className="stat">
                        <div className="stat-title">Available Templates</div>
                        <div className="stat-value">{templates.length}</div>
                        <div className="stat-desc">Ready for execution</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Recent Executions */}
        <div className="mt-8">
          <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
            <div className="card-body gap-[var(--card-gap)]">
              <h2 className="card-title">Recent Executions</h2>
              {executions.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="table table-zebra w-full">
                    <thead>
                      <tr>
                        <th>Workflow</th>
                        <th>Status</th>
                        <th>Started</th>
                        <th>Duration</th>
                        <th>Result</th>
                      </tr>
                    </thead>
                    <tbody>
                      {executions.slice(0, 10).map((execution) => (
                        <tr key={execution.id}>
                          <td>
                            <div className="font-medium">{execution.templateId}</div>
                            <div className="text-xs opacity-70">{execution.id}</div>
                          </td>
                          <td>
                            <div className="flex items-center gap-1">
                              <div className={`badge badge-sm ${
                                execution.status === 'completed' ? 'badge-success' :
                                execution.status === 'running' ? 'badge-warning' :
                                execution.status === 'failed' ? 'badge-error' :
                                execution.status === 'cancelled' ? 'badge-neutral' : 'badge-info'
                              }`}>
                                {execution.status}
                              </div>
                              {execution.degraded && (
                                <div
                                  className="badge badge-warning badge-sm tooltip tooltip-top"
                                  data-tip="A step failed and the run absorbed it — part of the result may be missing"
                                >
                                  degraded
                                </div>
                              )}
                            </div>
                          </td>
                          <td>
                            {execution.startedAt ? new Date(execution.startedAt).toLocaleString() : 'N/A'}
                          </td>
                          <td>
                            {execution.executionTime ? `${execution.executionTime}s` :
                             execution.startedAt && execution.completedAt ?
                               `${Math.round((new Date(execution.completedAt).getTime() - new Date(execution.startedAt).getTime()) / 1000)}s`
                               : 'N/A'}
                          </td>
                          <td>
                            {execution.outputs ? (
                              <div className="text-sm truncate max-w-xs" title={JSON.stringify(execution.outputs)}>
                                {Object.keys(execution.outputs).length} output(s)
                              </div>
                            ) : execution.error ? (
                              <div className="text-error text-sm" title={execution.error}>Error</div>
                            ) : (
                              <div className="text-sm opacity-70">-</div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-8 opacity-70">
                  <div className="text-4xl mb-2 text-readout">
                    <ChartColumn className="h-10 w-10 mx-auto" />
                  </div>
                  <div>Execution history will appear here</div>
                  <div className="text-sm mt-1">Start executing workflows to see history</div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </ErrorBoundary>
  )
}