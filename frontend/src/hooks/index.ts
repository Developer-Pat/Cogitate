/**
 * Hooks Index - Export all custom hooks
 */

// Page Title Hooks
export { usePageTitle, useDynamicPageTitle } from './usePageTitle';

// System Health Hooks
export { useSystemHealth, useServiceStatus, useSystemMetrics, useUptime, useHealthCheck } from './useSystemHealth';

// System Info Hooks
export { useSystemStatus, useSystemInfo, useRecentEvents } from './useSystemInfo';

// Logs Hooks
export { useLogs, useLogSources, useLogStats, useClearLogs } from './useLogs';

// History Hooks
export {
  useLogsHistogram,
  useHistoryStats,
  useHistoryIssues,
  useMessageAnalysis,
  useMessagePerformance,
  useMessageDistribution,
  useProviderModelStats,
  useSessionAnalysis,
  useSessionSummary
} from './useHistory';

// Agents Hooks
export {
  useAgents,
  useAgentById,
  useAgentMetrics,
  useCreateAgent,
  useUpdateAgent,
  useDeleteAgent,
  useAgentActions,
  useAgentTypes,
  useAgentCapabilities
} from './useAgents';

// Notifications Hook
export { useNotifications } from './useNotifications';

// Settings & Theme Hooks
export { useSettings } from './useSettings';
export { useTheme } from './useTheme';
export { useLocalStorage } from './useLocalStorage';

// Chat Interaction Hooks (Refactored)
export { useAgentInteraction } from './useAgentInteraction';
export { useAgentSelection } from './useAgentSelection';
export { useSessionManagement } from './useSessionManagement';
export { useChatStreaming } from './useChatStreaming';
export { useChatPersistence } from './useChatPersistence';

// Mode Macros Hooks
export { useModeMacros, useMacroByKey, useMacroKeys } from './useModeMacros';