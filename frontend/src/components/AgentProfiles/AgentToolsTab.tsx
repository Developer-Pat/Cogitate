/**
 * AgentToolsTab Component
 *
 * Wrapper component for AgentToolManager integration in ProfileDetail.
 * Provides notification callbacks and logging for tool management.
 */

import { AgentToolManager } from '../features/agentTools/AgentToolManager/AgentToolManager'
import { frontendLoggingService } from '@/services/frontendLoggingService'
import { useNotificationStore } from '@/stores/notificationStore'

interface AgentToolsTabProps {
  /** Agent/Profile ID to manage tools for */
  agentId: string
  /** Agent/Profile name for display purposes */
  agentName: string
}

/**
 * AgentToolsTab Component
 */
export default function AgentToolsTab({ agentId, agentName }: AgentToolsTabProps) {
  const addNotification = useNotificationStore((state) => state.addNotification)

  const handleConfigUpdate = (toolId: string, config: unknown) => {
    frontendLoggingService.info('AgentToolsTab', 'Tool configuration updated', {
      agentId,
      toolId,
      config
    })

    addNotification({
      type: 'success',
      title: 'Tool Configuration Updated',
      message: `Configuration for tool has been saved`
    })
  }

  const handleToolsChanged = () => {
    frontendLoggingService.info('AgentToolsTab', 'Tools changed for agent', {
      agentId,
      agentName
    })

    addNotification({
      type: 'success',
      title: 'Tools Updated',
      message: `Tool assignments for "${agentName}" have been updated`
    })
  }

  return (
    <div className="bg-base-100 rounded-lg">
      <AgentToolManager
        agentId={agentId}
        onConfigUpdate={handleConfigUpdate}
        onToolsChanged={handleToolsChanged}
      />
    </div>
  )
}
