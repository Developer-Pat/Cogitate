/**
 * Enhanced API Client for Cogitate Backend
 *
 * This client provides comprehensive error handling, authentication support,
 * request/response interceptors, and retry logic.
 *
 * THE ONE CLIENT (2026-09-04, the _34 consolidation): the duplicate
 * domains/shared/apiClient.ts was DELETED — its missing machinery
 * (the failure tracker + the 3rd-consecutive notification + the
 * recovery toast + the real params support + the final-error log)
 * was ported INTO this file, the one 51 consumers import. The
 * return contract ({data} | {error}), the clean join, and the
 * FormData guard are untouched.
 *
 * THE DYNAMIC-EDGE RULE (the _33 doctrine): this client sits at the
 * BOTTOM of the logging + notification stacks (frontendLoggingService
 * -> logsService -> this file; notificationStore ->
 * notificationConfigStore -> notificationConfigService -> this
 * file) — a STATIC import of either stack here would close a cycle
 * (the app-killer class). Both edges are DYNAMIC imports, resolved
 * at call time after the module graph is fully loaded.
 */

import type { ApiResponse, ApiError } from '../types';
import { useUserStore } from '../stores/userStore';
import { notifyBus } from './notifyBus';
import { outageGate } from './outageGate';

// The frontend's API locator — ONE source for the backend base URL
// (the pathing discipline 2026-08-17: services import this instead of
// repeating the env fallback; the hardcoded-fetch sites fixed).
// THE ONE BASE (2026-08-29 — the '//'-bug's root-fix): the same-
// origin ABSOLUTE (the window.location.origin) — no relative-base
// pitfalls anywhere (the '/' base turned '/api/...' into '//api/...'
// — the protocol-relative host 'api' — the ws + SSE + fetch all
// broke!). The vite-proxy forwards the same-origin's /api to the
// backend.
export const API_BASE_URL = import.meta.env.VITE_API_URL || window.location.origin;

interface RequestOptions extends RequestInit {
  timeout?: number;
  retries?: number;
  requireAuth?: boolean;
  params?: Record<string, unknown>;
  /** TELEMETRY OPT-OUT (2026-09-05): a request whose failures must
   * NOT count toward the outage streak — the log-funnel's own flush
   * is best-effort telemetry; a slow/dropped log POST is not a
   * backend-down signal. */
  excludeFromOutageTracking?: boolean;
}

