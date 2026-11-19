/**
 * Add Tools Modal Component
 *
 * Modal for selecting and assigning tools to a team.
 */

import React, { useState, useEffect } from 'react'
import type { Team, TeamTool } from '@/types/team_tools'
import type { Tool, ToolListResponse } from '@/types/tools'
import { ToolService } from '@/services/domain/ToolService'

interface AddToolsModalProps {
  team: Team
  onClose: () => void
  onAssign: (toolId: string, priority: number) => Promise<void>
}

export const AddToolsModal: React.FC<AddToolsModalProps> = ({
  team,
  onClose,
  onAssign,
}) => {
  const [availableTools, setAvailableTools] = useState<Tool[]>([])
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set())
  const [priority, setPriority] = useState(0)
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isAssigning, setIsAssigning] = useState(false)

  // Load available tools
  useEffect(() => {
    const loadTools = async () => {
      try {
        setIsLoading(true)
        const toolService = new ToolService()
        const response: ToolListResponse = await toolService.listTools({ is_active: true })
        // Filter out tools already in the team
        const teamToolIds = team.tools.map((t: TeamTool) => t.tool_id)
        const available = response.tools.filter((t: Tool) => !teamToolIds.includes(t.id))
        setAvailableTools(available)
      } catch (err) {
        console.error('Failed to load tools:', err)
      } finally {
        setIsLoading(false)
      }
    }
    loadTools()
  }, [team.tools])

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

  const handleAssign = async () => {
    if (selectedTools.size === 0) return
    
    try {
      setIsAssigning(true)
      // Assign all selected tools
      for (const toolId of selectedTools) {
        await onAssign(toolId, priority)
      }
      onClose()
    } catch (err) {
      console.error('Failed to assign tools:', err)
    } finally {
      setIsAssigning(false)
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
          Add Tools to {team.name}
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
            <span className="label-text-alt">Higher priority tools are more important</span>
          </label>
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
            className="btn btn-ghost"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={handleAssign}
            disabled={selectedTools.size === 0 || isAssigning}
          >
            {isAssigning ? (
              <>
                <span className="loading loading-spinner loading-xs"></span>
                Assigning...
              </>
            ) : (
              `Assign ${selectedTools.size} Tool${selectedTools.size !== 1 ? 's' : ''}`
            )}
          </button>
        </div>
      </div>
      <div className="modal-backdrop" onClick={onClose}></div>
    </div>
  )
}
