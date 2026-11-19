/**
 * WorkflowListEditor Component
 *
 * Component for editing workflow list details
 */

import { useState } from 'react';
import type { WorkflowList, WorkflowInList } from '@/types/workflows';
import { WorkflowSelectionModal } from './WorkflowSelectionModal';

interface WorkflowListEditorProps {
  isOpen: boolean;
  list: WorkflowList | null;
  workflows: WorkflowInList[];
  availableTags: string[];
  onClose: () => void;
  onSave: (data: { name: string; description?: string; tags?: string[] }) => void;
  onAddWorkflows?: (workflowIds: string[]) => Promise<void>;
  onRemoveWorkflow?: (workflowId: string) => Promise<void>;
}

/**
 * WorkflowListEditor Component
 */
const WorkflowListEditor: React.FC<WorkflowListEditorProps> = ({
  isOpen,
  list,
  workflows,
  availableTags,
  onClose,
  onSave,
  onAddWorkflows,
  onRemoveWorkflow
}) => {
  const [selectedTags, setSelectedTags] = useState<string[]>(list?.tags || []);
  const [showAddModal, setShowAddModal] = useState(false);

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    onSave({
      name: formData.get('name') as string,
      description: formData.get('description') as string || undefined,
      tags: selectedTags
    });
    onClose();
  };

  const handleTagToggle = (tag: string) => {
    setSelectedTags(prev =>
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    );
  };

  const handleAddWorkflows = async (workflowIds: string[]) => {
    if (onAddWorkflows && list) {
      await onAddWorkflows(workflowIds);
      setShowAddModal(false);
    }
  };

  const handleRemoveWorkflow = async (workflowId: string, workflowName: string) => {
    if (!onRemoveWorkflow || !list) return;

    const confirmed = confirm(`Remove "${workflowName}" from this list?`);
    if (!confirmed) return;

    await onRemoveWorkflow(workflowId);
  };

  // Early return if not open
  if (!isOpen) return null;

  const existingWorkflowIds = workflows.map(wf => wf.template_id);

  return (
    <>
      <div className="modal modal-open" role="dialog">
        <div className="modal-box max-w-4xl max-h-[90vh] overflow-y-auto">
          <form onSubmit={handleSubmit}>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-bold text-lg">
                {list ? 'Edit Workflow List' : 'Create Workflow List'}
              </h3>
              <button
                type="button"
                onClick={onClose}
                className="btn btn-ghost btn-sm btn-circle"
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            {/* Content */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">
                  Name
                </label>
                <input
                  name="name"
                  type="text"
                  className="input input-bordered w-full"
                  defaultValue={list?.name || ''}
                  placeholder="My Workflow List"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Description
                </label>
                <textarea
                  name="description"
                  className="textarea textarea-bordered w-full"
                  defaultValue={list?.description || ''}
                  placeholder="Describe this workflow list..."
                  rows={3}
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">
                  Tags
                </label>
                {availableTags.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {availableTags.map((tag) => (
                      <button
                        key={tag}
                        type="button"
                        onClick={() => handleTagToggle(tag)}
                        className={`badge badge-sm cursor-pointer border-0 ${
                          selectedTags.includes(tag)
                            ? 'badge-primary'
                            : 'badge-ghost hover:badge-outline'
                        }`}
                      >
                        {tag}
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-readout">No tags available</p>
                )}
              </div>

              {/* Workflows Section - Only show when editing existing list */}
              {list && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium">
                      Workflows ({workflows.length})
                    </label>
                    <button
                      type="button"
                      onClick={() => setShowAddModal(true)}
                      className="btn btn-primary btn-sm"
                    >
                      <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                      Add Workflow
                    </button>
                  </div>

                  {workflows.length === 0 ? (
                    <div className="text-center py-6 bg-base-200 rounded-lg">
                      <div className="text-3xl mb-2">📋</div>
                      <p className="text-sm text-readout mb-3">No workflows in this list yet</p>
                      <button
                        type="button"
                        onClick={() => setShowAddModal(true)}
                        className="btn btn-outline btn-sm"
                      >
                        Add Your First Workflow
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      {workflows.map((workflow, index) => (
                        <div
                          key={workflow.template_id}
                          className="flex items-start justify-between p-3 bg-base-100 border border-base-300 rounded-lg"
                        >
                          <div className="flex items-start gap-3 flex-1">
                            <span className="flex-shrink-0 w-6 h-6 bg-primary text-primary-content rounded-full flex items-center justify-center text-xs font-medium mt-0.5">
                              {index + 1}
                            </span>
                            <div className="flex-1">
                              <h4 className="text-sm font-medium">{workflow.name}</h4>
                              {workflow.description && (
                                <p className="text-xs text-readout mt-1">
                                  {workflow.description}
                                </p>
                              )}
                              {workflow.tags && workflow.tags.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-1">
                                  {workflow.tags.slice(0, 3).map((tag, idx) => (
                                    <span key={idx} className="badge badge-ghost badge-xs">
                                      {tag}
                                    </span>
                                  ))}
                                  {workflow.tags.length > 3 && (
                                    <span className="text-xs text-readout">
                                      +{workflow.tags.length - 3}
                                    </span>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleRemoveWorkflow(workflow.template_id, workflow.name)}
                            className="btn btn-ghost btn-xs text-error ml-2"
                            aria-label="Remove workflow"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="modal-action">
              <button
                type="button"
                onClick={onClose}
                className="btn btn-ghost"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
              >
                {list ? 'Save Changes' : 'Create List'}
              </button>
            </div>
          </form>
        </div>
        <div className="modal-backdrop" onClick={onClose}></div>
      </div>

      {/* Add Workflow Modal */}
      {list && showAddModal && (
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

export default WorkflowListEditor;
