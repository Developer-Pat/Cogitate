/**
 * WorkflowPreview Component
 * 
 * Component for previewing workflow template details and structure
 */

import React from 'react';
import type { WorkflowPreviewProps } from '@/types/workflows';

/**
 * WorkflowPreview Component
 */
const WorkflowPreview: React.FC<WorkflowPreviewProps> = ({
  template,
  onClose,
  onExecute,
  onEdit,
  className: _className = ''
}) => {
  /**
   * Handle execute button click
   */
  const handleExecuteClick = () => {
    onExecute(template.id);
  };

  /**
   * Handle edit button click
   */
  const handleEditClick = () => {
    onEdit(template);
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
   * Get step type badge color
   */
  const getStepTypeColor = (type: string) => {
    switch (type) {
      case 'agent':
        return 'bg-primary/10 text-primary';
      case 'condition':
        return 'bg-purple-100 text-purple-800';
      case 'loop':
        return 'bg-orange-100 text-orange-800';
      case 'input':
        return 'bg-success/10 text-success';
      case 'output':
        return 'bg-error/10 text-error';
      case 'transform':
        return 'bg-indigo-100 text-indigo-800';
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
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
        {/* Background overlay */}
        <div
          className="fixed inset-0 transition-opacity bg-black bg-opacity-50"
          onClick={onClose}
          aria-hidden="true"
        ></div>

        {/* Modal panel */}
        <div className="inline-block align-bottom bg-base-100 rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-4xl sm:w-full">
          {/* Header */}
          <div className="px-6 py-4 border-b border-base-content/20">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-base-content">{template.name}</h2>
                <p className="text-sm text-readout mt-1">{template.description}</p>
              </div>
              <button
                onClick={onClose}
                className="text-base-content/50 hover:text-base-content/60 transition-colors"
                aria-label="Close"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

      {/* Content */}
      <div className="p-6 space-y-6 max-h-96 overflow-y-auto">
        {/* Template Information */}
        <div>
          <h3 className="text-lg font-medium text-base-content mb-4">Template Information</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-readout">Category:</span>
              <span className="ml-2 font-medium text-base-content">{template.category}</span>
            </div>
            <div>
              <span className="text-readout">Version:</span>
              <span className="ml-2 font-medium text-base-content">{template.version}</span>
            </div>
            <div>
              <span className="text-readout">Author:</span>
              <span className="ml-2 font-medium text-base-content">{template.author}</span>
            </div>
            <div>
              <span className="text-readout">Status:</span>
              <span className={`ml-2 inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(template.isPublic)}`}>
                {template.isPublic ? 'Public' : 'Private'}
              </span>
            </div>
            <div>
              <span className="text-readout">Complexity:</span>
              <span className={`ml-2 inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getComplexityColor(template.metadata?.complexity || 'simple')}`}>
                {template.metadata?.complexity || 'simple'}
              </span>
            </div>
            <div>
              <span className="text-readout">Steps:</span>
              <span className="ml-2 font-medium text-base-content">{template.steps?.length || 0}</span>
            </div>
          </div>
        </div>

        {/* Tags */}
        {template.tags?.length > 0 && (
          <div>
            <h3 className="text-lg font-medium text-base-content mb-3">Tags</h3>
            <div className="flex flex-wrap gap-2">
              {template.tags.map((tag, index) => (
                <span
                  key={index}
                  className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-base-200 text-readout"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Steps */}
        <div>
          <h3 className="text-lg font-medium text-base-content mb-4">Workflow Steps</h3>
          <div className="space-y-3">
            {template.steps?.map((step, index) => (
              <div
                key={step.id}
                className="border border-base-content/20 rounded-lg p-4 hover:bg-base-200 transition-colors"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center space-x-3">
                    <span className="flex-shrink-0 w-6 h-6 bg-primary text-base-content rounded-full flex items-center justify-center text-xs font-medium">
                      {index + 1}
                    </span>
                    <h4 className="text-sm font-medium text-base-content">{step.name}</h4>
                  </div>
                  <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStepTypeColor(step.type)}`}>
                    {step.type}
                  </span>
                </div>
                

                {step.agentId && (
                  <div className="text-xs text-readout">
                    Agent: <span className="font-medium">{step.agentId}</span>
                  </div>
                )}

                {step.nextSteps && step.nextSteps.length > 0 && (
                  <div className="text-xs text-readout mt-2">
                    Next: {step.nextSteps.join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Inputs */}
        {template.inputs?.length > 0 && (
          <div>
            <h3 className="text-lg font-medium text-base-content mb-3">Inputs</h3>
            <div className="space-y-2">
              {template.inputs.map((input, index) => (
                <div key={index} className="flex items-center justify-between text-sm">
                  <div>
                    <span className="font-medium text-base-content">{input.name}</span>
                    <span className="text-readout ml-2">({input.type})</span>
                    {input.required && (
                      <span className="ml-2 text-error">*</span>
                    )}
                  </div>
                  {input.defaultValue !== undefined && (
                    <span className="text-readout">Default: {String(input.defaultValue)}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Outputs */}
        {template.outputs?.length > 0 && (
          <div>
            <h3 className="text-lg font-medium text-base-content mb-3">Outputs</h3>
            <div className="space-y-2">
              {template.outputs.map((output, index) => (
                <div key={index} className="flex items-center justify-between text-sm">
                  <div>
                    <span className="font-medium text-base-content">{output.name}</span>
                    <span className="text-readout ml-2">({output.type})</span>
                  </div>
                  <span className="text-readout">From: {output.sourceStep}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Metadata */}
        <div>
          <h3 className="text-lg font-medium text-base-content mb-3">Additional Information</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-readout">Estimated Duration:</span>
              <span className="ml-2 font-medium text-base-content">
                {template.metadata?.estimatedDuration ? (
                  template.metadata.estimatedDuration > 60
                    ? `${Math.round(template.metadata.estimatedDuration / 60)} minutes`
                    : `${template.metadata.estimatedDuration} seconds`
                ) : (
                  'Not specified'
                )}
              </span>
            </div>
            <div>
              <span className="text-readout">Required Capabilities:</span>
              <span className="ml-2 font-medium text-base-content">
                {template.metadata?.requiredCapabilities?.join(', ') || 'None'}
              </span>
            </div>
            <div>
              <span className="text-readout">Execution Count:</span>
              <span className="ml-2 font-medium text-base-content">{template.executionCount}</span>
            </div>
            <div>
              <span className="text-readout">Success Rate:</span>
              <span className="ml-2 font-medium text-base-content">{Math.round(template.successRate * 100)}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-base-content/20 bg-base-200 rounded-b-lg">
        <div className="flex justify-between items-center">
          <div className="text-sm text-readout">
            Created {new Date(template.createdAt).toLocaleDateString()} • 
            Updated {new Date(template.updatedAt).toLocaleDateString()}
          </div>
          <div className="flex space-x-3">
            <button
              onClick={handleEditClick}
              disabled={!template.isCustomizable}
              className="px-4 py-2 border border-base-content/20 rounded-md shadow-sm text-sm font-medium text-base-content/90 bg-base-100 hover:bg-base-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Edit Template
            </button>
            <button
              onClick={handleExecuteClick}
              className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-base-content bg-primary hover:bg-info focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
            >
              Execute Workflow
            </button>
          </div>
        </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkflowPreview;