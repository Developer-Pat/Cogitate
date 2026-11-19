/**
 * ToolService - Manage tool definitions and registry.
 * 
 * Provides API client for tool management endpoints.
 */

import type {
  ToolCreate,
  ToolUpdate,
  ToolResponse,
  ToolListResponse,
  ToolSearchResponse,
  ToolFilters,
} from '@/types/tools';
import { apiClient } from '../apiClient';
import { frontendLoggingService } from '../frontendLoggingService';

/**
 * ToolService - Manage tool definitions
 */
export class ToolService {
  private basePath = '/api/v1/tools';
  private toolsCache: ToolResponse[] | null = null;
  private cacheTimestamp: number | null = null;
  private readonly CACHE_TTL = 5 * 60 * 1000; // 5 minutes

  /**
   * List tools with optional filters
   */
  async listTools(filters: ToolFilters = {}): Promise<ToolListResponse> {
    const {
      category_id,
      is_active,
      provider,
      tags,
      query,
      limit = 100,
      offset = 0,
    } = filters;

    // Use cache for basic listings without filters
    const useCache = !category_id && !is_active && !provider && !tags && !query && offset === 0;
    
    if (useCache && this.toolsCache && this.cacheTimestamp) {
      const now = Date.now();
      if (now - this.cacheTimestamp < this.CACHE_TTL) {
        frontendLoggingService.debug('ToolService', 'Returning cached tools', {
          count: this.toolsCache.length
        });
        return {
          tools: this.toolsCache,
          total: this.toolsCache.length
        };
      }
    }

    try {
      const params = new URLSearchParams();
      if (category_id) params.append('category_id', category_id);
      if (is_active !== undefined) params.append('is_active', is_active.toString());
      if (provider) params.append('provider', provider);
      if (tags && tags.length > 0) params.append('tags', tags.join(','));
      if (limit !== undefined) params.append('limit', limit.toString());
      if (offset !== undefined) params.append('offset', offset.toString());

      const queryString = params.toString();
      const endpoint = query ? `${this.basePath}/search?query=${encodeURIComponent(query)}&${queryString}`
                            : `${this.basePath}?${queryString}`;

      const response = await apiClient.get<ToolListResponse | ToolSearchResponse>(endpoint);
      
      if (!response.error && response.data) {
        const tools = 'tools' in response.data ? response.data.tools : [];
        
        // Update cache for basic listings
        if (useCache && !query) {
          this.toolsCache = tools;
          this.cacheTimestamp = Date.now();
        }

        return {
          tools,
          total: 'total' in response.data ? response.data.total : tools.length
        };
      }

      throw new Error(response.error?.message || 'Failed to fetch tools');
    } catch (error) {
      frontendLoggingService.error('ToolService', 'Failed to list tools', error);
      throw error;
    }
  }

  /**
   * Get a tool by ID
   */
  async getTool(toolId: string): Promise<ToolResponse> {
    try {
      const response = await apiClient.get<ToolResponse>(`${this.basePath}/${toolId}`);
      
      if (!response.error && response.data) {
        return response.data;
      }

      throw new Error(response.error?.message || `Tool not found: ${toolId}`);
    } catch (error) {
      frontendLoggingService.error('ToolService', `Failed to get tool ${toolId}`, error);
      throw error;
    }
  }

  /**
   * Get a tool by slug
   */
  async getToolBySlug(slug: string): Promise<ToolResponse> {
    try {
      const response = await apiClient.get<ToolResponse>(`${this.basePath}/slug/${slug}`);
      
      if (!response.error && response.data) {
        return response.data;
      }

      throw new Error(response.error?.message || `Tool not found with slug: ${slug}`);
    } catch (error) {
      frontendLoggingService.error('ToolService', `Failed to get tool by slug ${slug}`, error);
      throw error;
    }
  }

  /**
   * Create a new tool
   */
  async createTool(toolData: ToolCreate): Promise<ToolResponse> {
    try {
      const response = await apiClient.post<ToolResponse>(this.basePath, toolData);
      
      if (!response.error && response.data) {
        // Invalidate cache
        this.toolsCache = null;
        this.cacheTimestamp = null;
        
        frontendLoggingService.info('ToolService', `Created tool: ${toolData.name}`, {
          toolId: response.data.id
        });
        
        return response.data;
      }

      throw new Error(response.error?.message || 'Failed to create tool');
    } catch (error) {
      frontendLoggingService.error('ToolService', 'Failed to create tool', error);
      throw error;
    }
  }

  /**
   * Update a tool
   */
  async updateTool(toolId: string, toolData: ToolUpdate): Promise<ToolResponse> {
    try {
      const response = await apiClient.put<ToolResponse>(`${this.basePath}/${toolId}`, toolData);
      
      if (!response.error && response.data) {
        // Invalidate cache
        this.toolsCache = null;
        this.cacheTimestamp = null;
        
        frontendLoggingService.info('ToolService', `Updated tool: ${toolId}`);
        
        return response.data;
      }

      throw new Error(response.error?.message || `Failed to update tool: ${toolId}`);
    } catch (error) {
      frontendLoggingService.error('ToolService', `Failed to update tool ${toolId}`, error);
      throw error;
    }
  }

  /**
   * Delete a tool
   */
  async deleteTool(toolId: string): Promise<void> {
    try {
      const response = await apiClient.delete(`${this.basePath}/${toolId}`);
      
      if (!response.error) {
        // Invalidate cache
        this.toolsCache = null;
        this.cacheTimestamp = null;
        
        frontendLoggingService.info('ToolService', `Deleted tool: ${toolId}`);
        return;
      }

      throw new Error(response.error?.message || `Failed to delete tool: ${toolId}`);
    } catch (error) {
      frontendLoggingService.error('ToolService', `Failed to delete tool ${toolId}`, error);
      throw error;
    }
  }

  /**
   * Search tools by query
   */
  async searchTools(query: string, categoryId?: string, limit: number = 20): Promise<ToolResponse[]> {
    try {
      const params = new URLSearchParams();
      params.append('query', query);
      if (categoryId) params.append('category_id', categoryId);
      params.append('limit', limit.toString());

      const response = await apiClient.get<ToolSearchResponse>(`${this.basePath}/search?${params.toString()}`);
      
      if (!response.error && response.data) {
        return response.data.tools;
      }

      throw new Error(response.error?.message || 'Failed to search tools');
    } catch (error) {
      frontendLoggingService.error('ToolService', `Failed to search tools: ${query}`, error);
      throw error;
    }
  }

  /**
   * Get active tools (convenience method)
   */
  async getActiveTools(): Promise<ToolResponse[]> {
    const response = await this.listTools({ is_active: true });
    return response.tools;
  }

  /**
   * Get built-in tools (convenience method)
   */
  async getBuiltinTools(): Promise<ToolResponse[]> {
    const response = await this.listTools({ is_active: true });
    return response.tools.filter(tool => tool.is_builtin);
  }

  /**
   * Get tools by category (convenience method)
   */
  async getToolsByCategory(categoryId: string): Promise<ToolResponse[]> {
    const response = await this.listTools({ category_id: categoryId, is_active: true });
    return response.tools;
  }

  /**
   * Get tools by tags (convenience method)
   */
  async getToolsByTags(tags: string[]): Promise<ToolResponse[]> {
    const response = await this.listTools({ tags, is_active: true });
    return response.tools;
  }

  /**
   * Clear cache
   */
  clearCache(): void {
    this.toolsCache = null;
    this.cacheTimestamp = null;
    frontendLoggingService.debug('ToolService', 'Cache cleared');
  }
}

// Export singleton instance
export const toolService = new ToolService();