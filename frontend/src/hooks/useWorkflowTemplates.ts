/**
 * useWorkflowTemplates Hook
 *
 * Hook for managing workflow templates with filtering, selection, and CRUD operations
 */

import { useState, useEffect, useCallback } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { workflowService } from '../services/domains/llm/workflowService';
import type {
  WorkflowTemplate,
  WorkflowTemplateFilters,
  WorkflowTemplateState,
  UseWorkflowTemplatesReturn,
  WorkflowTemplateFormData
} from '../types/workflows';
import { workflowTemplateFormSchema } from '../types/workflows';

/**
 * Default filter values
 */
const defaultFilters: WorkflowTemplateFilters = {
  search: '',
  category: [],
  complexity: [],
  tags: [],
  isPublic: null,
  isCustomizable: null,
  sortBy: 'name',
  sortOrder: 'asc'
};

/**
 * useWorkflowTemplates Hook
 */
export const useWorkflowTemplates = (): UseWorkflowTemplatesReturn => {
  const [state, setState] = useState<WorkflowTemplateState>({
    templates: [],
    filteredTemplates: [],
    filters: defaultFilters,
    loading: false,
    error: null,
    selectedTemplate: null,
    categories: [],
    tags: [],
    includeTesting: false
  });

  // Form handling for template creation/editing
  const form = useForm<WorkflowTemplateFormData>({
    resolver: zodResolver(workflowTemplateFormSchema) as never,
    defaultValues: {
      name: '',
      description: '',
      category: '',
      tags: [],
      isPublic: false,
      isCustomizable: true
    }
  });

  /**
   * Load templates and categories
   */
  const loadTemplates = useCallback(async () => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const [templatesResponse, categoriesResponse] = await Promise.all([
        workflowService.getTemplates(),
        workflowService.getTemplateCategories()
      ]);

      if (!templatesResponse.error && !categoriesResponse.error) {
        setState(prev => ({
          ...prev,
          templates: templatesResponse.data || [],
          filteredTemplates: templatesResponse.data || [],
          categories: categoriesResponse.data?.categories || [],
          tags: categoriesResponse.data?.tags || [],
          loading: false
        }));
      } else {
        setState(prev => ({
          ...prev,
          error: templatesResponse.error?.message || categoriesResponse.error?.message || 'Failed to load templates',
          loading: false
        }));
      }
    } catch (error) {
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to load templates',
        loading: false
      }));
    }
  }, []);

  /**
   * Apply filters to templates
   */
  const applyFilters = useCallback((
    templates: WorkflowTemplate[],
    filters: WorkflowTemplateFilters,
    includeTesting: boolean
  ): WorkflowTemplate[] => {
    let filtered = templates;

    // Phase E: testing-namespace fixtures hidden by default
    if (!includeTesting) {
      filtered = filtered.filter(t => t.category !== 'testing');
    }

    // Search filter
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      filtered = filtered.filter(template =>
        template.name.toLowerCase().includes(searchLower) ||
        template.description.toLowerCase().includes(searchLower) ||
        template.tags.some(tag => tag.toLowerCase().includes(searchLower))
      );
    }

    // Category filter
    if (filters.category.length > 0) {
      filtered = filtered.filter(template =>
        filters.category.includes(template.category)
      );
    }

    // Complexity filter
    if (filters.complexity.length > 0) {
      filtered = filtered.filter(template =>
        filters.complexity.includes(template.metadata.complexity)
      );
    }

    // Tags filter
    if (filters.tags.length > 0) {
      filtered = filtered.filter(template =>
        filters.tags.some(tag => template.tags.includes(tag))
      );
    }

    // Public filter
    if (filters.isPublic !== null) {
      filtered = filtered.filter(template => template.isPublic === filters.isPublic);
    }

    // Customizable filter
    if (filters.isCustomizable !== null) {
      filtered = filtered.filter(template => template.isCustomizable === filters.isCustomizable);
    }

    // Sorting
    filtered.sort((a, b) => {
      const sortBy = filters.sortBy;
      
      const aValue: string | number | Date = (() => {
        switch (sortBy) {
          case 'name': return a.name;
          case 'category': return a.category;
          case 'complexity': return a.metadata.complexity;
          case 'executionCount': return a.executionCount;
          case 'successRate': return a.successRate;
          case 'createdAt': return new Date(a.createdAt);
          default: return a.name;
        }
      })();
      const bValue: string | number | Date = (() => {
        switch (sortBy) {
          case 'name': return b.name;
          case 'category': return b.category;
          case 'complexity': return b.metadata.complexity;
          case 'executionCount': return b.executionCount;
          case 'successRate': return b.successRate;
          case 'createdAt': return new Date(b.createdAt);
          default: return b.name;
        }
      })();

      if (filters.sortOrder === 'asc') {
        return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
      } else {
        return aValue > bValue ? -1 : aValue < bValue ? 1 : 0;
      }
    });

    return filtered;
  }, []);

  /**
   * Set filters and update filtered templates
   */
  const setFilters = useCallback((newFilters: WorkflowTemplateFilters) => {
    setState(prev => {
      const filteredTemplates = applyFilters(prev.templates, newFilters, prev.includeTesting);
      return {
        ...prev,
        filters: newFilters,
        filteredTemplates
      };
    });
  }, [applyFilters]);

  /**
   * Set selected template
   */
  const setSelectedTemplate = useCallback((template: WorkflowTemplate | null) => {
    setState(prev => ({ ...prev, selectedTemplate: template }));
  }, []);

  /**
   * Create a new template
   */
  const createTemplate = useCallback(async (templateData: Omit<WorkflowTemplate, 'id' | 'createdAt' | 'updatedAt'>) => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const response = await workflowService.createTemplate(templateData);
      
      if (!response.error) {
        await loadTemplates(); // Reload to get the new template
        setState(prev => ({ ...prev, loading: false }));
      } else {
        setState(prev => ({
          ...prev,
          error: response.error?.message || 'Failed to create template',
          loading: false
        }));
      }
    } catch (error) {
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to create template',
        loading: false
      }));
    }
  }, [loadTemplates]);

  /**
   * Update an existing template
   */
  const updateTemplate = useCallback(async (id: string, templateData: Partial<WorkflowTemplate>) => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const response = await workflowService.updateTemplate(id, templateData);
      
      if (!response.error) {
        await loadTemplates(); // Reload to get the updated template
        setState(prev => ({ ...prev, loading: false }));
      } else {
        setState(prev => ({
          ...prev,
          error: response.error?.message || 'Failed to update template',
          loading: false
        }));
      }
    } catch (error) {
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to update template',
        loading: false
      }));
    }
  }, [loadTemplates]);

  /**
   * Delete a template
   */
  const deleteTemplate = useCallback(async (id: string) => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const response = await workflowService.deleteTemplate(id);
      
      if (!response.error) {
        await loadTemplates(); // Reload to remove the deleted template
        setState(prev => ({ ...prev, loading: false }));
      } else {
        setState(prev => ({
          ...prev,
          error: response.error?.message || 'Failed to delete template',
          loading: false
        }));
      }
    } catch (error) {
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to delete template',
        loading: false
      }));
    }
  }, [loadTemplates]);

  /**
   * Refresh templates
   */
  const refreshTemplates = useCallback(async () => {
    await loadTemplates();
  }, [loadTemplates]);

  // Load templates on mount
  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  // Apply filters when templates or filters change
  useEffect(() => {
    setState(prev => ({
      ...prev,
      filteredTemplates: applyFilters(prev.templates, prev.filters, prev.includeTesting)
    }));
  }, [state.templates, applyFilters]);

  const setIncludeTesting = useCallback((v: boolean) => {
    setState(prev => ({
      ...prev,
      includeTesting: v,
      filteredTemplates: applyFilters(prev.templates, prev.filters, v)
    }));
  }, [applyFilters]);

  return {
    templates: state.templates,
    filteredTemplates: state.filteredTemplates,
    filters: state.filters,
    loading: state.loading,
    error: state.error,
    categories: state.categories,
    tags: state.tags,
    includeTesting: state.includeTesting,
    setIncludeTesting,
    setFilters,
    refreshTemplates,
    selectedTemplate: state.selectedTemplate,
    setSelectedTemplate,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    form
  };
};

export default useWorkflowTemplates;