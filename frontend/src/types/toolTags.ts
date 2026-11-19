/**
 * Tool Tagging System
 *
 * Defines tag categories, colors, and utilities for tool tagging.
 */

/**
 * Tag categories for color coding
 */
export type TagCategory = 'operation' | 'purpose' | 'source' | 'complexity' | 'format';

/**
 * Known operation tags
 */
export const OPERATION_TAGS = [
  'op:read',
  'op:write',
  'op:execute',
  'op:transform',
  'op:create',
  'op:delete',
  'op:search',
  'op:communicate',
] as const;

/**
 * Known purpose tags
 */
export const PURPOSE_TAGS = [
  'purpose:productivity',
  'purpose:development',
  'purpose:system',
  'purpose:communication',
  'purpose:research',
  'purpose:analysis',
  'purpose:automation',
  'purpose:organization',
] as const;

/**
 * Known source tags
 */
export const SOURCE_TAGS = [
  'source:local-file',
  'source:clipboard',
  'source:system',
  'source:internet',
  'source:memory',
  'source:database',
  'source:api',
] as const;

/**
 * Known complexity tags
 */
export const COMPLEXITY_TAGS = [
  'safe',
  'stateful',
  'side-effects',
  'destructive',
  'external',
] as const;

/**
 * Known format tags
 */
export const FORMAT_TAGS = [
  'text',
  'json',
  'file',
  'structured',
  'binary',
] as const;

/**
 * All known tags
 */
export const KNOWN_TAGS = [
  ...OPERATION_TAGS,
  ...PURPOSE_TAGS,
  ...SOURCE_TAGS,
  ...COMPLEXITY_TAGS,
  ...FORMAT_TAGS,
];

/**
 * Tag category mapping
 */
export const TAG_CATEGORIES: Record<string, TagCategory> = {
  // Operation tags
  'op:read': 'operation',
  'op:write': 'operation',
  'op:execute': 'operation',
  'op:transform': 'operation',
  'op:create': 'operation',
  'op:delete': 'operation',
  'op:search': 'operation',
  'op:communicate': 'operation',
  
  // Purpose tags
  'purpose:productivity': 'purpose',
  'purpose:development': 'purpose',
  'purpose:system': 'purpose',
  'purpose:communication': 'purpose',
  'purpose:research': 'purpose',
  'purpose:analysis': 'purpose',
  'purpose:automation': 'purpose',
  'purpose:organization': 'purpose',
  
  // Source tags
  'source:local-file': 'source',
  'source:clipboard': 'source',
  'source:system': 'source',
  'source:internet': 'source',
  'source:memory': 'source',
  'source:database': 'source',
  'source:api': 'source',
  
  // Complexity tags
  'safe': 'complexity',
  'stateful': 'complexity',
  'side-effects': 'complexity',
  'destructive': 'complexity',
  'external': 'complexity',
  
  // Format tags
  'text': 'format',
  'json': 'format',
  'file': 'format',
  'structured': 'format',
  'binary': 'format',
};

/**
 * Get DaisyUI badge class for tag based on category
 */
export function getTagBadgeClass(tag: string): string {
  const category = TAG_CATEGORIES[tag] || getTagCategory(tag);
  
  switch (category) {
    case 'operation':
      return 'badge-info';
    case 'purpose':
      return 'badge-success';
    case 'source':
      return 'badge-secondary';
    case 'complexity':
      return 'badge-warning';
    case 'format':
      return 'badge-ghost';
    default:
      return 'badge-ghost';
  }
}

/**
 * Get tag category from tag name (with prefix detection)
 */
export function getTagCategory(tag: string): TagCategory {
  if (tag.startsWith('op:')) return 'operation';
  if (tag.startsWith('purpose:')) return 'purpose';
  if (tag.startsWith('source:')) return 'source';
  if (tag.startsWith('format:')) return 'format';
  return 'complexity'; // Default for unprefixed tags
}

/**
 * Get display label for tag (removes prefix)
 */
export function getTagLabel(tag: string): string {
  // Remove prefix for display
  if (tag.includes(':')) {
    return tag.split(':')[1];
  }
  return tag;
}

/**
 * Get tooltip description for tag
 */
export function getTagDescription(tag: string): string {
  const descriptions: Record<string, string> = {
    // Operation
    'op:read': 'Read-only operations',
    'op:write': 'Modifies data or state',
    'op:execute': 'Runs computations',
    'op:transform': 'Transforms input to output',
    'op:create': 'Creates new resources',
    'op:delete': 'Removes resources',
    'op:search': 'Search or query operations',
    'op:communicate': 'External communication',
    
    // Purpose
    'purpose:productivity': 'General productivity',
    'purpose:development': 'Coding and development',
    'purpose:system': 'System operations',
    'purpose:communication': 'Messaging and notifications',
    'purpose:research': 'Information gathering',
    'purpose:analysis': 'Data analysis',
    'purpose:automation': 'Task automation',
    'purpose:organization': 'Organizing information',
    
    // Source
    'source:local-file': 'Local filesystem',
    'source:clipboard': 'System clipboard',
    'source:system': 'System APIs',
    'source:internet': 'Web/online services',
    'source:memory': 'In-memory state',
    'source:database': 'Database queries',
    'source:api': 'External APIs',
    
    // Complexity
    'safe': 'No side effects, reversible',
    'stateful': 'Maintains state',
    'side-effects': 'Has external effects',
    'destructive': 'Can delete or destroy',
    'external': 'Calls external services',
    
    // Format
    'text': 'Text input/output',
    'json': 'JSON processing',
    'file': 'File-based',
    'structured': 'Structured data',
    'binary': 'Binary data',
  };
  
  return descriptions[tag] || 'Custom tag';
}

/**
 * Filter tags by category
 */
export function filterTagsByCategory(tags: string[], category: TagCategory): string[] {
  return tags.filter(tag => getTagCategory(tag) === category);
}

/**
 * Check if tag is known
 */
export function isKnownTag(tag: string): boolean {
  return (KNOWN_TAGS as readonly string[]).includes(tag);
}

/**
 * Group tags by category
 */
export function groupTagsByCategory(tags: string[]): Record<TagCategory, string[]> {
  const grouped: Record<string, string[]> = {
    operation: [],
    purpose: [],
    source: [],
    complexity: [],
    format: [],
  };
  
  tags.forEach(tag => {
    const category = getTagCategory(tag);
    if (!grouped[category]) {
      grouped[category] = [];
    }
    grouped[category].push(tag);
  });
  
  return grouped as Record<TagCategory, string[]>;
}
