import { useState, useEffect } from 'react'
import { usePageTitle } from '../hooks/usePageTitle'
import { apiClient } from '../services/apiClient'
import { useNotificationStore } from '../stores/notificationStore'
import { frontendLoggingService } from '../services/frontendLoggingService'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar
} from 'recharts'

interface UsageStats {
  period: string
  days: number
  summary: {
    total_requests: number
    total_tokens: number
    total_cost_usd: number
    unique_sessions: number
    success_rate: number
    avg_response_time_ms: number
  }
  usage_by_agent: Array<{
    agent_id: number
    agent_name: string
    requests: number
    tokens: number
    cost_usd: number
  }>
  usage_by_provider: Array<{
    provider: string
    requests: number
    tokens: number
    cost_usd: number
  }>
  daily_usage: Array<{
    date: string
    requests: number
    tokens: number
    cost_usd: number
  }>
}

interface CostBreakdown {
  period: string
  days: number
  total_cost_usd: number
  projected_monthly_cost_usd: number
  cost_by_model: Array<{
    model: string
    cost_usd: number
    tokens: number
    requests: number
    avg_cost_per_1k_tokens: number
  }>
}

interface PerformanceMetrics {
  period: string
  agent_id: number | null
  response_time: {
    p50_ms: number
    p95_ms: number
    p99_ms: number
    min_ms: number
    max_ms: number
    avg_ms: number
  }
  token_stats: {
    total_prompt_tokens: number
    total_completion_tokens: number
    total_tokens: number
    avg_tokens_per_request: number
  }
  error_rate: number
  total_requests: number
}

interface SummaryCardProps {
  title: string
  value: string
  trend?: number
  trendLabel?: string
  icon?: React.ReactNode
  valueClass?: string
}

const SummaryCard: React.FC<SummaryCardProps> = ({
  title, value, trend, trendLabel, valueClass = 'text-3xl font-bold'
}) => {
  const isPositive = trend !== undefined && trend >= 0

  return (
    <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)]">
      <div className="card-body p-[var(--card-padding)]">
        <div className="text-sm text-readout">{title}</div>
        <div className={valueClass}>{value}</div>
        {trend !== undefined && (
          <div className={`text-sm ${isPositive ? 'text-error' : 'text-success'}`}>
            {isPositive ? '↑' : '↓'} {Math.abs(trend)}% {trendLabel || 'vs last period'}
          </div>
        )}
      </div>
    </div>
  )
}

