/**
 * Server-Sent Events (SSE) Client for Real-time Communication
 *
 * This service provides a robust SSE client with reconnection logic,
 * event handling, and connection management for real-time features.
 */

import { frontendLoggingService } from './frontendLoggingService'
import { API_BASE_URL } from './apiClient'

export interface SSEEvent {
  id?: string;
  event?: string;
  data: string;
  retry?: number;
}

export interface SSEOptions {
  url: string;
  headers?: Record<string, string>;
  withCredentials?: boolean;
  retryInterval?: number;
  maxRetries?: number;
  onOpen?: (event: Event) => void;
  onMessage?: (event: SSEEvent) => void;
  onError?: (event: Event) => void;
  onClose?: (event: Event) => void;
}

export class SSEClient {
  private eventSource: EventSource | null = null;
  private options: SSEOptions;
  private retryCount = 0;
  private isConnected = false;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

  constructor(options: SSEOptions) {
    this.options = {
      retryInterval: 3000,
      maxRetries: 5,
      ...options,
    };
  }

  /**
   * Connect to the SSE endpoint
   */
  connect(): void {
    if (this.eventSource) {
      this.disconnect();
    }

    try {
      this.eventSource = new EventSource(this.options.url, {
        withCredentials: this.options.withCredentials || false,
      });

      this.setupEventListeners();
      this.isConnected = true;
      this.retryCount = 0;

      if (this.options.onOpen) {
        this.eventSource.onopen = this.options.onOpen;
      }

    } catch (error) {
      frontendLoggingService.error('SSEClient', 'SSE connection failed', error)
      this.handleConnectionError()
    }
  }

  /**
   * Setup event listeners for the SSE connection
   */
  private setupEventListeners(): void {
    if (!this.eventSource) return;

    this.eventSource.onmessage = (event: MessageEvent) => {
      const sseEvent: SSEEvent = {
        data: event.data,
      };

      // Parse JSON data if possible
      try {
        sseEvent.data = JSON.parse(event.data);
      } catch {
        // Keep as string if not JSON
      }

      if (this.options.onMessage) {
        this.options.onMessage(sseEvent);
      }
    };

    this.eventSource.onerror = (event: Event) => {
      frontendLoggingService.error('SSEClient', 'SSE connection error', event)
      this.handleConnectionError()

      if (this.options.onError) {
        this.options.onError(event)
      }
    }
  }

  /**
   * Handle connection errors with retry logic
   */
  private handleConnectionError(): void {
    this.isConnected = false;

    // Check if this is a 404 error - if so, don't reconnect
    // This happens when workflow is completed or endpoint doesn't exist
    if (this.eventSource?.readyState === EventSource.CLOSED) {
      frontendLoggingService.warning('SSEClient', 'SSE connection closed permanently - workflow likely completed', {
        url: this.options.url,
        readyState: this.eventSource?.readyState
      });
      this.disconnect();
      if (this.options.onClose) {
        this.options.onClose(new Event('close'));
      }
      return;
    }

    if (this.retryCount < (this.options.maxRetries || 5)) {
      this.retryCount++
      frontendLoggingService.info('SSEClient', `SSE reconnecting in ${this.options.retryInterval}ms (attempt ${this.retryCount})`)

      this.reconnectTimeout = setTimeout(() => {
        this.connect()
      }, this.options.retryInterval)
    } else {
      frontendLoggingService.error('SSEClient', 'SSE connection failed after maximum retries', {
        url: this.options.url,
        maxRetries: this.options.maxRetries
      });
      this.disconnect();
      if (this.options.onClose) {
        this.options.onClose(new Event('close'));
      }
    }
  }

  /**
   * Disconnect from the SSE endpoint
   */
  disconnect(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    this.isConnected = false;
    this.retryCount = 0;
  }

  /**
   * Get connection status
   */
  getConnectionStatus(): 'connected' | 'connecting' | 'disconnected' | 'error' {
    if (this.isConnected && this.eventSource?.readyState === EventSource.OPEN) {
      return 'connected';
    } else if (this.reconnectTimeout) {
      return 'connecting';
    } else if (this.eventSource?.readyState === EventSource.CLOSED) {
      return 'error';
    } else {
      return 'disconnected';
    }
  }

  /**
   * Add custom event listener
   */
  addEventListener(eventType: string, listener: (event: MessageEvent) => void): void {
    if (this.eventSource) {
      this.eventSource.addEventListener(eventType, listener);
    }
  }

  /**
   * Remove custom event listener
   */
  removeEventListener(eventType: string, listener: (event: MessageEvent) => void): void {
    if (this.eventSource) {
      this.eventSource.removeEventListener(eventType, listener);
    }
  }
}

/**
 * SSE Client Factory for creating pre-configured clients
 */
export class SSEClientFactory {
  private static baseUrl = API_BASE_URL;

  /**
   * Create SSE client for LLM streaming
   */
  static createLLMStreamClient(sessionId: string, onMessage: (event: SSEEvent) => void): SSEClient {
    const url = `${this.baseUrl}/api/v1/chat/stream?session_id=${sessionId}`

    return new SSEClient({
      url,
      onMessage,
      onError: (event) => {
        frontendLoggingService.error('SSEClientFactory', 'LLM stream error', event)
      },
      onClose: () => {
        frontendLoggingService.info('SSEClientFactory', 'LLM stream closed')
      },
      retryInterval: 2000,
      maxRetries: 3,
    })
  }

  /**
   * Create SSE client for workflow progress
   */
  static createWorkflowProgressClient(workflowId: string, onMessage: (event: SSEEvent) => void): SSEClient {
    const url = `${this.baseUrl}/api/v1/workflows/${workflowId}/progress`

    return new SSEClient({
      url,
      onMessage,
      onError: (event) => {
        frontendLoggingService.error('SSEClientFactory', 'Workflow progress stream error', event)
      },
      retryInterval: 3000,
      maxRetries: 5,
    })
  }

  /**
   * Create SSE client for system metrics
   */
  static createSystemMetricsClient(onMessage: (event: SSEEvent) => void): SSEClient {
    const url = `${this.baseUrl}/api/v1/system/metrics`

    return new SSEClient({
      url,
      onMessage,
      onError: (event) => {
        frontendLoggingService.error('SSEClientFactory', 'System metrics stream error', event)
      },
      retryInterval: 5000,
      maxRetries: 10,
    })
  }

  /**
   * Create SSE client for log streaming
   */
  static createLogStreamClient(onMessage: (event: SSEEvent) => void): SSEClient {
    const url = `${this.baseUrl}/api/v1/system/logs/stream`

    return new SSEClient({
      url,
      onMessage,
      onError: (event) => {
        frontendLoggingService.error('SSEClientFactory', 'Log stream error', event)
      },
      retryInterval: 3000,
      maxRetries: 5,
    })
  }
}

export default SSEClient