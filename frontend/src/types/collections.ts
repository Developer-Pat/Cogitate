/**
 * Collections domain types.
 *
 * TypeScript interfaces for collection management.
 */

/**
 * Entity types that can be added to collections.
 */
export type CollectionEntityType = 'agent' | 'tool' | 'provider' | 'macro_set' | 'template' | 'workflow';

/**
 * Represents a collection of entities.
 */
export interface Collection {
  id: string;
  name: string;
  description: string | null;
  entity_type: CollectionEntityType;
  color: string;
  icon: string;
  user_key: string;
  is_active: boolean;
  item_count: number;
  items: CollectionItem[];
  created_at: string;
  updated_at: string;
}

/**
 * Represents an item within a collection.
 */
export interface CollectionItem {
  id: string;
  collection_id: string;
  entity_id: string;
  entity_type: CollectionEntityType;
  entity_name: string;
  added_at: string;
}

/**
 * Request payload for creating a collection.
 */
export interface CollectionCreate {
  name: string;
  description?: string;
  entity_type: CollectionEntityType;
  color?: string;
  icon?: string;
  user_key?: string;
}

/**
 * Request payload for updating a collection.
 */
export interface CollectionUpdate {
  name?: string;
  description?: string;
  color?: string;
  icon?: string;
  is_active?: boolean;
}

/**
 * Request payload for adding an item to a collection.
 */
export interface CollectionItemCreate {
  entity_id: string;
  entity_type: CollectionEntityType;
  entity_name: string;
}

/**
 * Response for listing collections.
 */
export interface CollectionListResponse {
  collections: Collection[];
  total: number;
}

/**
 * Response for checking which collections contain an entity.
 */
export interface CollectionContainsResponse {
  collections: Collection[];
  total: number;
}

/**
 * Filters for listing collections.
 */
export interface CollectionFilters {
  entity_type?: CollectionEntityType;
  search?: string;
  is_active?: boolean;
  limit?: number;
  offset?: number;
}
