import { useState } from 'react';
import type { ReactNode } from 'react';
import { frontendLoggingService } from '@/services/frontendLoggingService';
import type { WorkflowExecution } from '@/types/workflows';

interface ResultViewerProps {
  execution: WorkflowExecution;
  className?: string;
}

export default function ResultViewer({
  execution,
  className = ''
}: ResultViewerProps) {
  const [activeTab, setActiveTab] = useState<'outputs' | 'logs' | 'steps'>('outputs');
  const [expandedLogs, setExpandedLogs] = useState<Set<number>>(new Set());

  const toggleLogExpansion = (index: number) => {
    setExpandedLogs(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  const formatOutput = (output: unknown): string => {
    if (typeof output === 'string') {
      return output;
    }
    try {
      return JSON.stringify(output, null, 2);
    } catch {
      return String(output);
    }
  };

  const getLogLevelColor = (level: string) => {
    switch (level) {
      case 'error':
        return 'text-error';
      case 'warning':
        return 'text-warning';
      case 'info':
        return 'text-info';
      case 'debug':
        return 'text-base-content opacity-70';
      default:
        return 'text-base-content';
    }
  };

  const getLogLevelIcon = (level: string) => {
    switch (level) {
      case 'error':
        return '❌';
      case 'warning':
        return '⚠️';
      case 'info':
        return 'ℹ️';
      case 'debug':
        return '🐛';
      default:
        return '📝';
    }
  };

  const downloadResults = () => {
    const results = {
      executionId: execution.id,
      templateId: execution.templateId,
      status: execution.status,
      startedAt: execution.startedAt,
      completedAt: execution.completedAt,
      executionTime: execution.executionTime,
      outputs: execution.outputs,
      stepExecutions: execution.stepExecutions,
      logs: execution.logs
    };

    const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `workflow-execution-${execution.id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      // Could show a toast notification here
      frontendLoggingService.info('ResultViewer', 'Copied to clipboard');
    });
  };

  return (
    <div className={`result-viewer ${className}`}>
      <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
        <div className="card-body gap-[var(--card-gap)]">
          <div className="flex justify-between items-center mb-4">
            <h2 className="card-title">Execution Results</h2>
            <div className="flex gap-2">
              <button
                className="btn btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)] btn-outline rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                onClick={downloadResults}
                disabled={!execution.outputs && !(execution.logs?.length > 0)}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Export
              </button>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="tabs tabs-boxed mb-4">
            <button
              className={`tab ${activeTab === 'outputs' ? 'tab-active' : ''}`}
              onClick={() => setActiveTab('outputs')}
            >
              Outputs
            </button>
            <button
              className={`tab ${activeTab === 'logs' ? 'tab-active' : ''}`}
              onClick={() => setActiveTab('logs')}
            >
              Logs ({execution.logs?.length || 0})
            </button>
            <button
              className={`tab ${activeTab === 'steps' ? 'tab-active' : ''}`}
              onClick={() => setActiveTab('steps')}
            >
              Steps ({execution.stepExecutions?.length || 0})
            </button>
          </div>

          {/* Tab Content */}
          {/* Outputs Tab */}
          {activeTab === 'outputs' && (
            <div>
              {execution.outputs ? (
                <div className="space-y-4">
                  {Object.entries(execution.outputs).map(([key, value]) => (
                    <div key={key} className="border border-base-300 rounded-lg p-4">
                      <div className="flex justify-between items-center mb-2">
                        <h4 className="font-semibold">{key}</h4>
                        <button
                          className="btn btn-xs btn-outline rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                          onClick={() => copyToClipboard(formatOutput(value))}
                        >
                          Copy
                        </button>
                      </div>
                      <pre className="bg-base-300 p-3 rounded text-sm overflow-x-auto">
                        {formatOutput(value)}
                      </pre>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-base-content opacity-50">
                  <div className="text-4xl mb-2">📄</div>
                  <div>No outputs available yet</div>
                  <div className="text-sm mt-1">
                    {execution.status === 'running'
                      ? 'Outputs will appear when execution completes'
                      : 'This execution did not produce any outputs'}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Logs Tab */}
          {activeTab === 'logs' && (
            <div>
                {execution.logs?.length > 0 ? (
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {execution.logs.map((log, index) => (
                      <div
                        key={index}
                        className={`p-3 rounded-lg border ${
                          log.level === 'error' ? 'border-error bg-error/10' :
                          log.level === 'warning' ? 'border-warning bg-warning/10' :
                          'border-base-300'
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div className="flex-shrink-0 mt-1">
                            <span className="text-sm">
                              {getLogLevelIcon(log.level)}
                            </span>
                          </div>
                          <div className="flex-grow">
                            <div className="flex justify-between items-start">
                              <div>
                                <span className={`font-medium ${getLogLevelColor(log.level)}`}>
                                  {log.level.toUpperCase()}
                                </span>
                                {log.stepId && (
                                  <span className="text-xs opacity-70 ml-2">
                                    Step: {log.stepId}
                                  </span>
                                )}
                              </div>
                              <span className="text-xs opacity-70">
                                {new Date(log.timestamp).toLocaleTimeString()}
                              </span>
                            </div>
                            <div className="mt-1 text-sm">
                              {log.message}
                            </div>
                            {(log.data as ReactNode) && (
                              <div className="mt-2">
                                <button
                                  className="btn btn-xs btn-outline mb-2 rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                                  onClick={() => toggleLogExpansion(index)}
                                >
                                  {expandedLogs.has(index) ? 'Hide Data' : 'Show Data'}
                                </button>
                                {expandedLogs.has(index) && (
                                  <pre className="bg-base-300 p-2 rounded text-xs overflow-x-auto">
                                    {formatOutput(log.data)}
                                  </pre>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-base-content opacity-50">
                    <div className="text-4xl mb-2">📋</div>
                    <div>No logs available</div>
                  </div>
                )}
            </div>
          )}

          {/* Steps Tab */}
          {activeTab === 'steps' && (
            <div>
              {execution.stepExecutions?.length > 0 ? (
                  <div className="space-y-3">
                    {execution.stepExecutions.map((step, index) => (
                      <div
                        key={step.stepId}
                        className={`p-4 rounded-lg border ${
                          step.status === 'completed' ? 'border-success bg-success/10' :
                          step.status === 'failed' ? 'border-error bg-error/10' :
                          step.status === 'running' ? 'border-warning bg-warning/10' :
                          'border-base-300'
                        }`}
                      >
                        <div className="flex justify-between items-start mb-2">
                          <div>
                            <h4 className="font-semibold">
                              Step {index + 1}: {step.stepId}
                            </h4>
                            <div className={`text-sm ${
                              step.status === 'completed' ? 'text-success' :
                              step.status === 'failed' ? 'text-error' :
                              step.status === 'running' ? 'text-warning' :
                              'text-base-content opacity-70'
                            }`}>
                              {step.status.charAt(0).toUpperCase() + step.status.slice(1)}
                            </div>
                          </div>
                          <div className="text-right text-sm opacity-70">
                            {step.executionTime && (
                              <div>Duration: {step.executionTime}s</div>
                            )}
                            {step.retryCount && step.retryCount > 0 && (
                              <div>Retries: {step.retryCount}</div>
                            )}
                          </div>
                        </div>
                        
                        {step.error && (
                          <div className="mt-2 p-2 bg-error/20 rounded text-sm">
                            <strong>Error:</strong> {step.error}
                          </div>
                        )}
                        
                        {(step.output as ReactNode) && (
                          <div className="mt-2">
                            <details>
                              <summary className="cursor-pointer font-medium text-sm">
                                Output
                              </summary>
                              <pre className="mt-2 bg-base-300 p-2 rounded text-xs overflow-x-auto">
                                {formatOutput(step.output)}
                              </pre>
                            </details>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-base-content opacity-50">
                    <div className="text-4xl mb-2">⚙️</div>
                    <div>No step execution data available</div>
                  </div>
                )}
            </div>
          )}

          {/* Execution Summary */}
          <div className="mt-6 pt-4 border-t border-base-300">
            <h4 className="font-semibold mb-3">Execution Summary</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div>
                <span className="font-medium">Status:</span>
                <div className={`font-medium ${
                  execution.status === 'completed' ? 'text-success' :
                  execution.status === 'failed' ? 'text-error' :
                  execution.status === 'running' ? 'text-warning' :
                  'text-base-content'
                }`}>
                  {execution.status.charAt(0).toUpperCase() + execution.status.slice(1)}
                </div>
              </div>
              <div>
                <span className="font-medium">Duration:</span>
                <div className="opacity-70">
                  {execution.executionTime ? `${execution.executionTime}s` : 'N/A'}
                </div>
              </div>
              <div>
                <span className="font-medium">Completed:</span>
                <div className="opacity-70">
                  {execution.completedAt 
                    ? new Date(execution.completedAt).toLocaleString()
                    : 'N/A'
                  }
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}