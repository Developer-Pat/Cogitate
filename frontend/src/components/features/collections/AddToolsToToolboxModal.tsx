/**
 * Add Tools to Toolbox Modal
 *
 * Modal for selecting and adding tools to a toolbox (collection).
 */

import React, { useState, useEffect } from 'react'
import type { Collection, CollectionItemCreate } from '@/types/collections'
import type { Tool, ToolListResponse } from '@/types/tools'
import { collectionsService } from '@/services/domain/CollectionsService'
import { ToolService } from '@/services/domain/ToolService'
import { useNotificationStore } from '@/stores/notificationStore'

interface AddToolsToToolboxModalProps {
  toolbox: Collection
  onClose: () => void
  onToolsAdded: () => void
}

export const AddToolsToToolboxModal: React.FC<AddToolsToToolboxModalProps> = ({
  toolbox,
  onClose,
  onToolsAdded,
}) => {
  const [availableTools, setAvailableTools] = useState<Tool[]>([])
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isAdding, setIsAdding] = useState(false)

  // Load available tools (not already in toolbox)
  useEffect(() => {
    const loadTools = async () => {
      try {
        setIsLoading(true)
        const toolService = new ToolService()
        const response: ToolListResponse = await toolService.listTools({ is_active: true })
        
        // Get tools already in this toolbox
        const existingToolIds = toolbox.items
          .filter(item => item.entity_type === 'tool')
          .map(item => item.entity_id)
        
        // Filter out tools already in toolbox
        const available = response.tools.filter(tool => !existingToolIds.includes(tool.id))
        setAvailableTools(available)
      } catch (err) {
        console.error('Failed to load tools:', err)
        useNotificationStore.getState().addError(
          'Failed to Load Tools',
          'Could not load available tools'
        )
      } finally {
        setIsLoading(false)
      }
    }
    loadTools()
  }, [toolbox.items])

  const handleToggleTool = (toolId: string) => {
    const newSelected = new Set(selectedTools)
    if (newSelected.has(toolId)) {
      newSelected.delete(toolId)
    } else {
      newSelected.add(toolId)
    }
    setSelectedTools(newSelected)
  }

  const handleSelectAll = () => {
    if (selectedTools.size === filteredTools.length) {
      setSelectedTools(new Set())
    } else {
      setSelectedTools(new Set(filteredTools.map(t => t.id)))
    }
  }

  const handleAddTools = async () => {
    if (selectedTools.size === 0) return
    
    try {
      setIsAdding(true)
      
      // Add each selected tool to the toolbox
      for (const toolId of selectedTools) {
        const tool = availableTools.find(t => t.id === toolId)
        if (!tool) continue
        
        const itemData: CollectionItemCreate = {
          entity_id: toolId,
          entity_type: 'tool',
          entity_name: tool.name,
        }
        
        await collectionsService.addItemToCollection(toolbox.id, itemData)
      }
      
      useNotificationStore.getState().addSuccess(
        'Tools Added',
        `${selectedTools.size} tool${selectedTools.size !== 1 ? 's' : ''} added to toolbox`
      )
      
      onToolsAdded()
      onClose()
    } catch (err) {
      console.error('Failed to add tools:', err)
      useNotificationStore.getState().addError(
        'Failed to Add Tools',
        'Could not add tools to toolbox'
      )
    } finally {
      setIsAdding(false)
    }
  }

  // Filter tools by search
  const filteredTools = availableTools.filter(tool =>
    tool.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    tool.description.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="modal modal-open">
      <div className="modal-box max-w-2xl">
        <h3 className="font-bold text-lg mb-4">
          Add Tools to {toolbox.name}
        </h3>

        {/* Search */}
        <div className="form-control mb-4">
          <input
            type="text"
            placeholder="Search tools..."
            className="input input-bordered input-sm"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        {/* Select All */}
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm text-readout">
            {selectedTools.size} of {filteredTools.length} selected
          </span>
          <button
            className="btn btn-ghost btn-xs"
            onClick={handleSelectAll}
          >
            {selectedTools.size === filteredTools.length ? 'Deselect All' : 'Select All'}
          </button>
        </div>

        {/* Tools List */}
        <div className="max-h-96 overflow-y-auto space-y-2">
          {isLoading ? (
            <div className="text-center py-8">
              <span className="loading loading-spinner"></span>
            </div>
          ) : filteredTools.length === 0 ? (
            <div className="text-center py-8 text-readout">
              {searchQuery ? 'No tools match your search' : 'No tools available'}
            </div>
          ) : (
            filteredTools.map(tool => (
              <label
                key={tool.id}
                className="flex items-center gap-3 p-3 rounded-lg border border-base-300 hover:border-primary cursor-pointer transition-colors"
              >
                <input
                  type="checkbox"
                  className="checkbox checkbox-sm checkbox-primary"
                  checked={selectedTools.has(tool.id)}
                  onChange={() => handleToggleTool(tool.id)}
                />
                <div className="flex-1">
                  <div className="font-medium">{tool.name}</div>
                  <div className="text-xs text-readout line-clamp-1">{tool.description}</div>
                </div>
                {tool.icon && (
                  <div className="text-xl">{tool.icon}</div>
                )}
              </label>
            ))
          )}
        </div>

        {/* Actions */}
        <div className="modal-action">
          <button
            className="btn btn-neutral btn-ghost"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={handleAddTools}
            disabled={selectedTools.size === 0 || isAdding}
          >
            {isAdding ? (
              <>
                <span className="loading loading-spinner loading-xs"></span>
                Adding...
              </>
            ) : (
              `Add ${selectedTools.size} Tool${selectedTools.size !== 1 ? 's' : ''}`
            )}
          </button>
        </div>
      </div>
      <div className="modal-backdrop" onClick={onClose}></div>
    </div>
  )
}
