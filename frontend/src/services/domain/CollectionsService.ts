/**
 * CollectionsService - Manage collections and collection items.
 *
 * Provides API client for collection management endpoints.
 */

import type {
  Collection,
  CollectionCreate,
  CollectionUpdate,
  CollectionItem,
  CollectionItemCreate,
  CollectionListResponse,
  CollectionContainsResponse,
  CollectionFilters,
} from '@/types/collections';
import { apiClient } from '../apiClient';
import { frontendLoggingService } from '../frontendLoggingService';

/**
 * CollectionsService - Manage collections
 */
export class CollectionsService {
  private basePath = '/api/v1/collections';
  private collectionsCache: Collection[] | null = null;
  private cacheTimestamp: number | null = null;
  private readonly CACHE_TTL = 2 * 60 * 1000; // 2 minutes

  /**
   * List all collections with optional filters.
   */
  async listCollections(filters: CollectionFilters = {}): Promise<CollectionListResponse> {
    const {
      entity_type,
      search,
      is_active,
      limit = 100,
      offset = 0,
    } = filters;

    // Use cache for basic listings without filters
    const useCache = !entity_type && !search && is_active === undefined && offset === 0;

    if (useCache && this.collectionsCache && this.cacheTimestamp) {
      const now = Date.now();
      if (now - this.cacheTimestamp < this.CACHE_TTL) {
        frontendLoggingService.debug('CollectionsService', 'Returning cached collections', {
          count: this.collectionsCache.length
        });
        return {
          collections: this.collectionsCache,
          total: this.collectionsCache.length
        };
      }
    }

    try {
      const params = new URLSearchParams();
      if (entity_type) params.append('entity_type', entity_type);
      if (search) params.append('search', search);
      if (is_active !== undefined) params.append('is_active', is_active.toString());
      if (limit !== undefined) params.append('limit', limit.toString());
      if (offset !== undefined) params.append('offset', offset.toString());

      const queryString = params.toString();
      const endpoint = `${this.basePath}${queryString ? `?${queryString}` : ''}`;

      const response = await apiClient.get<CollectionListResponse>(endpoint);

      if (response.error) {
        frontendLoggingService.error('CollectionsService', 'Failed to list collections', response.error);
        throw new Error(response.error.message);
      }

      const result = response.data!;

      // Update cache for basic listings
      if (useCache) {
        this.collectionsCache = result.collections;
        this.cacheTimestamp = Date.now();
      }

      frontendLoggingService.debug('CollectionsService', `Listed ${result.total} collections`, {
        total: result.total,
        filters
      });

      return result;
    } catch (error) {
      frontendLoggingService.error('CollectionsService', 'Failed to list collections', error);
      throw error;
    }
  }

  /**
   * Get a single collection by ID.
   */
  async getCollection(collectionId: string): Promise<Collection> {
    try {
      const response = await apiClient.get<Collection>(`${this.basePath}/${collectionId}`);

      if (response.error) {
        frontendLoggingService.error('CollectionsService', 'Failed to get collection', response.error);
        throw new Error(response.error.message);
      }

      frontendLoggingService.debug('CollectionsService', 'Got collection', {
        collectionId,
        name: response.data?.name
      });

      return response.data!;
    } catch (error) {
      frontendLoggingService.error('CollectionsService', 'Failed to get collection', error);
      throw error;
    }
  }

  /**
   * Create a new collection.
   */
  async createCollection(collectionData: CollectionCreate): Promise<Collection> {
    try {
      const response = await apiClient.post<Collection>(this.basePath, collectionData);

      if (response.error) {
        frontendLoggingService.error('CollectionsService', 'Failed to create collection', response.error);
        throw new Error(response.error.message);
      }

      // Invalidate cache
      this.invalidateCache();

      frontendLoggingService.info('CollectionsService', 'Created collection', {
        collectionId: response.data?.id,
        name: response.data?.name
      });

      return response.data!;
    } catch (error) {
      frontendLoggingService.error('CollectionsService', 'Failed to create collection', error);
      throw error;
    }
  }

  /**
   * Update an existing collection.
   */
  async updateCollection(
    collectionId: string,
    collectionData: CollectionUpdate
  ): Promise<Collection> {
    try {
      const response = await apiClient.put<Collection>(`${this.basePath}/${collectionId}`, collectionData);

      if (response.error) {
        frontendLoggingService.error('CollectionsService', 'Failed to update collection', response.error);
        throw new Error(response.error.message);
      }

      // Invalidate cache
      this.invalidateCache();

      frontendLoggingService.info('CollectionsService', 'Updated collection', {
        collectionId,
        ...collectionData
      });

      return response.data!;
    } catch (error) {
      frontendLoggingService.error('CollectionsService', 'Failed to update collection', error);
      throw error;
    }
  }

