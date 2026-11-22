/**
 * The SETUP tile in Quick Navigation (ruled 2026-11-22, option 2).
 *
 * Setup lives on the Setup page, so the Dashboard's job is the DOOR plus the state: one badge,
 * read from the same measured verdict the card above it renders (`/api/v1/setup/readiness`) —
 * never a second grade assembled in the browser.
 *
 * The badge is the state, not a summary: `READY` when nothing is left, `N left` otherwise, and it
 * stays silent if the verdict cannot be read at all (a page that cannot measure says nothing).
 */
import { useCallback, useEffect, useState } from 'react'
import { Settings2 } from 'lucide-react'
import NavigationCard from './NavigationCard'
import { readinessService } from '@/services/readinessService'

export default function SetupNavCard() {
  const [remaining, setRemaining] = useState<number | null>(null)

  const load = useCallback(async () => {
    try {
      const report = await readinessService.get()
      setRemaining(report.remaining)
    } catch {
      setRemaining(null)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const ready = remaining === 0
  const badge = remaining === null ? null : (
    <span
      className={`badge ${ready ? 'badge-success' : 'badge-warning'} badge-sm`}
      data-tip={ready ? 'Every setup step is done.' : `${remaining} setup step(s) still need you.`}
    >
      {ready ? 'ready' : `${remaining} left`}
    </span>
  )

  return (
    <NavigationCard
      icon={<Settings2 className="h-7 w-7" />}
      title="Setup"
      description="Providers, keys, chat model and the system agent — what the install still needs."
      to="/setup"
      badge={badge}
    />
  )
}
