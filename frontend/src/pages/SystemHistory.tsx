/**
 * System History Page - Log analysis and historical insights
 *
 * Philosophy:
 * - History is derived from logs (single source of truth)
 * - No Zustand store dependency (pure log analysis)
 * - No persistence initially (compute on-demand)
 *
 * Tabs:
 * - Log Analysis: Message frequency and error analysis
 * - Message Analysis: Performance metrics and provider comparison
 * - Session Analysis: Recent session statistics and trends
 */

import { useState } from 'react'
import { usePageTitle } from '../hooks/usePageTitle'
import { PageBanner } from '../components/ui/PageBanner'
import { PageContainer } from '../components/ui/PageContainer'
import DateRangeSelector, { type TimeRange } from '../components/history/DateRangeSelector'
import StatsCards from '../components/history/StatsCards'
import HistogramTable from '../components/history/HistogramTable'
import IssueAlerts from '../components/history/IssueAlerts'
import MessagePerformanceCards from '../components/history/MessagePerformanceCards'
import MessageDistributionChart from '../components/history/MessageDistributionChart'
import ProviderComparisonTable from '../components/history/ProviderComparisonTable'
import SessionSummaryCards from '../components/history/SessionSummaryCards'
import SessionCards from '../components/history/SessionCards'
import SessionAnalysisControls from '../components/history/SessionAnalysisControls'
import {
  useLogsHistogram,
  useHistoryStats,
  useHistoryIssues,
  useMessageAnalysis,
  useSessionAnalysis
} from '../hooks/useHistory'

type AnalysisTab = 'logs' | 'messages' | 'sessions'

export default function SystemHistory() {
  usePageTitle('History', 'Analyze log patterns and message frequencies')
  
  // Active tab
  const [activeTab, setActiveTab] = useState<AnalysisTab>('logs')

  // Time range state - default to last 24 hours
  const [timeRange, setTimeRange] = useState<TimeRange>({
    from: new Date(Date.now() - 24 * 60 * 60 * 1000),
    to: new Date()
  })

  // Session analysis state
  const [sessionLimit, setSessionLimit] = useState<number>(10)

  // Log Analysis data
  const {
    data: histogram,
    isLoading: histogramLoading,
    error: histogramError,
    refetch: refetchHistogram
  } = useLogsHistogram(timeRange)

  const {
    data: stats,
    isLoading: statsLoading
  } = useHistoryStats(timeRange)

  const {
    data: issues,
    isLoading: issuesLoading
  } = useHistoryIssues()

  // Message Analysis data
  const {
    data: messageAnalysis,
    isLoading: messageLoading,
    refetch: refetchMessageAnalysis
  } = useMessageAnalysis(timeRange)

  // Session Analysis data
  const {
    data: sessionAnalysis,
    isLoading: sessionLoading,
    refetch: refetchSessionAnalysis
  } = useSessionAnalysis(sessionLimit)

  const handleTimeRangeChange = (newRange: TimeRange) => {
    setTimeRange(newRange)
  }

  const handleTabChange = (tab: AnalysisTab) => {
    setActiveTab(tab)
  }

  const handleSessionLimitChange = (newLimit: number) => {
    setSessionLimit(newLimit)
  }

  const handleGenerateSessionAnalysis = () => {
    refetchSessionAnalysis()
  }

  return (
    <PageContainer>
      <PageBanner
        title="History"
        description="Analyze log patterns, message performance, and session trends to understand system behavior"

      />

      <div className="space-y-6">
        {/* Tab Navigation */}
        <div className="tabs tabs-boxed bg-base-200 p-1 rounded-lg">
          <button
            className={`tab flex-1 ${activeTab === 'logs' ? 'tab-active' : ''}`}
            onClick={() => handleTabChange('logs')}
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Log Analysis
          </button>
          <button
            className={`tab flex-1 ${activeTab === 'messages' ? 'tab-active' : ''}`}
            onClick={() => handleTabChange('messages')}
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
            Message Analysis
          </button>
          <button
            className={`tab flex-1 ${activeTab === 'sessions' ? 'tab-active' : ''}`}
            onClick={() => handleTabChange('sessions')}
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            Session Analysis
          </button>
        </div>

        {/* Time Range Selector (shared between Log and Message tabs) */}
        {activeTab !== 'sessions' && (
          <DateRangeSelector
            value={timeRange}
            onChange={handleTimeRangeChange}
          />
        )}

        {/* Log Analysis Tab */}
        {activeTab === 'logs' && (
          <div className="space-y-6">
            {/* Issue Alerts */}
            {!issuesLoading && <IssueAlerts issueReport={issues} />}

            {/* Summary Statistics */}
            <StatsCards
              histogram={histogram || []}
              totalLogs={stats?.totalLogs}
              errorCount={stats?.errorCount}
              warningCount={stats?.warningCount}
            />

            {/* Error Display */}
            {histogramError && (
              <div className="alert alert-error">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>Failed to load histogram: {histogramError.message}</span>
              </div>
            )}

            {/* Histogram Table */}
            <HistogramTable
              data={histogram || []}
              isLoading={histogramLoading || statsLoading}
            />

            {/* Refresh Button */}
            <div className="flex justify-end">
              <button
                onClick={() => refetchHistogram()}
                className="btn btn-primary btn-sm"
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Refresh
              </button>
            </div>
          </div>
        )}

        {/* Message Analysis Tab */}
        {activeTab === 'messages' && (
          <div className="space-y-6">
            {/* Performance Cards */}
            <MessagePerformanceCards
              performance={messageAnalysis?.performance}
              isLoading={messageLoading}
            />

            {/* Distribution Chart */}
            <MessageDistributionChart
              distribution={messageAnalysis?.distribution}
              isLoading={messageLoading}
            />

            {/* Provider Comparison Table */}
            <ProviderComparisonTable
              stats={messageAnalysis?.providerStats}
              isLoading={messageLoading}
            />

            {/* Refresh Button */}
            <div className="flex justify-end">
              <button
                onClick={() => refetchMessageAnalysis()}
                className="btn btn-primary btn-sm"
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Refresh
              </button>
            </div>
          </div>
        )}

        {/* Session Analysis Tab */}
        {activeTab === 'sessions' && (
          <div className="space-y-6">
            {/* Controls */}
            <SessionAnalysisControls
              limit={sessionLimit}
              onLimitChange={handleSessionLimitChange}
              onGenerate={handleGenerateSessionAnalysis}
              isLoading={sessionLoading}
              hasData={!!sessionAnalysis}
            />

            {/* Summary Cards */}
            <SessionSummaryCards
              result={sessionAnalysis}
              isLoading={sessionLoading}
            />

            {/* Session Cards */}
            <SessionCards
              sessions={sessionAnalysis?.sessions}
              isLoading={sessionLoading}
            />
          </div>
        )}
      </div>
    </PageContainer>
  )
}
