/**
 * Add Toolboxes Modal Component
 *
 * Modal for selecting and assigning toolboxes to a team.
 */

import React, { useState, useEffect } from 'react'
import type { Team } from '@/types/team_tools'
import type { Collection } from '@/types/collections'
import { collectionsService } from '@/services/domain/CollectionsService'

interface AddToolboxesModalProps {
  team: Team
  onClose: () => void
  onAssign: (toolboxId: string, priority: number) => Promise<void>
}

export const AddToolboxesModal: React.FC<AddToolboxesModalProps> = ({
  team,
  onClose,
  onAssign,
}) => {
  const [availableToolboxes, setAvailableToolboxes] = useState<Collection[]>([])
  const [selectedToolboxes, setSelectedToolboxes] = useState<Set<string>>(new Set())
  const [priority, setPriority] = useState(0)
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isAssigning, setIsAssigning] = useState(false)

  // Load available toolboxes
  useEffect(() => {
    const loadToolboxes = async () => {
      try {
        setIsLoading(true)
        const response = await collectionsService.listCollections({ entity_type: 'tool' })
        // Filter out toolboxes already assigned to the team
        const teamToolboxIds = team.tools
          .filter(t => t.source_type === 'toolbox' && t.source_id)
          .map(t => t.source_id!)
        const available = response.collections.filter(tb => !teamToolboxIds.includes(tb.id))
        setAvailableToolboxes(available)
      } catch (err) {
        console.error('Failed to load toolboxes:', err)
      } finally {
        setIsLoading(false)
      }
    }
    loadToolboxes()
  }, [team.tools])

  const handleToggleToolbox = (toolboxId: string) => {
    const newSelected = new Set(selectedToolboxes)
    if (newSelected.has(toolboxId)) {
      newSelected.delete(toolboxId)
    } else {
      newSelected.add(toolboxId)
    }
    setSelectedToolboxes(newSelected)
  }

  const handleSelectAll = () => {
    if (selectedToolboxes.size === filteredToolboxes.length) {
      setSelectedToolboxes(new Set())
    } else {
      setSelectedToolboxes(new Set(filteredToolboxes.map(tb => tb.id)))
    }
  }

  const handleAssign = async () => {
    if (selectedToolboxes.size === 0) return
    
    try {
      setIsAssigning(true)
      // Assign all selected toolboxes
      for (const toolboxId of selectedToolboxes) {
        await onAssign(toolboxId, priority)
      }
      onClose()
    } catch (err) {
      console.error('Failed to assign toolboxes:', err)
    } finally {
      setIsAssigning(false)
    }
  }

  // Filter toolboxes by search
  const filteredToolboxes = availableToolboxes.filter(toolbox =>
    toolbox.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    toolbox.description?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="modal modal-open">
      <div className="modal-box max-w-2xl">
        <h3 className="font-bold text-lg mb-4">
          Add Toolboxes to {team.name}
        </h3>

        {/* Search */}
        <div className="form-control mb-4">
          <input
            type="text"
            placeholder="Search toolboxes..."
            className="input input-bordered input-sm"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        {/* Priority */}
        <div className="form-control mb-4">
          <label className="label">
            <span className="label-text">Priority</span>
          </label>
          <input
            type="number"
            className="input input-bordered input-sm"
            value={priority}
            onChange={(e) => setPriority(parseInt(e.target.value) || 0)}
            min={0}
          />
          <label className="label">
            <span className="label-text-alt">Higher priority toolboxes take precedence</span>
          </label>
        </div>

        {/* Select All */}
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm text-readout">
            {selectedToolboxes.size} of {filteredToolboxes.length} selected
          </span>
          <button
            className="btn btn-ghost btn-xs"
            onClick={handleSelectAll}
          >
            {selectedToolboxes.size === filteredToolboxes.length ? 'Deselect All' : 'Select All'}
          </button>
        </div>

        {/* Toolboxes List */}
        <div className="max-h-96 overflow-y-auto space-y-2">
          {isLoading ? (
            <div className="text-center py-8">
              <span className="loading loading-spinner"></span>
            </div>
          ) : filteredToolboxes.length === 0 ? (
            <div className="text-center py-8 text-readout">
              {searchQuery ? 'No toolboxes match your search' : 'No toolboxes available'}
            </div>
          ) : (
            filteredToolboxes.map(toolbox => (
              <label
                key={toolbox.id}
                className="flex items-center gap-3 p-3 rounded-lg border border-base-300 hover:border-secondary cursor-pointer transition-colors"
              >
                <input
                  type="checkbox"
                  className="checkbox checkbox-sm checkbox-primary"
                  checked={selectedToolboxes.has(toolbox.id)}
                  onChange={() => handleToggleToolbox(toolbox.id)}
                />
                <div className="flex-1">
                  <div className="font-medium">{toolbox.name}</div>
                  <div className="text-xs text-readout line-clamp-1">
                    {toolbox.description || 'No description'}
                  </div>
                  <div className="text-xs text-readout mt-1">
                    {toolbox.item_count} tools
                  </div>
                </div>
                <div className="text-2xl">{toolbox.icon}</div>
              </label>
            ))
          )}
        </div>

        {/* Actions */}
        <div className="modal-action">
          <button
            className="btn btn-ghost"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="btn btn-secondary"
            onClick={handleAssign}
            disabled={selectedToolboxes.size === 0 || isAssigning}
          >
            {isAssigning ? (
              <>
                <span className="loading loading-spinner loading-xs"></span>
                Assigning...
              </>
            ) : (
              `Assign ${selectedToolboxes.size} Toolbox${selectedToolboxes.size !== 1 ? 'es' : ''}`
            )}
          </button>
        </div>
      </div>
      <div className="modal-backdrop" onClick={onClose}></div>
    </div>
  )
}