class EnhancedApiClient {
  private baseUrl: string;
  private authToken: string | null = null;
  // THE OUTAGE TRACKER (2026-09-04, the _34 port — from the deleted
  // domains/shared client): consecutive failures + the 10s
  // notification rate limit.
  private consecutiveFailures: number = 0;
  private lastNotificationTime: number = 0;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
    this.loadAuthToken();
  }

  // THE DYNAMIC EDGES (the _33 doctrine — see the header): the
  // notification + logging stacks both statically depend on THIS
  // client, so the references resolve at CALL time — no static
  // cycle can form, regardless of the module evaluation order.
  private notifyBackendDown(): void {
    // THE STATIC BUS EDGE (2026-09-04): the notification stack
    // depends on THIS client — the store reference rides the
    // notifyBus (registered at the app boot), never a direct
    // import (cycle-free by construction).
    // THE EPISODE GATE (2026-09-04, the dedupe): the indicator +
    // the health hook announce the same outage — the FIRST
    // down-detector of an episode wins; the rest stay silent.
    if (!outageGate.markDown()) return
    notifyBus.error('Backend Unavailable', 'Cannot connect to backend server. Some features may not work.', 10000)
  }

  private notifyBackendRestored(): void {
    // the first recovery-detector announces + closes the episode
    if (!outageGate.markUp()) return
    notifyBus.success('Backend Connection Restored', 'Connection to backend server has been restored.', 5000)
  }

  // THE FLOOD THRESHOLD (2026-08-25, the user's 'flooded with error
  // toasts' report; ported 2026-09-04): the toast fires at the 3rd
  // CONSECUTIVE failure (or every 5th) — the sustained-outage
  // signal; the first two track silently. Rate-limited to one per
  // 10s (the notification store's own display duration).
  private trackRequestFailure(): void {
    this.consecutiveFailures++;
    if (this.consecutiveFailures === 3 || this.consecutiveFailures % 5 === 0) {
      const now = Date.now();
      if (now - this.lastNotificationTime > 10000) {
        this.lastNotificationTime = now;
        this.notifyBackendDown();
      }
    }
  }

  private trackRequestSuccess(): void {
    if (this.consecutiveFailures >= 3 && this.consecutiveFailures > 0) {
      const now = Date.now();
      if (now - this.lastNotificationTime > 10000) {
        this.lastNotificationTime = now;
        this.notifyBackendRestored();
      }
    }
    this.consecutiveFailures = 0;
  }

  private loadAuthToken() {
    // Load token from localStorage or state management
    const token = localStorage.getItem('auth_token');
    if (token) {
      this.authToken = token;
    }
  }

  private async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<ApiResponse<T>> {
    const {
      timeout = 10000,
      retries = 3,
      requireAuth = true,
      params,
      excludeFromOutageTracking = false,
      ...fetchOptions
    } = options;

    // THE CLEAN JOIN (2026-08-29 — the '//'-bug!): the naive
    // `${base}${endpoint}` turned VITE_API_URL='/' + '/api/...' into
    // '//api/...' — a PROTOCOL-RELATIVE URL (host 'api'!) — the
    // DNS-fail -> the NetworkErrors -> the 'Backend Unavailable'
    // storm! The slash-normalization keeps both the absolute and
    // the relative bases correct.
    let url = `${this.baseUrl.replace(/\/+$/, '')}/${endpoint.replace(/^\/+/, '')}`;

    // THE PARAMS BUILDER (2026-09-04, the _34 port — the real
    // support the interface always declared): endpoints may carry
    // an existing query (e.g. '?page=1') — the params merge onto
    // it with the right separator.
    if (params && Object.keys(params).length > 0) {
      const qs = Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join('&');
      if (qs) {
        url += `${url.includes('?') ? '&' : '?'}${qs}`;
      }
    }

    // Prepare headers
    // Don't set Content-Type for FormData - let the browser set it with the correct boundary
    const headers: Record<string, string> = {};
    if (!(fetchOptions.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }
    Object.assign(headers, fetchOptions.headers as Record<string, string>);

    // Add authentication if required
    if (requireAuth && this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`;
    }

    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= retries; attempt++) {
      // THE ABORT POLICY (2026-09-05, the user's 'Backend Unavailable
      // while the backend is up' report): the client's OWN timeout and
      // an EXTERNAL abort (a page navigation cancels in-flight fetches)
      // both surface as DOMException AbortError — but only the timeout
      // is a real failure signal. Navigation aborts must never count
      // toward the outage streak (they tripped the 'Backend
      // Unavailable' false positives at 13:01) and never spam the log.
      let timedOut = false;
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => {
          timedOut = true;
          controller.abort();
        }, timeout);

        const response = await fetch(url, {
          ...fetchOptions,
          headers,
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        const responseData = await response.json().catch(() => null);

        if (response.ok) {
          this.trackRequestSuccess();
          return {
            data: responseData,
            status: response.status,
            timestamp: new Date().toISOString(),
          };
        } else {
          // Handle specific HTTP status codes
          if (response.status === 401 && requireAuth) {
            // Unauthorized - clear auth and redirect
            this.clearAuth();
            useUserStore.getState().clearUser();
            window.location.href = '/login';
            break;
          }

          if (response.status === 429) {
            // Rate limited - wait and retry
            const retryAfter = response.headers.get('Retry-After');
            const waitTime = retryAfter ? parseInt(retryAfter) * 1000 : 1000;
            await new Promise(resolve => setTimeout(resolve, waitTime));
            continue;
          }

          const apiError: ApiError = {
            code: `HTTP_${response.status}`,
            message: responseData?.detail || responseData?.message || `HTTP ${response.status}: ${response.statusText}`,
            details: responseData,
            timestamp: new Date().toISOString(),
          };

          // THE FAILURE TRACK (2026-09-04, the _34 port): a failed
          // response counts toward the outage streak — except the
          // telemetry opt-out (the log funnel's flush).
          if (!excludeFromOutageTracking) {
            this.trackRequestFailure();
          }

          return {
            error: apiError,
            status: response.status,
            timestamp: new Date().toISOString(),
          };
        }
      } catch (error) {
        lastError = error as Error;

        // THE ABORT EDGE (2026-09-05): an AbortError is NOT an outage
        // signal. The client's own timeout = the request genuinely
        // hung: count + log it ONCE (no retry — timeouts don't retry).
        // An external abort (navigation) = the page left, not the
        // backend: silent + untracked + unlogged.
        if (error instanceof DOMException && error.name === 'AbortError') {
          if (timedOut) {
            if (!excludeFromOutageTracking) {
              this.trackRequestFailure();
              notifyBus.log(
                'apiClient',
                `Request timed out after ${timeout}ms: ${url}`,
                error,
              );
            }
          }
          return {
            error: {
              code: 'ABORTED',
              message: lastError?.message || 'Request aborted',
              details: { timedOut },
              timestamp: new Date().toISOString(),
            },
            status: 0,
            timestamp: new Date().toISOString(),
          };
        }

        // Wait before retry (exponential backoff)
        if (attempt < retries) {
          const backoffDelay = Math.min(1000 * Math.pow(2, attempt), 30000);
          await new Promise(resolve => setTimeout(resolve, backoffDelay));
        }
      }
    }

    // All retries failed — the sustained-outage signal: count the
    // streak (the notification fires at the 3rd consecutive) AND
    // log the failure through the funnel (the STATIC bus edge — the
    // logging stack depends on this client; see notifyBus.ts). The
    // telemetry opt-out skips both — its own catch reports.
    if (!excludeFromOutageTracking) {
      this.trackRequestFailure();
      notifyBus.log('apiClient', `Request failed after ${retries} retries: ${url}`, new Error(lastError?.message || 'Network request failed'))
    }

    const apiError: ApiError = {
      code: 'NETWORK_ERROR',
      message: lastError?.message || 'Network request failed',
      details: { lastError: lastError?.toString() },
      timestamp: new Date().toISOString(),
    };

    return {
      error: apiError,
      status: 0,
      timestamp: new Date().toISOString(),
    };
  }

  // Authentication methods
  setAuthToken(token: string) {
    this.authToken = token;
    localStorage.setItem('auth_token', token);
  }

  clearAuth() {
    this.authToken = null;
    localStorage.removeItem('auth_token');
  }

  // HTTP methods
  async get<T>(endpoint: string, options: RequestOptions = {}): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { ...options, method: 'GET' });
  }

  async post<T>(endpoint: string, data?: unknown, options: RequestOptions = {}): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data?: unknown, options: RequestOptions = {}): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async patch<T>(endpoint: string, data?: unknown, options: RequestOptions = {}): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string, options: RequestOptions = {}): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' });
  }

  // File upload
  async upload<T>(endpoint: string, formData: FormData, options: RequestOptions = {}): Promise<ApiResponse<T>> {
    const headers: Record<string, string> = {};
    if (options.requireAuth && this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`;
    }

    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: formData,
      headers,
    });
  }

  // Streaming support for SSE responses
  async stream(
    endpoint: string,
    data?: unknown,
    options: RequestOptions & { signal?: AbortSignal } = {}
  ): Promise<Response> {
    const {
      timeout = 60000, // Longer timeout for streaming
      requireAuth = true,
      signal,
      ...fetchOptions
    } = options;

    const url = `${this.baseUrl}${endpoint}`;

    // Prepare headers
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    };
    Object.assign(headers, fetchOptions.headers as Record<string, string>);

    // Add authentication if required
    if (requireAuth && this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    // Combine with the caller's signal — a REAL AbortSignal. The old
    // Proxy-over-EventTarget fake failed the browser's WebIDL brand
    // check ('signal' member of RequestInit does not implement
    // interface AbortSignal) — fetch() demands a genuine AbortSignal
    // and a Proxy can never carry the internal slot. AbortSignal.any
    // (FF 124+ / Chrome 116+ / Safari 17.4+) yields a genuine
    // combined signal; the listener pattern is the universal
    // fallback (the caller's abort drives the controller).
    let combinedSignal: AbortSignal = controller.signal;
    if (signal) {
      if (typeof AbortSignal.any === 'function') {
        combinedSignal = AbortSignal.any([controller.signal, signal]);
      } else if (signal.aborted) {
        controller.abort();
      } else {
        signal.addEventListener('abort', () => controller.abort(), { once: true });
      }
    }

    try {
      const response = await fetch(url, {
        ...fetchOptions,
        method: 'POST',
        headers,
        body: data ? JSON.stringify(data) : undefined,
        signal: combinedSignal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        // Try to get error details from response
        let errorDetail = response.statusText;
        try {
          const errorBody = await response.text();
          if (errorBody) {
            errorDetail = `${response.status} ${response.statusText}: ${errorBody}`;
          }
        } catch {
          // Ignore error reading response body
        }
        throw new Error(`Streaming request failed: ${errorDetail}`);
      }

      return response;
    } catch (error) {
      clearTimeout(timeoutId);

      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new Error('Streaming request aborted');
      }

      throw error;
    }
  }
}

// Create and export a singleton instance
export const apiClient = new EnhancedApiClient();

// THE CLASS EXPORT (2026-09-04, the _34 tests): the tests build
// FRESH instances — the singleton's streak + rate-limit state
// must not leak across test cases.
export { EnhancedApiClient };

export default apiClient;