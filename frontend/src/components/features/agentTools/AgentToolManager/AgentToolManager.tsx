/**
 * AgentToolManager Component
 *
 * Component for managing agent-tool associations, configuration, and priority.
 * Table-based UI with filtering and search.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { agentToolService } from '@/services/domain/AgentToolService';
import { toolService } from '@/services/domain/ToolService';
import type { AgentToolResponse, ToolResponse } from '@/types/tools';
import { ToolConfigModal } from './ToolConfigModal';
import {
  Activity, AlarmClock, Bell, Book, BookOpen, Bookmark, Bot, Brain, Bug,
  CircleArrowRight, Clock, Code, Database, FileText, Folder, Globe,
  Keyboard, List, MessageCircle, Plus, Save, Search as SearchIcon,
  Send, Settings, Tags, ToggleLeft, ToggleRight, TriangleAlert,
  Wrench,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// The registry's icon vocabulary (2026-09-06: the old fa-${tool.icon}
// prefix rendered nothing — font-awesome was never loaded). Mostly
// lucide names already, a few FA-era names + emoji stragglers; the map
// normalizes them and Wrench catches anything unknown.
const TOOL_ICONS: Record<string, LucideIcon> = {
  activity: Activity,
  'arrow-right-circle': CircleArrowRight,
  book: Book,
  'book-open': BookOpen,
  bookmark: Bookmark,
  bot: Bot,
  brain: Brain,
  bug: Bug,
  clock: Clock,
  code: Code,
  database: Database,
  'file-info': FileText,
  'file-text': FileText,
  folder: Folder,
  globe: Globe,
  keyboard: Keyboard,
  list: List,
  'magnifying-glass': SearchIcon,
  'message-circle-question': MessageCircle,
  publish: Send,
  save: Save,
  search: SearchIcon,
  settings: Settings,
  'toggle-left': ToggleLeft,
  '⏰': AlarmClock,
  '🔔': Bell,
};

function ToolIcon({ name, className = 'h-4 w-4' }: { name?: string; className?: string }) {
  const Icon = (name && TOOL_ICONS[name]) || Wrench
  return <Icon className={className} />
}

export interface AgentToolManagerProps {
  /** Agent ID to manage tools for */
  agentId: string;
  /** Callback when tool configuration is updated */
  onConfigUpdate?: (toolId: string, config: unknown) => void;
  /** Callback when tools are enabled/disabled */
  onToolsChanged?: () => void;
}

/**
 * AgentToolManager Component
 */
