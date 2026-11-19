/**
 * Create Collection Modal
 *
 * Modal dialog for creating a new collection.
 */

import React, { useState } from 'react'
import type { CollectionEntityType } from '@/types/collections'

interface CreateCollectionModalProps {
  onClose: () => void
  onCreate: (
    name: string,
    description: string,
    entityType: CollectionEntityType,
    color: string,
    icon: string
  ) => void
  /** When provided, locks the modal to this entity type and hides the type selector */
  entityType?: CollectionEntityType
}

const ENTITY_TYPE_OPTIONS: { value: CollectionEntityType; label: string; icon: string }[] = [
  { value: 'tool', label: 'Tools', icon: '🛠️' },
  { value: 'provider', label: 'Providers', icon: '⚡' },
  { value: 'macro_set', label: 'Macro Sets', icon: '📝' },
  { value: 'template', label: 'Templates', icon: '📋' },
]

const COLOR_OPTIONS = [
  { value: 'primary', label: 'Blue', class: 'bg-primary' },
  { value: 'secondary', label: 'Purple', class: 'bg-secondary' },
  { value: 'accent', label: 'Orange', class: 'bg-accent' },
  { value: 'info', label: 'Cyan', class: 'bg-info' },
  { value: 'success', label: 'Green', class: 'bg-success' },
  { value: 'warning', label: 'Yellow', class: 'bg-warning' },
  { value: 'error', label: 'Red', class: 'bg-error' },
]

const ICON_OPTIONS = [
  '📁', '⭐', '🔥', '💎', '🎯', '🚀', '💡', '📚', '🎨', '⚡', '🛠️', '🤖', '👁️',
]

export const CreateCollectionModal: React.FC<CreateCollectionModalProps> = ({
  onClose,
  onCreate,
  entityType: lockedEntityType,
}) => {
  const [entityType, setEntityType] = useState<CollectionEntityType>(lockedEntityType || 'tool')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [color, setColor] = useState('primary')
  const [selectedIcon, setSelectedIcon] = useState('📁')

  const isLocked = lockedEntityType !== undefined
  const isTeams = lockedEntityType === 'agent'

  const modalTitle = isTeams ? 'Create New Collective' : 'Create New Collection'
  const modalSubtitle = isTeams
    ? 'Group agents together by a common attribute'
    : 'Choose what type of items this collection will contain'
  const submitLabel = isTeams ? 'Create Collective' : 'Create Collection'
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    onCreate(name.trim(), description.trim(), entityType, color, selectedIcon)
  }
  
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
      <div className="bg-base-200 rounded-lg shadow-xl w-[var(--dialog-width-lg)] max-w-[var(--dialog-width-full)] mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-base-300">
          <div>
            <h2 className="text-2xl font-bold text-base-content">{modalTitle}</h2>
            <p className="text-sm text-readout mt-1">{modalSubtitle}</p>
          </div>
          <button
            onClick={onClose}
            className="text-base-content/50 hover:text-base-content/70"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Entity Type - hidden when locked to a specific type */}
          {!isLocked && (
            <div>
              <label className="block text-sm font-medium text-base-content mb-2">
                Collection Type
              </label>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                {ENTITY_TYPE_OPTIONS.map(option => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setEntityType(option.value)}
                    className={`
                      btn ${entityType === option.value ? 'btn-active btn-selected' : 'btn-outline'} justify-start gap-2 h-auto py-3
                    `}
                  >
                    <span className="text-2xl">{option.icon}</span>
                    <span className="text-sm">{option.label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Name and Description */}
          <div className="grid grid-cols-1 gap-4">
            {/* Name */}
            <div>
              <label className="block text-sm font-medium text-base-content mb-2">
                Name <span className="text-error">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Math Teaching Tools"
                className="input input-bordered w-full"
                autoFocus
                required
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-base-content mb-2">
                Description
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description..."
                className="input input-bordered w-full"
              />
            </div>
          </div>

          {/* Color */}
          <div>
            <label className="block text-sm font-medium text-base-content mb-2">
              Color
            </label>
            <div className="flex gap-2 flex-wrap">
              {COLOR_OPTIONS.map(option => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setColor(option.value)}
                  className={`
                    w-10 h-10 rounded-full ${option.class}
                    ${color === option.value ? 'ring-2 ring-offset-2 ring-base-content/50' : ''}
                  `}
                  title={option.label}
                />
              ))}
            </div>
          </div>

          {/* Icon */}
          <div>
            <label className="block text-sm font-medium text-base-content mb-2">
              Icon
            </label>
            <div className="flex gap-2 flex-wrap">
              {ICON_OPTIONS.map(icon => (
                <button
                  key={icon}
                  type="button"
                  onClick={() => setSelectedIcon(icon)}
                  className={`
                    w-10 h-10 flex items-center justify-center text-xl border rounded
                    ${selectedIcon === icon
                      ? 'border-primary bg-primary/5'
                      : 'border-base-300 hover:border-base-content/40'
                    }
                  `}
                >
                  {icon}
                </button>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4 border-t border-base-300">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-neutral btn-ghost"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim()}
              className="btn btn-primary"
            >
              {submitLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
