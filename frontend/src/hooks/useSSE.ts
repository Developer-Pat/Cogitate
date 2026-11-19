import { useState, useEffect, useRef, useCallback } from 'react'
import { SSEClient, SSEClientFactory } from '../services/sseClient'
import { frontendLoggingService } from '../services/frontendLoggingService'
import type { SSEEvent } from '../services/sseClient'

export interface UseSSEOptions {
  url?: string
  type?: 'llm-stream' | 'workflow-progress' | 'system-metrics' | 'log-stream'
  sessionId?: string
  workflowId?: string
  enabled?: boolean
  onMessage?: (event: SSEEvent) => void
  onError?: (error: Event) => void
  onOpen?: () => void
  onClose?: () => void
}

export interface UseSSEReturn {
  data: SSEEvent | null
  error: Event | null
  status: 'idle' | 'connecting' | 'connected' | 'error' | 'closed'
  connect: () => void
  disconnect: () => void
  isConnected: boolean
}

/**
 * React hook for using Server-Sent Events (SSE) in components
 * 
 * @param options SSE configuration options
 * @returns SSE state and control functions
 */
export function useSSE(options: UseSSEOptions = {}): UseSSEReturn {
  const {
    url,
    type,
    sessionId,
    workflowId,
    enabled = true,
    onMessage,
    onError,
    onOpen,
    onClose,
  } = options

  const [data, setData] = useState<SSEEvent | null>(null)
  const [error, setError] = useState<Event | null>(null)
  const [status, setStatus] = useState<'idle' | 'connecting' | 'connected' | 'error' | 'closed'>('idle')
  
  const sseClientRef = useRef<SSEClient | null>(null)
  const isConnected = status === 'connected'

  // Create SSE client based on configuration
  const createClient = useCallback((): SSEClient | null => {
    if (!enabled) return null

    try {
      if (url) {
        // Custom URL
        return new SSEClient({
          url,
          onMessage: handleMessage,
          onError: handleError,
          onOpen: handleOpen,
          onClose: handleClose,
        })
      } else if (type) {
        // Pre-configured client types
        switch (type) {
          case 'llm-stream':
            if (!sessionId) {
              frontendLoggingService.error('useSSE', 'Session ID required for LLM stream')
              return null
            }
            return SSEClientFactory.createLLMStreamClient(sessionId, handleMessage)
          case 'workflow-progress':
            if (!workflowId) {
              frontendLoggingService.debug('useSSE', 'Workflow ID not provided - skipping SSE connection')
              return null
            }
            return SSEClientFactory.createWorkflowProgressClient(workflowId, handleMessage)
          case 'system-metrics':
            return SSEClientFactory.createSystemMetricsClient(handleMessage)
          case 'log-stream':
            return SSEClientFactory.createLogStreamClient(handleMessage)
          default:
            frontendLoggingService.error('useSSE', `Unknown SSE type: ${type}`)
            return null
        }
      } else {
        frontendLoggingService.error('useSSE', 'SSE configuration incomplete: provide either URL or type with required IDs')
        return null
      }
    } catch (err) {
      frontendLoggingService.error('useSSE', 'Failed to create SSE client', err as Error)
      setError(err as Event)
      setStatus('error')
      return null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, type, sessionId, workflowId, enabled])

  // Event handlers
  const handleMessage = useCallback((event: SSEEvent) => {
    setData(event)
    if (onMessage) {
      onMessage(event)
    }
  }, [onMessage])

  const handleError = useCallback((event: Event) => {
    setError(event)
    setStatus('error')
    if (onError) {
      onError(event)
    }
  }, [onError])

  const handleOpen = useCallback(() => {
    setStatus('connected')
    setError(null)
    if (onOpen) {
      onOpen()
    }
  }, [onOpen])

  const handleClose = useCallback(() => {
    setStatus('closed')
    if (onClose) {
      onClose()
    }
  }, [onClose])

  // Connect to SSE
  const connect = useCallback(() => {
    if (sseClientRef.current) {
      sseClientRef.current.disconnect()
    }

    const client = createClient()
    if (client) {
      sseClientRef.current = client
      setStatus('connecting')
      client.connect()
    }
  }, [createClient])

  // Disconnect from SSE
  const disconnect = useCallback(() => {
    if (sseClientRef.current) {
      sseClientRef.current.disconnect()
      sseClientRef.current = null
      setStatus('closed')
    }
  }, [])

  // Auto-connect when enabled changes
  useEffect(() => {
    if (enabled) {
      connect()
    } else {
      disconnect()
    }

    return () => {
      disconnect()
    }
  }, [enabled, connect, disconnect])

  // Reconnect when dependencies change
  useEffect(() => {
    if (isConnected) {
      disconnect()
      connect()
    }
  }, [url, type, sessionId, workflowId, isConnected, disconnect, connect])

  return {
    data,
    error,
    status,
    connect,
    disconnect,
    isConnected,
  }
}

/**
 * Hook for LLM streaming
 */
export function useLLMStream(sessionId: string, onMessage?: (event: SSEEvent) => void) {
  return useSSE({
    type: 'llm-stream',
    sessionId,
    onMessage,
  })
}

/**
 * Hook for workflow progress tracking
 *
 * Note: SSE endpoint for workflow progress is not yet implemented on backend.
 * Progress tracking currently relies on polling via useWorkflowExecution hook.
 * When backend SSE endpoint is available, set sseEnabled to true.
 */
export function useWorkflowProgress(
  workflowId: string,
  onMessage?: (event: SSEEvent) => void,
  _enabled: boolean = true
) {
  // SSE endpoint not yet implemented on backend
  // Progress tracking uses polling instead
  const sseEnabled = false;

  return useSSE({
    type: 'workflow-progress',
    workflowId,
    onMessage,
    enabled: sseEnabled,  // Set to false - using polling instead
  })
}

/**
 * Hook for system metrics
 */
export function useSystemMetrics(onMessage?: (event: SSEEvent) => void) {
  return useSSE({
    type: 'system-metrics',
    onMessage,
  })
}

/**
 * Hook for log streaming
 */
export function useLogStream(onMessage?: (event: SSEEvent) => void) {
  return useSSE({
    type: 'log-stream',
    onMessage,
  })
}

export default useSSE