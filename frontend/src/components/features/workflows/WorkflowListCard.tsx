/**
 * WorkflowListCard Component
 *
 * Component for displaying workflow list information in a card format
 */

import React from 'react';
import type { WorkflowList } from '@/types/workflows';

interface WorkflowListCardProps {
  list: WorkflowList;
  onSelect: (list: WorkflowList) => void;
  onEdit: (list: WorkflowList) => void;
  onDelete: (list: WorkflowList) => void;
  isSelected?: boolean;
  className?: string;
}

/**
 * WorkflowListCard Component
 */
const WorkflowListCard: React.FC<WorkflowListCardProps> = ({
  list,
  onSelect,
  onEdit,
  onDelete,
  isSelected = false,
  className = ''
}) => {
  /**
   * Handle card click
   */
  const handleCardClick = () => {
    onSelect(list);
  };

  /**
   * Handle edit button click
   */
  const handleEditClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onEdit(list);
  };

  /**
   * Handle delete button click
   */
  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete(list);
  };

  return (
    <div
      className={`
        bg-base-100 rounded-lg border shadow-sm hover:shadow-md transition-shadow duration-200 cursor-pointer
        ${isSelected ? 'border-primary ring-2 ring-primary/30' : 'border-base-content/20'}
        ${className}
      `}
      onClick={handleCardClick}
    >
      {/* Header */}
      <div className="p-4 border-b border-base-content/20">
        <div className="flex items-start justify-between mb-2">
          <h3 className="text-lg font-semibold text-base-content truncate">
            {list.name}
          </h3>
          <div className="flex space-x-1 ml-2">
            {list.is_default && (
              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary">
                Default
              </span>
            )}
            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-base-200 text-base-content">
              {list.workflow_count} workflows
            </span>
          </div>
        </div>

        <p className="text-sm text-readout line-clamp-2">
          {list.description || 'No description'}
        </p>
      </div>

      {/* Content */}
      <div className="p-4">
        {/* Tags */}
        {list.tags && list.tags.length > 0 && (
          <div className="mb-4">
            <div className="flex flex-wrap gap-1">
              {list.tags.slice(0, 5).map((tag, index) => (
                <span
                  key={index}
                  className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-base-200 text-readout"
                >
                  {tag}
                </span>
              ))}
              {list.tags.length > 5 && (
                <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-base-200 text-readout">
                  +{list.tags.length - 5} more
                </span>
              )}
            </div>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 gap-2 text-center text-xs text-readout mb-4">
          <div>
            <div className="font-semibold text-base-content">{list.workflow_count}</div>
            <div>Workflows</div>
          </div>
          <div>
            <div className="font-semibold text-base-content">
              {new Date(list.updated_at).toLocaleDateString()}
            </div>
            <div>Updated</div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-between space-x-2">
          <button
            onClick={handleEditClick}
            className="flex-1 inline-flex justify-center items-center px-3 py-2 border border-base-content/20 text-sm font-medium rounded-md text-base-content/90 bg-base-100 hover:bg-base-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
          >
            Edit
          </button>

          <button
            onClick={handleDeleteClick}
            className="inline-flex justify-center items-center px-3 py-2 border border-base-content/20 text-sm font-medium rounded-md text-error bg-base-100 hover:bg-error hover:text-white focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-error"
          >
            Delete
          </button>
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-3 bg-base-200 border-t border-base-content/20 rounded-b-lg">
        <div className="flex justify-between items-center text-xs text-readout">
          <span>Updated {new Date(list.updated_at).toLocaleDateString()}</span>
          <span>Created {new Date(list.created_at).toLocaleDateString()}</span>
        </div>
      </div>
    </div>
  );
};

export default WorkflowListCard;