export const AgentToolManager: React.FC<AgentToolManagerProps> = ({
  agentId,
  onConfigUpdate,
  onToolsChanged,
}) => {
  const [agentTools, setAgentTools] = useState<AgentToolResponse[]>([]);
  const [allTools, setAllTools] = useState<ToolResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [configModalOpen, setConfigModalOpen] = useState(false);
  const [selectedTool, setSelectedTool] = useState<AgentToolResponse | null>(null);
  const [bulkOperation, setBulkOperation] = useState<'enable' | 'disable' | null>(null);
  
  // Filter states
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [filterStatus, setFilterStatus] = useState<'all' | 'assigned' | 'available'>('all');
  const [showTagDropdown, setShowTagDropdown] = useState(false);
  
  // Pagination states
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Load agent tools and all available tools
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);

      try {
        // Load agent's tools
        const agentToolsResponse = await agentToolService.listAgentTools(agentId);
        setAgentTools(agentToolsResponse.tools);

        // Load all available tools
        const allToolsResponse = await toolService.listTools();
        setAllTools(allToolsResponse.tools);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load tools');
        console.error('Failed to load agent tools:', err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [agentId]);

  // Extract all unique tags from tools
  const allTags = useMemo(() => {
    const tags = new Set<string>();
    allTools.forEach(tool => {
      tool.tags?.forEach(tag => tags.add(tag));
    });
    return Array.from(tags).sort();
  }, [allTools]);

  // Filter tools based on search, tags, and status
  const filteredTools = useMemo(() => {
    return allTools.filter(tool => {
      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const matchesSearch = 
          tool.name.toLowerCase().includes(query) ||
          tool.description.toLowerCase().includes(query) ||
          tool.tags?.some(tag => tag.toLowerCase().includes(query));
        
        if (!matchesSearch) return false;
      }

      // Tag filter
      if (selectedTags.length > 0) {
        const hasMatchingTag = tool.tags?.some(tag => selectedTags.includes(tag));
        if (!hasMatchingTag) return false;
      }

      // Status filter
      const isAssigned = agentTools.some(at => at.tool_id === tool.id);
      if (filterStatus === 'assigned' && !isAssigned) return false;
      if (filterStatus === 'available' && isAssigned) return false;

      return true;
    });
  }, [allTools, agentTools, searchQuery, selectedTags, filterStatus]);

  // Calculate pagination
  const totalPages = Math.ceil(filteredTools.length / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  const paginatedTools = filteredTools.slice(startIndex, endIndex);

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, selectedTags, filterStatus]);

  // Separate into assigned and available for display
  const assignedTools = useMemo(() => {
    return paginatedTools.map(tool => {
      const agentTool = agentTools.find(at => at.tool_id === tool.id);
      return {
        ...tool,
        agentTool,
        is_assigned: !!agentTool,
        is_enabled: agentTool?.is_enabled ?? false,
        priority: agentTool?.priority ?? 0,
        config: agentTool?.config ?? {},
      };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filteredTools, agentTools]);

  const handleEnableTool = async (toolId: string) => {
    try {
      await agentToolService.enableToolForAgent(agentId, {
        tool_id: toolId,
        priority: 0,
        config: {},
      });

      // Refresh the list
      const agentToolsResponse = await agentToolService.listAgentTools(agentId);
      setAgentTools(agentToolsResponse.tools);
      onToolsChanged?.();
    } catch (err) {
      console.error('Failed to enable tool:', err);
    }
  };

  const handleDisableTool = async (toolId: string) => {
    try {
      await agentToolService.disableToolForAgent(agentId, toolId);

      // Refresh the list
      const agentToolsResponse = await agentToolService.listAgentTools(agentId);
      setAgentTools(agentToolsResponse.tools);
      onToolsChanged?.();
    } catch (err) {
      console.error('Failed to disable tool:', err);
    }
  };

  const handleUpdatePriority = async (toolId: string, priority: number) => {
    try {
      await agentToolService.updateAgentTool(agentId, toolId, { priority });

      // Update local state
      setAgentTools(prev =>
        prev.map(at =>
          at.tool_id === toolId ? { ...at, priority } : at
        )
      );
      onToolsChanged?.();
    } catch (err) {
      console.error('Failed to update priority:', err);
    }
  };

  const handleOpenConfig = (agentTool: AgentToolResponse) => {
    setSelectedTool(agentTool);
    setConfigModalOpen(true);
  };

  const handleCloseConfig = () => {
    setConfigModalOpen(false);
    setSelectedTool(null);
  };

  const handleSaveConfig = async (toolId: string, config: unknown) => {
    try {
      await agentToolService.updateAgentTool(agentId, toolId, { config: config as Record<string, unknown> });

      // Update local state
      setAgentTools(prev =>
        prev.map(at =>
          at.tool_id === toolId ? { ...at, config: config as Record<string, unknown> } : at
        )
      );

      onConfigUpdate?.(toolId, config);
      handleCloseConfig();
    } catch (err) {
      console.error('Failed to save config:', err);
    }
  };

  const handleBulkEnable = async () => {
    setBulkOperation('enable');
    try {
      // Get all disabled tools
      const disabledTools = agentTools.filter(at => !at.is_enabled);

      for (const agentTool of disabledTools) {
        await agentToolService.enableToolForAgent(agentId, {
          tool_id: agentTool.tool_id,
          priority: agentTool.priority,
          config: agentTool.config,
        });
      }

      // Refresh the list
      const agentToolsResponse = await agentToolService.listAgentTools(agentId);
      setAgentTools(agentToolsResponse.tools);
      onToolsChanged?.();
    } catch (err) {
      console.error('Failed to bulk enable tools:', err);
    } finally {
      setBulkOperation(null);
    }
  };

  const handleBulkDisable = async () => {
    setBulkOperation('disable');
    try {
      await agentToolService.disableAllToolsForAgent(agentId);

      // Refresh the list
      const agentToolsResponse = await agentToolService.listAgentTools(agentId);
      setAgentTools(agentToolsResponse.tools);
      onToolsChanged?.();
    } catch (err) {
      console.error('Failed to bulk disable tools:', err);
    } finally {
      setBulkOperation(null);
    }
  };

  const handleTagToggle = (tag: string) => {
    setSelectedTags(prev =>
      prev.includes(tag)
        ? prev.filter(t => t !== tag)
        : [...prev, tag]
    );
  };

  const clearFilters = () => {
    setSearchQuery('');
    setSelectedTags([]);
    setFilterStatus('all');
  };

  const enabledToolsCount = agentTools.filter(at => at.is_enabled).length;
  const disabledToolsCount = agentTools.filter(at => !at.is_enabled).length;
  const assignedToolsCount = agentTools.length;
  const availableToolsCount = allTools.length - assignedToolsCount;

  if (loading) {
    return (
      <div className="min-h-[400px] flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          <p className="mt-2 text-readout">Loading agent tools...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-[400px] flex items-center justify-center">
        <div className="text-center">
          <div className="text-error mb-4">
            <TriangleAlert className="h-7 w-7 mx-auto" />
          </div>
          <p className="text-error mb-4">{error}</p>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => window.location.reload()}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-base-100 rounded-lg border border-base-content/20">
      {/* Header */}
      <div className="p-6 border-b border-base-content/10">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-2xl font-bold text-base-content">Agent Tool Manager</h2>
            <p className="text-readout mt-1">
              Manage tools for agent: <span className="font-medium">{agentId}</span>
            </p>
          </div>
          <div className="flex gap-2">
            <div className="tooltip tooltip-top" data-tip={`Enable all ${disabledToolsCount} disabled tools`}>
              <button
                className="btn btn-success btn-sm"
                onClick={handleBulkEnable}
                disabled={bulkOperation === 'enable' || disabledToolsCount === 0}
              >
                {bulkOperation === 'enable' ? (
                  <>
                    <span className="loading loading-spinner loading-sm mr-2"></span>
                    Enabling...
                  </>
                ) : (
                  `Enable All (${disabledToolsCount})`
                )}
              </button>
            </div>
            <div className="tooltip tooltip-top" data-tip={`Disable all ${enabledToolsCount} enabled tools`}>
              <button
                className="btn btn-error btn-outline btn-sm"
                onClick={handleBulkDisable}
                disabled={bulkOperation === 'disable' || enabledToolsCount === 0}
              >
                {bulkOperation === 'disable' ? (
                  <>
                    <span className="loading loading-spinner loading-sm mr-2"></span>
                    Disabling...
                  </>
                ) : (
                  `Disable All (${enabledToolsCount})`
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Statistics */}
        <div className="flex gap-4 mt-3 text-xs">
          <div className="tooltip" data-tip="Tools assigned to this agent">
            <div className="flex items-center gap-1">
              <span className="text-readout">Assigned:</span>
              <span className="font-semibold">{assignedToolsCount}</span>
            </div>
          </div>
          <div className="tooltip" data-tip="Tools that are enabled">
            <div className="flex items-center gap-1">
              <span className="text-readout">Enabled:</span>
              <span className="font-semibold">{enabledToolsCount}</span>
            </div>
          </div>
          <div className="tooltip" data-tip="Tools that are disabled">
            <div className="flex items-center gap-1">
              <span className="text-readout">Disabled:</span>
              <span className="font-semibold">{disabledToolsCount}</span>
            </div>
          </div>
          <div className="tooltip" data-tip="Tools available to add">
            <div className="flex items-center gap-1">
              <span className="text-readout">Available:</span>
              <span className="font-semibold">{availableToolsCount}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="p-6 border-b border-base-content/10 bg-base-200/50">
        <div className="flex flex-col gap-3">
          {/* Search and Status Filter */}
          <div className="flex gap-3 items-center">
            {/* Search */}
            <div className="flex-1">
              <div className="relative">
                <SearchIcon className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-readout" />
                <input
                  type="text"
                  placeholder="Search tools by name, description, or tags..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="input input-bordered w-full pl-10 rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-input-bg)] border-[var(--form-input-border)] text-[var(--form-input-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                />
              </div>
            </div>

            {/* Status Filter */}
            <div className="flex btn-group">
              <button
                className={`btn btn-sm ${filterStatus === 'all' ? 'btn-active btn-selected' : 'btn-outline'}`}
                onClick={() => setFilterStatus('all')}
              >
                All
              </button>
              <button
                className={`btn btn-sm ${filterStatus === 'assigned' ? 'btn-active btn-selected' : 'btn-outline'}`}
                onClick={() => setFilterStatus('assigned')}
              >
                Assigned
              </button>
              <button
                className={`btn btn-sm ${filterStatus === 'available' ? 'btn-active btn-selected' : 'btn-outline'}`}
                onClick={() => setFilterStatus('available')}
              >
                Available
              </button>
            </div>

            {/* Tag Filter Dropdown */}
            <div className="relative">
              <button
                className={`btn btn-sm ${selectedTags.length > 0 ? 'btn-active btn-selected' : 'btn-outline'}`}
                onClick={() => setShowTagDropdown(!showTagDropdown)}
              >
                Tags
                {selectedTags.length > 0 && (
                  <span className="badge badge-xs badge-light ml-1">{selectedTags.length}</span>
                )}
              </button>
              
              {showTagDropdown && (
                <>
                  <div 
                    className="fixed inset-0 z-10" 
                    onClick={() => setShowTagDropdown(false)}
                  ></div>
                  <div className="absolute right-0 mt-2 w-64 max-h-80 overflow-y-auto bg-base-100 border border-base-300 rounded-lg shadow-lg z-20">
                    <div className="p-3 border-b border-base-300">
                      <div className="flex justify-between items-center">
                        <span className="font-semibold text-sm">Filter by Tags</span>
                        {selectedTags.length > 0 && (
                          <button
                            className="text-xs text-error hover:underline"
                            onClick={() => setSelectedTags([])}
                          >
                            Clear all
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="p-2 max-h-64 overflow-y-auto">
                      {allTags.length === 0 ? (
                        <p className="text-sm text-readout p-2">No tags available</p>
                      ) : (
                        allTags.map(tag => (
                          <label
                            key={tag}
                            className="flex items-center gap-2 p-2 hover:bg-base-200 rounded cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={selectedTags.includes(tag)}
                              onChange={() => handleTagToggle(tag)}
                              className="checkbox checkbox-sm checkbox-primary"
                            />
                            <span className="text-sm">{tag}</span>
                          </label>
                        ))
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Clear Filters */}
            {(searchQuery || selectedTags.length > 0 || filterStatus !== 'all') && (
              <button
                className="btn btn-sm btn-error btn-outline"
                onClick={clearFilters}
              >
                Clear
              </button>
            )}
          </div>

          {/* Active Tag Filters Display */}
          {selectedTags.length > 0 && (
            <div className="flex flex-wrap gap-2 items-center">
              <span className="text-sm text-readout">Active filters:</span>
              {selectedTags.map(tag => (
                <span
                  key={tag}
                  className="badge badge-primary badge-outline badge-sm gap-1"
                >
                  {tag}
                  <div className="tooltip tooltip-top" data-tip="Remove tag filter">
                    <button
                      className="btn btn-ghost btn-xs btn-circle"
                      onClick={() => handleTagToggle(tag)}
                    >
                      ×
                    </button>
                  </div>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Tools Table */}
      <div className="p-6">
        {filteredTools.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-readout mb-4">
              <Wrench className="h-10 w-10 mx-auto text-readout" />
            </div>
            <p className="text-readout mb-4">
              No tools match your filters
            </p>
            <button
              className="btn btn-sm btn-primary"
              onClick={clearFilters}
            >
              Clear Filters
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-base-content/10">
              <thead>
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-readout uppercase tracking-wider">Tool</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-readout uppercase tracking-wider w-24">Tags</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-readout uppercase tracking-wider w-28">Status</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-readout uppercase tracking-wider w-24">Priority</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-readout uppercase tracking-wider w-28">Config</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-readout uppercase tracking-wider w-32">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-base-content/10">
                {assignedTools.map(tool => (
                  <tr 
                    key={tool.id} 
                    className={`hover:bg-base-200/50 transition-colors border-l-2 ${tool.is_assigned ? 'bg-base-100 border-success' : 'opacity-50 bg-base-100/50 border-base-300'}`}
                  >
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2">
                        <ToolIcon name={tool.icon || undefined} className="h-4 w-4 text-readout" />
                        <div className="tooltip tooltip-right" data-tip={tool.description}>
                          <span className="font-medium text-base-content text-sm cursor-help hover:text-primary transition-colors">
                            {tool.name}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      {tool.tags && tool.tags.length > 0 ? (
                        <div className="tooltip" data-tip={tool.tags.join(', ')}>
                          <div className="flex items-center gap-1">
                            <Tags className="h-3 w-3 text-readout" />
                            <span className="badge badge-sm badge-ghost">{tool.tags.length}</span>
                          </div>
                        </div>
                      ) : (
                        <span className="text-readout text-xs">—</span>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      {tool.is_assigned ? (
                        <div className="tooltip" data-tip={tool.is_enabled ? 'Tool is enabled' : 'Tool is disabled'}>
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${tool.is_enabled ? 'bg-success/20 text-success' : 'bg-base-200 text-readout'}`}>
                            {tool.is_enabled ? '✓' : '○'}
                          </span>
                        </div>
                      ) : (
                        <div className="tooltip" data-tip='Tool not assigned to agent'>
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-info/20 text-info">
                            +
                          </span>
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      {tool.is_assigned ? (
                        <input
                          type="number"
                          min="0"
                          max="100"
                          value={tool.priority}
                          onChange={(e) => handleUpdatePriority(tool.id, parseInt(e.target.value) || 0)}
                          className="input input-bordered input-xs w-16"
                        />
                      ) : (
                        <span className="text-readout text-xs">—</span>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      {tool.is_assigned && tool.config_schema && Object.keys(tool.config_schema).length > 0 ? (
                        <div className="tooltip tooltip-left" data-tip="Configure tool">
                          <button
                            className="btn btn-ghost btn-xs"
                            onClick={() => tool.agentTool && handleOpenConfig(tool.agentTool)}
                          >
                            <Settings className="h-4 w-4" />
                          </button>
                        </div>
                      ) : (
                        <span className="text-readout text-xs">—</span>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex gap-1">
                        {tool.is_assigned ? (
                          tool.is_enabled ? (
                            <div className="tooltip tooltip-left" data-tip="Disable tool">
                              <button
                                className="btn btn-xs btn-error btn-ghost"
                                onClick={() => handleDisableTool(tool.id)}
                              >
                                <ToggleRight className="h-4 w-4" />
                              </button>
                            </div>
                          ) : (
                            <div className="tooltip tooltip-left" data-tip="Enable tool">
                              <button
                                className="btn btn-xs btn-success btn-ghost"
                                onClick={() => handleEnableTool(tool.id)}
                              >
                                <ToggleLeft className="h-4 w-4" />
                              </button>
                            </div>
                          )
                        ) : (
                          <div className="tooltip tooltip-left" data-tip="Add tool">
                            <button
                              className="btn btn-xs btn-primary btn-ghost"
                              onClick={() => handleEnableTool(tool.id)}
                            >
                              <Plus className="h-4 w-4" />
                            </button>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {filteredTools.length > 0 && (
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-base-content/10">
            <div className="text-sm text-readout">
              Showing {startIndex + 1}-{Math.min(endIndex, filteredTools.length)} of {filteredTools.length} tools
            </div>
            <div className="flex items-center gap-2">
              {/* Page Size Selector */}
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setCurrentPage(1);
                }}
                className="select select-bordered select-xs"
              >
                <option value={5}>5 / page</option>
                <option value={10}>10 / page</option>
                <option value={20}>20 / page</option>
                <option value={50}>50 / page</option>
              </select>

              {/* Pagination Buttons */}
              <div className="btn-group">
                <div className="tooltip tooltip-top" data-tip="First page">
                  <button
                    className="btn btn-xs"
                    onClick={() => setCurrentPage(1)}
                    disabled={currentPage === 1}
                    aria-label="First page"
                  >
                    ««
                  </button>
                </div>
                <div className="tooltip tooltip-top" data-tip="Previous page">
                  <button
                    className="btn btn-xs"
                    onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                    disabled={currentPage === 1}
                    aria-label="Previous page"
                  >
                    «
                  </button>
                </div>
                <span className="btn btn-xs btn-disabled">
                  Page {currentPage} of {totalPages || 1}
                </span>
                <div className="tooltip tooltip-top" data-tip="Next page">
                  <button
                    className="btn btn-xs"
                    onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                    disabled={currentPage === totalPages}
                    aria-label="Next page"
                  >
                    »
                  </button>
                </div>
                <div className="tooltip tooltip-top" data-tip="Last page">
                  <button
                    className="btn btn-xs"
                    onClick={() => setCurrentPage(totalPages)}
                    disabled={currentPage === totalPages}
                    aria-label="Last page"
                  >
                    »»
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {selectedTool && (
        <ToolConfigModal
          isOpen={configModalOpen}
          onClose={handleCloseConfig}
          onSave={handleSaveConfig}
          agentTool={selectedTool}
        />
      )}
    </div>
  );
};
