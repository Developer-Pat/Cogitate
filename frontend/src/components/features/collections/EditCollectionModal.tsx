/**
 * Edit Collection Modal
 *
 * Modal dialog for editing an existing collection.
 */

import React, { useState, useEffect } from 'react'
import type { Collection, CollectionEntityType, CollectionUpdate } from '@/types/collections'

interface EditCollectionModalProps {
  collection: Collection
  onClose: () => void
  onSave: (id: string, updates: CollectionUpdate) => void
}

const ENTITY_TYPE_OPTIONS: { value: CollectionEntityType; label: string; icon: string }[] = [
  { value: 'agent', label: 'Agents', icon: '🤖' },
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

export const EditCollectionModal: React.FC<EditCollectionModalProps> = ({
  collection,
  onClose,
  onSave,
}) => {
  const [entityType, setEntityType] = useState<CollectionEntityType>(collection.entity_type)
  const [name, setName] = useState(collection.name)
  const [description, setDescription] = useState(collection.description || '')
  const [color, setColor] = useState(collection.color)
  const [selectedIcon, setSelectedIcon] = useState(collection.icon)

  // Reset form when collection changes
  useEffect(() => {
    setEntityType(collection.entity_type)
    setName(collection.name)
    setDescription(collection.description || '')
    setColor(collection.color)
    setSelectedIcon(collection.icon)
  }, [collection])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    onSave(collection.id, {
      name: name.trim(),
      description: description.trim(),
      color,
      icon: selectedIcon,
    })
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
      <div className="bg-base-200 rounded-lg shadow-xl w-[var(--dialog-width-lg)] max-w-[var(--dialog-width-full)] mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-base-300">
          <div>
            <h2 className="text-2xl font-bold text-base-content">Edit Collection</h2>
            <p className="text-sm text-readout mt-1">
              Update collection details
            </p>
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
          {/* Entity Type */}
          <div>
            <label className="block text-sm font-medium text-base-content mb-2">
              Collection Type
            </label>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
              {ENTITY_TYPE_OPTIONS.map(option => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setEntityType(option.value)}
                  className={`
                    btn ${entityType === option.value ? 'btn-active btn-selected' : 'btn-outline'} justify-start gap-2
                  `}
                >
                  <span className="text-xl">{option.icon}</span>
                  <span>{option.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Name and Description */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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

          {/* Collection Stats (read-only) */}
          <div className="divider"></div>
          <div className="grid grid-cols-2 gap-4">
            <div className="stats bg-base-100 shadow">
              <div className="stat p-3">
                <div className="stat-title text-xs">Items</div>
                <div className="stat-value text-2xl">{collection.item_count}</div>
              </div>
            </div>
            <div className="stats bg-base-100 shadow">
              <div className="stat p-3">
                <div className="stat-title text-xs">Created</div>
                <div className="stat-value text-xs">{new Date(collection.created_at).toLocaleDateString()}</div>
              </div>
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
              disabled={!name.trim() || (name === collection.name && description === (collection.description || '') && color === collection.color && selectedIcon === collection.icon)}
              className="btn btn-primary"
            >
              Save Changes
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
