/**
 * WorkflowTemplates Page
 *
 * Main page for discovering, managing, and executing workflow templates
 */

import React, { useState } from 'react';
import { PageBanner } from '../components/ui/PageBanner';
import { PageContainer } from '../components/ui/PageContainer';
import { ClipboardList } from 'lucide-react';
import { usePageTitle } from '../hooks/usePageTitle';
import WorkflowCard from '../components/features/workflows/WorkflowCard';
import WorkflowEditor from '../components/features/workflows/WorkflowEditor';
import WorkflowPreview from '../components/features/workflows/WorkflowPreview';
import WorkflowImport from '../components/features/workflows/WorkflowImport';
import WorkflowListCard from '../components/features/workflows/WorkflowListCard';
import WorkflowListPreview from '../components/features/workflows/WorkflowListPreview';
import WorkflowListEditor from '../components/features/workflows/WorkflowListEditor';
import WorkflowTable from '../components/features/workflows/WorkflowTable';
import WorkflowTemplateTable from '../components/features/workflows/WorkflowTemplateTable';
import useWorkflowTemplates from '../hooks/useWorkflowTemplates';
import useWorkflowLists from '../hooks/useWorkflowLists';
import useWorkflowExecution from '../hooks/useWorkflowExecution';
import useWorkflowValidation from '../hooks/useWorkflowValidation';
import { frontendLoggingService } from '../services/frontendLoggingService';
import { workflowService } from '../services/domains/llm/workflowService';
import type { WorkflowTemplate, WorkflowList } from '../types/workflows';
import { HelpButton } from '../components/help';
import { AskExaButton } from '../components/agentPanel/AskExaButton';

/**
 * WorkflowTemplates Page Component
 */
