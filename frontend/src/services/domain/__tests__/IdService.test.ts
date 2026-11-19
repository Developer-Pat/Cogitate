import { describe, it, expect } from 'vitest'
import { IdService } from '../IdService'

describe('IdService', () => {
  describe('toFrontend', () => {
    it('should convert number to string', () => {
      expect(IdService.toFrontend(123)).toBe('123')
      expect(IdService.toFrontend(1)).toBe('1')
      expect(IdService.toFrontend(0)).toBe('0')
    })

    it('should return string as-is', () => {
      expect(IdService.toFrontend('123')).toBe('123')
      expect(IdService.toFrontend('abc')).toBe('abc')
      expect(IdService.toFrontend('session-123-abc')).toBe('session-123-abc')
    })

    it('should handle null and undefined', () => {
      expect(IdService.toFrontend(null)).toBe('')
      expect(IdService.toFrontend(undefined)).toBe('')
    })

    it('should handle large numbers', () => {
      expect(IdService.toFrontend(999999999)).toBe('999999999')
    })
  })

  describe('toBackend', () => {
    it('should convert numeric string to number', () => {
      expect(IdService.toBackend('123')).toBe(123)
      expect(IdService.toBackend('1')).toBe(1)
      expect(IdService.toBackend('0')).toBe(0)
    })

    it('should throw error for temp IDs', () => {
      expect(() => IdService.toBackend('session-123-abc')).toThrow(
        'Cannot convert temporary ID to backend format: session-123-abc'
      )
      expect(() => IdService.toBackend('session-1710614400000-xyz')).toThrow(
        'Cannot convert temporary ID to backend format'
      )
    })

    it('should throw error for non-numeric strings', () => {
      expect(() => IdService.toBackend('abc')).toThrow(
        'Invalid ID format, cannot convert to number: abc'
      )
      expect(() => IdService.toBackend('')).toThrow(
        'Invalid ID format, cannot convert to number'
      )
    })
  })

  describe('generateTempId', () => {
    it('should generate ID with session- prefix', () => {
      const tempId = IdService.generateTempId()
      expect(tempId).toMatch(/^session-\d+-[a-z0-9]+$/)
    })

    it('should generate unique IDs', () => {
      const id1 = IdService.generateTempId()
      const id2 = IdService.generateTempId()
      // IDs should be different (random suffix)
      expect(id1).not.toBe(id2)
    })

    it('should generate IDs that are recognized as temp IDs', () => {
      const tempId = IdService.generateTempId()
      expect(IdService.isTempId(tempId)).toBe(true)
    })
  })

  describe('isTempId', () => {
    it('should return true for temp IDs', () => {
      expect(IdService.isTempId('session-123-abc')).toBe(true)
      expect(IdService.isTempId('session-1710614400000-xyz')).toBe(true)
    })

    it('should return false for numeric IDs', () => {
      expect(IdService.isTempId('123')).toBe(false)
      expect(IdService.isTempId('1')).toBe(false)
    })

    it('should return false for numeric input', () => {
      expect(IdService.isTempId(123)).toBe(false)
      expect(IdService.isTempId(1)).toBe(false)
    })

    it('should return false for null and undefined', () => {
      expect(IdService.isTempId(null)).toBe(false)
      expect(IdService.isTempId(undefined)).toBe(false)
    })

    it('should return false for other string formats', () => {
      expect(IdService.isTempId('abc')).toBe(false)
      expect(IdService.isTempId('')).toBe(false)
    })
  })

  describe('equals', () => {
    it('should compare same types correctly', () => {
      expect(IdService.equals(123, 123)).toBe(true)
      expect(IdService.equals('123', '123')).toBe(true)
      expect(IdService.equals(123, 456)).toBe(false)
      expect(IdService.equals('123', '456')).toBe(false)
    })

    it('should compare different types correctly', () => {
      expect(IdService.equals(123, '123')).toBe(true)
      expect(IdService.equals('123', 123)).toBe(true)
    })

    it('should handle temp IDs', () => {
      const tempId = 'session-123-abc'
      expect(IdService.equals(tempId, tempId)).toBe(true)
      expect(IdService.equals(tempId, 'session-456-xyz')).toBe(false)
    })

    it('should handle null and undefined', () => {
      expect(IdService.equals(null, null)).toBe(true)
      expect(IdService.equals(undefined, undefined)).toBe(true)
      expect(IdService.equals(null, undefined)).toBe(false)
      expect(IdService.equals(123, null)).toBe(false)
      expect(IdService.equals('123', undefined)).toBe(false)
    })

    it('should handle edge cases', () => {
      expect(IdService.equals(0, '0')).toBe(true)
      expect(IdService.equals('', '')).toBe(true)
    })
  })

  describe('tryToBackend', () => {
    it('should convert numeric string to number', () => {
      expect(IdService.tryToBackend('123')).toBe(123)
      expect(IdService.tryToBackend('1')).toBe(1)
    })

    it('should return null for temp IDs', () => {
      expect(IdService.tryToBackend('session-123-abc')).toBe(null)
    })

    it('should return null for non-numeric strings', () => {
      expect(IdService.tryToBackend('abc')).toBe(null)
      expect(IdService.tryToBackend('')).toBe(null)
    })
  })
})
