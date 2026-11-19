/**
 * useWorkflowLists Hook
 *
 * Hook for managing workflow lists with filtering, selection, and CRUD operations
 */

import { useState, useEffect, useCallback } from 'react';
import { useForm } from 'react-hook-form';
import type { Resolver } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { workflowListsService } from '../services/domains/llm/workflowListsService';
import type {
  WorkflowList,
  WorkflowListCreate,
  WorkflowListUpdate,
  WorkflowInList
} from '../types/workflows';
import { workflowTemplateFormSchema } from '../types/workflows';

/**
 * Workflow List State
 */
interface WorkflowListState {
  workflowLists: WorkflowList[];
  filteredLists: WorkflowList[];
  loading: boolean;
  error: string | null;
  selectedList: WorkflowList | null;
  selectedListWorkflows: WorkflowInList[];
  tags: string[];
  filterTags: string[];
}

/**
 * useWorkflowLists Hook Return Type
 */
interface UseWorkflowListsReturn {
  workflowLists: WorkflowList[];
  filteredLists: WorkflowList[];
  loading: boolean;
  error: string | null;
  tags: string[];
  filterTags: string[];
  setFilterTags: (tags: string[]) => void;
  refreshLists: () => Promise<void>;
  selectedList: WorkflowList | null;
  setSelectedList: (list: WorkflowList | null) => void;
  selectedListWorkflows: WorkflowInList[];
  loadListWorkflows: (listId: string) => Promise<void>;
  createList: (data: WorkflowListCreate) => Promise<void>;
  updateList: (id: string, data: WorkflowListUpdate) => Promise<void>;
  deleteList: (id: string) => Promise<void>;
  addWorkflowToList: (listId: string, workflowId: string) => Promise<void>;
  removeWorkflowFromList: (listId: string, workflowId: string) => Promise<void>;
  form: unknown; // UseFormReturn<WorkflowListCreate>
}

/**
 * Default filter values
 */
const defaultFilterTags: string[] = [];

/**
 * useWorkflowLists Hook
 */
