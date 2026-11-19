/**
 * WorkflowListPreview Component
 *
 * Component for previewing workflow list details and contained workflows
 */

import { useState } from 'react';
import type { WorkflowList, WorkflowInList } from '@/types/workflows';
import { WorkflowSelectionModal } from './WorkflowSelectionModal';

interface WorkflowListPreviewProps {
  isOpen: boolean;
  list: WorkflowList;
  workflows: WorkflowInList[];
  onClose: () => void;
  onEdit: (list: WorkflowList) => void;
  onAddWorkflows?: (workflowIds: string[]) => Promise<void>;
  onRemoveWorkflow?: (workflowId: string) => Promise<void>;
  className?: string;
}

/**
 * WorkflowListPreview Component
 */
const WorkflowListPreview: React.FC<WorkflowListPreviewProps> = ({
  isOpen,
  list,
  workflows,
  onClose,
  onEdit,
  onAddWorkflows,
  onRemoveWorkflow
}) => {
  const [showAddModal, setShowAddModal] = useState(false);

  // Early return if not open
  if (!isOpen) return null;

  /**
   * Handle edit button click
   */
  const handleEditClick = () => {
    onEdit(list);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const handleAddWorkflows = async (workflowIds: string[]) => {
    if (onAddWorkflows) {
      await onAddWorkflows(workflowIds);
      setShowAddModal(false);
    }
  };

  const handleRemoveWorkflow = async (workflowId: string, workflowName: string) => {
    if (!onRemoveWorkflow) return;

    const confirmed = confirm(`Remove "${workflowName}" from this list?`);
    if (!confirmed) return;

    await onRemoveWorkflow(workflowId);
  };

  const existingWorkflowIds = workflows.map(wf => wf.template_id);

  return (
    <>
      <div className="modal modal-open" role="dialog">
        <div className="modal-box max-w-4xl max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="flex items-start justify-between mb-6">
            <div>
              <h3 className="font-bold text-xl">{list.name}</h3>
              {list.description && (
                <p className="text-sm text-readout mt-1">{list.description}</p>
              )}
            </div>
            <button
              onClick={onClose}
              className="btn btn-ghost btn-sm btn-circle"
              aria-label="Close"
            >
              ✕
            </button>
          </div>

          {/* Content */}
          <div className="space-y-6">
            {/* List Information */}
            <div>
              <h4 className="text-sm font-semibold text-base-content mb-3 uppercase tracking-wide">List Information</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-readout">Workflows:</span>
                  <span className="ml-2 font-medium">{list.workflow_count}</span>
                </div>
                <div>
                  <span className="text-readout">Status:</span>
                  <span className={`ml-2 badge badge-sm ${list.is_default ? 'badge-primary badge-outline' : 'badge-ghost'}`}>
                    {list.is_default ? 'Default' : 'Custom'}
                  </span>
                </div>
                <div>
                  <span className="text-readout">Created:</span>
                  <span className="ml-2 font-medium">
                    {formatDate(list.created_at)}
                  </span>
                </div>
                <div>
                  <span className="text-readout">Updated:</span>
                  <span className="ml-2 font-medium">
                    {formatDate(list.updated_at)}
                  </span>
                </div>
              </div>
            </div>

            {/* Tags */}
            {list.tags && list.tags.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-base-content mb-3 uppercase tracking-wide">Tags</h4>
                <div className="flex flex-wrap gap-2">
                  {list.tags.map((tag, index) => (
                    <span
                      key={index}
                      className="badge badge-primary badge-outline badge-sm"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Workflows in List */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-semibold text-base-content uppercase tracking-wide">
                  Workflows ({workflows.length})
                </h4>
                <button
                  onClick={() => setShowAddModal(true)}
                  className="btn btn-primary btn-sm"
                >
                  Add Workflow
                </button>
              </div>
              {workflows.length > 0 ? (
                <div className="space-y-3">
                  {workflows.map((workflow, index) => (
                    <div
                      key={workflow.template_id}
                      className="border border-base-300 rounded-lg p-4 bg-base-100"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-start space-x-3 flex-1">
                          <span className="flex-shrink-0 w-6 h-6 bg-primary text-primary-content rounded-full flex items-center justify-center text-xs font-medium">
                            {index + 1}
                          </span>
                          <div className="flex-1">
                            <div className="flex items-center justify-between">
                              <h4 className="text-sm font-medium">{workflow.name}</h4>
                              <button
                                onClick={() => handleRemoveWorkflow(workflow.template_id, workflow.name)}
                                className="btn btn-ghost btn-xs text-error ml-2"
                                aria-label="Remove workflow"
                              >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              </button>
                            </div>
                            <span className="text-xs text-readout">v{workflow.version}</span>
                          </div>
                        </div>
                      </div>

                      {workflow.description && (
                        <p className="text-xs text-readout mt-2 ml-9">
                          {workflow.description}
                        </p>
                      )}

                      {workflow.tags && workflow.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2 ml-9">
                          {workflow.tags.map((tag, tagIndex) => (
                            <span
                              key={tagIndex}
                              className="badge badge-ghost badge-xs"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-readout">
                  <svg className="mx-auto h-12 w-12 text-readout" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                  <p className="mt-2 text-sm">No workflows in this list yet</p>
                  <button
                    onClick={() => setShowAddModal(true)}
                    className="btn btn-outline btn-sm mt-3"
                  >
                    Add Your First Workflow
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="modal-action">
            <div className="flex-1 text-sm text-readout">
              {list.workflow_count} workflow{list.workflow_count !== 1 ? 's' : ''} in list
            </div>
            <button
              onClick={handleEditClick}
              className="btn btn-primary"
            >
              Edit List
            </button>
          </div>
        </div>
        <div className="modal-backdrop" onClick={onClose}></div>
      </div>

      {/* Add Workflow Modal */}
      {showAddModal && (
        <WorkflowSelectionModal
          listId={list.id}
          listName={list.name}
          existingWorkflowIds={existingWorkflowIds}
          onClose={() => setShowAddModal(false)}
          onWorkflowsAdded={handleAddWorkflows}
        />
      )}
    </>
  );
};

export default WorkflowListPreview;
