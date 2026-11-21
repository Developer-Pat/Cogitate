import { describe, it, expect } from 'vitest'

describe('Testing Infrastructure', () => {
  it('should run basic tests', () => {
    expect(1 + 1).toBe(2)
  })

  it('should have jsdom environment', () => {
    expect(window).toBeDefined()
    expect(document).toBeDefined()
  })
})