export const useWorkflowLists = (): UseWorkflowListsReturn => {
  const [state, setState] = useState<WorkflowListState>({
    workflowLists: [],
    filteredLists: [],
    loading: false,
    error: null,
    selectedList: null,
    selectedListWorkflows: [],
    tags: [],
    filterTags: defaultFilterTags
  });

  // Form handling for list creation
  const form = useForm<WorkflowListCreate>({
    resolver: zodResolver(workflowTemplateFormSchema) as unknown as Resolver<WorkflowListCreate>,
    defaultValues: {
      name: '',
      description: '',
      tags: [],
      workflow_ids: [],
      is_default: false
    }
  });

  /**
   * Load workflow lists and extract tags
   */
  const loadLists = useCallback(async () => {
    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const response = await workflowListsService.getLists();

      if (!response.error) {
        const lists = response.data || [];
        
        // Extract all unique tags from lists
        const tagSet = new Set<string>();
        lists.forEach(list => {
          list.tags?.forEach(tag => tagSet.add(tag));
        });

        setState(prev => ({
          ...prev,
          workflowLists: lists,
          filteredLists: lists,
          tags: Array.from(tagSet),
          loading: false
        }));
      } else {
        setState(prev => ({
          ...prev,
          error: response.error?.message || 'Failed to load workflow lists',
          loading: false
        }));
      }
    } catch (error) {
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to load workflow lists',
        loading: false
      }));
    }
  }, []);

  /**
   * Apply tag filters to lists
   */
  const applyFilters = useCallback(() => {
    setState(prev => {
      let filtered = prev.workflowLists;

      // Filter by tags (match any tag)
      if (prev.filterTags.length > 0) {
        filtered = filtered.filter(list =>
          list.tags?.some(tag => prev.filterTags.includes(tag))
        );
      }

      return { ...prev, filteredLists: filtered };
    });
  }, []);

  /**
   * Set filter tags and apply filters
   */
  const setFilterTags = useCallback((tags: string[]) => {
    setState(prev => ({ ...prev, filterTags: tags }));
  }, []);

  /**
   * Load workflows in a specific list
   */
  const loadListWorkflows = useCallback(async (listId: string) => {
    try {
      const response = await workflowListsService.getWorkflowsInList(listId);

      if (!response.error) {
        setState(prev => ({
          ...prev,
          selectedListWorkflows: response.data || []
        }));
      }
    } catch (error) {
      console.error('Failed to load list workflows:', error);
    }
  }, []);

  /**
   * Create a new workflow list
   */
  const createList = useCallback(async (data: WorkflowListCreate) => {
    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const response = await workflowListsService.createList(data);

      if (!response.error) {
        await loadLists();
        form.reset();
      } else {
        setState(prev => ({
          ...prev,
          error: response.error?.message || 'Failed to create workflow list',
          loading: false
        }));
      }
    } catch (error) {
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to create workflow list',
        loading: false
      }));
    }
  }, [loadLists, form]);

  /**
   * Update an existing workflow list
   */
  const updateList = useCallback(async (id: string, data: WorkflowListUpdate) => {
    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const response = await workflowListsService.updateList(id, data);

      if (!response.error) {
        await loadLists();
        // Update selected list if it's the one being updated
        setState(prev => ({
          ...prev,
          selectedList: response.data || prev.selectedList,
          loading: false
        }));
      } else {
        setState(prev => ({
          ...prev,
          error: response.error?.message || 'Failed to update workflow list',
          loading: false
        }));
      }
    } catch (error) {
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to update workflow list',
        loading: false
      }));
    }
  }, [loadLists]);

  /**
   * Delete a workflow list
   */
  const deleteList = useCallback(async (id: string) => {
    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const response = await workflowListsService.deleteList(id);

      if (!response.error) {
        await loadLists();
        setState(prev => ({
          ...prev,
          selectedList: null,
          selectedListWorkflows: [],
          loading: false
        }));
      } else {
        setState(prev => ({
          ...prev,
          error: response.error?.message || 'Failed to delete workflow list',
          loading: false
        }));
      }
    } catch (error) {
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to delete workflow list',
        loading: false
      }));
    }
  }, [loadLists]);

  /**
   * Add a workflow to a list
   */
  const addWorkflowToList = useCallback(async (listId: string, workflowId: string) => {
    try {
      const response = await workflowListsService.addWorkflowToList(listId, workflowId);

      if (!response.error) {
        await loadLists();
        // Refresh selected list
        if (workflowId) {
          await loadListWorkflows(listId);
        }
      }
    } catch (error) {
      console.error('Failed to add workflow to list:', error);
    }
  }, [loadLists, loadListWorkflows]);

  /**
   * Remove a workflow from a list
   */
  const removeWorkflowFromList = useCallback(async (listId: string, workflowId: string) => {
    try {
      const response = await workflowListsService.removeWorkflowFromList(listId, workflowId);

      if (!response.error) {
        await loadLists();
        // Refresh selected list workflows
        await loadListWorkflows(listId);
      }
    } catch (error) {
      console.error('Failed to remove workflow from list:', error);
    }
  }, [loadLists, loadListWorkflows]);

  /**
   * Set selected list
   */
  const setSelectedList = useCallback((list: WorkflowList | null) => {
    setState(prev => ({
      ...prev,
      selectedList: list,
      selectedListWorkflows: [] // Clear workflows when selecting a new list
    }));
  }, []);

  /**
   * Refresh lists
   */
  const refreshLists = useCallback(async () => {
    await loadLists();
  }, [loadLists]);

  // Apply filters when filterTags change
  useEffect(() => {
    applyFilters();
  }, [state.filterTags, applyFilters]);

  // Load lists on mount
  useEffect(() => {
    loadLists();
  }, [loadLists]);

  return {
    workflowLists: state.workflowLists,
    filteredLists: state.filteredLists,
    loading: state.loading,
    error: state.error,
    tags: state.tags,
    filterTags: state.filterTags,
    setFilterTags,
    refreshLists,
    selectedList: state.selectedList,
    setSelectedList,
    selectedListWorkflows: state.selectedListWorkflows,
    loadListWorkflows,
    createList,
    updateList,
    deleteList,
    addWorkflowToList,
    removeWorkflowFromList,
    form
  };
};

export default useWorkflowLists;
