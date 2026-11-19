/**
 * PackageTab — the agent profile's PACKAGE tab (2026-08-25, the
 * package's UI half): Phase 1 the read-only provenance + contents;
 * Phase 2 (THIS) the picker + the preview — the available packages,
 * the selection, the contents previewed BEFORE the adopt (Phase 3).
 */
import { useEffect, useState } from 'react'
import { useDomainSync } from '@/hooks/useDomainSync'
import { agentPackagesService, type AgentPackage } from '@/services/domain/agentPackages'
import type { Profile } from '@/services/domain/ProfileService'
import { profileService } from '@/services/domain/ProfileService'
import { collectionsService } from '@/services/domain/CollectionsService'
import { useNotificationStore } from '@/stores/notificationStore'

interface PackageTabProps {
  profile: Profile
}

function PackageContents({ pkg }: { pkg: AgentPackage }) {
  // THE KIT NAME (2026-08-25, the user's report: 'the toolkit id is
  // unreadable to users'): the raw UUID means nothing — resolve the
  // collection's name; the id's the fallback.
  const [kitName, setKitName] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    if (!pkg.kit_id) {
      setKitName(null)
      return
    }
    collectionsService
      .getCollection(pkg.kit_id)
      .then((col) => {
        if (alive) setKitName(col?.name ?? null)
      })
      .catch(() => {
        if (alive) setKitName(null)
      })
    return () => {
      alive = false
    }
  }, [pkg.kit_id])

  return (
    <div className="space-y-3">
      <div>
        <h4 className="font-semibold text-sm mb-1">Toolkit (kit)</h4>
        <div className="text-xs text-readout">
          {pkg.kit_id
            ? kitName
              ? kitName
              : pkg.kit_id
            : 'None — the agent keeps its own tool surface'}
        </div>
      </div>
      <div>
        <h4 className="font-semibold text-sm mb-1">Skillset</h4>
        {pkg.skills.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {pkg.skills.map((s) => (
              <span key={s} className="badge badge-sm badge-ghost">{s}</span>
            ))}
          </div>
        ) : (
          <div className="text-xs text-readout">None</div>
        )}
      </div>
      <div>
        <h4 className="font-semibold text-sm mb-1">LLM spec (advisory)</h4>
        {pkg.llm_spec ? (
          <div className="text-xs text-readout space-y-0.5">
            <div>kind: {pkg.llm_spec.kind ?? '—'}</div>
            <div>thinking: {pkg.llm_spec.thinking ?? '—'}</div>
            <div>location: {pkg.llm_spec.location ?? '—'}</div>
            {pkg.llm_spec.min_context != null && (
              <div>min context: {pkg.llm_spec.min_context}</div>
            )}
          </div>
        ) : (
          <div className="text-xs text-readout">None</div>
        )}
      </div>
    </div>
  )
}

