/**
 * CognitiveProfilesTab — CRUD table for cognitive profile configurations.
 * Bundles strategy selectors with a memory profile picker.
 */

import { useState, useEffect } from 'react'
import { cognitiveProfileService, type CognitiveProfile, type CognitiveProfileCreate, type CognitiveProfileUpdate } from '@/services/domain/CognitiveProfileService'
import { memoryProfileService, type MemoryProfile } from '@/services/domain/MemoryProfileService'
import { frontendLoggingService } from '@/services/frontendLoggingService'

export default function CognitiveProfilesTab() {
  const [profiles, setProfiles] = useState<CognitiveProfile[]>([])
  const [memoryProfiles, setMemoryProfiles] = useState<MemoryProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [formData, setFormData] = useState<CognitiveProfileCreate>({
    name: '',
    description: '',
    context_builder: 'default',
    executor: 'default',
    response_formatter: 'default',
    memory_profile_id: null,
  })

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [profilesData, memData] = await Promise.all([
        cognitiveProfileService.list(),
        memoryProfileService.list(),
      ])
      setProfiles(profilesData)
      setMemoryProfiles(memData)
    } catch (err) {
      frontendLoggingService.error('CognitiveProfilesTab', 'Failed to fetch data', err)
      setError('Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleCreate = async () => {
    if (!formData.name.trim()) return
    try {
      await cognitiveProfileService.create(formData)
      setShowCreate(false)
      setFormData({ name: '', description: '', context_builder: 'default', executor: 'default', response_formatter: 'default', memory_profile_id: null })
      await fetchData()
    } catch (err) {
      frontendLoggingService.error('CognitiveProfilesTab', 'Failed to create profile', err)
      setError('Failed to create profile')
    }
  }

  const handleUpdate = async (id: number, data: CognitiveProfileUpdate) => {
    try {
      await cognitiveProfileService.update(id, data)
      setEditingId(null)
      await fetchData()
    } catch (err) {
      frontendLoggingService.error('CognitiveProfilesTab', 'Failed to update profile', err)
      setError('Failed to update profile')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await cognitiveProfileService.delete(id)
      await fetchData()
    } catch (err) {
      frontendLoggingService.error('CognitiveProfilesTab', 'Failed to delete profile', err)
      setError('Failed to delete profile')
    }
  }

  if (loading) {
    return <div className="flex justify-center py-8"><span className="loading loading-spinner loading-md"></span></div>
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-readout">Cognitive Profiles</h3>
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
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="text-[11px] text-readout">Context Builder</label>
              <select className="select select-bordered select-xs w-full" value={formData.context_builder} onChange={(e) => setFormData({ ...formData, context_builder: e.target.value })}>
                <option value="default">default</option>
                <option value="minimal">minimal</option>
                <option value="augmented">augmented</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] text-readout">Executor</label>
              <select className="select select-bordered select-xs w-full" value={formData.executor} onChange={(e) => setFormData({ ...formData, executor: e.target.value })}>
                <option value="default">default</option>
                <option value="fast">fast</option>
                <option value="hybrid">hybrid</option>
                <option value="stub">stub</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] text-readout">Response Formatter</label>
              <select className="select select-bordered select-xs w-full" value={formData.response_formatter} onChange={(e) => setFormData({ ...formData, response_formatter: e.target.value })}>
                <option value="default">default</option>
                <option value="direct_yield">direct_yield</option>
                <option value="structured">structured</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-[11px] text-readout">Memory Profile</label>
            <select className="select select-bordered select-xs w-full" value={formData.memory_profile_id ?? ''} onChange={(e) => setFormData({ ...formData, memory_profile_id: e.target.value ? parseInt(e.target.value) : null })}>
              <option value="">— None —</option>
              {memoryProfiles.map((mp) => (
                <option key={mp.id} value={mp.id}>{mp.name}</option>
              ))}
            </select>
          </div>
          <button className="btn btn-primary btn-xs w-full mt-1" onClick={handleCreate} disabled={!formData.name.trim()}>
            Create Profile
          </button>
        </div>
      )}

      {profiles.length === 0 ? (
        <div className="text-center py-8 text-readout text-sm">No cognitive profiles configured</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="table table-xs">
            <thead>
              <tr>
                <th>Name</th>
                <th>Context Builder</th>
                <th>Executor</th>
                <th>Response Formatter</th>
                <th>Memory Profile</th>
                <th>Built-in</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {profiles.map((p) => (
                <tr key={p.id} className="hover">
                  {editingId === p.id ? (
                    <>
                      <td><input className="input input-bordered input-xs w-20" defaultValue={p.name} id={'ce-name-' + p.id} /></td>
                      <td>
                        <select className="select select-bordered select-xs" defaultValue={p.context_builder} id={'ce-cb-' + p.id}>
                          <option value="default">default</option>
                        </select>
                      </td>
                      <td>
                        <select className="select select-bordered select-xs" defaultValue={p.executor} id={'ce-ex-' + p.id}>
                          <option value="default">default</option>
                          <option value="fast">fast</option>
                <option value="hybrid">hybrid</option>
                <option value="stub">stub</option>
                        </select>
                      </td>
                      <td>
                        <select className="select select-bordered select-xs" defaultValue={p.response_formatter} id={'ce-rf-' + p.id}>
                          <option value="default">default</option>
                        </select>
                      </td>
                      <td>
                        <select className="select select-bordered select-xs" defaultValue={p.memory_profile_id ?? ''} id={'ce-mp-' + p.id}>
                          <option value="">None</option>
                          {memoryProfiles.map((mp) => (
                            <option key={mp.id} value={mp.id}>{mp.name}</option>
                          ))}
                        </select>
                      </td>
                      <td>{p.is_builtin ? '🔒' : ''}</td>
                      <td className="flex gap-1">
                        <button className="btn btn-ghost btn-xs" onClick={async () => {
                          const nameEl = document.getElementById('ce-name-' + p.id) as HTMLInputElement
                          const cbEl = document.getElementById('ce-cb-' + p.id) as HTMLSelectElement
                          const exEl = document.getElementById('ce-ex-' + p.id) as HTMLSelectElement
                          const rfEl = document.getElementById('ce-rf-' + p.id) as HTMLSelectElement
                          const mpEl = document.getElementById('ce-mp-' + p.id) as HTMLSelectElement
                          await handleUpdate(p.id, {
                            name: nameEl?.value || p.name,
                            context_builder: cbEl?.value || p.context_builder,
                            executor: exEl?.value || p.executor,
                            response_formatter: rfEl?.value || p.response_formatter,
                            memory_profile_id: mpEl?.value ? parseInt(mpEl.value) : null,
                          })
                        }}>Save</button>
                        <button className="btn btn-neutral btn-ghost btn-xs" onClick={() => setEditingId(null)}>Cancel</button>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="font-medium">{p.name}</td>
                      <td><code className="text-xs">{p.context_builder}</code></td>
                      <td><code className="text-xs">{p.executor}</code></td>
                      <td><code className="text-xs">{p.response_formatter}</code></td>
                      <td>{p.memory_profile_name || '-'}</td>
                      <td>{p.is_builtin ? '🔒' : ''}</td>
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
