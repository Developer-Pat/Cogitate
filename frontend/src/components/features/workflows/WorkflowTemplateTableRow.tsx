import type { WorkflowTemplate } from '@/types/workflows'

interface Props {
  template: WorkflowTemplate
  isSelected: boolean
  onSelect: () => void
  onEdit: () => void
  onExecute: () => void
  onReset?: () => void
  onDelete?: () => void
  isLoading: boolean
}

function typeBadgeColor(type: string): string {
  // Canonical kind names; the legacy workflow_type values
  // ('file-clerk', 'boss-agent', 'workflow') map to their kinds so
  // the UI never surfaces the old persona names.
  switch (type) {
    case 'multi_agent': return 'badge-secondary badge-outline'
    case 'advanced': return 'badge-accent'
    case 'monitor':
    case 'workflow': return 'badge-primary'
    case 'file-processing':
    case 'file-clerk': return 'badge-warning'
    case 'batch-orchestration':
    case 'boss-agent': return 'badge-info'
    default: return 'badge-ghost'
  }
}

export default function WorkflowTemplateTableRow({
  template,
  isSelected,
  onSelect,
  onEdit: _onEdit,
  onExecute,
  onReset,
  onDelete: _onDelete,
  isLoading
}: Props) {
  const updated = template.updatedAt || template.createdAt
  const updatedDate = updated ? new Date(updated).toLocaleDateString() : '—'
  const type = template.workflowType || 'simple'


  return (
    <tr
      className={`cursor-pointer hover:bg-base-200 ${isSelected ? 'bg-primary/10' : ''}`}
      onClick={onSelect}
    >
      {/* Name */}
      <td>
        <div className="flex flex-col">
          <span className="font-medium">{template.name}</span>
          <span className="text-xs opacity-60 truncate max-w-xs">{template.description}</span>
        </div>
      </td>

      {/* Category */}
      <td>
        <span className="text-sm">{template.category || '—'}</span>
      </td>

      {/* Type */}
      <td>
        <span className={`badge badge-sm ${typeBadgeColor(type)}`}>{type}</span>
      </td>

      {/* Version */}
      <td className="font-mono text-sm">{template.version}</td>

      {/* Tags */}
      <td>
        <div className="flex gap-1 flex-wrap">
          {template.tags.slice(0, 3).map(tag => (
            <span key={tag} className="badge badge-xs badge-ghost">{tag}</span>
          ))}
          {template.tags.length > 3 && (
            <span className="badge badge-xs badge-ghost">+{template.tags.length - 3}</span>
          )}
        </div>
      </td>

      {/* Updated */}
      <td className="text-sm opacity-70">{updatedDate}</td>

      {/* Actions */}
      <td>
        <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
          <div className="tooltip" data-tip="Run">
            <button
              className="btn btn-ghost btn-xs"
              onClick={onExecute}
              aria-label="Run workflow"
              disabled={isLoading}
            >
              ▶
            </button>
          </div>
          <div className="tooltip" data-tip="Edit">
            <button
              className="btn btn-ghost btn-xs opacity-40 cursor-not-allowed"
              aria-label="Edit workflow steps (not yet implemented)"
              disabled
            >
              ✏️
            </button>
          </div>
          {onReset && (
            <div className="tooltip tooltip-bottom-left" data-tip="Reset">
              <button
                className="btn btn-ghost btn-xs text-warning"
                onClick={onReset}
                aria-label="Reset the dedup checkpoint"
              >
                ↺ Reset
              </button>
            </div>
          )}
        </div>
      </td>
    </tr>
  )
}
