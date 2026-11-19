/**
 * AgentMemoryTab — Memory profile UI for deep agents.
 *
 * Shows memory status, facts, summaries, and vector index for each deep agent.
 * Provides clear/reset/export buttons.
 */

import { useEffect, useState } from 'react'
import { frontendLoggingService } from '@/services/frontendLoggingService'
import { useNotificationStore } from '@/stores/notificationStore'

interface MemoryStatus {
  agent_folder: string
  has_cognitive_memory_db: boolean
  session_count: number
  turn_count: number
  has_summaries: boolean
  summary_count: number
  fact_count: number
  has_vector_index: boolean
  vector_turn_count: number
}

interface DeepAgent {
  folder: string
  name: string
  description: string
}

const API = '/api/v1'

export default function AgentMemoryTab() {
  const [agents, setAgents] = useState<DeepAgent[]>([])
  const [statuses, setStatuses] = useState<Record<string, MemoryStatus>>({})
  const [expanded, setExpanded] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // Load deep agents from the server dynamically
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/v1/cognitive/memory/agents')
        if (res.ok) {
          const list: DeepAgent[] = await res.json()
          setAgents(list)
          loadStatuses(list.map((a) => a.folder))
        }
      } catch (err) {
        frontendLoggingService.warning('AgentMemoryTab', 'Memory operation failed', { error: err instanceof Error ? err.message : String(err) })
      }
      setLoading(false)
    })()
  }, [])

  async function loadStatuses(folders: string[]) {
    const results: Record<string, MemoryStatus> = {}
    for (const f of folders) {
      try {
        const res = await fetch(`${API}/cognitive/memory/${f}/status`)
        if (res.ok) results[f] = await res.json()
      } catch (err) {
        frontendLoggingService.warning('AgentMemoryTab', 'Memory operation failed', { error: err instanceof Error ? err.message : String(err) })
      }
    }
    setStatuses(results)
  }

  async function doAction(action: string, folder: string, extra = '') {
    try {
      const url = extra
        ? `${API}/${action}/${folder}/${extra}`
        : `${API}/${action}/${folder}`
      const res = await fetch(url, { method: action.includes('prune') ? 'POST' : 'DELETE' })
      const data = await res.json()
      useNotificationStore.getState().addSuccess('Memory Action', data.message || JSON.stringify(data))
      // Refresh
      setTimeout(() => loadStatuses(agents.map((a) => a.folder)), 500)
    } catch (e: any) { // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
      useNotificationStore.getState().addError('Memory Action', e.message)
    }
  }

  async function doExport(folder: string) {
    try {
      const res = await fetch(`${API}/cognitive/memory/${folder}/export`)
      const data = await res.json()
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${folder}-memory-export.json`
      a.click()
      URL.revokeObjectURL(url)
      useNotificationStore.getState().addSuccess('Export', `Exported ${folder} memory`)
    } catch (e: any) { // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
      useNotificationStore.getState().addError('Export', e.message)
    }
  }

  if (loading) return <div className="p-4">Loading agents...</div>

  return (
    <div>

      {agents.length === 0 && (
        <div className="text-center py-8 text-readout">
          <p className="text-lg mb-2">No deep agents provisioned</p>
          <p className="text-sm">Use <code>POST /api/v1/agents/{'{name}'}/provision</code> to create one</p>
        </div>
      )}

      <div className="space-y-3">
        {agents.map((agent) => {
          const s = statuses[agent.folder]
          return (
            <div key={agent.folder} className="card bg-base-200 rounded-box">
              <div className="card-body p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-bold text-lg">{agent.name}</h3>
                    <p className="text-sm text-readout">{agent.folder}</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      className="btn btn-xs btn-outline"
                      onClick={() => setExpanded(expanded === agent.folder ? null : agent.folder)}
                    >
                      {expanded === agent.folder ? 'Collapse' : 'Details'}
                    </button>
                    <button
                      className="btn btn-xs btn-primary"
                      onClick={() => doExport(agent.folder)}
                    >
                      Export
                    </button>
                  </div>
                </div>

                {/* Summary row */}
                {s && (
                  <div className="flex flex-wrap gap-3 mt-2 text-xs">
                    <span className="badge badge-sm badge-ghost">
                      Sessions: {s.session_count}
                    </span>
                    <span className="badge badge-sm badge-ghost">
                      Turns: {s.turn_count}
                    </span>
                    <span className={'badge badge-sm badge-ghost ' + (s.has_summaries ? 'badge-success badge-outline' : '')}>
                      Summaries: {s.summary_count}
                    </span>
                    <span className={'badge badge-sm badge-ghost ' + (s.fact_count > 0 ? 'badge-success badge-outline' : '')}>
                      Facts: {s.fact_count}
                    </span>
                    <span className={'badge badge-sm badge-ghost ' + (s.has_vector_index ? 'badge-success badge-outline' : '')}>
                      Vector: {s.vector_turn_count} turns
                    </span>
                  </div>
                )}

                {/* Expanded details */}
                {expanded === agent.folder && s && (
                  <div className="mt-3 pt-3 border-t border-base-300 space-y-2">
                    <div className="flex flex-wrap gap-2">
                      <button
                        className="btn btn-xs btn-warning"
                        onClick={() => doAction('cognitive/memory', agent.folder, 'clear/sessions')}
                      >
                        Clear Sessions
                      </button>
                      <button
                        className="btn btn-xs btn-warning"
                        onClick={() => doAction('cognitive/memory', agent.folder, 'clear/all')}
                      >
                        Clear All Memory
                      </button>
                      <button
                        className="btn btn-xs btn-warning"
                        onClick={async () => {
                          try {
                            await fetch(`${API}/cognitive/memory/prune`, {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ max_days: 30 }),
                            })
                            useNotificationStore.getState().addSuccess('Prune', 'Pruned entries older than 30 days')
                            setTimeout(() => loadStatuses(agents.map((a) => a.folder)), 500)
                          } catch (e: any) { // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
                            useNotificationStore.getState().addError('Prune', e.message)
                          }
                        }}
                      >
                        Prune (30d)
                      </button>
                      {s.has_vector_index && (
                        <button
                          className="btn btn-xs btn-warning"
                          onClick={() => doAction('cognitive/vectors', agent.folder, 'all')}
                        >
                          Clear Vectors
                        </button>
                      )}
                    </div>
                    {s.fact_count > 0 && (
                      <div className="text-xs">
                        <span className="font-semibold">Facts extracted:</span> {s.fact_count} facts stored
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
