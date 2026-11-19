import { describe, it, expect, vi, beforeAll, afterAll } from 'vitest'
import { render, screen } from '@/test/test-utils'
import ErrorBoundary from '../ErrorBoundary'

// Mock console.error to avoid noise in test output
const originalError = console.error
beforeAll(() => {
  console.error = vi.fn()
})

afterAll(() => {
  console.error = originalError
})

const ThrowError = () => {
  throw new Error('Test error')
}

describe('ErrorBoundary', () => {
  it('should render children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <div>Normal content</div>
      </ErrorBoundary>
    )
    
    expect(screen.getByText('Normal content')).toBeInTheDocument()
  })

  it('should render fallback when error occurs', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )
    
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
  })
})