const WorkflowTemplates: React.FC = () => {
  usePageTitle('Workflows', 'Your configured workflows — each is a template (kind) with concrete parameters')

  const {
    filteredTemplates,
    filters,
    loading,
    error,
    categories: _categories,
    tags: _tags,
    refreshTemplates,
    selectedTemplate,
    setSelectedTemplate,
    createTemplate,
    updateTemplate,
    includeTesting,
    setIncludeTesting,
  } = useWorkflowTemplates();

  const {
    filteredLists,
    loading: listsLoading,
    error: listsError,
    tags: listTags,
    filterTags,
    setFilterTags,
    selectedList,
    setSelectedList,
    selectedListWorkflows,
    loadListWorkflows,
    createList,
    updateList,
    deleteList,
    addWorkflowToList,
    removeWorkflowFromList,
    refreshLists
  } = useWorkflowLists();

  const {
    executeWorkflow,
    polling: _polling
  } = useWorkflowExecution();

  const {
    validateTemplate
  } = useWorkflowValidation();

  const [activeTab, setActiveTab] = useState<'templates' | 'lists'>('templates');
  const [templateViewMode, setTemplateViewMode] = useState<'grid' | 'table'>('table');
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('table');
  const [showPreview, setShowPreview] = useState<boolean>(false);
  const [showEditor, setShowEditor] = useState<boolean>(false);
  const [showImport, setShowImport] = useState<boolean>(false);
  const [showListPreview, setShowListPreview] = useState<boolean>(false);
  const [showListEditor, setShowListEditor] = useState<boolean>(false);
  const [editingTemplate, setEditingTemplate] = useState<WorkflowTemplate | null>(null);
  const [editingList, setEditingList] = useState<WorkflowList | null>(null);

  /**
   * Handle template selection
   */
  const handleTemplateSelect = (template: WorkflowTemplate) => {
    setSelectedTemplate(template);
    setShowPreview(true);
  };

  /**
   * Handle template edit
   */
  const handleTemplateEdit = (template: WorkflowTemplate) => {
    setEditingTemplate(template);
    setShowEditor(true);
  };

  /**
   * Handle template execution
   */
  const handleTemplateExecute = async (templateId: string, _inputs?: Record<string, unknown>) => {
    try {
      await executeWorkflow(templateId, {});
      // Handle execution result
    } catch (error) {
      frontendLoggingService.error('WorkflowTemplates', 'Failed to execute template', error as Error);
    }
  };

  /** Reset a monitor's dedup checkpoint — the next run is a FULL run (2026-08-18). */
  const handleTemplateReset = async (templateId: string) => {
    try {
      const resp = await workflowService.resetMonitorCheckpoint(templateId);
      const n = resp.data?.cleared_count ?? 0;
      frontendLoggingService.info('WorkflowTemplates', `Reset ${templateId} checkpoint (${n} feeds cleared)`);
      // the honest toast — the reset is done, the next run re-reports everything
      // (the monitor's next trigger delivers the full digest)
    } catch (error) {
      frontendLoggingService.error('WorkflowTemplates', `Failed to reset ${templateId}`, error as Error);
    }
  };

  /**
   * Handle template validation
   */
  const handleTemplateValidate = async (template: WorkflowTemplate): Promise<boolean> => {
    try {
      const result = await validateTemplate(template);
      return result.isValid;
    } catch (error) {
      frontendLoggingService.error('WorkflowTemplates', 'Failed to validate template', error as Error);
      return false;
    }
  };

  /**
   * Handle template export
   */
  const handleTemplateExport = (template: WorkflowTemplate) => {
    frontendLoggingService.info('WorkflowTemplates', `Export template: ${template.name}`);
    // TODO: Implement export functionality
  };

  /**
   * Handle create new template — the editor needs a NON-null
   * skeleton to render (the render gate is `showEditor &&
   * editingTemplate`). FIX 2026-08-14: the button used to set
   * editingTemplate(null) so nothing ever opened.
   */
  const handleCreateNewTemplate = () => {
    setEditingTemplate({
      id: '', // empty id = create mode (not update)
      name: '',
      description: '',
      category: 'General',
      version: '1.0.0',
      author: 'user',
      tags: [],
      steps: [],
      inputs: [],
      outputs: [],
      metadata: {
        complexity: 'simple',
        estimatedDuration: 0,
        requiredCapabilities: [],
        dependencies: [],
        supportedAgents: [],
      },
      createdAt: '',
      updatedAt: '',
      isPublic: false,
      isCustomizable: true,
      executionCount: 0,
      successRate: 0,
      averageExecutionTime: 0,
      workflowType: 'simple',
    });
    setShowEditor(true);
  };

  /**
   * Handle list selection
   */
  const handleListSelect = async (list: WorkflowList) => {
    setSelectedList(list);
    await loadListWorkflows(list.id);
    setShowListPreview(true);
  };

  /**
   * Handle list edit
   */
  const handleListEdit = async (list: WorkflowList) => {
    // Close preview if open
    setShowListPreview(false);
    setSelectedList(list);
    // Load workflows for this list
    await loadListWorkflows(list.id);
    setEditingList(list);
    setShowListEditor(true);
  };

  /**
   * Handle list delete
   */
  const handleListDelete = async (list: WorkflowList) => {
    if (confirm(`Are you sure you want to delete "${list.name}"?`)) {
      await deleteList(list.id);
    }
  };

  /**
   * Handle create new list
   */
  const handleCreateNewList = () => {
    setEditingList(null);
    setShowListEditor(true);
  };

  /**
   * Close list editor
   */
  const handleCloseListEditor = () => {
    setShowListEditor(false);
    setEditingList(null);
  };

  /**
   * Close list preview
   */
  const handleCloseListPreview = () => {
    setShowListPreview(false);
    setSelectedList(null);
  };

  /**
   * Handle adding workflows to a list
   */
  const handleAddWorkflowsToList = async (workflowIds: string[]) => {
    if (!selectedList) return;

    try {
      // Add each workflow to the list
      for (const workflowId of workflowIds) {
        await addWorkflowToList(selectedList.id, workflowId);
      }
      // Refresh the workflows for this list
      await loadListWorkflows(selectedList.id);
      // Refresh the lists to update workflow counts
      await refreshLists();
    } catch (error) {
      frontendLoggingService.error('WorkflowTemplates', 'Failed to add workflows to list', error as Error);
    }
  };

  /**
   * Handle removing a workflow from a list
   */
  const handleRemoveWorkflowFromList = async (workflowId: string) => {
    if (!selectedList) return;

    try {
      await removeWorkflowFromList(selectedList.id, workflowId);
      // Refresh the workflows for this list
      await loadListWorkflows(selectedList.id);
      // Refresh the lists to update workflow counts
      await refreshLists();
    } catch (error) {
      frontendLoggingService.error('WorkflowTemplates', 'Failed to remove workflow from list', error as Error);
    }
  };

  /**
   * Close editor
   */
  const handleCloseEditor = () => {
    setShowEditor(false);
    setEditingTemplate(null);
  };

  /**
   * Close preview
   */
  const handleClosePreview = () => {
    setShowPreview(false);
    setSelectedTemplate(null);
  };

  /**
   * Close import
   */
  const handleCloseImport = () => {
    setShowImport(false);
  };

  return (
    <PageContainer>
      {/* Page Header */}
      <PageBanner
        title="Workflows"
        tooltip="Configured workflows — each is a template (kind) with concrete parameters. Create one from the Templates page."
        action={
          <div className="flex items-center space-x-3">
            <AskExaButton
              context="workflow"
              tooltip="Ask Exa to create or maintain a workflow template"
            />
            <HelpButton context="workflows" tooltipPosition="bottom" />
          </div>
        }
      >
        {activeTab === 'templates' ? (
            <>
              <button
                onClick={() => setShowImport(true)}
                className="btn btn-transfer btn-outline"
              >
                Import Template
              </button>
              <button
                onClick={handleCreateNewTemplate}
                className="btn btn-primary"
              >
                Create Template
              </button>
            </>
          ) : (
            <button
              onClick={handleCreateNewList}
              className="btn btn-primary"
            >
              Create List
            </button>
          )}
      </PageBanner>


      {/* Tabs */}
      <div className="mb-6">
        <div className="border-b border-base-content/20">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('templates')}
              className={`
                py-4 px-1 border-b-2 font-medium text-sm transition-colors
                ${activeTab === 'templates'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-base-content/60 hover:text-base-content hover:border-base-content/20'}
              `}
            >
              Templates
            </button>
            <button
              onClick={() => setActiveTab('lists')}
              className={`
                py-4 px-1 border-b-2 font-medium text-sm transition-colors
                ${activeTab === 'lists'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-base-content/60 hover:text-base-content hover:border-base-content/20'}
              `}
            >
              Workflow Lists
            </button>
          </nav>
        </div>
      </div>

      {/* Error Display */}
      {activeTab === 'templates' && error && (
        <div className="alert alert-error mb-6">
          <div>
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span>Failed to load templates: {error}</span>
          </div>
        </div>
      )}

      {activeTab === 'lists' && listsError && (
        <div className="alert alert-error mb-6">
          <div>
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span>Failed to load workflow lists: {listsError}</span>
          </div>
        </div>
      )}

      {/* Templates Tab Content */}
      {activeTab === 'templates' && (
        <div className="bg-base-100 shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            {/* View Mode Toggle */}
            <div className="flex flex-wrap justify-between items-center gap-3 mb-4">
              <h3 className="text-lg font-medium">Templates</h3>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={includeTesting}
                    onChange={(e) => setIncludeTesting(e.target.checked)}
                    className="toggle toggle-primary toggle-sm"
                    aria-label="Show testing fixtures"
                  />
                  Show testing fixtures
                </label>
                <div className="btn-group">
                <div className="tooltip tooltip-top" data-tip="Grid view">
                  <button
                    className={`btn btn-sm ${templateViewMode === 'grid' ? 'btn-active btn-selected' : 'btn-outline'}`}
                    onClick={() => setTemplateViewMode('grid')}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                    </svg>
                  </button>
                </div>
                <div className="tooltip tooltip-top" data-tip="Table view">
                  <button
                    className={`btn btn-sm ${templateViewMode === 'table' ? 'btn-active btn-selected' : 'btn-outline'}`}
                    onClick={() => setTemplateViewMode('table')}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-12">
                <span className="loading loading-spinner loading-lg"></span>
                <span className="ml-2">Loading templates...</span>
              </div>
            ) : filteredTemplates.length > 0 ? (
              templateViewMode === 'grid' ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {filteredTemplates.map((template) => (
                    <WorkflowCard
                      key={template.id}
                      template={template}
                      onSelect={handleTemplateSelect}
                      onEdit={handleTemplateEdit}
                      onExport={handleTemplateExport}
                      onExecute={handleTemplateExecute}
                    />
                  ))}
                </div>
              ) : (
                <div className="h-[700px]">
                  <WorkflowTemplateTable
                    templates={filteredTemplates}
                    selectedTemplateId={selectedTemplate?.id}
                    onSelect={handleTemplateSelect}
                    onEdit={handleTemplateEdit}
                    onExecute={handleTemplateExecute}
                    onReset={handleTemplateReset}
                    tags={_tags}
                    filterTags={filters.tags}
                    onFilterTagsChange={(_t) => {/* filters are managed by useWorkflowTemplates hook */}}
                  />
                </div>
              )
            ) : (
              <div className="text-center py-12">
                <div className="text-readout mb-4 flex justify-center">
                  <ClipboardList className="h-16 w-16" />
                </div>
                <h3 className="text-lg font-medium text-base-content mb-2">
                  No templates found
                </h3>
                <p className="text-readout mb-4">
                  {filters.search || filters.category || filters.tags
                    ? 'Try adjusting your filters'
                    : 'Get started by creating your first template'}
                </p>
                <button
                  onClick={handleCreateNewTemplate}
                  className="btn btn-primary rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                >
                  Create Template
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Workflow Lists Tab Content */}
      {activeTab === 'lists' && (
        <div className="bg-base-100 shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            {/* View Mode Toggle */}
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-medium">Workflow Lists</h3>
              <div className="btn-group">
                <div className="tooltip tooltip-top" data-tip="Grid view">
                  <button
                    className={`btn btn-sm ${viewMode === 'grid' ? 'btn-active btn-selected' : 'btn-outline'}`}
                    onClick={() => setViewMode('grid')}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                    </svg>
                  </button>
                </div>
                <div className="tooltip tooltip-top" data-tip="Table view">
                  <button
                    className={`btn btn-sm ${viewMode === 'table' ? 'btn-active btn-selected' : 'btn-outline'}`}
                    onClick={() => setViewMode('table')}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>

            {/* Tag Filter - Only show in grid view */}
            {viewMode === 'grid' && listTags.length > 0 && (
              <div className="mb-6">
                <label className="label">
                  <span className="label-text font-medium">Filter by Tags</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {listTags.map((tag) => (
                    <button
                      key={tag}
                      onClick={() => {
                        const newTags = filterTags.includes(tag)
                          ? filterTags.filter(t => t !== tag)
                          : [...filterTags, tag];
                        setFilterTags(newTags);
                      }}
                      className={`
                        px-3 py-1.5 rounded-full text-sm font-medium transition-colors
                        ${filterTags.includes(tag)
                          ? 'bg-primary text-primary-content'
                          : 'bg-base-200 text-base-content hover:bg-base-300'}
                      `}
                    >
                      {tag}
                    </button>
                  ))}
                  {filterTags.length > 0 && (
                    <button
                      onClick={() => setFilterTags([])}
                      className="px-3 py-1.5 rounded-full text-sm font-medium bg-base-200 text-base-content hover:bg-base-300"
                    >
                      Clear
                    </button>
                  )}
                </div>
              </div>
            )}

            {listsLoading ? (
              <div className="flex items-center justify-center py-12">
                <span className="loading loading-spinner loading-lg"></span>
                <span className="ml-2">Loading workflow lists...</span>
              </div>
            ) : filteredLists.length > 0 ? (
              viewMode === 'grid' ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {filteredLists.map((list) => (
                    <WorkflowListCard
                      key={list.id}
                      list={list}
                      onSelect={handleListSelect}
                      onEdit={handleListEdit}
                      onDelete={handleListDelete}
                    />
                  ))}
                </div>
              ) : (
                <div className="h-[600px]">
                  <WorkflowTable
                    workflowLists={filteredLists}
                    selectedListId={selectedList?.id}
                    onSelectList={handleListSelect}
                    onEdit={handleListEdit}
                    onDelete={handleListDelete}
                    isLoading={listsLoading}
                    tags={listTags}
                    filterTags={filterTags}
                    onFilterTagsChange={setFilterTags}
                  />
                </div>
              )
            ) : (
              <div className="text-center py-12">
                <div className="text-readout mb-4 flex justify-center">
                  <ClipboardList className="h-16 w-16" />
                </div>
                <h3 className="text-lg font-medium text-base-content mb-2">
                  No workflow lists found
                </h3>
                <p className="text-readout mb-4">
                  {filterTags.length > 0
                    ? 'Try adjusting your tag filter'
                    : 'Get started by creating your first workflow list'}
                </p>
                <button
                  onClick={handleCreateNewList}
                  className="btn btn-primary rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                >
                  Create List
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modals */}
      {showPreview && selectedTemplate && (
        <WorkflowPreview
          template={selectedTemplate}
          onClose={handleClosePreview}
          onExecute={handleTemplateExecute}
          onEdit={handleTemplateEdit}
        />
      )}

      {showEditor && editingTemplate && (
        <WorkflowEditor
          template={editingTemplate}
          onCancel={handleCloseEditor}
          onSave={(template) => {
            if (editingTemplate?.id) {
              updateTemplate(editingTemplate.id, template);
            } else {
              // NEW template (skeleton id is ''): the frontend sends
              // the shape minus id/timestamps; backend POST creates
              createTemplate(template);
            }
          }}
          onValidate={handleTemplateValidate}
        />
      )}

      {showImport && (
        <WorkflowImport
          onCancel={handleCloseImport}
          onImport={async (_data) => {
            await refreshTemplates();
            handleCloseImport();
          }}
        />
      )}

      {/* List Modals */}
      {selectedList && (
        <WorkflowListPreview
          isOpen={showListPreview}
          list={selectedList}
          workflows={selectedListWorkflows}
          onClose={handleCloseListPreview}
          onEdit={handleListEdit}
          onAddWorkflows={handleAddWorkflowsToList}
          onRemoveWorkflow={handleRemoveWorkflowFromList}
        />
      )}

      <WorkflowListEditor
        isOpen={showListEditor}
        list={editingList}
        workflows={editingList ? selectedListWorkflows : []}
        availableTags={listTags}
        onClose={handleCloseListEditor}
        onSave={(data) => {
          if (editingList) {
            updateList(editingList.id, data);
          } else {
            createList(data);
          }
        }}
        onAddWorkflows={handleAddWorkflowsToList}
        onRemoveWorkflow={handleRemoveWorkflowFromList}
      />
    </PageContainer>
  );
};

export default WorkflowTemplates;