/**
 * Team Tools Tab Component
 *
 * Displays and manages team tools and toolboxes.
 */

import React from 'react'
import type { Team, TeamTool } from '@/types/team_tools'

interface TeamToolsTabProps {
  team: Team
  onAddTools: () => void
  onAddToolboxes: () => void
  onRemoveTool: (toolId: string, sourceType?: 'direct' | 'toolbox') => Promise<void>
}

export const TeamToolsTab: React.FC<TeamToolsTabProps> = ({
  team,
  onAddTools,
  onAddToolboxes,
  onRemoveTool,
}) => {
  // Group tools by source type
  const directTools = team.tools.filter(t => t.source_type === 'direct')
  const toolboxTools = team.tools.filter(t => t.source_type === 'toolbox')

  if (team.tools.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="text-6xl mb-4">🧰</div>
        <h3 className="text-xl font-semibold text-base-content mb-2">No tools assigned yet</h3>
        <p className="text-readout mb-6">
          Assign tools or toolboxes to this team. Members will automatically receive these tools.
        </p>
        <div className="flex gap-4 justify-center">
          <button
            onClick={onAddTools}
            className="btn btn-primary"
          >
            Add Tools
          </button>
          <button
            onClick={onAddToolboxes}
            className="btn btn-secondary"
          >
            Add Toolboxes
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Action Buttons */}
      <div className="flex gap-2">
        <button
          onClick={onAddTools}
          className="btn btn-primary btn-sm gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Tools
        </button>
        <button
          onClick={onAddToolboxes}
          className="btn btn-secondary btn-sm gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
          Add Toolboxes
        </button>
      </div>

      {/* Direct Tools */}
      {directTools.length > 0 && (
        <div className="space-y-3">
          <h3 className="font-semibold text-base-content">Direct Tools ({directTools.length})</h3>
          <ToolsTable tools={directTools} onRemove={onRemoveTool} />
        </div>
      )}

      {/* Toolbox Tools */}
      {toolboxTools.length > 0 && (
        <div className="space-y-3">
          <h3 className="font-semibold text-base-content">Tools from Toolboxes ({toolboxTools.length})</h3>
          <ToolsTable tools={toolboxTools} onRemove={onRemoveTool} />
        </div>
      )}
    </div>
  )
}

interface ToolsTableProps {
  tools: TeamTool[]
  onRemove: (toolId: string, sourceType?: 'direct' | 'toolbox') => Promise<void>
}

const ToolsTable: React.FC<ToolsTableProps> = ({ tools, onRemove }) => {
  return (
    <div className="overflow-x-auto bg-base-100 border border-base-300 rounded-lg">
      <table className="table table-zebra w-full">
        <thead>
          <tr>
            <th>Tool</th>
            <th className="w-24">Priority</th>
            <th className="w-24">Status</th>
            <th className="w-20 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {tools.map(tool => {
            const name = tool.tool?.name || `Tool ${tool.tool_id.slice(0, 8)}`
            const desc = tool.tool?.description || ''
            return (
              <tr key={tool.id}>
                <td>
                  <div className="font-medium">{name}</div>
                  {desc && (
                    <div className="text-sm text-readout truncate max-w-md">{desc}</div>
                  )}
                </td>
                <td>
                  <span className="badge badge-ghost badge-sm">{tool.priority}</span>
                </td>
                <td>
                  {tool.is_active
                    ? <span className="badge badge-success badge-sm">Active</span>
                    : <span className="badge badge-error badge-sm">Inactive</span>
                  }
                </td>
                <td className="text-right">
                  <button
                    onClick={() => onRemove(tool.tool_id, tool.source_type)}
                    className="btn btn-ghost btn-xs text-error"
                    data-tip="Remove from team"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
