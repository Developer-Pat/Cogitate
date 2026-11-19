import type { Profile } from '@/services/domain/ProfileService'
import AgentTableActions from './AgentTableActions'

interface AgentTableRowProps {
  profile: Profile
  isSelected: boolean
  isRowSelected: boolean
  onSelect: () => void
  onSelectProfile: () => void
  onDuplicate: () => void
  isLoading: boolean
  onManageTools?: (agentId: string) => void
}

export default function AgentTableRow({
  profile,
  isSelected,
  isRowSelected,
  onSelect,
  onSelectProfile,
  onDuplicate,
  isLoading,
  onManageTools
}: AgentTableRowProps) {

  return (
    <tr
      className={`hover:bg-base-200 transition-colors ${
        isRowSelected ? 'bg-primary/10' : ''
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

      {/* Agent Info */}
      <td>
        <button
          onClick={onSelectProfile}
          className="flex items-center gap-3 text-left hover:bg-base-200 p-2 rounded -ml-2 w-full min-w-0"
        >
          {/* Thumbnail */}
          <div className="flex-shrink-0">
            {profile.image_url ? (
              <img
                src={profile.image_url}
                alt={profile.name}
                className="w-10 h-10 rounded object-cover"
              />
            ) : (
              <div className="w-10 h-10 rounded bg-base-300 flex items-center justify-center text-lg">
                👤
              </div>
            )}
          </div>

          {/* Name. The description is a hover tooltip, not a line of text: this
              panel is for picking an agent, and rendering the description
              inline forced the row wide enough to push Actions behind a
              scrollbar. DaisyUI tooltip + data-tip, the same pattern the
              buttons use.

              Three things this bubble needs, each for a measured reason:
              - It sits on this WRAPPER, not on the truncating child, because
                `truncate` is overflow:hidden and would clip the bubble.
              - before:max-w-[20rem] wraps it. Unconstrained, DaisyUI lays a
                long tip on one line wider than the panel. An arbitrary value
                is used rather than a named token: `xs` is a 4px SPACING token
                in this project (tokens.css), so `max-w-xs` is a 4px box.
              - z-50 clears the table's own header, which is `sticky top-0 z-10`
                with an opaque background. Without it the header paints over
                the tooltip's first line and a two-line tip reads as its tail. */}
          <div
            className={`flex-1 min-w-0 ${
              profile.description
                ? 'tooltip tooltip-top z-50 before:max-w-[20rem] before:whitespace-pre-line'
                : ''
            }`}
            data-tip={profile.description || undefined}
          >
            <div className="font-medium text-sm truncate">{profile.name}</div>
          </div>
        </button>
      </td>

      {/* Status */}
      <td>
        <div className="badge badge-success badge-outline badge-sm">
          Active
        </div>
      </td>

      {/* Actions */}
      <td>
        <AgentTableActions
            profile={profile}
            onDuplicate={onDuplicate}
            isLoading={isLoading}
            onManageTools={onManageTools}
          />
      </td>
    </tr>
  )
}
