/**
 * Automatic Logging Initialization
 * 
 * Captures frontend errors, navigation events, and performance metrics
 * automatically without manual instrumentation.
 * 
 * Usage: Import this module once in your app entry point (main.tsx)
 * 
 * import './utils/autoLogging'
 */

import { frontendLoggingService } from '../services/frontendLoggingService'

let isInitialized = false

/**
 * Initialize automatic logging
 * Captures errors, unhandled rejections, and navigation events
 */
export function initAutoLogging() {
  if (isInitialized) {
    return
  }

  isInitialized = true

  // Capture unhandled errors
  window.addEventListener('error', (event) => {
    frontendLoggingService.error(
      'GlobalErrorHandler',
      `Error: ${event.message}`,
      event.error,
      {
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno
      }
    )
  })
  
  // Capture unhandled promise rejections
  window.addEventListener('unhandledrejection', (event) => {
    frontendLoggingService.error(
      'UnhandledRejection',
      `Unhandled Promise Rejection: ${event.reason}`,
      event.reason instanceof Error ? event.reason : new Error(String(event.reason)),
      {
        type: 'unhandledrejection'
      }
    )
    event.preventDefault() // Prevent console spam
  })
  
  // Log page navigation (SPA)
  let lastPathname = window.location.pathname
  const originalPushState = history.pushState
  const originalReplaceState = history.replaceState
  
  history.pushState = function(...args) {
    originalPushState.apply(this, args)
    onNavigation('pushState', args[2]?.toString() || window.location.pathname)
  }
  
  history.replaceState = function(...args) {
    originalReplaceState.apply(this, args)
    onNavigation('replaceState', args[2]?.toString() || window.location.pathname)
  }
  
  window.addEventListener('popstate', () => {
    onNavigation('popstate', window.location.pathname)
  })
  
  function onNavigation(type: string, pathname: string) {
    if (pathname !== lastPathname) {
      frontendLoggingService.info(
        'Navigation',
        `Navigated to ${pathname}`,
        {
          navigationType: type,
          from: lastPathname,
          to: pathname
        }
      )
      lastPathname = pathname
    }
  }
  
  // Log page visibility changes (tab switch, minimize)
  document.addEventListener('visibilitychange', () => {
    frontendLoggingService.debug(
      'VisibilityChange',
      `Page visibility changed to ${document.visibilityState}`
    )
  })
  
  // Log before unload (user leaving page)
  window.addEventListener('beforeunload', () => {
    frontendLoggingService.info(
      'BeforeUnload',
      'User is leaving the page'
    )
  })
  
  // Capture performance metrics on page load
  if (window.performance && typeof window.performance.getEntriesByType === 'function') {
    window.addEventListener('load', () => {
      setTimeout(() => {
        const entries = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming
        if (entries) {
          frontendLoggingService.info(
            'Performance',
            'Page load performance metrics',
            {
              domContentLoaded: entries.domContentLoadedEventEnd - entries.startTime,
              loadComplete: entries.loadEventEnd - entries.startTime,
              dnsLookup: entries.domainLookupEnd - entries.domainLookupStart,
              tcpConnect: entries.connectEnd - entries.connectStart,
              firstByte: entries.responseStart - entries.requestStart,
              download: entries.responseEnd - entries.responseStart
            }
          )
        }
      }, 0)
    })
  }

  // Log API errors (intercept fetch)
  const originalFetch = window.fetch

  // THE RESTART FLOOD GATE (2026-09-06, the user's catch): when the
  // backend is down (restart window) EVERY 4xx/5xx warned — and each
  // warning POSTed to /logs/frontend, failed, and warned again: a
  // self-amplifying flood. Now: (1) the log-ingest endpoints are
  // skipped entirely (their failures are silent by design — the local
  // store is the backup), and (2) every other failed URL warns at most
  // once per cooldown window (the outage itself is announced once by
  // the apiClient's outage gate).
  const apiErrorCooldowns = new Map<string, number>()
  const LOG_INGEST_MARKERS = ['/api/v1/logs/frontend']
  const API_ERROR_COOLDOWN_MS = 15000

  window.fetch = async function(...args) {
    const url = typeof args[0] === 'string' ? args[0] : (args[0] as Request).url
    const method = (args[1]?.method || 'GET').toUpperCase()
    
    const response = await originalFetch(...args)
    
    // Log errors (4xx, 5xx) — gated (see the comment above)
    if (response.status >= 400) {
      const isLogIngest = LOG_INGEST_MARKERS.some(marker => url.includes(marker))
      const now = Date.now()
      const lastWarned = apiErrorCooldowns.get(url) || 0
      if (!isLogIngest && now - lastWarned >= API_ERROR_COOLDOWN_MS) {
        apiErrorCooldowns.set(url, now)
        frontendLoggingService.warning(
          'APIError',
          `API request failed: ${method} ${url}`,
          {
            status: response.status,
            statusText: response.statusText,
            url
          }
        )
      }
    }
    
    return response
  }
}

// Auto-initialize if this module is imported
initAutoLogging()