  /**
   * Delete a collection.
   */
  async deleteCollection(collectionId: string): Promise<void> {
    try {
      const response = await apiClient.delete(`${this.basePath}/${collectionId}`);

      if (response.error) {
        frontendLoggingService.error('CollectionsService', 'Failed to delete collection', response.error);
        throw new Error(response.error.message);
      }

      // Invalidate cache
      this.invalidateCache();

      frontendLoggingService.info('CollectionsService', 'Deleted collection', {
        collectionId
      });
    } catch (error) {
      frontendLoggingService.error('CollectionsService', 'Failed to delete collection', error);
      throw error;
    }
  }

  /**
   * Add an item to a collection.
   */
  async addItemToCollection(
    collectionId: string,
    itemData: CollectionItemCreate
  ): Promise<CollectionItem> {
    try {
      const response = await apiClient.post<CollectionItem>(
        `${this.basePath}/${collectionId}/items`,
        itemData
      );

      if (response.error) {
        frontendLoggingService.error('CollectionsService', 'Failed to add item to collection', response.error);
        throw new Error(response.error.message);
      }

      // Invalidate cache
      this.invalidateCache();

      frontendLoggingService.info('CollectionsService', 'Added item to collection', {
        collectionId,
        entityId: itemData.entity_id,
        entityName: itemData.entity_name
      });

      return response.data!;
    } catch (error) {
      frontendLoggingService.error('CollectionsService', 'Failed to add item to collection', error);
      throw error;
    }
  }

  /**
   * Remove an item from a collection.
   */
  async removeItemFromCollection(
    collectionId: string,
    itemId: string
  ): Promise<void> {
    try {
      const response = await apiClient.delete(`${this.basePath}/${collectionId}/items/${itemId}`);

      if (response.error) {
        frontendLoggingService.error('CollectionsService', 'Failed to remove item from collection', response.error);
        throw new Error(response.error.message);
      }

      // Invalidate cache
      this.invalidateCache();

      frontendLoggingService.info('CollectionsService', 'Removed item from collection', {
        collectionId,
        itemId
      });
    } catch (error) {
      frontendLoggingService.error('CollectionsService', 'Failed to remove item from collection', error);
      throw error;
    }
  }

  /**
   * Get all items in a collection.
   */
  async getCollectionItems(collectionId: string): Promise<CollectionItem[]> {
    try {
      const response = await apiClient.get<CollectionItem[]>(`${this.basePath}/${collectionId}/items`);

      if (response.error) {
        frontendLoggingService.error('CollectionsService', 'Failed to get collection items', response.error);
        throw new Error(response.error.message);
      }

      frontendLoggingService.debug('CollectionsService', 'Got collection items', {
        collectionId,
        count: response.data?.length
      });

      return response.data!;
    } catch (error) {
      frontendLoggingService.error('CollectionsService', 'Failed to get collection items', error);
      throw error;
    }
  }

  /**
   * Find all collections containing a specific entity.
   */
  async findCollectionsContainingEntity(
    entityType: string,
    entityId: string
  ): Promise<CollectionContainsResponse> {
    try {
      const response = await apiClient.get<CollectionContainsResponse>(
        `${this.basePath}/contains/${entityType}/${entityId}`
      );

      if (response.error) {
        frontendLoggingService.error('CollectionsService', 'Failed to find collections containing entity', response.error);
        throw new Error(response.error.message);
      }

      frontendLoggingService.debug('CollectionsService', 'Found collections containing entity', {
        entityType,
        entityId,
        count: response.data?.total
      });

      return response.data!;
    } catch (error) {
      frontendLoggingService.error('CollectionsService', 'Failed to find collections containing entity', error);
      throw error;
    }
  }

  /**
   * Check if an entity is in any collections.
   */
  async isEntityInAnyCollection(
    entityType: string,
    entityId: string
  ): Promise<boolean> {
    try {
      const result = await this.findCollectionsContainingEntity(entityType, entityId);
      return result.total > 0;
    } catch (error) {
      frontendLoggingService.error('CollectionsService', 'Failed to check entity in collections', error);
      return false;
    }
  }

  /**
   * Invalidate the collections cache.
   */
  private invalidateCache(): void {
    this.collectionsCache = null;
    this.cacheTimestamp = null;
    frontendLoggingService.debug('CollectionsService', 'Cache invalidated');
  }

  /**
   * Clear the collections cache.
   */
  clearCache(): void {
    this.invalidateCache();
  }
}

// Create and export a singleton instance
export const collectionsService = new CollectionsService();

export default collectionsService;
