/**
 * Delete Confirmation Modal
 *
 * Modal dialog for confirming collection deletion.
 */

import React from 'react'
import type { Collection } from '@/types/collections'

interface DeleteConfirmationModalProps {
  collection: Collection
  onClose: () => void
  onConfirm: (id: string) => void
}

export const DeleteConfirmationModal: React.FC<DeleteConfirmationModalProps> = ({
  collection,
  onClose,
  onConfirm,
}) => {
  const handleConfirm = () => {
    onConfirm(collection.id)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
      <div className="bg-base-200 rounded-lg shadow-xl w-[var(--dialog-width-sm)] max-w-[var(--dialog-width-full)] mx-4">
        {/* Header */}
        <div className="p-6 border-b border-base-300">
          <div className="flex items-center gap-4">
            <div className="flex-shrink-0 w-12 h-12 rounded-full bg-error/20 flex items-center justify-center">
              <svg className="w-6 h-6 text-error" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div>
              <h3 className="text-xl font-bold text-base-content">Delete Collection?</h3>
              <p className="text-sm text-readout mt-1">
                This action cannot be undone
              </p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          <p className="text-base-content">
            Are you sure you want to delete <span className="font-semibold">"{collection.name}"</span>?
          </p>
          <p className="text-sm text-readout mt-2">
            This will permanently remove the collection and all {collection.item_count} item{collection.item_count !== 1 ? 's' : ''}.
          </p>
        </div>

        {/* Actions */}
        <div className="flex gap-3 p-6 border-t border-base-300">
          <button
            type="button"
            onClick={onClose}
            className="btn btn-neutral btn-ghost flex-1"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            className="btn btn-error flex-1"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  )
}
