import { useState, useEffect } from 'react'

interface TraceSummary {
  trace_id: string
  name: string
  session_id: string | null
  mode: string | null
  started_at: number
  duration_ms: number
  observation_count: number
  warning_count: number
  tags: string[]
}

interface TraceObservation {
  id: string
  name: string
  kind: string
  trace_id: string
  parent_id: string | null
  started_at: number
  duration_ms: number | null
  level: string
  status_message: string | null
  metadata: Record<string, unknown>
  mode: string | null
}

const API_BASE = "/api/v1/traces"

export default function BackendTraceViewer({ defaultSource, title, sourceLabel }: { defaultSource?: string; title?: string; sourceLabel?: string }) {
  const [traces, setTraces] = useState<TraceSummary[]>([])
  const [selectedTrace, setSelectedTrace] = useState<string | null>(null)
  const [traceDetail, setTraceDetail] = useState<TraceObservation[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sessionFilter, setSessionFilter] = useState("")

  const fetchTraces = async (sessionId?: string, source?: string) => {
    setLoading(true)
    setError(null)
    try {
      let url = `${API_BASE}/traces?limit=50`
      if (sessionId) url += `&session_id=${encodeURIComponent(sessionId)}`
      if (source) url += `&source=${encodeURIComponent(source)}`
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setTraces(data.traces || [])
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  const fetchTraceDetail = async (traceId: string) => {
    setSelectedTrace(traceId)
    setTraceDetail(null)
    try {
      const res = await fetch(`${API_BASE}/traces/${encodeURIComponent(traceId)}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setTraceDetail(data.observations || [])
    } catch {
      setTraceDetail([])
    }
  }

  useEffect(() => {
    fetchTraces(undefined, defaultSource)
  }, [defaultSource])

  const formatTime = (ts: number) => {
    const d = new Date(ts * 1000)
    return d.toLocaleTimeString()
  }

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms.toFixed(0)}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  return (
    <div style={{ padding: "1rem" }}>
      <h3>{title || "Request Traces"}</h3>
      <p style={{ color: "var(--text-secondary)", marginBottom: "1rem" }}>
        {sourceLabel || "Recent traces from the cognitive pipeline."}
      </p>

      {/* Session filter */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <input
          type="text"
          placeholder="Filter by session ID..."
          value={sessionFilter}
          onChange={(e) => setSessionFilter(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") fetchTraces(sessionFilter || undefined) }}
          style={{ flex: 1, padding: "0.4rem" }}
        />
        <button onClick={() => fetchTraces(sessionFilter || undefined)}>Search</button>
        <button onClick={() => { setSessionFilter(""); fetchTraces() }}>Clear</button>
      </div>

      {error && <p style={{ color: "var(--danger)" }}>Error: {error}</p>}

      {loading ? (
        <p>Loading traces...</p>
      ) : traces.length === 0 ? (
        <p>No traces found. {title?.includes("Agent") ? "Chat with an agent to generate traces." : "Chat with an agent to generate traces."}</p>
      ) : (
        <>
          {/* Trace list */}
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
                <th style={{ padding: "0.4rem" }}>Time</th>
                <th style={{ padding: "0.4rem" }}>Mode</th>
                <th style={{ padding: "0.4rem" }}>Session</th>
                <th style={{ padding: "0.4rem" }}>Duration</th>
                <th style={{ padding: "0.4rem" }}>Observations</th>
                <th style={{ padding: "0.4rem" }}>Warnings</th>
                <th style={{ padding: "0.4rem" }}></th>
              </tr>
            </thead>
            <tbody>
              {traces.map((t) => (
                <tr
                  key={t.trace_id}
                  style={{
                    borderBottom: "1px solid var(--border)",
                    background: t.trace_id === selectedTrace ? "var(--accent-bg)" : undefined,
                    cursor: "pointer",
                  }}
                  onClick={() => fetchTraceDetail(t.trace_id)}
                >
                  <td style={{ padding: "0.4rem" }}>{formatTime(t.started_at)}</td>
                  <td style={{ padding: "0.4rem" }}>{t.mode || "-"}</td>
                  <td style={{ padding: "0.4rem", fontSize: "0.85em" }}>
                    {String(t.session_id ?? "-").slice(0, 20)}
                  </td>
                  <td style={{ padding: "0.4rem" }}>{formatDuration(t.duration_ms)}</td>
                  <td style={{ padding: "0.4rem" }}>{t.observation_count}</td>
                  <td style={{
                    padding: "0.4rem",
                    color: t.warning_count > 0 ? "var(--warning)" : undefined,
                    fontWeight: t.warning_count > 0 ? "bold" : undefined,
                  }}>
                    {t.warning_count > 0 ? t.warning_count : "-"}
                  </td>
                  <td style={{ padding: "0.4rem" }}>
                    {t.warning_count > 0 ? "⚠️" : "🔍"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Trace detail */}
          {selectedTrace && traceDetail && (
            <div style={{ marginTop: "1.5rem", border: "1px solid var(--border)", borderRadius: "6px", padding: "1rem" }}>
              <h4>Trace: {selectedTrace.slice(0, 30)}...</h4>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9em" }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
                    <th style={{ padding: "0.3rem" }}>Name</th>
                    <th style={{ padding: "0.3rem" }}>Kind</th>
                    <th style={{ padding: "0.3rem" }}>Duration</th>
                    <th style={{ padding: "0.3rem" }}>Level</th>
                    <th style={{ padding: "0.3rem" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {traceDetail.map((obs) => (
                    <tr key={obs.id} style={{ borderBottom: "1px solid var(--border)" }}>
                      <td style={{ padding: "0.3rem" }}>{obs.name}</td>
                      <td style={{ padding: "0.3rem" }}>{obs.kind}</td>
                      <td style={{ padding: "0.3rem" }}>
                        {obs.duration_ms ? formatDuration(obs.duration_ms) : "-"}
                      </td>
                      <td style={{
                        padding: "0.3rem",
                        color: obs.level === "ERROR" ? "var(--danger)" : obs.level === "WARNING" ? "var(--warning)" : undefined,
                      }}>
                        {obs.level}
                      </td>
                      <td style={{ padding: "0.3rem", fontSize: "0.85em" }}>
                        {obs.status_message ? obs.status_message.slice(0, 60) : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
