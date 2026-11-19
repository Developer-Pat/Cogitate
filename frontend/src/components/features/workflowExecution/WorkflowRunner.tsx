import { useState, useEffect } from 'react';
import { useWorkflowExecution } from '@/hooks/useWorkflowExecution';
import { useWorkflowProgress } from '@/hooks/useSSE';
import { frontendLoggingService } from '@/services/frontendLoggingService';
import type { WorkflowExecution, WorkflowTemplate } from '@/types/workflows';
import ExecutionControls from './ExecutionControls';
import ProgressTracker from './ProgressTracker';
import ResultViewer from './ResultViewer';
import RunFailurePanel from './RunFailurePanel';

interface WorkflowRunnerProps {
  template: WorkflowTemplate;
  onExecutionComplete?: (execution: WorkflowExecution) => void;
  onExecutionError?: (error: string) => void;
  className?: string;
}

export default function WorkflowRunner({
  template,
  onExecutionComplete,
  onExecutionError,
  className = ''
}: WorkflowRunnerProps) {
  const {
    executeWorkflow,
    cancelExecution,
    selectedExecution,
    loading,
    error,
    setSSEDisconnect,
    disconnectSSE: _disconnectSSE
  } = useWorkflowExecution();

  const [executionInputs, setExecutionInputs] = useState<Record<string, unknown>>({});
  const [isExecuting, setIsExecuting] = useState(false);

  // Use SSE for real-time progress updates (only when we have a valid workflow ID)
  const { data: progressData, status: progressStatus, disconnect: disconnectProgress } = useWorkflowProgress(
    selectedExecution?.id || '',
    (event) => {
      // Handle real-time progress updates
      frontendLoggingService.debug('WorkflowRunner', 'Workflow progress update', event as unknown as Record<string, unknown>);
    },
    !!selectedExecution?.id  // Only enable when we have a valid execution ID
  );

  // Register the SSE disconnect function with the execution hook
  useEffect(() => {
    if (disconnectProgress) {
      setSSEDisconnect(disconnectProgress);
    }
  }, [disconnectProgress, setSSEDisconnect]);

  // Initialize inputs based on template
  //
  // THE TWO SHAPES (2026-08-24, the live-test catch): most
  // templates carry inputs as an ARRAY of {name, type, defaultValue}
  // — but the monitoring family (readiness-check, market-watch,
  // rss-monitor, system-audit) delivers inputs as an OBJECT (a
  // keyed config: {symbol: {type, default}, ...}). The old code
  // called template.inputs?.forEach unconditionally -> TypeError
  // ('template.inputs?.forEach is not a function') crashed the
  // whole runner. Normalize both shapes before initializing.
  useEffect(() => {
    const initialInputs: Record<string, unknown> = {};
    const inputs = template.inputs ?? [];
    if (Array.isArray(inputs)) {
      inputs.forEach((input: { name?: string; defaultValue?: unknown }) => {
        if (input?.name && input.defaultValue !== undefined) {
          initialInputs[input.name] = input.defaultValue;
        }
      });
    } else if (typeof inputs === 'object') {
      // the keyed-config shape: {key: {type, default, ...}}
      Object.entries(inputs).forEach(([name, conf]) => {
        const c = (conf ?? {}) as { default?: unknown; defaultValue?: unknown };
        const dv = c.defaultValue !== undefined ? c.defaultValue : c.default;
        if (dv !== undefined) initialInputs[name] = dv;
      });
    }
    setExecutionInputs(initialInputs);
  }, [template]);

  const handleStartExecution = async () => {
    setIsExecuting(true);
    try {
      // Detect workflow type from template
      const workflowType = (template as unknown as Record<string, unknown>).workflowType === 'multi_agent' ? 'multi_agent' : 'simple';
      
      frontendLoggingService.info('WorkflowRunner', `Starting ${workflowType} workflow execution`, {
        templateId: template.id,
        templateName: template.name,
        workflowType
      });

      await executeWorkflow(template.id, executionInputs, workflowType);
    } catch (err) {
      // Log the error
      frontendLoggingService.error('WorkflowRunner', 'Failed to start workflow execution', err as Error, {
        templateId: template.id,
        templateName: template.name
      });

      onExecutionError?.(err instanceof Error ? err.message : 'Failed to start execution');
    } finally {
      setIsExecuting(false);
    }
  };

  const handlePauseExecution = () => {
    // TODO: Implement pause functionality
    frontendLoggingService.warning('WorkflowRunner', 'Pause execution not yet implemented');
  };

  const handleStopExecution = async () => {
    if (selectedExecution) {
      frontendLoggingService.warning('WorkflowRunner', '⏹️ User requested workflow termination', {
        executionId: selectedExecution.id,
        templateId: template.id,
        templateName: template.name,
        status: selectedExecution.status
      });
      await cancelExecution(selectedExecution.id);
    } else {
      frontendLoggingService.warning('WorkflowRunner', 'Stop requested but no active execution found');
    }
  };

  const handleResumeExecution = () => {
    // TODO: Implement resume functionality
    frontendLoggingService.warning('WorkflowRunner', 'Resume execution not yet implemented');
  };

  const handleInputChange = (inputName: string, value: unknown) => {
    setExecutionInputs(prev => ({
      ...prev,
      [inputName]: value
    }));
  };

  // Monitor execution completion
  useEffect(() => {
    if (selectedExecution && ['completed', 'failed', 'cancelled'].includes(selectedExecution.status)) {
      if (selectedExecution.status === 'completed') {
        frontendLoggingService.info('WorkflowRunner', '🎉 Workflow completed successfully', {
          workflowId: selectedExecution.id,
          templateId: selectedExecution.templateId,
          executionTime: selectedExecution.executionTime
        });
        onExecutionComplete?.(selectedExecution);
      } else if (selectedExecution.status === 'failed') {
        // Log the failure
        frontendLoggingService.error('WorkflowRunner', '💥 Workflow execution failed', {
          workflowId: selectedExecution.id,
          templateId: selectedExecution.templateId,
          error: selectedExecution.error || 'Unknown error'
        });

        onExecutionError?.(selectedExecution.error || 'Execution failed');
      } else if (selectedExecution.status === 'cancelled') {
        // Already logged in cancelExecution, but add context here
        frontendLoggingService.warning('WorkflowRunner', '⏹️ Workflow execution terminated', {
          workflowId: selectedExecution.id,
          templateId: selectedExecution.templateId
        });
      }
    }
  }, [selectedExecution, onExecutionComplete, onExecutionError]);

  return (
    <div className={`workflow-runner ${className}`}>
      {/* Workflow Configuration */}
      <div className="card bg-base-200 shadow-xl mb-6 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
        <div className="card-body gap-[var(--card-gap)]">
          <h2 className="card-title">Workflow Configuration</h2>
          <div className="space-y-4">
            <div>
              <h3 className="font-semibold mb-2">Template: {template.name}</h3>
              <p className="text-sm opacity-70">{template.description}</p>
            </div>

            {/* Input Fields */}
            {template.inputs?.length > 0 && (
              <div>
                <h4 className="font-semibold mb-3">Input Parameters</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {template.inputs.map(input => (
                    <div key={input.name} className="form-control">
                      <label className="label">
                        <span className="label-text">
                          {input.name}
                          {input.required && <span className="text-error ml-1">*</span>}
                        </span>
                      </label>
                      <input
                        type="text"
                        placeholder={input.description}
                        value={(executionInputs[input.name] as string) || ''}
                        onChange={(e) => handleInputChange(input.name, e.target.value)}
                        className="input input-bordered rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-input-bg)] border-[var(--form-input-border)] text-[var(--form-input-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                        disabled={isExecuting || loading}
                      />
                      {input.validation && (
                        <div className="text-xs opacity-70 mt-1">
                          {input.validation.min && `Min: ${input.validation.min} `}
                          {input.validation.max && `Max: ${input.validation.max} `}
                          {input.validation.enum && `Options: ${input.validation.enum.join(', ')}`}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Execution Controls */}
      <ExecutionControls
        execution={selectedExecution}
        isExecuting={isExecuting || loading}
        onStart={handleStartExecution}
        onPause={handlePauseExecution}
        onStop={handleStopExecution}
        onResume={handleResumeExecution}
        className="mb-6"
      />

      {/* Run-level failure — the ONE wording naming the service, or the raw error (Stage 3) */}
      {selectedExecution && (
        <RunFailurePanel execution={selectedExecution} className="mb-6" />
      )}

      {/* Progress Tracking */}
      {selectedExecution && (
        <ProgressTracker
          execution={selectedExecution}
          progressData={progressData}
          progressStatus={progressStatus}
          className="mb-6"
        />
      )}

      {/* Results */}
      {selectedExecution && (
        <ResultViewer
          execution={selectedExecution}
          className="mb-6"
        />
      )}

      {/* Error Display */}
      {error && (
        <div className="alert alert-error mb-6">
          <div>
            <span>{error}</span>
          </div>
        </div>
      )}
    </div>
  );
}