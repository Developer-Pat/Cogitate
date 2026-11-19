/**
 * useWorkflowExecution Hook
 *
 * Hook for managing workflow execution, polling, and execution history
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useForm } from 'react-hook-form';
import type { Resolver } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { workflowService } from '../services/domains/llm/workflowService';
import { frontendLoggingService } from '../services/frontendLoggingService';
import { useNotifications } from './useNotifications';
import type {
  WorkflowExecutionState,
  UseWorkflowExecutionReturn,
  WorkflowExecutionFormData
} from '../types/workflows';
import { workflowExecutionFormSchema } from '../types/workflows';

/**
 * useWorkflowExecution Hook
 */
export const useWorkflowExecution = (): UseWorkflowExecutionReturn => {
  const { notifyWarning, notifySuccess } = useNotifications();
  const [state, setState] = useState<WorkflowExecutionState>({
    executions: [],
    selectedExecution: null,
    loading: false,
    error: null,
    polling: false
  });

  const pollingIntervalRef = useRef<number | null>(null);

  // Callback reference for SSE disconnect function
  const disconnectSSERef = useRef<(() => void) | null>(null);

  /**
   * Set the SSE disconnect function
   */
  const setSSEDisconnect = useCallback((disconnectFn: () => void) => {
    disconnectSSERef.current = disconnectFn;
  }, []);

  /**
   * Disconnect SSE connection
   */
  const disconnectSSE = useCallback(() => {
    if (disconnectSSERef.current) {
      disconnectSSERef.current();
      disconnectSSERef.current = null;
    }
  }, []);

  // Form handling for execution inputs
  const form = useForm<WorkflowExecutionFormData>({
    resolver: zodResolver(workflowExecutionFormSchema) as Resolver<WorkflowExecutionFormData>,
    defaultValues: {
      templateId: '',
      inputs: {}
    }
  });

  /**
   * Execute a workflow template
   */
  const executeWorkflow = useCallback(async (templateId: string, inputs: Record<string, unknown>, workflowType?: 'simple' | 'multi_agent') => {
    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      // Log workflow start attempt with clear visual markers
      frontendLoggingService.info('useWorkflowExecution', '═══════════════════════════════════════════════════════════');
      frontendLoggingService.info('useWorkflowExecution', '🚀 WORKFLOW EXECUTION STARTING');
      frontendLoggingService.info('useWorkflowExecution', `   Template ID: ${templateId}`);
      frontendLoggingService.info('useWorkflowExecution', `   Workflow Type: ${workflowType || 'auto-detect'}`);
      frontendLoggingService.info('useWorkflowExecution', '═══════════════════════════════════════════════════════════');

      const response = await workflowService.executeTemplate(templateId, inputs, workflowType);

      if (!response.error && response.data) {
        // Add the new execution to the list
        const newExecution = response.data;

        // Validate execution ID before starting polling
        if (!newExecution.id) {
          frontendLoggingService.error('useWorkflowExecution', 'Execution response missing ID', {
            templateId,
            responseData: response.data
          });

          setState(prev => ({
            ...prev,
            error: 'Invalid workflow execution response',
            loading: false
          }));
          return;
        }

        setState(prev => ({
          ...prev,
          executions: [newExecution, ...prev.executions],
          selectedExecution: newExecution,
          loading: false
        }));

        // Log successful execution start
        frontendLoggingService.info('useWorkflowExecution', '✅ Workflow execution started successfully', {
          executionId: newExecution.id,
          templateId,
          templateName: newExecution.templateId
        });

        // Start polling for execution updates
        startPolling(newExecution.id);
      } else {
        // Log the error
        frontendLoggingService.error('useWorkflowExecution', 'Failed to execute workflow', {
          templateId,
          errorMessage: response.error?.message || 'Unknown error'
        });

        setState(prev => ({
          ...prev,
          error: response.error?.message || 'Failed to execute workflow',
          loading: false
        }));
      }
    } catch (error) {
      // Log the error
      frontendLoggingService.error('useWorkflowExecution', 'Workflow execution failed', error as Error, {
        templateId,
        inputs
      });

      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to execute workflow',
        loading: false
      }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Get specific execution details
   */
  const getExecution = useCallback(async (executionId: string) => {
    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const response = await workflowService.getExecution(executionId);

      if (!response.error && response.data) {
        setState(prev => ({
          ...prev,
          selectedExecution: response.data || null,
          loading: false
        }));
      } else {
        // Log the error
        frontendLoggingService.error('useWorkflowExecution', 'Failed to get execution details', {
          executionId,
          errorMessage: response.error?.message || 'Unknown error'
        });

        setState(prev => ({
          ...prev,
          error: response.error?.message || 'Failed to get execution details',
          loading: false
        }));
      }
    } catch (error) {
      // Log the error
      frontendLoggingService.error('useWorkflowExecution', 'Get execution failed', error as Error, {
        executionId
      });

      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to get execution details',
        loading: false
      }));
    }
  }, []);

  /**
   * Cancel an execution
   */
  const cancelExecution = useCallback(async (executionId: string) => {
    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      // Log workflow cancellation attempt
      frontendLoggingService.warning('useWorkflowExecution', '⏹️ Workflow execution cancellation requested', {
        executionId
      });

      const response = await workflowService.cancelExecution(executionId);

      if (!response.error) {
        // Stop polling for this execution
        stopPolling();

        // Disconnect SSE connection
        disconnectSSE();

        // Log successful cancellation
        frontendLoggingService.warning('useWorkflowExecution', '⚠️ Workflow execution cancelled by user', {
          executionId,
          reason: 'User requested termination'
        });
        
        // Show cancellation toast
        notifyWarning(
          'Workflow Cancelled',
          'Workflow execution was stopped by user',
          5000
        );

        // Update the execution status
        setState(prev => ({
          ...prev,
          executions: prev.executions.map(exec =>
            exec.id === executionId
              ? { ...exec, status: 'cancelled' }
              : exec
          ),
          selectedExecution: prev.selectedExecution?.id === executionId
            ? { ...prev.selectedExecution, status: 'cancelled' }
            : prev.selectedExecution,
          loading: false
        }));
      } else {
        // Log the error
        frontendLoggingService.error('useWorkflowExecution', 'Failed to cancel execution', {
          executionId,
          errorMessage: response.error?.message || 'Unknown error'
        });

        setState(prev => ({
          ...prev,
          error: response.error?.message || 'Failed to cancel execution',
          loading: false
        }));
      }
    } catch (error) {
      // Log the error
      frontendLoggingService.error('useWorkflowExecution', 'Cancel execution failed', error as Error, {
        executionId
      });

      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to cancel execution',
        loading: false
      }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disconnectSSE]);

  /**
   * Retry a failed execution
   */
  const retryExecution = useCallback(async (executionId: string) => {
    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const response = await workflowService.retryExecution(executionId);

      if (!response.error && response.data) {
        // Replace the old execution with the new one
        const newExecution = response.data;
        setState(prev => ({
          ...prev,
          executions: [newExecution, ...prev.executions.filter(exec => exec.id !== executionId)],
          selectedExecution: newExecution,
          loading: false
        }));

        // Start polling for the new execution
        startPolling(newExecution.id);
      } else {
        // Log the error
        frontendLoggingService.error('useWorkflowExecution', 'Failed to retry execution', {
          executionId,
          errorMessage: response.error?.message || 'Unknown error'
        });

        setState(prev => ({
          ...prev,
          error: response.error?.message || 'Failed to retry execution',
          loading: false
        }));
      }
    } catch (error) {
      // Log the error
      frontendLoggingService.error('useWorkflowExecution', 'Retry execution failed', error as Error, {
        executionId
      });

      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to retry execution',
        loading: false
      }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Start polling for execution updates
   */
  const startPolling = useCallback((executionId: string) => {
    // Don't start polling without valid execution ID
    if (!executionId) {
      frontendLoggingService.warning('useWorkflowExecution', 'Cannot start polling - execution ID is invalid', {
        executionId
      });
      return;
    }

    // Clear any existing polling
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    setState(prev => ({ ...prev, polling: true }));

    // Poll every 2 seconds
    pollingIntervalRef.current = window.setInterval(async () => {
      try {
        const response = await workflowService.getExecution(executionId);

        if (!response.error && response.data) {
          const updatedExecution = response.data;

          setState(prev => ({
            ...prev,
            executions: prev.executions.map(exec =>
              exec.id === executionId ? updatedExecution : exec
            ),
            selectedExecution: prev.selectedExecution?.id === executionId
              ? updatedExecution
              : prev.selectedExecution
          }));

          // Stop polling if execution reached terminal status
          // Terminal statuses: completed, failed, cancelled, error
          if (['completed', 'failed', 'cancelled', 'error'].includes(updatedExecution.status)) {
            stopPolling();

            // Calculate elapsed time
            let elapsedSeconds = 'N/A';
            if (updatedExecution.startedAt && updatedExecution.completedAt) {
              const start = new Date(updatedExecution.startedAt);
              const end = new Date(updatedExecution.completedAt);
              const diffMs = end.getTime() - start.getTime();
              elapsedSeconds = (diffMs / 1000).toFixed(2) + 's';
            }

            // Log the final status with clear visual markers
            if (updatedExecution.status === 'completed') {
              frontendLoggingService.info('useWorkflowExecution', '═══════════════════════════════════════════════════════════');
              frontendLoggingService.info('useWorkflowExecution', '✅ WORKFLOW EXECUTION COMPLETED SUCCESSFULLY');
              frontendLoggingService.info('useWorkflowExecution', `   Execution ID: ${updatedExecution.id}`);
              frontendLoggingService.info('useWorkflowExecution', `   Template: ${updatedExecution.templateId}`);
              frontendLoggingService.info('useWorkflowExecution', `   Elapsed Time: ${elapsedSeconds}`);
              frontendLoggingService.info('useWorkflowExecution', '═══════════════════════════════════════════════════════════');
              
              // Show success toast
              notifySuccess(
                'Workflow Completed',
                `Workflow finished successfully in ${elapsedSeconds}`,
                5000
              );
            } else if (updatedExecution.status === 'failed') {
              frontendLoggingService.error('useWorkflowExecution', '═══════════════════════════════════════════════════════════');
              frontendLoggingService.error('useWorkflowExecution', '❌ WORKFLOW EXECUTION FAILED');
              frontendLoggingService.error('useWorkflowExecution', `   Execution ID: ${updatedExecution.id}`);
              frontendLoggingService.error('useWorkflowExecution', `   Template: ${updatedExecution.templateId}`);
              frontendLoggingService.error('useWorkflowExecution', `   Error: ${updatedExecution.error || 'Unknown error'}`);
              frontendLoggingService.error('useWorkflowExecution', '═══════════════════════════════════════════════════════════');
            }
            // Note: cancelled status is already logged in cancelExecution
          }
        }
      } catch (error) {
        frontendLoggingService.error('useWorkflowExecution', 'Error polling execution', error as Error);
        // Don't set error state for polling failures to avoid disrupting user experience
      }
    }, 2000);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Stop polling
   */
  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setState(prev => ({ ...prev, polling: false }));
  }, []);

  /**
   * Cleanup polling on unmount
   */
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  return {
    executions: state.executions,
    selectedExecution: state.selectedExecution,
    loading: state.loading,
    error: state.error,
    polling: state.polling,
    executeWorkflow,
    getExecution,
    cancelExecution,
    retryExecution,
    startPolling,
    stopPolling,
    setSSEDisconnect,
    disconnectSSE,
    form
  };
};

export default useWorkflowExecution;