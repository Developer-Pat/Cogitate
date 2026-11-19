/**
 * Mock Data for Collections Feature
 * 
 * This file contains all mock data for testing the Collections UI.
 * No backend integration - pure frontend mock with zero side effects.
 * 
 * Usage:
 *   import { MOCK_COLLECTIONS } from '@/mocks/collectionsData'
 */

// ========== Types ==========

export type EntityType = 'agent' | 'tool' | 'provider' | 'macro_set' | 'template'

export interface CollectionItem {
  id: number
  entityId: string | number
  entityName: string
  entityType: string
  addedAt: string
}

export interface Collection {
  id: number
  name: string
  description: string
  entityType: EntityType
  color: string
  icon: string
  itemCount: number
  items: CollectionItem[]
  createdAt: string
  updatedAt: string
}

// ========== Mock Data ==========

export const MOCK_COLLECTIONS: Collection[] = [
  // ─────────────────────────────────────────────────────────────
  // TOOL COLLECTIONS
  // ─────────────────────────────────────────────────────────────
  {
    id: 1,
    name: 'Math Teaching Tools',
    description: 'Essential tools for math lessons and problem solving',
    entityType: 'tool',
    color: 'blue',
    icon: '🛠️',
    itemCount: 8,
    items: [
      { id: 1, entityId: 'calculator', entityName: 'Calculator', entityType: 'tool', addedAt: '2026-03-15' },
      { id: 2, entityId: 'graph-plotter', entityName: 'Graph Plotter', entityType: 'tool', addedAt: '2026-03-15' },
      { id: 3, entityId: 'equation-solver', entityName: 'Equation Solver', entityType: 'tool', addedAt: '2026-03-16' },
      { id: 4, entityId: 'geometry-tool', entityName: 'Geometry Tool', entityType: 'tool', addedAt: '2026-03-16' },
      { id: 5, entityId: 'statistics-calc', entityName: 'Statistics Calculator', entityType: 'tool', addedAt: '2026-03-17' },
      { id: 6, entityId: 'algebra-helper', entityName: 'Algebra Helper', entityType: 'tool', addedAt: '2026-03-17' },
      { id: 7, entityId: 'number-line', entityName: 'Number Line Visualizer', entityType: 'tool', addedAt: '2026-03-17' },
      { id: 8, entityId: 'fraction-tool', entityName: 'Fraction Calculator', entityType: 'tool', addedAt: '2026-03-17' },
    ],
    createdAt: '2026-03-01',
    updatedAt: '2026-03-17',
  },
  {
    id: 2,
    name: 'Writing & Research',
    description: 'Tools for writing assistance and research tasks',
    entityType: 'tool',
    color: 'purple',
    icon: '✍️',
    itemCount: 6,
    items: [
      { id: 1, entityId: 'grammar-checker', entityName: 'Grammar Checker', entityType: 'tool', addedAt: '2026-03-10' },
      { id: 2, entityId: 'thesaurus', entityName: 'Thesaurus', entityType: 'tool', addedAt: '2026-03-10' },
      { id: 3, entityId: 'citation-generator', entityName: 'Citation Generator', entityType: 'tool', addedAt: '2026-03-11' },
      { id: 4, entityId: 'plagiarism-checker', entityName: 'Plagiarism Checker', entityType: 'tool', addedAt: '2026-03-12' },
      { id: 5, entityId: 'summarizer', entityName: 'Text Summarizer', entityType: 'tool', addedAt: '2026-03-14' },
      { id: 6, entityId: 'outline-builder', entityName: 'Outline Builder', entityType: 'tool', addedAt: '2026-03-16' },
    ],
    createdAt: '2026-03-05',
    updatedAt: '2026-03-16',
  },
  {
    id: 3,
    name: 'Quick Utilities',
    description: 'Fast tools for everyday tasks',
    entityType: 'tool',
    color: 'green',
    icon: '⚡',
    itemCount: 5,
    items: [
      { id: 1, entityId: 'unit-converter', entityName: 'Unit Converter', entityType: 'tool', addedAt: '2026-03-08' },
      { id: 2, entityId: 'timer', entityName: 'Timer', entityType: 'tool', addedAt: '2026-03-08' },
      { id: 3, entityId: 'calendar', entityName: 'Calendar', entityType: 'tool', addedAt: '2026-03-09' },
      { id: 4, entityId: 'note-taker', entityName: 'Quick Notes', entityType: 'tool', addedAt: '2026-03-10' },
      { id: 5, entityId: 'translator', entityName: 'Translator', entityType: 'tool', addedAt: '2026-03-12' },
    ],
    createdAt: '2026-03-08',
    updatedAt: '2026-03-12',
  },
  {
    id: 4,
    name: 'Data Analysis',
    description: 'Tools for data processing and visualization',
    entityType: 'tool',
    color: 'orange',
    icon: '📊',
    itemCount: 7,
    items: [
      { id: 1, entityId: 'chart-maker', entityName: 'Chart Maker', entityType: 'tool', addedAt: '2026-03-05' },
      { id: 2, entityId: 'spreadsheet', entityName: 'Spreadsheet Tool', entityType: 'tool', addedAt: '2026-03-06' },
      { id: 3, entityId: 'data-cleaner', entityName: 'Data Cleaner', entityType: 'tool', addedAt: '2026-03-07' },
      { id: 4, entityId: 'pivot-table', entityName: 'Pivot Table Creator', entityType: 'tool', addedAt: '2026-03-08' },
      { id: 5, entityId: 'regression-tool', entityName: 'Regression Analyzer', entityType: 'tool', addedAt: '2026-03-10' },
      { id: 6, entityId: 'heatmap-generator', entityName: 'Heatmap Generator', entityType: 'tool', addedAt: '2026-03-12' },
      { id: 7, entityId: 'correlation-finder', entityName: 'Correlation Finder', entityType: 'tool', addedAt: '2026-03-15' },
    ],
    createdAt: '2026-03-05',
    updatedAt: '2026-03-15',
  },

  // ─────────────────────────────────────────────────────────────
  // TEAMS (Agent Collections)
  // ─────────────────────────────────────────────────────────────
  {
    id: 5,
    name: 'Daily Tutor Agents',
    description: 'My go-to agents for daily tutoring sessions',
    entityType: 'agent',
    color: 'blue',
    icon: '🤖',
    itemCount: 5,
    items: [
      { id: 1, entityId: 14, entityName: 'Math Tutor', entityType: 'agent', addedAt: '2026-03-10' },
      { id: 2, entityId: 23, entityName: 'Science Explainer', entityType: 'agent', addedAt: '2026-03-10' },
      { id: 3, entityId: 31, entityName: 'Writing Coach', entityType: 'agent', addedAt: '2026-03-11' },
      { id: 4, entityId: 42, entityName: 'History Guide', entityType: 'agent', addedAt: '2026-03-12' },
      { id: 5, entityId: 56, entityName: 'Language Partner', entityType: 'agent', addedAt: '2026-03-14' },
    ],
    createdAt: '2026-03-10',
    updatedAt: '2026-03-14',
  },
  {
    id: 6,
    name: 'Administrative Helpers',
    description: 'Agents for grading, scheduling, and admin tasks',
    entityType: 'agent',
    color: 'gray',
    icon: '📋',
    itemCount: 4,
    items: [
      { id: 1, entityId: 67, entityName: 'Grading Assistant', entityType: 'agent', addedAt: '2026-03-08' },
      { id: 2, entityId: 78, entityName: 'Email Drafter', entityType: 'agent', addedAt: '2026-03-09' },
      { id: 3, entityId: 89, entityName: 'Schedule Coordinator', entityType: 'agent', addedAt: '2026-03-11' },
      { id: 4, entityId: 91, entityName: 'Report Generator', entityType: 'agent', addedAt: '2026-03-13' },
    ],
    createdAt: '2026-03-08',
    updatedAt: '2026-03-13',
  },
  {
    id: 7,
    name: 'Creative Agents',
    description: 'Agents for brainstorming and creative work',
    entityType: 'agent',
    color: 'purple',
    icon: '🎨',
    itemCount: 6,
    items: [
      { id: 1, entityId: 102, entityName: 'Idea Generator', entityType: 'agent', addedAt: '2026-03-05' },
      { id: 2, entityId: 115, entityName: 'Story Builder', entityType: 'agent', addedAt: '2026-03-06' },
      { id: 3, entityId: 128, entityName: 'Poetry Assistant', entityType: 'agent', addedAt: '2026-03-07' },
      { id: 4, entityId: 134, entityName: 'Art Critic', entityType: 'agent', addedAt: '2026-03-09' },
      { id: 5, entityId: 147, entityName: 'Music Composer', entityType: 'agent', addedAt: '2026-03-11' },
      { id: 6, entityId: 159, entityName: 'Design Reviewer', entityType: 'agent', addedAt: '2026-03-15' },
    ],
    createdAt: '2026-03-05',
    updatedAt: '2026-03-15',
  },

  // ─────────────────────────────────────────────────────────────
  // PROVIDER COLLECTIONS
  // ─────────────────────────────────────────────────────────────
  {
    id: 8,
    name: 'Fast Local Providers',
    description: 'Quick responses for simple tasks - local models',
    entityType: 'provider',
    color: 'green',
    icon: '⚡',
    itemCount: 3,
    items: [
      { id: 1, entityId: 'ollama-llama3.2', entityName: 'Ollama (Llama 3.2)', entityType: 'provider', addedAt: '2026-03-08' },
      { id: 2, entityId: 'ollama-mistral', entityName: 'Ollama (Mistral)', entityType: 'provider', addedAt: '2026-03-08' },
      { id: 3, entityId: 'local-phi3', entityName: 'Phi-3 Local', entityType: 'provider', addedAt: '2026-03-10' },
    ],
    createdAt: '2026-03-08',
    updatedAt: '2026-03-10',
  },
  {
    id: 9,
    name: 'High Quality Providers',
    description: 'Best quality for complex reasoning tasks',
    entityType: 'provider',
    color: 'blue',
    icon: '💎',
    itemCount: 4,
    items: [
      { id: 1, entityId: 'openai-gpt4', entityName: 'OpenAI GPT-4', entityType: 'provider', addedAt: '2026-03-05' },
      { id: 2, entityId: 'anthropic-claude', entityName: 'Anthropic Claude', entityType: 'provider', addedAt: '2026-03-05' },
      { id: 3, entityId: 'google-gemini', entityName: 'Google Gemini Pro', entityType: 'provider', addedAt: '2026-03-07' },
      { id: 4, entityId: 'openai-gpt4-turbo', entityName: 'GPT-4 Turbo', entityType: 'provider', addedAt: '2026-03-12' },
    ],
    createdAt: '2026-03-05',
    updatedAt: '2026-03-12',
  },

  // ─────────────────────────────────────────────────────────────
  // MACRO SET COLLECTIONS
  // ─────────────────────────────────────────────────────────────
  {
    id: 10,
    name: 'Math Question Banks',
    description: 'Macro sets for different math topics',
    entityType: 'macro_set',
    color: 'orange',
    icon: '📝',
    itemCount: 4,
    items: [
      { id: 1, entityId: 'algebra-macros', entityName: 'Algebra Questions (F1-F5)', entityType: 'macro_set', addedAt: '2026-03-11' },
      { id: 2, entityId: 'geometry-macros', entityName: 'Geometry Questions (F6-F10)', entityType: 'macro_set', addedAt: '2026-03-11' },
      { id: 3, entityId: 'calculus-macros', entityName: 'Calculus Questions (F11-F15)', entityType: 'macro_set', addedAt: '2026-03-12' },
      { id: 4, entityId: 'statistics-macros', entityName: 'Statistics Questions (F16-F20)', entityType: 'macro_set', addedAt: '2026-03-14' },
    ],
    createdAt: '2026-03-11',
    updatedAt: '2026-03-14',
  },
  {
    id: 11,
    name: 'Writing Assistants',
    description: 'Macros for grammar, style, and clarity',
    entityType: 'macro_set',
    color: 'purple',
    icon: '✍️',
    itemCount: 3,
    items: [
      { id: 1, entityId: 'grammar-macros', entityName: 'Grammar Check Macros', entityType: 'macro_set', addedAt: '2026-03-09' },
      { id: 2, entityId: 'style-macros', entityName: 'Style Improvement Macros', entityType: 'macro_set', addedAt: '2026-03-10' },
      { id: 3, entityId: 'clarity-macros', entityName: 'Clarity Enhancement Macros', entityType: 'macro_set', addedAt: '2026-03-12' },
    ],
    createdAt: '2026-03-09',
    updatedAt: '2026-03-12',
  },
]

