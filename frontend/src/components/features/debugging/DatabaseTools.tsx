import { API_BASE_URL } from '@/services/apiClient';
/**
 * DatabaseTools - Debug tools for managing backend database
 *
 * Features:
 * - Clear all sessions (for testing/debugging)
 * - View database statistics
 * - Reset database state
 */

import { useState } from 'react'


interface DeleteAllResponse {
  deleted: number[]
  failed: Array<{ id: number; reason: string }>
  total_requested: number
  total_deleted: number
  total_failed: number
}

export function DatabaseTools() {
  const [isClearing, setIsClearing] = useState(false)
  const [result, setResult] = useState<DeleteAllResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleClearSessions = async () => {
    if (!confirm('WARNING: This will delete ALL sessions and messages. This cannot be undone. Continue?')) {
      return
    }

    setIsClearing(true)
    setError(null)
    setResult(null)

    // traceService.trace('DatabaseTools', 'clearSessions started', {})

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/sessions/all`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const data: DeleteAllResponse = await response.json()
      setResult(data)

      // traceService.trace('DatabaseTools', 'clearSessions complete', {
        // deleted: data.total_deleted,
        // failed: data.total_failed
      // })
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err)
      setError(errorMessage)
      // traceService.trace('DatabaseTools', 'clearSessions failed', {
        // error: errorMessage
      // })
    } finally {
      setIsClearing(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="card bg-base-100 shadow-xl">
        <div className="card-body">
          <h2 className="card-title text-xl">🗑️ Clear Sessions Database</h2>
          <p className="text-sm text-readout">
            Delete all chat sessions and their messages from the backend database.
            This is useful for resetting test data during development.
          </p>

          <div className="alert alert-warning mt-4">
            <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span>
              <strong>Warning:</strong> This action cannot be undone. All session data will be permanently deleted.
            </span>
          </div>

          <button
            className="btn btn-error mt-4"
            onClick={handleClearSessions}
            disabled={isClearing}
          >
            {isClearing ? (
              <>
                <span className="loading loading-spinner"></span>
                Clearing...
              </>
            ) : (
              '🗑️ Clear All Sessions'
            )}
          </button>

          {error && (
            <div className="alert alert-error mt-4">
              <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>Error: {error}</span>
            </div>
          )}

          {result && (
            <div className="alert alert-success mt-4">
              <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <strong>Success!</strong>
                <ul className="mt-2 text-sm">
                  <li>Sessions deleted: {result.total_deleted}</li>
                  {result.total_failed > 0 && (
                    <li>Failed: {result.total_failed}</li>
                  )}
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="card bg-base-100 shadow-xl">
        <div className="card-body">
          <h2 className="card-title text-xl">📋 Command Line Alternative</h2>
          <p className="text-sm text-readout mb-2">
            You can also clear sessions from the command line:
          </p>
          <pre className="bg-base-200 p-4 rounded text-sm overflow-x-auto">
            <code>python backend/scripts/clear_sessions.py</code>
          </pre>
        </div>
      </div>
    </div>
  )
}
