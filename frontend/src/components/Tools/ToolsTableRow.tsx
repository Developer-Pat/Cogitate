import type { Tool } from '@/types/tools'

// The keyed tier (mirrors capabilities.py — the admin/write family)
const KEYED_CAPABILITIES = new Set([
  'file-write', 'db-write', 'clipboard-io',
  'agent-admin', 'workflow-admin', 'provider-admin',
  'macro-admin', 'doc-admin', 'todo-mgmt',
])

function isKeyedCapability(capability: string): boolean {
  return KEYED_CAPABILITIES.has(capability)
}
import ToolsTableActions from './ToolsTableActions'
import { TagBadge } from './TagBadge'

interface ToolsTableRowProps {
  tool: Tool
  isSelected: boolean
  onSelect: () => void
  onDuplicate: () => void
  isLoading: boolean
}

export default function ToolsTableRow({
  tool,
  isSelected,
  onSelect,
  onDuplicate,
  isLoading
}: ToolsTableRowProps) {
  // Get first 3 tags for display
  const displayTags = tool.tags?.slice(0, 3) || []
  const remainingTags = (tool.tags?.length || 0) - 3

  return (
    <tr
      className={`hover:bg-base-200 transition-colors ${
        isSelected ? 'bg-primary/10' : ''
      }`}
    >
      {/* Select Checkbox */}
      <td className="text-center">
        <label className="flex items-center justify-center cursor-pointer">
          <input
            type="checkbox"
            checked={isSelected}
            onChange={onSelect}
            className="checkbox checkbox-sm checkbox-primary"
          />
        </label>
      </td>

      {/* Tool Info */}
      <td>
        <div className="flex items-center gap-3">
          {/* Name and Description */}
          <div className="flex-1 min-w-0">
            <div className="font-medium text-sm truncate">{tool.name}</div>
            {tool.description && (
              <div className="text-xs text-readout truncate max-w-md">
                {tool.description}
              </div>
            )}
            {/* Tags */}
            {displayTags.length > 0 && (
              <div className="flex gap-1 mt-1 flex-wrap">
                {displayTags.map(tag => (
                  <TagBadge key={tag} tag={tag} showTooltip={true} size="sm" />
                ))}
                {remainingTags > 0 && (
                  <span className="text-xs text-readout self-center">
                    +{remainingTags} more
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </td>

      {/* Type */}
      <td>
        {tool.type ? (
          <div className="badge badge-ghost badge-sm">
            {tool.type}
          </div>
        ) : (
          <span className="text-xs text-readout">—</span>
        )}
      </td>

      {/* Capability (Phase A — the canonical vocabulary) */}
      <td>
        {tool.capability ? (
          <div className="flex items-center gap-1.5">
            <div className="badge badge-outline badge-sm font-mono">
              {tool.capability}
            </div>
          </div>
        ) : (
          <span className="text-xs text-readout">—</span>
        )}
      </td>

      {/* Status */}
      <td>
        <div className={`badge badge-sm ${tool.is_active ? 'badge-success badge-outline' : 'badge-ghost'}`}>
          {tool.is_active ? 'Active' : 'Inactive'}
        </div>
      </td>

      {/* Access — the tool's registry tier (keyed vs GRAS) */}
      <td>
        {tool.capability ? (
          isKeyedCapability(tool.capability) ? (
            <div className="tooltip tooltip-top" data-tip="Keyed — requires a grant to execute">
              <div className="badge badge-warning badge-outline badge-sm">Keyed</div>
            </div>
          ) : (
            <div className="tooltip tooltip-top" data-tip="GRAS — safe to execute without grants">
              <div className="badge badge-success badge-outline badge-sm">GRAS</div>
            </div>
          )
        ) : (
          <span className="text-readout text-xs">—</span>
        )}
      </td>

      {/* Actions */}
      <td>
        <ToolsTableActions
          tool={tool}
          onDuplicate={onDuplicate}
          isLoading={isLoading}
        />
      </td>
    </tr>
  )
}
