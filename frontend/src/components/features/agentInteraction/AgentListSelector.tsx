/**
 * AgentListSelector Component
 *
 * Allows users to select an agent list from available teams.
 * Auto-selects the default team on load.
 */

import { useState, useRef, useEffect } from 'react'
import { collectionsService } from '@/services/domain/CollectionsService'
import type { Collection } from '@/types/collections'
import { useNotificationStore } from '@/stores/notificationStore'

interface AgentListSelectorProps {
  selectedListId: string | null
  onSelectList: (listId: string) => void
  userKey?: string
}

export default function AgentListSelector({
  selectedListId,
  onSelectList,
  userKey: _userKey = 'default'
}: AgentListSelectorProps) {
  const [teams, setTeams] = useState<Collection[]>([])
  const [loading, setLoading] = useState(true)
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Load teams on mount
  useEffect(() => {
    loadTeams()
  }, [])

  // Auto-select default team when teams are loaded
  useEffect(() => {
    if (!loading && teams.length > 0 && !selectedListId) {
      // Try to find a team named "Default" first
      const defaultTeam = teams.find(c => c.name.toLowerCase() === 'default')
      if (defaultTeam) {
        onSelectList(defaultTeam.id)
      } else if (teams[0]) {
        onSelectList(teams[0].id)
      }
    }
  }, [teams, loading, selectedListId, onSelectList])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [])

  const loadTeams = async () => {
    try {
      setLoading(true)
      // Load collections that are for agents (teams)
      const result = await collectionsService.listCollections({ entity_type: 'agent' })
      setTeams(result.collections)
    } catch (error) {
      console.error('Failed to load teams:', error)
      useNotificationStore.getState().addError(
        'Failed to Load',
        'Could not load teams'
      )
      setTeams([])
    } finally {
      setLoading(false)
    }
  }

  const handleSelectList = (listId: string) => {
    onSelectList(listId)
    setIsOpen(false)
  }

  const toggleDropdown = () => {
    setIsOpen(!isOpen)
  }

  const getSelectedCollection = () => {
    return teams.find(c => c.id === selectedListId)
  }

  const selectedCollection = getSelectedCollection()

  return (
    <div className="relative w-56" ref={dropdownRef}>
      <button
        type="button"
        onClick={toggleDropdown}
        disabled={loading}
        className="btn btn-outline w-full justify-start text-left"
      >
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {selectedCollection ? (
            <>
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <span className="text-lg">{selectedCollection.icon}</span>
                <span className="truncate font-medium">
                  {selectedCollection.name}
                </span>
                <span className="badge badge-ghost badge-xs flex-shrink-0">
                  {selectedCollection.item_count} agents
                </span>
              </div>
            </>
          ) : (
            <span className="text-readout">
              {loading ? 'Loading...' : 'All Agents'}
            </span>
          )}
        </div>
        <svg
          className={`w-4 h-4 transition-transform duration-200 flex-shrink-0 ${
            isOpen ? 'rotate-180' : ''
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {isOpen && (
        <ul className="absolute z-50 menu p-0 shadow-lg bg-base-100 rounded-box w-full max-h-96 overflow-y-auto overflow-x-hidden border border-base-300 top-full left-0 mt-1">
          {/* Loading State */}
          {loading && (
            <li className="p-4 text-center">
              <div className="loading loading-spinner loading-sm"></div>
              <p className="mt-2 text-xs text-readout">Loading collections...</p>
            </li>
          )}

          {/* All Agents — the VIRTUAL all-agents option (2026-08-24,
              QW6): an agent outside any collection was hard to
              select (the selector pinned to a team). '' is the
              sentinel — the parent's filter treats it as no filter. */}
          {!loading && (
            <div
              className={`cursor-pointer transition-colors px-2 py-1.5 ${
                !selectedListId || selectedListId === ''
                  ? 'bg-primary/10'
                  : 'hover:bg-base-200'
              }`}
              onClick={() => handleSelectList('')}
            >
              <div className="flex items-center gap-2">
                <span className="text-lg flex-shrink-0">🌐</span>
                <div className="flex-1 min-w-0">
                  <span className="font-medium text-sm truncate block">
                    All Agents
                  </span>
                  <p className="text-xs text-readout truncate">
                    Every agent in the pool
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Teams */}
          {!loading && teams.length > 0 && (
            <div className="flex flex-col">
              {teams.map((collection) => (
                <div
                  key={collection.id}
                  className={`cursor-pointer transition-colors px-2 py-1.5 ${
                    selectedListId === collection.id
                      ? 'bg-primary/10'
                      : 'hover:bg-base-200'
                  }`}
                  onClick={() => handleSelectList(collection.id)}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-lg flex-shrink-0">{collection.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium text-sm truncate block">
                          {collection.name}
                        </span>
                      </div>
                      <p className="text-xs text-readout truncate">
                        {collection.item_count} agent{collection.item_count !== 1 ? 's' : ''}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Empty State */}
          {!loading && teams.length === 0 && (
            <li className="p-4 text-center">
              <p className="text-sm text-readout">No teams found</p>
            </li>
          )}

          {/* Footer */}
          <li className="p-2 border-t border-base-300 bg-base-100 sticky bottom-0">
            <div className="flex justify-between items-center text-xs text-readout">
              <span className="truncate">
                {teams.length} team{teams.length !== 1 ? 's' : ''}
              </span>
              <span className="badge badge-ghost badge-xs flex-shrink-0">Esc</span>
            </div>
          </li>
        </ul>
      )}
    </div>
  )
}
