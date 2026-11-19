/**
 * MemoryProfilesTab — CRUD table for memory profile configurations.
 */

import { useState, useEffect } from 'react'
import { memoryProfileService, type MemoryProfile, type MemoryProfileCreate, type MemoryProfileUpdate } from '@/services/domain/MemoryProfileService'
import { frontendLoggingService } from '@/services/frontendLoggingService'

export default function MemoryProfilesTab() {
  const [profiles, setProfiles] = useState<MemoryProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  // New profile form
  const [formData, setFormData] = useState<MemoryProfileCreate>({
    name: '',
    description: '',
    strategy: 'default',
    window_size: 50,
    persistence: 'memory',
    compaction_threshold: null,
    summarization: false,
  })

  const fetchProfiles = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await memoryProfileService.list()
      setProfiles(data)
    } catch (err) {
      frontendLoggingService.error('MemoryProfilesTab', 'Failed to fetch profiles', err)
      setError('Failed to load memory profiles')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProfiles()
  }, [])

  const handleCreate = async () => {
    if (!formData.name.trim()) return
    try {
      await memoryProfileService.create(formData)
      setShowCreate(false)
      setFormData({ name: '', description: '', strategy: 'default', window_size: 50, persistence: 'memory', compaction_threshold: null, summarization: false })
      await fetchProfiles()
    } catch (err) {
      frontendLoggingService.error('MemoryProfilesTab', 'Failed to create profile', err)
      setError('Failed to create profile')
    }
  }

  const handleUpdate = async (id: number, data: MemoryProfileUpdate) => {
    try {
      await memoryProfileService.update(id, data)
      setEditingId(null)
      await fetchProfiles()
    } catch (err) {
      frontendLoggingService.error('MemoryProfilesTab', 'Failed to update profile', err)
      setError('Failed to update profile')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await memoryProfileService.delete(id)
      await fetchProfiles()
    } catch (err) {
      frontendLoggingService.error('MemoryProfilesTab', 'Failed to delete profile', err)
      setError('Failed to delete profile')
    }
  }

  if (loading) {
    return <div className="flex justify-center py-8"><span className="loading loading-spinner loading-md"></span></div>
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-readout">Memory Profiles</h3>
        <button className="btn btn-primary btn-xs" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? 'Cancel' : '+ New Profile'}
        </button>
      </div>

      {error && (
        <div className="alert alert-error text-sm py-2">
          <span>{error}</span>
          <button className="btn btn-outline btn-xs" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {showCreate && (
        <div className="card bg-base-200 p-3 rounded-lg space-y-2">
          <input className="input input-bordered input-sm w-full" placeholder="Profile name *" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} />
          <input className="input input-bordered input-sm w-full" placeholder="Description" value={formData.description || ''} onChange={(e) => setFormData({ ...formData, description: e.target.value })} />
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[11px] text-readout">Strategy</label>
              <select className="select select-bordered select-xs w-full" value={formData.strategy} onChange={(e) => setFormData({ ...formData, strategy: e.target.value })}>
                <option value="default">default</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] text-readout">Window Size</label>
              <input type="number" className="input input-bordered input-xs w-full" value={formData.window_size} onChange={(e) => setFormData({ ...formData, window_size: parseInt(e.target.value) || 0 })} />
            </div>
            <div>
              <label className="text-[11px] text-readout">Persistence</label>
              <select className="select select-bordered select-xs w-full" value={formData.persistence} onChange={(e) => setFormData({ ...formData, persistence: e.target.value })}>
                <option value="memory">memory</option>
                          <option value="sqlite">sqlite</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] text-readout">Compaction</label>
              <input type="number" className="input input-bordered input-xs w-full" value={formData.compaction_threshold ?? ''} placeholder="None" onChange={(e) => setFormData({ ...formData, compaction_threshold: e.target.value ? parseInt(e.target.value) : null })} />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="checkbox checkbox-sm checkbox-primary" checked={formData.summarization} onChange={(e) => setFormData({ ...formData, summarization: e.target.checked })} />
            Enable summarization
          </label>
          <button className="btn btn-primary btn-xs w-full mt-1" onClick={handleCreate} disabled={!formData.name.trim()}>
            Create Profile
          </button>
        </div>
      )}

      {profiles.length === 0 ? (
        <div className="text-center py-8 text-readout text-sm">No memory profiles configured</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="table table-xs">
            <thead>
              <tr>
                <th>Name</th>
                <th>Strategy</th>
                <th>Window</th>
                <th>Persistence</th>
                <th>Compaction</th>
                <th>Summary</th>
                <th>Built-in</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {profiles.map((p) => (
                <tr key={p.id} className="hover">
                  {editingId === p.id ? (
                    <>
                      <td>
                        <input className="input input-bordered input-xs w-24" defaultValue={p.name} id={'edit-name-' + p.id} />
                      </td>
                      <td>
                        <select className="select select-bordered select-xs" defaultValue={p.strategy}>
                          <option value="default">default</option>
                        </select>
                      </td>
                      <td>
                        <input type="number" className="input input-bordered input-xs w-16" defaultValue={p.window_size} id={'edit-ws-' + p.id} />
                      </td>
                      <td>
                        <select className="select select-bordered select-xs" defaultValue={p.persistence} id={"edit-pers-" + p.id}>
                          <option value="memory">memory</option>
                          <option value="sqlite">sqlite</option>
                        </select>
                      </td>
                      <td>
                        <input type="number" className="input input-bordered input-xs w-16" defaultValue={p.compaction_threshold ?? ''} id={'edit-ct-' + p.id} />
                      </td>
                      <td>
                        <input type="checkbox" className="checkbox checkbox-sm checkbox-primary" defaultChecked={p.summarization} id={'edit-sum-' + p.id} />
                      </td>
                      <td>
                        {p.is_builtin ? <span className="badge badge-sm badge-ghost">built-in</span> : ''}
                      </td>
                      <td className="flex gap-1">
                        <button className="btn btn-ghost btn-xs" onClick={async () => {
                          const nameEl = document.getElementById('edit-name-' + p.id) as HTMLInputElement
                          const wsEl = document.getElementById('edit-ws-' + p.id) as HTMLInputElement
                          const ctEl = document.getElementById('edit-ct-' + p.id) as HTMLInputElement
                          const sumEl = document.getElementById('edit-sum-' + p.id) as HTMLInputElement
                          const persEl = document.getElementById('edit-pers-' + p.id) as HTMLSelectElement
                          await handleUpdate(p.id, {
                            name: nameEl?.value || p.name,
                            window_size: wsEl ? parseInt(wsEl.value) || 0 : p.window_size,
                            persistence: persEl?.value || p.persistence,
                            compaction_threshold: ctEl?.value ? parseInt(ctEl.value) : null,
                            summarization: sumEl?.checked ?? p.summarization,
                          })
                        }}>Save</button>
                        <button className="btn btn-neutral btn-ghost btn-xs" onClick={() => setEditingId(null)}>Cancel</button>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="font-medium">{p.name}</td>
                      <td><code className="text-xs">{p.strategy}</code></td>
                      <td>{p.window_size}</td>
                      <td>{p.persistence}</td>
                      <td>{p.compaction_threshold ?? '-'}</td>
                      <td>
                        {p.summarization ? (
                          <span className="badge badge-sm badge-success badge-outline">on</span>
                        ) : (
                          <span className="badge badge-sm badge-ghost">off</span>
                        )}
                      </td>
                      <td>
                        {p.is_builtin ? <span className="badge badge-sm badge-ghost">built-in</span> : ''}
                      </td>
                      <td className="flex gap-1">
                        {!p.is_builtin && (
                          <>
                            <button className="btn btn-outline btn-xs" onClick={() => setEditingId(p.id)}>Edit</button>
                            <button className="btn btn-error btn-outline btn-xs" onClick={() => handleDelete(p.id)}>Delete</button>
                          </>
                        )}
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
