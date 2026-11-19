/**
 * WorkflowCard Component
 * 
 * Component for displaying workflow template information in a card format
 */

import React from 'react';
import type { WorkflowCardProps } from '@/types/workflows';

/**
 * WorkflowCard Component
 */
const WorkflowCard: React.FC<WorkflowCardProps> = ({
  template,
  onSelect,
  onExecute,
  onEdit,
  onExport,
  isSelected = false,
  className = ''
}) => {
  /**
   * Handle card click
   */
  const handleCardClick = () => {
    onSelect(template);
  };

  /**
   * Handle execute button click
   */
  const handleExecuteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onExecute(template.id);
  };

  /**
   * Handle edit button click
   */
  const handleEditClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onEdit(template);
  };

  /**
   * Handle export button click
   */
  const handleExportClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onExport(template);
  };

  /**
   * Get complexity badge color
   */
  const getComplexityColor = (complexity: string) => {
    switch (complexity) {
      case 'simple':
        return 'bg-success/10 text-success';
      case 'medium':
        return 'bg-warning/10 text-warning';
      case 'complex':
        return 'bg-error/10 text-error';
      default:
        return 'bg-base-200 text-base-content';
    }
  };

  /**
   * Get status badge color
   */
  const getStatusColor = (isPublic: boolean) => {
    return isPublic 
      ? 'bg-primary/10 text-primary'
      : 'bg-base-200 text-base-content';
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
            {template.name}
          </h3>
          <div className="flex space-x-1 ml-2">
            <span
              className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getComplexityColor(template.metadata?.complexity || 'simple')}`}
            >
              {template.metadata?.complexity || 'simple'}
            </span>
            <span
              className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(template.isPublic)}`}
            >
              {template.isPublic ? 'Public' : 'Private'}
            </span>
          </div>
        </div>
        
        <p className="text-sm text-readout line-clamp-2">
          {template.description}
        </p>
      </div>

      {/* Content */}
      <div className="p-4">
        {/* Metadata */}
        <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
          <div>
            <span className="text-readout">Category:</span>
            <span className="ml-1 font-medium text-base-content">{template.category}</span>
          </div>
          <div>
            <span className="text-readout">Version:</span>
            <span className="ml-1 font-medium text-base-content">{template.version}</span>
          </div>
          <div>
            <span className="text-readout">Steps:</span>
            <span className="ml-1 font-medium text-base-content">{template.steps?.length || 0}</span>
          </div>
          <div>
            <span className="text-readout">Author:</span>
            <span className="ml-1 font-medium text-base-content">{template.author}</span>
          </div>
        </div>

        {/* Tags */}
        {template.tags?.length > 0 && (
          <div className="mb-4">
            <div className="flex flex-wrap gap-1">
              {template.tags.slice(0, 3).map((tag, index) => (
                <span
                  key={index}
                  className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-base-200 text-readout"
                >
                  {tag}
                </span>
              ))}
              {template.tags && template.tags.length > 3 && (
                <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-base-200 text-readout">
                  +{template.tags.length - 3} more
                </span>
              )}
            </div>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-3 gap-2 text-center text-xs text-readout mb-4">
          <div>
            <div className="font-semibold text-base-content">{template.executionCount}</div>
            <div>Executions</div>
          </div>
          <div>
            <div className="font-semibold text-base-content">{Math.round(template.successRate * 100)}%</div>
            <div>Success</div>
          </div>
          <div>
            <div className="font-semibold text-base-content">
              {template.averageExecutionTime > 60 
                ? `${Math.round(template.averageExecutionTime / 60)}m` 
                : `${Math.round(template.averageExecutionTime)}s`
              }
            </div>
            <div>Avg. Time</div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-between space-x-2">
          <button
            onClick={handleExecuteClick}
            className="btn btn-primary btn-outline btn-sm flex-1"
          >
            Execute
          </button>
          
          <span className="tooltip tooltip-top" data-tip="Edit workflow steps — not yet implemented">
          <button
            onClick={handleEditClick}
            disabled
            className="btn btn-neutral btn-ghost btn-sm"
          >
            Edit
          </button>
          </span>
          
          <button
            onClick={handleExportClick}
            className="btn btn-outline btn-sm"
          >
            Export
          </button>
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-3 bg-base-200 border-t border-base-content/20 rounded-b-lg">
        <div className="flex justify-between items-center text-xs text-readout">
          <span>Updated {new Date(template.updatedAt).toLocaleDateString()}</span>
          <span>Created {new Date(template.createdAt).toLocaleDateString()}</span>
        </div>
      </div>
    </div>
  );
};

export default WorkflowCard;