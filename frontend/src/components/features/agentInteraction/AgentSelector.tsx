import { useState, useRef, useEffect } from 'react'
import { Check, X } from 'lucide-react'
import type { Agent, AgentSelectorProps } from '@/types/agentInteraction'

import { getShortAgentName, formatAgentNameForContext } from '@/utils/agentNameUtils'
import { AvatarWithFallback } from './AvatarWithFallback'

export default function AgentSelector({
  agents,
  selectedAgent,
  onAgentSelect,
  loading = false
}: AgentSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside or Escape key
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen])

  const handleAgentSelect = (agent: Agent) => {
    onAgentSelect(agent)
    setIsOpen(false)
  }

  const toggleDropdown = () => {
    setIsOpen(!isOpen)
  }

  // The availability badge, WITH ITS TIP (2026-09-17, the user's ask: "the green
  // checkmark needs a tooltip so user know what it means").
  //
  // `isAvailable` is the backend's `Agent.is_active` — the agent's own Status flag, a
  // plain boolean (models.py, under "# Status"), mapped in useAgentSync.ts:100. It is
  // NOT a reachability probe, so the tip says "available" in the same word the
  // aria-label already uses: the whole point is that a sighted user learns what the
  // screen reader has been saying all along.
  //
  // `tooltip-bottom` matches the two tips already on this control in the page header
  // ("Select agent team", "Select an agent") and the house rule for page-top controls.
  // DaisyUI rather than PortalTooltip: the header's tips open DOWNWARD, well inside the
  // `h-dvh` root, so nothing clips them — PortalTooltip is for the side panel, whose
  // narrow scroll column does.
  const getStatusBadge = (agent: Agent) => {
    return agent.isAvailable ? (
      <div
        className="badge badge-success badge-xs tooltip tooltip-bottom"
        data-tip="This agent is available"
        aria-label="Available"
      >
        <Check className="h-3 w-3" />
      </div>
    ) : (
      <div
        className="badge badge-error badge-xs tooltip tooltip-bottom"
        data-tip="This agent is unavailable"
        aria-label="Unavailable"
      >
        <X className="h-3 w-3" />
      </div>
    )
  }

  // THE HEALTH BADGE AND ITS DISMISS WERE REMOVED HERE (2026-09-17, the user's ask).
  //
  // The selector carried a failures badge (warn = recent failures, fail = degraded)
  // and a dismiss button for it. That is the SAME data the AGENT PROFILES surface
  // shows — AgentHealthCell says so in its own words, "same data the AgentSelector
  // badge shows" — so this was a second place to read one thing, and a second place
  // to dismiss it. The profiles surface is the one that stays.
  //
  // `Agent.health` and the `AgentHealth` type DELIBERATELY STAY. ProfileService maps
  // them into the profile payload, so they are what FILLS the profiles' display:
  // removing them as "now unused" would break the surface this was removed in favour
  // of.

  const getAgentInitials = (name: string) => {
    // Get first letter of first two words
    const words = name.split(/\s+/)
    if (words.length >= 2) {
      return (words[0][0] + words[1][0]).toUpperCase()
    }
    return name.slice(0, 2).toUpperCase()
  }

  // THE LAST-GOOD AVATAR (2026-09-08, the 'shows up then goes
  // away' flap): agent refreshes drop profileImageUrl transiently
  // (the store-churn family), and the avatar flipped between the
  // image and the initials on every blip. Per-agent last-good: an
  // image, once seen, stays until a DIFFERENT url replaces it —
  // the initials only appear when the agent has genuinely never
  // had an image (or its url is removed for good).
  const lastGoodAvatarsRef = useRef<Record<string, string>>({})

  const renderAgentAvatar = (agent: Agent, size: 'sm' | 'md' = 'sm') => {
    const sizeClass = size === 'sm' ? 'w-6 h-6 text-xs' : 'w-8 h-8 text-sm'

    if (agent.profileImageUrl) {
      lastGoodAvatarsRef.current[agent.id] = agent.profileImageUrl
    }
    const imgUrl = agent.profileImageUrl || lastGoodAvatarsRef.current[agent.id] || ''

    if (!imgUrl) {
      // Fallback: show initials in a colored circle
      return (
        <div
          className={`${sizeClass} rounded-full bg-primary/20 text-primary flex items-center justify-center font-semibold`}
        >
          {getAgentInitials(agent.name)}
        </div>
      )
    }

    // Show image with fallback
    return (
      <AvatarWithFallback
        src={imgUrl}
        alt={agent.name}
        initials={getAgentInitials(agent.name)}
        size={sizeClass}
      />
    )
  }

  // THE PROVIDER BADGE'S TIP (2026-09-17, the user's ask): which provider this agent
  // runs on and which model it is configured with — the two facts the badge alone
  // refuses to tell you, because it shows only the provider's name.
  //
  // DaisyUI `tooltip` ON the badge, matching the availability badge directly below it
  // in the same header row. The header is the one place that positioning is safe, and
  // that is measured rather than assumed: those tips open downward inside the `h-dvh`
  // roots and escape none of the clipping ancestors. The side panel is the opposite
  // case, which is why the bulk-delete bar's long tips use PortalTooltip.
  const getProviderTip = (agent: Agent) =>
    agent.model
      ? `Provider: ${agent.provider} · Model: ${agent.model}`
      : `Provider: ${agent.provider}`

  return (
    <div className="relative w-64" ref={dropdownRef}>
      <button
        type="button"
        onClick={toggleDropdown}
        className="btn btn-outline w-full justify-start text-left"
      >
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {selectedAgent ? (
            <>
              <div className="flex items-center gap-2 flex-1 min-w-0">
                {renderAgentAvatar(selectedAgent, 'md')}
                <span className="truncate">
                  {formatAgentNameForContext(selectedAgent.name, 'header')}
                </span>
                <span
                  className="badge badge-sm badge-primary badge-outline flex-shrink-0 tooltip tooltip-bottom"
                  data-tip={getProviderTip(selectedAgent)}
                >
                  {selectedAgent.provider}
                </span>
                {getStatusBadge(selectedAgent)}
              </div>
            </>
          ) : (
            <span className="text-readout">Select an agent...</span>
          )}
        </div>
        <svg className={`w-4 h-4 transition-transform duration-200 flex-shrink-0 ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <ul className="absolute z-50 menu p-0 shadow-lg bg-base-100 rounded-box w-full max-h-96 overflow-y-auto overflow-x-hidden border border-base-300 top-full left-0 mt-1">
        {/* Loading State */}
        {loading && (
          <li className="p-4 text-center">
            <div className="loading loading-spinner loading-sm"></div>
            <p className="mt-2 text-xs text-readout">Loading agents...</p>
          </li>
        )}

        {/* Agents List - Single Column Vertical Scroll */}
        {!loading && (
          <div className="flex flex-col">
            {agents.map((agent) => (
                <div
                  key={agent.id}
                  className={`cursor-pointer transition-colors px-2 py-1.5 ${
                    selectedAgent?.id === agent.id
                      ? 'bg-primary/10'
                      : 'hover:bg-base-200'
                  }`}
                  onClick={() => handleAgentSelect(agent)}
                >
                  <div className="flex items-center gap-2">
                    <div className="flex-shrink-0">
                      {renderAgentAvatar(agent, 'sm')}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium text-sm truncate block max-w-[140px]">
                          {getShortAgentName(agent.name, 18)}
                        </span>
                        {getStatusBadge(agent)}
                      </div>
                      <p className="text-xs text-readout truncate block">
                        {agent.provider}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
        )}

        {/* Footer */}
        <li className="p-2 border-t border-base-300 bg-base-100 sticky bottom-0">
          <div className="flex justify-between items-center text-xs text-readout">
            <span className="truncate">{agents.length} agent{agents.length !== 1 ? 's' : ''}</span>
            <span className="badge badge-ghost badge-xs flex-shrink-0">Esc</span>
          </div>
        </li>
      </ul>
      )}
    </div>
  )
}