export default function Analytics() {
  usePageTitle('Analytics', 'Usage metrics and performance insights')
  const addNotification = useNotificationStore((state) => state.addNotification)

  const [loading, setLoading] = useState(false)
  const [period, setPeriod] = useState('7d')
  // THE CHART TABS (2026-08-22, user): the charts were stacked in one
  // long scroll — now grouped: Overview / Cost / Providers / Performance.
  const [chartTab, setChartTab] = useState<'overview' | 'cost' | 'providers' | 'performance'>('overview')
  const [usageStats, setUsageStats] = useState<UsageStats | null>(null)
  const [costBreakdown, setCostBreakdown] = useState<CostBreakdown | null>(null)
  const [performance, setPerformance] = useState<PerformanceMetrics | null>(null)

  useEffect(() => {
    loadAnalytics()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period])

  const loadAnalytics = async () => {
    setLoading(true)
    try {
      const [usageRes, costsRes, perfRes] = await Promise.all([
        apiClient.get(`/api/v1/analytics/usage?period=${period}`),
        apiClient.get(`/api/v1/analytics/costs?period=30d`),
        apiClient.get(`/api/v1/analytics/performance?period=${period}`)
      ])

      setUsageStats(usageRes.data as UsageStats | null)
      setCostBreakdown(costsRes.data as CostBreakdown | null)
      setPerformance(perfRes.data as PerformanceMetrics | null)
    } catch (error: unknown) {
      frontendLoggingService.error('Analytics', 'Failed to load analytics', error as Error)
      addNotification({
        type: 'error',
        title: 'Error',
        message: 'Failed to load analytics data'
      })
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (num: number) => {
    return num.toLocaleString()
  }

  const formatCurrency = (num: number) => {
    return `$${num.toFixed(4)}`
  }

  const formatTokens = (num: number) => {
    if (num >= 1000000) {
      return `${(num / 1000000).toFixed(1)}M`
    }
    if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}K`
    }
    return num.toString()
  }

  const prepareChartData = (data: Array<{ date: string; tokens: number; requests: number; cost_usd: number }>) => {
    return data.map(item => ({
      ...item,
      date: new Date(item.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      tokensK: Math.round(item.tokens / 1000),
      requestsFormatted: item.requests
    }))
  }

  const prepareCostBreakdownData = (data: Array<{ model: string; cost_usd: number; tokens: number; requests: number }>) => {
    return data.map(item => ({
      ...item,
      name: item.model.length > 20 ? item.model.substring(0, 20) + '...' : item.model
    }))
  }

  const COLORS = ['#8884d8', '#00C49F', '#FFBB28', '#FF8042', '#8B5CF6', '#EC4899', '#10B981', '#3B82F6']

  const handleExportCSV = () => {
    if (!usageStats) return

    const headers = ['Date', 'Requests', 'Tokens', 'Cost (USD)']
    const rows = usageStats.daily_usage.map(day => [
      day.date,
      day.requests,
      day.tokens,
      day.cost_usd.toFixed(4)
    ])

    const csv = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `usage-report-${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    window.URL.revokeObjectURL(url)

    addNotification({
      type: 'success',
      title: 'Export Complete',
      message: 'Usage report downloaded successfully'
    })
  }

  return (
    <div className="min-h-screen bg-base-100">
      {/* Header */}
      <div className="bg-base-200 border-b border-base-300">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-4">
            <div>
              {/* THE HEADER (2026-08-22, user): no 'Back to Dashboard'
                  (the nav is always present) + the blurb moved to a
                  tooltip on the title. */}
              <div className="tooltip tooltip-right" data-tip="Usage metrics, cost tracking, and performance insights">
                <h1 className="text-3xl font-bold cursor-default">Analytics</h1>
              </div>
            </div>

            {/* Period Selector & Export */}
            <div className="flex items-center gap-4">
              <div className="join">
                <button
                  className={`join-item btn btn-sm ${period === '7d' ? 'btn-active btn-selected' : 'btn-outline'}`}
                  onClick={() => setPeriod('7d')}
                >
                  7 Days
                </button>
                <button
                  className={`join-item btn btn-sm ${period === '30d' ? 'btn-active btn-selected' : 'btn-outline'}`}
                  onClick={() => setPeriod('30d')}
                >
                  30 Days
                </button>
                <button
                  className={`join-item btn btn-sm ${period === '90d' ? 'btn-active btn-selected' : 'btn-outline'}`}
                  onClick={() => setPeriod('90d')}
                >
                  90 Days
                </button>
              </div>

              <button 
                className="btn btn-outline btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                onClick={handleExportCSV}
                disabled={!usageStats}
              >
                📥 Export CSV
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* THE CHART TABS (2026-08-22, user): one long scroll -> four
          grouped tabs. The period selector + export stay in the header. */}
      <div className="container mx-auto px-4">
        <div className="mb-6 border-b border-base-content/20">
          <nav className="-mb-px flex gap-4 overflow-x-auto">
            {([
              ['overview', 'Overview'],
              ['cost', 'Cost'],
              ['providers', 'Providers'],
              ['performance', 'Performance'],
            ] as const).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setChartTab(key)}
                className={`pb-3 px-1 font-medium text-sm whitespace-nowrap transition-colors ${
                  chartTab === key
                    ? 'border-b-2 border-primary text-primary'
                    : 'text-base-content/60 hover:text-base-content'
                }`}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Content */}
      <div className="container mx-auto px-4 py-8">
        {loading ? (
          <div className="flex justify-center py-12">
            <span className="loading loading-spinner loading-lg"></span>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Summary Cards */}
            {usageStats && (
              <>
                {chartTab === 'overview' && (
                <>
                <div>
                  <h2 className="text-xl font-bold mb-4">Usage Summary</h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <SummaryCard
                      title="Total Requests"
                      value={formatNumber(usageStats.summary.total_requests)}
                      trend={12.5}
                      trendLabel="vs last period"
                    />

                    <SummaryCard
                      title="Total Tokens"
                      value={formatTokens(usageStats.summary.total_tokens)}
                      trend={8.3}
                      trendLabel="vs last period"
                    />

                    <SummaryCard
                      title="Total Cost"
                      value={formatCurrency(usageStats.summary.total_cost_usd)}
                      trend={5.2}
                      trendLabel="vs last period"
                      valueClass="text-3xl font-bold text-accent"
                    />

                    <SummaryCard
                      title="Success Rate"
                      value={`${usageStats.summary.success_rate}%`}
                      trend={-0.5}
                      trendLabel="vs last period"
                      valueClass="text-3xl font-bold text-success"
                    />
                  </div>
                </div>

                {/* Usage Trend Chart */}
                <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)]">
                  <div className="card-body p-[var(--card-padding)]">
                    <h2 className="card-title mb-4">Usage Trends</h2>
                    <ResponsiveContainer width="100%" height={300}>
                      <LineChart data={prepareChartData(usageStats.daily_usage)}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                        <XAxis 
                          dataKey="date" 
                          stroke="#9CA3AF"
                          fontSize={12}
                        />
                        <YAxis 
                          yAxisId="left"
                          stroke="#8884d8"
                          fontSize={12}
                          tickFormatter={(value) => `${value}K`}
                        />
                        <YAxis 
                          yAxisId="right"
                          orientation="right"
                          stroke="#82ca9d"
                          fontSize={12}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#1F2937',
                            border: '1px solid #374151',
                            borderRadius: '8px',
                            color: '#F9FAFB'
                          }}
                          formatter={((value: number, name: string): string => {
                            if (name === 'Tokens (K)') return `${value}K`
                            return value.toLocaleString()
                          }) as never}
                        />
                        <Legend />
                        <Line
                          yAxisId="left"
                          type="monotone"
                          dataKey="tokensK"
                          stroke="#8884d8"
                          strokeWidth={2}
                          dot={{ r: 4, fill: '#8884d8' }}
                          name="Tokens (K)"
                        />
                        <Line
                          yAxisId="right"
                          type="monotone"
                          dataKey="requestsFormatted"
                          stroke="#82ca9d"
                          strokeWidth={2}
                          dot={{ r: 4, fill: '#82ca9d' }}
                          name="Requests"
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                </>
                )}

                {chartTab === 'cost' && (
                <>
                {/* Cost Breakdown Chart */}
                <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)]">
                  <div className="card-body p-[var(--card-padding)]">
                    <h2 className="card-title mb-4">Cost Breakdown by Model</h2>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      <ResponsiveContainer width="100%" height={300}>
                        <PieChart>
                          <Pie
                            data={prepareCostBreakdownData(costBreakdown?.cost_by_model || [])}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            label={({ name, percent }) => `${name}: ${percent ? (percent * 100).toFixed(0) : 0}%`}
                            outerRadius={80}
                            fill="#8884d8"
                            dataKey="cost_usd"
                          >
                            {prepareCostBreakdownData(costBreakdown?.cost_by_model || []).map((_, index) => (
                              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip
                            contentStyle={{
                              backgroundColor: '#1F2937',
                              border: '1px solid #374151',
                              borderRadius: '8px',
                              color: '#F9FAFB'
                            }}
                            formatter={((value: number): string => `$${value.toFixed(4)}`) as (value: unknown, name: unknown, entry: unknown, index: number) => import('react').ReactNode}
                          />
                          <Legend />
                        </PieChart>
                      </ResponsiveContainer>

                      {/* Cost Summary */}
                      <div className="flex flex-col justify-center">
                        <div className="p-6 bg-base-200 rounded-[var(--card-radius)]">
                          <div className="text-sm text-readout mb-2">Total Cost (30 days)</div>
                          <div className="text-4xl font-bold text-accent mb-4">
                            {formatCurrency(costBreakdown?.total_cost_usd || 0)}
                          </div>
                          <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                              <span className="text-readout">Projected Monthly:</span>
                              <span className="font-medium">
                                {formatCurrency(costBreakdown?.projected_monthly_cost_usd || 0)}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-readout">Models:</span>
                              <span className="font-medium">{costBreakdown?.cost_by_model.length || 0}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                </>
                )}

                {chartTab === 'providers' && (
                <>
                {/* Usage by Agent */}
                <div>
                  <h2 className="text-xl font-bold mb-4">Usage by Agent</h2>
                  <div className="overflow-x-auto">
                    <table className="table table-zebra w-full">
                      <thead>
                        <tr>
                          <th>Agent</th>
                          <th className="text-right">Requests</th>
                          <th className="text-right">Tokens</th>
                          <th className="text-right">Cost</th>
                          <th className="text-right">% of Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {usageStats.usage_by_agent.map((agent, idx) => {
                          const pct = (agent.requests / usageStats.summary.total_requests * 100) || 0
                          return (
                            <tr key={idx}>
                              <td className="font-medium">{agent.agent_name}</td>
                              <td className="text-right">{formatNumber(agent.requests)}</td>
                              <td className="text-right">{formatNumber(agent.tokens)}</td>
                              <td className="text-right">{formatCurrency(agent.cost_usd)}</td>
                              <td className="text-right">
                                <div className="flex items-center justify-end gap-2">
                                  <div className="w-24 h-2 bg-base-200 rounded-full overflow-hidden">
                                    <div 
                                      className="h-full bg-primary rounded-full"
                                      style={{ width: `${pct}%` }}
                                    ></div>
                                  </div>
                                  <span className="text-xs text-readout">{pct.toFixed(1)}%</span>
                                </div>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Provider Comparison Chart */}
                <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)]">
                  <div className="card-body p-[var(--card-padding)]">
                    <h2 className="card-title mb-4">Provider Comparison</h2>
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={usageStats.usage_by_provider}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                        <XAxis 
                          dataKey="provider" 
                          stroke="#9CA3AF"
                          fontSize={12}
                        />
                        <YAxis 
                          yAxisId="left"
                          orientation="left"
                          stroke="#8884d8"
                          fontSize={12}
                          tickFormatter={(value) => `$${value.toFixed(2)}`}
                        />
                        <YAxis 
                          yAxisId="right"
                          orientation="right"
                          stroke="#82ca9d"
                          fontSize={12}
                          tickFormatter={(value) => `${value >= 1000 ? `${(value/1000).toFixed(0)}K` : value}`}
                        />
                        <Tooltip 
                          contentStyle={{
                            backgroundColor: '#1F2937',
                            border: '1px solid #374151',
                            borderRadius: '8px',
                            color: '#F9FAFB'
                          }}
                        />
                        <Legend />
                        <Bar 
                          yAxisId="left"
                          dataKey="cost_usd" 
                          fill="#8884d8" 
                          name="Cost (USD)"
                          radius={[4, 4, 0, 0]}
                        />
                        <Bar 
                          yAxisId="right"
                          dataKey="tokens" 
                          fill="#82ca9d" 
                          name="Tokens"
                          radius={[4, 4, 0, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Usage by Provider */}
                <div>
                  <h2 className="text-xl font-bold mb-4">Usage by Provider</h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {usageStats.usage_by_provider.map((provider, idx) => (
                      <div key={idx} className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)]">
                        <div className="card-body p-[var(--card-padding)]">
                          <div className="flex items-center justify-between mb-2">
                            <h3 className="font-bold text-lg">{provider.provider}</h3>
                            <span className="badge badge-primary badge-sm">
                              {formatNumber(provider.requests)} requests
                            </span>
                          </div>
                          <div className="space-y-1 text-sm">
                            <div className="flex justify-between">
                              <span className="text-readout">Tokens:</span>
                              <span className="font-medium">{formatNumber(provider.tokens)}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-readout">Cost:</span>
                              <span className="font-medium">{formatCurrency(provider.cost_usd)}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                </>
                )}
              </>
            )}

            {chartTab === 'performance' && performance && (
            <>
            {/* Performance Metrics */}
            <div>
              <div>
                <h2 className="text-xl font-bold mb-4">Performance Metrics</h2>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Response Times */}
                  <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)]">
                    <div className="card-body gap-[var(--card-gap)]">
                      <h3 className="font-bold text-lg mb-4">Response Times</h3>
                      <div className="space-y-3">
                        <div className="flex justify-between items-center">
                          <span className="text-readout">Average</span>
                          <span className="font-bold">{formatNumber(Math.round(performance.response_time.avg_ms))} ms</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-readout">P50 (Median)</span>
                          <span className="font-bold">{formatNumber(Math.round(performance.response_time.p50_ms))} ms</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-readout">P95</span>
                          <span className="font-bold">{formatNumber(Math.round(performance.response_time.p95_ms))} ms</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-readout">P99</span>
                          <span className="font-bold">{formatNumber(Math.round(performance.response_time.p99_ms))} ms</span>
                        </div>
                        <div className="divider my-2"></div>
                        <div className="flex justify-between items-center">
                          <span className="text-readout">Min</span>
                          <span className="text-sm">{formatNumber(Math.round(performance.response_time.min_ms))} ms</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-readout">Max</span>
                          <span className="text-sm">{formatNumber(Math.round(performance.response_time.max_ms))} ms</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Token Statistics */}
                  <div className="card bg-base-100 shadow-[var(--card-shadow)] rounded-[var(--card-radius)]">
                    <div className="card-body gap-[var(--card-gap)]">
                      <h3 className="font-bold text-lg mb-4">Token Statistics</h3>
                      <div className="space-y-3">
                        <div className="flex justify-between items-center">
                          <span className="text-readout">Total Tokens</span>
                          <span className="font-bold">{formatNumber(performance.token_stats.total_tokens)}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-readout">Prompt Tokens</span>
                          <span className="font-medium">{formatNumber(performance.token_stats.total_prompt_tokens)}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-readout">Completion Tokens</span>
                          <span className="font-medium">{formatNumber(performance.token_stats.total_completion_tokens)}</span>
                        </div>
                        <div className="divider my-2"></div>
                        <div className="flex justify-between items-center">
                          <span className="text-readout">Avg per Request</span>
                          <span className="font-bold">{formatNumber(performance.token_stats.avg_tokens_per_request)}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-readout">Error Rate</span>
                          <span className={`font-bold ${performance.error_rate > 0 ? 'text-error' : 'text-success'}`}>
                            {performance.error_rate}%
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            </>
            )}

            {chartTab === 'cost' && costBreakdown && (
            <>
            {/* Cost Breakdown */}
            <div>
              <div>
                <h2 className="text-xl font-bold mb-4">Cost Breakdown (30 days)</h2>
                <div className="overflow-x-auto">
                  <table className="table w-full">
                    <thead>
                      <tr>
                        <th>Model</th>
                        <th className="text-right">Requests</th>
                        <th className="text-right">Tokens</th>
                        <th className="text-right">Cost</th>
                        <th className="text-right">Cost per 1K tokens</th>
                      </tr>
                    </thead>
                    <tbody>
                      {costBreakdown.cost_by_model.map((model, idx) => (
                        <tr key={idx}>
                          <td className="font-medium">{model.model}</td>
                          <td className="text-right">{formatNumber(model.requests)}</td>
                          <td className="text-right">{formatNumber(model.tokens)}</td>
                          <td className="text-right">{formatCurrency(model.cost_usd)}</td>
                          <td className="text-right text-sm text-readout">
                            ${model.avg_cost_per_1k_tokens.toFixed(4)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="font-bold">
                        <td>Total</td>
                        <td className="text-right">{formatNumber(costBreakdown.cost_by_model.reduce((sum, m) => sum + m.requests, 0))}</td>
                        <td className="text-right">{formatNumber(costBreakdown.cost_by_model.reduce((sum, m) => sum + m.tokens, 0))}</td>
                        <td className="text-right">{formatCurrency(costBreakdown.total_cost_usd)}</td>
                        <td className="text-right"></td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>
            </div>
            </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
