import { useSystemHealth, useSystemMetrics, useLogStats } from '@/hooks'

interface SystemMetricsData {
  cpu?: { usage: number }
  memory?: { usage: number }
}

interface LogStatsData {
  recentActivity?: number
}

interface StatItem {
  label: string
  value: string
  color: string
}

export default function QuickStats() {
  const {
    isHealthy,
    isLoading: healthLoading
  } = useSystemHealth()

  const {
    data: rawMetrics,
    isLoading: metricsLoading
  } = useSystemMetrics()
  const metrics = rawMetrics as SystemMetricsData | undefined

  const {
    data: rawLogStats,
    isLoading: statsLoading
  } = useLogStats()
  const logStats = rawLogStats as LogStatsData | undefined

  const systemStats: StatItem[] = [
    {
      label: 'System Status',
      value: healthLoading ? 'Loading...' : isHealthy ? 'Healthy' : 'Unhealthy',
      color: healthLoading ? 'text-neutral' : isHealthy ? 'text-success' : 'text-error'
    },
    {
      label: 'CPU Usage',
      value: metricsLoading ? 'Loading...' : metrics?.cpu ? `${Math.round(metrics.cpu.usage)}%` : 'N/A',
      color: metricsLoading ? 'text-neutral' : (metrics?.cpu?.usage || 0) > 80 ? 'text-error' : (metrics?.cpu?.usage || 0) > 60 ? 'text-warning' : 'text-success'
    },
    {
      label: 'Memory Usage',
      value: metricsLoading ? 'Loading...' : metrics?.memory ? `${Math.round(metrics.memory.usage)}%` : 'N/A',
      color: metricsLoading ? 'text-neutral' : (metrics?.memory?.usage || 0) > 80 ? 'text-error' : (metrics?.memory?.usage || 0) > 60 ? 'text-warning' : 'text-success'
    },
    {
      label: 'Recent Logs',
      value: statsLoading ? 'Loading...' : logStats?.recentActivity ? `${logStats.recentActivity}` : 'N/A',
      color: 'text-info'
    }
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      {systemStats.map((stat, index) => (
        // the status/CPU/memory tiles are the at-a-glance summary;
        // the System Info page was removed (2026-08-16) — monitoring
        // isn't the product, so these are summary-only
        <div
          key={index}
          className="stat bg-base-100 shadow-lg rounded-box"
        >
          <div className="stat-title">{stat.label}</div>
          <div className={`stat-value text-2xl ${stat.color}`}>{stat.value}</div>
        </div>
      ))}
    </div>
  )
}