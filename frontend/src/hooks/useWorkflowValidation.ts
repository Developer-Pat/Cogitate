/**
 * useWorkflowValidation Hook
 * 
 * Hook for validating workflow templates, executions, and steps
 */

import { useCallback } from 'react';
import { workflowService } from '../services/domains/llm/workflowService';
import type {
  WorkflowTemplate,
  WorkflowStep,
  UseWorkflowValidationReturn
} from '../types/workflows';

/**
 * useWorkflowValidation Hook
 */
export const useWorkflowValidation = (): UseWorkflowValidationReturn => {

  /**
   * Validate a workflow template
   */
  const validateTemplate = useCallback(async (template: WorkflowTemplate): Promise<{
    isValid: boolean;
    errors: string[];
    warnings: string[];
  }> => {
    try {
      const response = await workflowService.validateTemplate(template);

      if (!response.error && response.data) {
        return response.data;
      } else {
        return {
          isValid: false,
          errors: [response.error?.message || 'Validation failed'],
          warnings: []
        };
      }
    } catch (error) {
      return {
        isValid: false,
        errors: [error instanceof Error ? error.message : 'Validation failed'],
        warnings: []
      };
    }
  }, []);

  /**
   * Validate workflow execution inputs
   */
  const validateExecution = useCallback(async (templateId: string, inputs: Record<string, unknown>): Promise<{
    isValid: boolean;
    errors: string[];
    warnings: string[];
  }> => {
    try {
      const response = await workflowService.validateExecution(templateId, inputs);

      if (!response.error && response.data) {
        return response.data;
      } else {
        return {
          isValid: false,
          errors: [response.error?.message || 'Execution validation failed'],
          warnings: []
        };
      }
    } catch (error) {
      return {
        isValid: false,
        errors: [error instanceof Error ? error.message : 'Execution validation failed'],
        warnings: []
      };
    }
  }, []);

  /**
   * Validate a workflow step
   */
  const validateStep = useCallback(async (step: WorkflowStep): Promise<{
    isValid: boolean;
    errors: string[];
    warnings: string[];
  }> => {
    // Client-side validation for workflow steps
    const errors: string[] = [];
    const warnings: string[] = [];

    // Validate required fields
    if (!step.name || step.name.trim() === '') {
      errors.push('Step name is required');
    }

    if (!step.type) {
      errors.push('Step type is required');
    }

    // Validate step type specific rules
    switch (step.type) {
      case 'agent':
        if (!step.agentId) {
          errors.push('Agent ID is required for agent steps');
        }
        break;
      case 'condition':
        if (!step.conditions || step.conditions.length === 0) {
          warnings.push('Condition steps should have at least one condition');
        }
        break;
      case 'loop':
        if (!step.parameters?.maxIterations) {
          warnings.push('Loop steps should specify maximum iterations');
        }
        break;
    }

    // Validate next steps
    if (step.nextSteps && step.nextSteps.length === 0) {
      warnings.push('Step has no next steps defined');
    }

    // Validate parameters
    if (step.parameters && typeof step.parameters !== 'object') {
      errors.push('Step parameters must be an object');
    }

    // Validate error handling
    if (step.errorHandling) {
      if (step.errorHandling.retryOnError && !step.errorHandling.maxRetries) {
        warnings.push('Retry on error is enabled but max retries is not specified');
      }
    }

    // Validate timeout
    if (step.timeout && step.timeout <= 0) {
      errors.push('Timeout must be a positive number');
    }

    // Validate retry count
    if (step.retryCount && step.retryCount < 0) {
      errors.push('Retry count cannot be negative');
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings
    };
  }, []);

  return {
    validateTemplate,
    validateExecution,
    validateStep
  };
};

export default useWorkflowValidation;