export default function PackageTab({ profile }: PackageTabProps) {
  const [packages, setPackages] = useState<AgentPackage[]>([])
  const [loading, setLoading] = useState(true)
  // THE DETAIL MODAL'S PACKAGE (2026-08-25, the table + the modal):
  // the row click opens the detail; the adopt flows from there.
  const [detailPkg, setDetailPkg] = useState<AgentPackage | null>(null)
  // THE KIT-NAMES MAP: the table's rows show the kits' NAMES (the
  // UUIDs are unreadable — the user's report!) — fetched once.
  const [kitNames, setKitNames] = useState<Record<string, string>>({})

  useEffect(() => {
    let alive = true
    agentPackagesService
      .list()
      .then((pkgs) => {
        if (alive) setPackages(pkgs)
      })
      .catch(() => {})
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  // THE CROSS-WINDOW PACKAGE SYNC (2026-08-25, the roadmap Phase 6):
  // the packages' CRUD elsewhere reloads this tab's list.
  useDomainSync('agent-package', () => {
    agentPackagesService
      .list()
      .then((pkgs) => setPackages(pkgs))
      .catch(() => {})
  })

  // THE KITS' NAMES (2026-08-25): fetch the referenced collections
  // once; the rows + the detail render the names.
  useEffect(() => {
    let alive = true
    const kitIds = [...new Set(packages.map((p) => p.kit_id).filter(Boolean))] as string[]
    if (kitIds.length === 0) return
    Promise.all(kitIds.map((id) => collectionsService.getCollection(id).catch(() => null)))
      .then((cols) => {
        if (!alive) return
        const map: Record<string, string> = {}
        cols.forEach((col, i) => {
          if (col) map[kitIds[i]] = col.name
        })
        setKitNames(map)
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [packages])

  const kitNameOf = (id: string) => kitNames[id] ?? id

  const current = profile.package_id
    ? packages.find((p) => p.id === profile.package_id)
    : undefined
  // THE ADOPT (Phase 3, 2026-08-25): the confirm-then-call — the
  // destructive-transform discipline (the current vs the new shown,
  // the explicit confirm); the success refreshes the profiles (the
  // subscribed pages update — the agent OWNS its copies now).
  const [confirming, setConfirming] = useState<AgentPackage | null>(null)
  const [adopting, setAdopting] = useState(false)
  const { addSuccess, addError } = useNotificationStore()

  const handleAdopt = async () => {
    if (!confirming) return
    setAdopting(true)
    try {
      await agentPackagesService.adopt(profile.id, confirming.id)
      addSuccess('Package adopted', `The ${confirming.name} package's kit, skills, and llm_spec are now the agent's own.`)
      setConfirming(null)
      await profileService.loadFromBackend()
    } catch (err) {
      addError('Package adopt failed', String(err instanceof Error ? err.message : err))
    } finally {
      setAdopting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="text-sm text-readout">
        The package is the agent's blueprint — the toolkit ref, the
        recommended skillset, and the advisory LLM contract. The agent
        OWNS its copies; the package records the provenance.
      </div>

      {loading ? (
        <div className="text-sm opacity-60">Loading packages…</div>
      ) : (
        <>
          <div className="card bg-base-100 border border-base-300 rounded-lg p-4">
            <h4 className="font-semibold text-sm mb-1">Current package</h4>
            {current ? (
              <>
                <div className="font-medium">{current.name}</div>
                {current.description && (
                  <p className="text-xs text-readout mt-0.5">{current.description}</p>
                )}
              </>
            ) : (
              <div className="text-xs text-readout">
                {profile.package_id ? 'Package not found' : 'No package — this agent was not provisioned from a blueprint'}
              </div>
            )}
          </div>

          {/* THE PACKAGES TABLE (2026-08-25, the user's call: the
              radio-list only works for a few packages — the table +
              the detail modal scales). The row click opens the
              detail modal (the contents + the adopt). */}
          <div className="card bg-base-100 border border-base-300 rounded-lg overflow-hidden">
            <div className="px-4 py-2 border-b border-base-300 flex items-center justify-between">
              <h4 className="font-semibold text-sm">Available packages</h4>
              <span className="text-xs text-readout">{packages.length} package(s)</span>
            </div>
            <div className="overflow-x-auto">
              <table className="table table-sm">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Toolkit</th>
                    <th>Skills</th>
                    <th>LLM spec</th>
                  </tr>
                </thead>
                <tbody>
                  {packages.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="text-center text-xs text-readout py-4">
                        No packages defined yet
                      </td>
                    </tr>
                  ) : (
                    packages.map((pkg) => (
                      <tr
                        key={pkg.id}
                        className="cursor-pointer hover:bg-base-200/50"
                        onClick={() => setDetailPkg(pkg)}
                      >
                        <td>
                          <span className="font-medium">{pkg.name}</span>
                          {pkg.id === profile.package_id && (
                            <span className="badge badge-xs badge-ghost ml-2">current</span>
                          )}
                          {pkg.description && (
                            <div className="text-xs text-readout max-w-xs truncate">{pkg.description}</div>
                          )}
                        </td>
                        <td className="text-xs">{pkg.kit_id ? kitNameOf(pkg.kit_id) : '—'}</td>
                        <td className="text-xs">{pkg.skills.length}</td>
                        <td className="text-xs">
                          {pkg.llm_spec
                            ? `${pkg.llm_spec.kind ?? '?'} · ${pkg.llm_spec.thinking ?? '?'} · ${pkg.llm_spec.location ?? '?'}`
                            : '—'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* THE DETAIL MODAL (2026-08-25, the table + the modal —
              the scalable shape): the row click opens the full
              contents + the adopt action. */}
          {detailPkg && (
            <div
              className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/50"
              onClick={() => !adopting && setDetailPkg(null)}
            >
              {/* THE SCHEDULER PATTERN (2026-08-25, the user's 'check
                  other modals' — the WORKING fix!): the plain fixed
                  overlay + the plain styled container + the width var
                  + p-6. NO modal-box (the known-issues rule: it
                  renders 48px wide in this Tailwind v4 setup). */}
              <div
                className="bg-base-100 rounded-lg shadow-xl max-h-[90vh] overflow-y-auto p-6"
                style={{ width: 'min(var(--dialog-width-md), 95vw)' }}
                onClick={(e) => e.stopPropagation()}
              >
                <h3 className="font-bold text-lg flex items-center gap-2">
                  {detailPkg.name}
                  {detailPkg.id === profile.package_id && (
                    <span className="badge badge-xs badge-ghost">current</span>
                  )}
                </h3>
                {detailPkg.description && (
                  <p className="text-sm text-readout mt-1">{detailPkg.description}</p>
                )}
                <div className="mt-3">
                  <PackageContents pkg={detailPkg} />
                </div>
                <div className="modal-action">
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => setDetailPkg(null)}
                    disabled={adopting}
                  >
                    Close
                  </button>
                  {detailPkg.id !== profile.package_id && (
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => setConfirming(detailPkg)}
                      disabled={adopting}
                    >
                      Adopt this package
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* THE CONFIRM MODAL (Phase 3): the current vs the new —
              the destructive-transform discipline, the explicit
              confirm before the agent's fields are replaced. */}
          {confirming && (
            <div
              className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/50"
              onClick={() => !adopting && setConfirming(null)}
            >
              <div
                className="bg-base-100 rounded-lg shadow-xl max-h-[90vh] overflow-y-auto p-6"
                style={{ width: 'min(var(--dialog-width-md), 95vw)' }}
                onClick={(e) => e.stopPropagation()}
              >
                <h3 className="font-bold text-lg">Adopt {confirming.name}?</h3>
                <p className="text-sm text-readout mt-2">
                  The package's kit, skillset, and llm_spec will be
                  copied into the agent's OWN fields (the agent owns
                  the copies; the package stays the blueprint).
                </p>
                <div className="mt-3 space-y-2 text-xs">
                  <div className="card bg-base-200/60 rounded-lg p-3">
                    <div className="font-semibold mb-1">Now</div>
                    <div>kit: {profile.kit_id ?? 'none'}</div>
                    <div>skills: {profile.tools?.length ? profile.tools.join(', ') : 'none'}</div>
                  </div>
                  <div className="card bg-primary/10 rounded-lg p-3">
                    <div className="font-semibold mb-1">After</div>
                    <div>kit: {confirming.kit_id ?? 'none'}</div>
                    <div>skills: {confirming.skills.length ? confirming.skills.join(', ') : 'none'}</div>
                  </div>
                </div>
                <div className="modal-action">
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => setConfirming(null)}
                    disabled={adopting}
                  >
                    Cancel
                  </button>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={handleAdopt}
                    disabled={adopting}
                  >
                    {adopting ? 'Adopting…' : 'Adopt'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
