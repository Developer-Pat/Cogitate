/**
 * FirstRunRedirect — Option A auto-redirect (decision 2026-08-04).
 *
 * If no provider has a working key AND no chat history exists, the app
 * lands on /setup instead of /. Checked once per browser (localStorage
 * flag) so it doesn't re-fire on every navigation. Once any key works
 * or any chat exists, the redirect never fires again.
 */

import { useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { apiClient } from '../services/apiClient'
import { frontendLoggingService } from '../services/frontendLoggingService'

const FLAG = 'cogitate_setup_redirect_checked'

export default function FirstRunRedirect() {
  const location = useLocation()
  const navigate = useNavigate()
  const checkedRef = useRef(false)

  useEffect(() => {
    if (checkedRef.current) return
    if (location.pathname === '/setup') return
    if (typeof window !== 'undefined' && window.localStorage.getItem(FLAG)) return

    checkedRef.current = true

    let cancelled = false
    const run = async () => {
      try {
        const [keysResp, sessionsResp] = await Promise.allSettled([
          apiClient.get<{ providers?: Array<{ has_key?: boolean }> }>('/api/v1/providers/managed/keys'),
          apiClient.get<{ sessions?: unknown[]; items?: unknown[] }>('/api/v1/sessions'),
        ])

        // Any working key?
        let hasKey = false
        if (keysResp.status === 'fulfilled') {
          const providers = keysResp.value?.data?.providers ?? []
          hasKey = providers.some((p: { has_key?: boolean }) => p.has_key)
        }

        // Any chat history?
        let hasSessions = false
        if (sessionsResp.status === 'fulfilled') {
          const data = sessionsResp.value?.data
          const items: unknown[] = Array.isArray(data) ? data : data?.sessions ?? data?.items ?? []
          hasSessions = items.length > 0
        }

        if (typeof window !== 'undefined') {
          window.localStorage.setItem(FLAG, '1')
        }

        if (!cancelled && !hasKey && !hasSessions) {
          navigate('/setup', { replace: true })
        }
      } catch (err) {
        frontendLoggingService.warn('FirstRunRedirect', 'Setup check failed', { error: err instanceof Error ? err.message : String(err) })
      }
    }
    run()

    return () => { cancelled = true }
     
  }, [location.pathname, navigate])

  return null
}