// ========== Helper Functions ==========

/**
 * Get collections filtered by entity type
 */
export function getCollectionsByType(entityType: EntityType | 'all'): Collection[] {
  if (entityType === 'all') {
    return MOCK_COLLECTIONS
  }
  return MOCK_COLLECTIONS.filter(c => c.entityType === entityType)
}

/**
 * Get a single collection by ID
 */
export function getCollectionById(id: number): Collection | undefined {
  return MOCK_COLLECTIONS.find(c => c.id === id)
}

/**
 * Get collections that contain a specific entity
 */
export function getCollectionsContainingEntity(
  entityType: string,
  entityId: string | number
): Collection[] {
  return MOCK_COLLECTIONS.filter(collection =>
    collection.items.some(
      item => item.entityType === entityType && item.entityId === entityId
    )
  )
}

/**
 * Get recent collections (by updatedAt)
 */
export function getRecentCollections(limit: number = 3): Collection[] {
  return [...MOCK_COLLECTIONS]
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    .slice(0, limit)
}

/**
 * Search collections by name or description
 */
export function searchCollections(query: string): Collection[] {
  const lowerQuery = query.toLowerCase()
  return MOCK_COLLECTIONS.filter(
    c =>
      c.name.toLowerCase().includes(lowerQuery) ||
      c.description.toLowerCase().includes(lowerQuery)
  )
}
