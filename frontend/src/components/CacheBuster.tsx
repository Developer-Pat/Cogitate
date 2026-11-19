import { useState, useEffect } from 'react'
import Tooltip from './ui/Tooltip'

/**
 * CacheBuster Component
 *
 * Provides a manual cache clear button and automatically detects when
 * the app version has changed (indicating a new deployment).
 *
 * Features:
 * - Displays app version from package.json
 * - Manual "Clear Cache & Reload" button
 * - Auto-detects new deployments
 * - Uses localStorage version tracking
 */
export const CacheBuster: React.FC = () => {
  const [currentVersion, setCurrentVersion] = useState<string>('')
  const [storedVersion, setStoredVersion] = useState<string>('')
  const [showUpdatePrompt, setShowUpdatePrompt] = useState(false)

  // Get version from package.json (injected by Vite at build time)
  const appVersion = import.meta.env.VITE_APP_VERSION || 'dev'

  useEffect(() => {
    setCurrentVersion(appVersion)

    // Check stored version
    const stored = localStorage.getItem('app_version')
    setStoredVersion(stored || 'none')

    // Detect version change
    if (stored && stored !== appVersion) {
      setShowUpdatePrompt(true)
    }

    // Store current version
    localStorage.setItem('app_version', appVersion)
  }, [appVersion])

  const handleClearCache = async () => {
    // Log using sendBeacon - best effort, survives page unload
    const logPayload = JSON.stringify({
      timestamp: new Date().toISOString(),
      level: 'info',
      source: 'CacheBuster',
      message: 'Clearing browser cache and reloading',
      context: {
        action: 'cache_clear',
        localStorage_keys: Object.keys(localStorage).length,
        sessionStorage_keys: Object.keys(sessionStorage).length
      }
    })

    // sendBeacon is fire-and-forget, works during page unload
    const logUrl = `${window.location.origin}/api/v1/logs/frontend`
    navigator.sendBeacon(logUrl, logPayload)

    // Also log to console (visible in DevTools Network tab)
    console.log('[CacheBuster] Clearing cache and reloading...')

    // Clear all localStorage (except essential data)
    const essentialKeys = ['auth_token', 'user_preferences']
    const allKeys = Object.keys(localStorage)
    
    allKeys.forEach(key => {
      if (!essentialKeys.includes(key)) {
        localStorage.removeItem(key)
      }
    })

    // Clear sessionStorage
    sessionStorage.clear()

    // Force reload with cache bypass
    window.location.reload()
  }

  const dismissUpdatePrompt = () => {
    setShowUpdatePrompt(false)
    localStorage.setItem('app_version', appVersion)
  }

  return (
    <>
      {/* Clear Cache Button - Clean, no version */}
      <Tooltip content="Clear browser cache and reload" position="bottom">
        <button
          className="btn btn-xs btn-primary gap-1"
          onClick={handleClearCache}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Clear Cache
        </button>
      </Tooltip>

      {/* Update Prompt Banner - Shows when version changes */}
      {showUpdatePrompt && (
        <div className="fixed bottom-4 right-4 z-50 max-w-sm">
          <div className="alert alert-info shadow-lg">
            <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <h3 className="font-bold">New Version Available!</h3>
              <div className="text-xs">
                Updated from v{storedVersion} to v{currentVersion}
              </div>
            </div>
            <div className="flex gap-2">
              <button 
                className="btn btn-sm btn-ghost"
                onClick={dismissUpdatePrompt}
              >
                Later
              </button>
              <button 
                className="btn btn-sm btn-primary"
                onClick={handleClearCache}
              >
                Update Now
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
