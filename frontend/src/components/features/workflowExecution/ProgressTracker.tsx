import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { frontendLoggingService } from '@/services/frontendLoggingService';
import type { WorkflowExecution, StepExecution } from '@/types/workflows';
import type { SSEEvent } from '@/services/sseClient';
import { useRunEstimator } from '@/hooks/useRunEstimator';

interface ProgressTrackerProps {
  execution: WorkflowExecution;
  progressData?: SSEEvent | null;
  progressStatus: 'idle' | 'connecting' | 'connected' | 'error' | 'closed';
  className?: string;
}

export default function ProgressTracker({
  execution,
  progressData,
  progressStatus,
  className = ''
}: ProgressTrackerProps) {
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [progressLogs, setProgressLogs] = useState<string[]>([]);

  // THE RUN-TIME ESTIMATE (2026-08-24): the useRunEstimator hook
  // consumes the bus's batch:done events (done/total + the rate +
  // the remaining estimate). Only when the execution id exists.
  const estimate = useRunEstimator(execution.id);

  // Process SSE progress data (when available)
  useEffect(() => {
    if (progressData && progressData.data) {
      try {
        // Parse the SSE data which could be a string or already parsed object
        const data = typeof progressData.data === 'string'
          ? JSON.parse(progressData.data)
          : progressData.data;

        if (data.stepId) {
          setCurrentStep(data.stepId);
        }

        if (data.message) {
          setProgressLogs(prev => [...prev.slice(-99), data.message]);
        }
      } catch (error) {
        frontendLoggingService.error('ProgressTracker', 'Error parsing SSE progress data', error as Error);
      }
    }
  }, [progressData]);

  // Calculate overall progress based on execution status
  const calculateProgress = () => {
    // If we have step executions, calculate based on completed steps
    const totalSteps = execution.stepExecutions?.length || 0;
    if (totalSteps > 0) {
      const completedSteps = execution.stepExecutions?.filter(
        step => step.status === 'completed'
      ).length || 0;
      return Math.round((completedSteps / totalSteps) * 100);
    }

    // For single-step workflows, use execution status
    switch (execution.status) {
      case 'completed':
        return 100;
      case 'running':
        return 50; // Mid-point for running workflows
      case 'pending':
      case 'failed':
      case 'cancelled':
        return 0;
      default:
        return 0;
    }
  };

  const getStepStatusIcon = (step: StepExecution) => {
    switch (step.status) {
      case 'completed':
        return '✅';
      case 'running':
        return '🔄';
      case 'failed':
        return '❌';
      case 'skipped':
        return '⏭️';
      default:
        return '⏳';
    }
  };

  const getStepStatusColor = (step: StepExecution) => {
    switch (step.status) {
      case 'completed':
        return 'text-success';
      case 'running':
        return 'text-warning animate-pulse';
      case 'failed':
        return 'text-error';
      case 'skipped':
        return 'text-info';
      default:
        return 'text-base-content opacity-50';
    }
  };

  const getExecutionStatusColor = () => {
    switch (execution.status) {
      case 'running':
        return 'text-success';
      case 'completed':
        return 'text-info';
      case 'failed':
        return 'text-error';
      case 'cancelled':
        return 'text-error';
      default:
        return 'text-base-content';
    }
  };

  const overallProgress = calculateProgress();

  return (
    <div className={`progress-tracker ${className}`}>
      <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
        <div className="card-body gap-[var(--card-gap)]">
          <h2 className="card-title">Progress Tracking</h2>

          {/* Overall Progress Bar */}
          <div className="space-y-4">
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="font-medium">Overall Progress</span>
                <span className={`text-sm font-medium ${getExecutionStatusColor()}`}>
                  {execution.status.charAt(0).toUpperCase() + execution.status.slice(1)}
                  {overallProgress > 0 && ` • ${overallProgress}%`}
                </span>
              </div>
              <progress
                className="progress progress-primary w-full"
                value={overallProgress}
                max="100"
              ></progress>

              {/* THE RUN-TIME ESTIMATE (2026-08-24): '2/10 batches
                  • ~20s remaining' — the live estimate from the
                  bus's batch:done events */}
              {estimate && !estimate.finished && (
                <div className="flex items-center gap-2 text-sm mt-2">
                  <span className="font-medium">
                    {estimate.done}/{estimate.total} batches
                  </span>
                  <span className="opacity-50">•</span>
                  <span className="text-info">
                    {estimate.remainingSec >= 60
                      ? `~${Math.round(estimate.remainingSec / 60)}m ${Math.round(estimate.remainingSec % 60)}s remaining`
                      : `~${Math.max(1, Math.round(estimate.remainingSec))}s remaining`}
                  </span>
                </div>
              )}
              {estimate?.finished && (
                <div className="text-sm text-success mt-2">
                  Completed {estimate.total} batches in {Math.round(estimate.elapsedSec)}s
                </div>
              )}
            </div>

            {/* SSE Connection Status */}
            <div className="flex items-center gap-2 text-sm">
              <div className={`badge badge-sm ${
                progressStatus === 'connected' ? 'badge-success badge-outline' :
                progressStatus === 'connecting' ? 'badge-warning badge-outline' :
                progressStatus === 'error' ? 'badge-error badge-outline' : 'badge-muted badge-outline'
              }`}>
                {progressStatus === 'connected' ? 'Live' :
                 progressStatus === 'connecting' ? 'Connecting' :
                 progressStatus === 'error' ? 'Error' : 'Disconnected'}
              </div>
              <span className="opacity-70">
                Real-time updates {progressStatus === 'connected' ? 'active' : 'inactive'}
              </span>
            </div>

            {/* Step Progress - Only show if we have multiple steps */}
            {execution.stepExecutions?.length > 1 && (
              <div>
                <h4 className="font-semibold mb-3">Step Progress</h4>
                <div className="space-y-3">
                  {execution.stepExecutions.map((step, index) => (
                    <div
                      key={step.stepId}
                      className={`flex items-center gap-3 p-3 rounded-lg border ${
                        step.status === 'running' ? 'border-warning bg-warning/10' :
                        step.status === 'completed' ? 'border-success bg-success/10' :
                        step.status === 'failed' ? 'border-error bg-error/10' :
                        'border-base-300'
                      }`}
                    >
                      <div className="flex-shrink-0">
                        <span className="text-lg">
                          {getStepStatusIcon(step)}
                        </span>
                      </div>
                      <div className="flex-grow">
                        <div className="flex justify-between items-center">
                          <span className={`font-medium ${getStepStatusColor(step)}`}>
                            Step {index + 1}: {step.stepId}
                          </span>
                          <span className="text-xs opacity-70">
                            {step.executionTime ? `${step.executionTime}s` : ''}
                          </span>
                        </div>
                        {step.status === 'running' && currentStep === step.stepId && (
                          <div className="text-xs text-warning mt-1">
                            Currently executing...
                          </div>
                        )}
                        {step.error && (
                          <div className="text-xs text-error mt-1">
                            Error: {step.error}
                          </div>
                        )}
                        {(step.output as ReactNode) && (
                          <div className="text-xs opacity-70 mt-1 truncate">
                            Output: {typeof step.output === 'string' ? step.output : JSON.stringify(step.output)}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Progress Logs */}
            <div>
              <h4 className="font-semibold mb-3">Execution Logs</h4>
              <div className="bg-base-300 rounded-lg p-4 max-h-48 overflow-y-auto">
                {progressLogs.length > 0 ? (
                  <div className="space-y-2">
                    {progressLogs.map((log, index) => (
                      <div key={index} className="text-sm font-mono">
                        <span className="opacity-50">[{new Date().toLocaleTimeString()}]</span>
                        <span className="ml-2">{log}</span>
                      </div>
                    ))}
                  </div>
                ) : execution.executionResult ? (
                  <div className="space-y-2">
                    <div className="text-sm">
                      <span className="font-medium">Result:</span>
                      <span className="ml-2 font-mono">{(execution.executionResult.result as string) || 'N/A'}</span>
                    </div>
                    {(execution.executionResult.completed_at as ReactNode) && (
                      <div className="text-sm">
                        <span className="font-medium">Completed:</span>
                        <span className="ml-2 font-mono">{new Date(execution.executionResult.completed_at as string | number).toLocaleString()}</span>
                      </div>
                    )}
                    {(execution.executionResult.agent_name as ReactNode) && (
                      <div className="text-sm">
                        <span className="font-medium">Agent:</span>
                        <span className="ml-2 font-mono">{execution.executionResult.agent_name as ReactNode}</span>
                      </div>
                    )}
                  </div>
                ) : execution.logs?.length > 0 ? (
                  <div className="space-y-2">
                    {execution.logs.map((log, index) => (
                      <div key={index} className="text-sm font-mono">
                        <span className="opacity-50">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                        <span className="ml-2">{log.message}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center text-sm opacity-50 py-8">
                    {execution.status === 'running' 
                      ? 'Workflow executing... (SSE real-time updates not available)'
                      : 'No execution logs available'}
                  </div>
                )}
              </div>
            </div>

            {/* Execution Statistics - Only show for multi-step workflows */}
            {execution.stepExecutions?.length > 1 && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div className="text-center">
                  <div className="font-semibold">
                    {execution.stepExecutions?.filter(s => s.status === 'completed').length || 0}
                  </div>
                  <div className="opacity-70">Completed</div>
                </div>
                <div className="text-center">
                  <div className="font-semibold">
                    {execution.stepExecutions?.filter(s => s.status === 'running').length || 0}
                  </div>
                  <div className="opacity-70">Running</div>
                </div>
                <div className="text-center">
                  <div className="font-semibold">
                    {execution.stepExecutions?.filter(s => s.status === 'failed').length || 0}
                  </div>
                  <div className="opacity-70">Failed</div>
                </div>
                <div className="text-center">
                  <div className="font-semibold">
                    {execution.stepExecutions?.length || 0}
                  </div>
                  <div className="opacity-70">Total</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}