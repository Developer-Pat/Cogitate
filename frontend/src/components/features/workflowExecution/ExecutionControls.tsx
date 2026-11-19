import { useState } from 'react';
import type { WorkflowExecution } from '@/types/workflows';

interface ExecutionControlsProps {
  execution?: WorkflowExecution | null;
  isExecuting: boolean;
  onStart: () => void;
  onPause: () => void;
  onStop: () => void;
  onResume: () => void;
  className?: string;
}

export default function ExecutionControls({
  execution,
  isExecuting,
  onStart,
  onPause,
  onStop,
  onResume,
  className = ''
}: ExecutionControlsProps) {
  const [isPaused, setIsPaused] = useState(false);
  const [stopRequested, setStopRequested] = useState(false);

  const handlePause = () => {
    setIsPaused(true);
    onPause();
  };

  const handleResume = () => {
    setIsPaused(false);
    onResume();
  };

  const handleStop = () => {
    setStopRequested(true);
    onStop();
  };

  const getExecutionStatus = () => {
    if (!execution) return 'idle';
    return execution.status;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'text-success';
      case 'paused':
        return 'text-warning';
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

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return '▶️';
      case 'paused':
        return '⏸️';
      case 'completed':
        return '✅';
      case 'failed':
        return '❌';
      case 'cancelled':
        return '⏹️';
      default:
        return '⏳';
    }
  };

  // Reset stopRequested when execution status changes to cancelled
  if (execution?.status === 'cancelled' && stopRequested) {
    setStopRequested(false);
  }

  const canStart = !execution || ['completed', 'failed', 'cancelled'].includes(execution.status);
  const canPause = execution?.status === 'running' && !isPaused;
  const canResume = execution?.status === 'running' && isPaused;
  const canStop = execution && ['running', 'paused'].includes(execution.status) && !stopRequested;

  return (
    <div className={`execution-controls ${className}`}>
      <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
        <div className="card-body gap-[var(--card-gap)]">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            {/* Status Display */}
            <div className="flex items-center gap-3">
              <div className="text-2xl">
                {getStatusIcon(getExecutionStatus())}
              </div>
              <div>
                <h3 className="font-semibold">Execution Status</h3>
                <div className={`text-sm font-medium ${getStatusColor(getExecutionStatus())}`}>
                  {execution ? (
                    <>
                      {execution.status.charAt(0).toUpperCase() + execution.status.slice(1)}
                      {execution.startedAt && !isNaN(new Date(execution.startedAt).getTime()) && (
                        <span className="opacity-70 ml-2">
                          • Started: {new Date(execution.startedAt).toLocaleTimeString()}
                        </span>
                      )}
                    </>
                  ) : (
                    'Ready to start'
                  )}
                </div>
              </div>
            </div>

            {/* Control Buttons */}
            <div className="flex flex-wrap gap-2">
              {/* Start Button */}
              <button
                className={`btn btn-success ${!canStart ? 'btn-disabled' : ''}`}
                onClick={onStart}
                disabled={!canStart || isExecuting}
              >
                {isExecuting ? (
                  <>
                    <span className="loading loading-spinner loading-sm"></span>
                    Starting...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.828 14.828a4 4 0 01-5.656 0M9 10h1m4 0h1m-6 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Start
                  </>
                )}
              </button>

              {/* Pause Button */}
              <button
                className={`btn btn-warning ${!canPause ? 'btn-disabled' : ''}`}
                onClick={handlePause}
                disabled={!canPause}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Pause
              </button>

              {/* Resume Button */}
              <button
                className={`btn btn-info ${!canResume ? 'btn-disabled' : ''}`}
                onClick={handleResume}
                disabled={!canResume}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Resume
              </button>

              {/* Stop Button */}
              <button
                className={`btn btn-error ${!canStop ? 'btn-disabled' : ''}`}
                onClick={handleStop}
                disabled={!canStop || stopRequested}
              >
                {stopRequested ? (
                  <>
                    <span className="loading loading-spinner loading-sm"></span>
                    Stopping...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
                    </svg>
                    Stop
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Execution Details */}
          {execution && (
            <div className="mt-4 pt-4 border-t border-base-300">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="font-medium">Execution ID:</span>
                  <div className="font-mono text-xs opacity-70 truncate">
                    {execution.id}
                  </div>
                </div>
                <div>
                  <span className="font-medium">Template:</span>
                  <div className="opacity-70 truncate">
                    {execution.templateId}
                  </div>
                </div>
                <div>
                  <span className="font-medium">Duration:</span>
                  <div className="opacity-70">
                    {execution.executionTime ? `${execution.executionTime}s` : 'N/A'}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}