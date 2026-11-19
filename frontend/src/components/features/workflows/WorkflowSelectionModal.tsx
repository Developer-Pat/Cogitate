/**
 * Workflow Selection Modal
 *
 * Modal dialog for selecting workflows to add to a workflow list.
 * Supports search, filtering, and multi-select.
 */

import React, { useState, useEffect, useMemo } from 'react'
import { ClipboardList } from 'lucide-react'
import { workflowService } from '@/services/domains/llm/workflowService'
import type { WorkflowTemplate } from '@/types/workflows'
import { useNotificationStore } from '@/stores/notificationStore'

interface WorkflowSelectionModalProps {
  listId: string
  listName: string
  existingWorkflowIds: string[]
  onClose: () => void
  onWorkflowsAdded: (workflowIds: string[]) => void
}

/**
 * WorkflowSelectionModal Component
 */
export const WorkflowSelectionModal: React.FC<WorkflowSelectionModalProps> = ({
  listId: _listId,
  listName,
  existingWorkflowIds,
  onClose,
  onWorkflowsAdded
}) => {
  const [workflows, setWorkflows] = useState<WorkflowTemplate[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedWorkflowIds, setSelectedWorkflowIds] = useState<string[]>([])
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [categories, setCategories] = useState<string[]>([])

  const addNotification = useNotificationStore((state) => state.addNotification)

  /**
   * Load all workflows and extract categories
   */
  useEffect(() => {
    const loadWorkflows = async () => {
      try {
        setIsLoading(true)
        const response = await workflowService.getTemplates()
        const allWorkflows = response.data || []
        setWorkflows(allWorkflows)

        // Extract unique categories
        const categorySet = new Set<string>()
        allWorkflows.forEach(wf => categorySet.add(wf.category))
        setCategories(Array.from(categorySet))
      } catch (error) {
        console.error('Failed to load workflows:', error)
        addNotification({
          type: 'error',
          title: 'Error',
          message: 'Failed to load workflows'
        })
      } finally {
        setIsLoading(false)
      }
    }
    loadWorkflows()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /**
   * Filter workflows based on search and category
   */
  const filteredWorkflows = useMemo(() => {
    return workflows.filter(workflow => {
      // Exclude workflows already in the list
      if (existingWorkflowIds.includes(workflow.id)) {
        return false
      }

      // Search filter
      const matchesSearch = searchQuery === '' ||
        workflow.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        workflow.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        workflow.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))

      // Category filter
      const matchesCategory = categoryFilter === '' || workflow.category === categoryFilter

      return matchesSearch && matchesCategory
    })
  }, [workflows, searchQuery, categoryFilter, existingWorkflowIds])

  /**
   * Toggle workflow selection
   */
  const handleToggleWorkflow = (workflowId: string) => {
    setSelectedWorkflowIds(prev =>
      prev.includes(workflowId)
        ? prev.filter(id => id !== workflowId)
        : [...prev, workflowId]
    )
  }

  /**
   * Select all visible workflows
   */
  const handleSelectAll = () => {
    const allVisibleIds = filteredWorkflows.map(wf => wf.id)
    setSelectedWorkflowIds(allVisibleIds)
  }

  /**
   * Deselect all workflows
   */
  const handleDeselectAll = () => {
    setSelectedWorkflowIds([])
  }

  /**
   * Handle save - add selected workflows to list
   */
  const handleSave = async () => {
    if (selectedWorkflowIds.length === 0) {
      addNotification({
        type: 'warning',
        title: 'No Selection',
        message: 'Please select at least one workflow'
      })
      return
    }

    try {
      // Add workflows to list (caller will handle the actual API calls)
      addNotification({
        type: 'success',
        title: 'Workflows Selected',
        message: `Selected ${selectedWorkflowIds.length} workflow(s) to add`
      })
      onWorkflowsAdded(selectedWorkflowIds)
    } catch (error) {
      console.error('Failed to add workflows:', error)
      addNotification({
        type: 'error',
        title: 'Error',
        message: 'Failed to add workflows to list'
      })
    }
  }

  if (isLoading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
        <div className="bg-base-200 rounded-lg shadow-xl p-6">
          <span className="loading loading-lg"></span>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
      <div className="bg-base-200 rounded-lg shadow-xl w-[var(--dialog-width-md)] max-w-[var(--dialog-width-full)] mx-4 max-h-[80vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-base-300 sticky top-0 bg-base-200 z-10">
          <div>
            <h2 className="text-2xl font-bold text-base-content">Add Workflows to List</h2>
            <p className="text-sm text-readout mt-1">
              Add workflows to "{listName}"
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-base-content/50 hover:text-base-content/70"
            aria-label="Close"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Filters */}
        <div className="p-6 border-b border-base-300 space-y-4">
          {/* Search */}
          <div>
            <label className="block text-sm font-medium text-base-content mb-2">
              Search Workflows
            </label>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name, description, or tags..."
              className="input input-bordered w-full"
            />
          </div>

          {/* Category Filter */}
          {categories.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-base-content mb-2">
                Filter by Category
              </label>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="select select-bordered w-full"
              >
                <option value="">All Categories</option>
                {categories.map(cat => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </div>
          )}

          {/* Selection Actions */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-readout">
              Showing {filteredWorkflows.length} workflow(s)
              {existingWorkflowIds.length > 0 && (
                <span className="ml-2">
                  ({existingWorkflowIds.length} already in list)
                </span>
              )}
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleSelectAll}
                className="btn btn-outline btn-xs"
                disabled={filteredWorkflows.length === 0}
              >
                Select All
              </button>
              <button
                onClick={handleDeselectAll}
                className="btn btn-outline btn-xs"
                disabled={selectedWorkflowIds.length === 0}
              >
                Deselect All
              </button>
            </div>
          </div>
        </div>

        {/* Workflow List */}
        <div className="p-6 space-y-3">
          {filteredWorkflows.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-4xl mb-4 text-readout">
              <ClipboardList className="h-10 w-10 mx-auto" />
            </div>
              <p className="text-readout mb-4">
                {existingWorkflowIds.length === workflows.length
                  ? 'All workflows are already in this list'
                  : 'No workflows match your search criteria'}
              </p>
              {(searchQuery || categoryFilter) && (
                <button
                  onClick={() => {
                    setSearchQuery('')
                    setCategoryFilter('')
                  }}
                  className="btn btn-error btn-outline btn-sm"
                >
                  Clear Filters
                </button>
              )}
            </div>
          ) : (
            filteredWorkflows.map(workflow => (
              <label
                key={workflow.id}
                className={`flex items-start gap-4 p-4 rounded-lg border cursor-pointer transition-colors ${
                  selectedWorkflowIds.includes(workflow.id)
                    ? 'bg-primary/10 border-primary'
                    : 'bg-base-100 border-base-300 hover:bg-base-100/50'
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedWorkflowIds.includes(workflow.id)}
                  onChange={() => handleToggleWorkflow(workflow.id)}
                  className="checkbox checkbox-sm mt-1 checkbox-primary"
                />
                <div className="flex-1">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h4 className="font-medium text-base-content">{workflow.name}</h4>
                      <p className="text-sm text-readout mt-1">
                        {workflow.description}
                      </p>
                    </div>
                    <span className="text-xs text-readout whitespace-nowrap ml-2">
                      v{workflow.version}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="badge badge-ghost badge-xs">
                      {workflow.category}
                    </span>
                    {workflow.tags.slice(0, 3).map((tag, idx) => (
                      <span key={idx} className="badge badge-outline badge-xs">
                        {tag}
                      </span>
                    ))}
                    {workflow.tags.length > 3 && (
                      <span className="text-xs text-readout">
                        +{workflow.tags.length - 3}
                      </span>
                    )}
                  </div>
                </div>
              </label>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-base-300 flex justify-end gap-2 sticky bottom-0 bg-base-200">
          <button onClick={onClose} className="btn btn-neutral btn-ghost">
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="btn btn-primary"
            disabled={selectedWorkflowIds.length === 0}
          >
            Add {selectedWorkflowIds.length} Workflow{selectedWorkflowIds.length !== 1 ? 's' : ''}
          </button>
        </div>
      </div>
    </div>
  )
}