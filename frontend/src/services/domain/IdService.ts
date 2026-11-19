/**
 * IdService - Centralized ID conversion and management
 *
 * Provides a single source of truth for all ID conversions between
 * backend (numeric integer) and frontend (string) formats.
 *
 * @example
 * ```typescript
 * import { IdService } from './IdService'
 *
 * // Convert backend ID to frontend format
 * const frontendId = IdService.toFrontend(123)  // '123'
 *
 * // Convert frontend ID to backend format
 * const backendId = IdService.toBackend('123')  // 123
 *
 * // Generate temporary session ID
 * const tempId = IdService.generateTempId()  // 'session-1710614400000-abc123'
 *
 * // Check if ID is temporary
 * IdService.isTempId('session-123-abc')  // true
 * IdService.isTempId('123')  // false
 *
 * // Compare IDs regardless of type
 * IdService.equals(123, '123')  // true
 * IdService.equals('123', '123')  // true
 * ```
 */

const TEMP_ID_PREFIX = 'session-'

/**
 * Generate a random suffix for temporary IDs
 */
function generateRandomSuffix(): string {
  return Math.random().toString(36).substring(2, 8)
}

export class IdService {
  /**
   * Convert backend ID to frontend ID (always returns string)
   *
   * @param backendId - Backend ID (number or string)
   * @returns Frontend ID as string
   */
  static toFrontend(backendId: number | string | null | undefined): string {
    if (backendId === null || backendId === undefined) {
      return ''
    }
    return String(backendId)
  }

  /**
   * Convert frontend ID to backend ID (returns number for backend API)
   *
   * @param frontendId - Frontend ID as string
   * @returns Backend ID as number
   * @throws Error if ID cannot be converted to number (e.g., temp IDs)
   */
  static toBackend(frontendId: string): number {
    // Check if this is a temp ID - cannot convert to backend format
    if (this.isTempId(frontendId)) {
      throw new Error(`Cannot convert temporary ID to backend format: ${frontendId}`)
    }

    const parsed = parseInt(frontendId, 10)
    if (isNaN(parsed)) {
      throw new Error(`Invalid ID format, cannot convert to number: ${frontendId}`)
    }
    return parsed
  }

  /**
   * Generate temporary session ID
   *
   * @returns Temporary session ID in format 'session-{timestamp}-{random}'
   */
  static generateTempId(): string {
    return `${TEMP_ID_PREFIX}${Date.now()}-${generateRandomSuffix()}`
  }

  /**
   * Check if ID is temporary (not yet synced to backend)
   *
   * @param id - ID to check
   * @returns True if ID is temporary
   */
  static isTempId(id: string | number | null | undefined): boolean {
    if (id === null || id === undefined) {
      return false
    }
    return String(id).startsWith(TEMP_ID_PREFIX)
  }

  /**
   * Compare two IDs for equality (handles type conversion)
   *
   * @param id1 - First ID
   * @param id2 - Second ID
   * @returns True if IDs are equal
   */
  static equals(id1: string | number | null | undefined, id2: string | number | null | undefined): boolean {
    // Handle null/undefined
    if (id1 === null || id1 === undefined || id2 === null || id2 === undefined) {
      return id1 === id2
    }

    // Convert both to strings for comparison
    return String(id1) === String(id2)
  }

  /**
   * Safely parse a frontend ID to backend format
   * Returns null if conversion fails (instead of throwing)
   *
   * @param frontendId - Frontend ID as string
   * @returns Backend ID as number, or null if conversion fails
   */
  static tryToBackend(frontendId: string): number | null {
    try {
      return this.toBackend(frontendId)
    } catch {
      return null
    }
  }
}

export default IdService
