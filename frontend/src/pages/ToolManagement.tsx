/**
 * Tool Management Page
 *
 * Compact table-based tool management for collections.
 */

import { useState, useEffect } from 'react'
import { usePageTitle } from '../hooks/usePageTitle'
import { toolService } from '../services/domain/ToolService'
import type { Tool } from '../types/tools'
import { ToolsTable } from '../components/Tools'
import { useNotificationStore } from '../stores/notificationStore'
import { frontendLoggingService } from '../services/frontendLoggingService'
import { HelpButton } from '../components/help';

export default function ToolManagement() {
  usePageTitle('Tool Management', 'Manage agent tools and collections')

  const addNotification = useNotificationStore((state) => state.addNotification)

  const [tools, setTools] = useState<Tool[]>([])
  const [selectedToolIds, setSelectedToolIds] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadTools()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const loadTools = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await toolService.listTools()
      setTools(response.tools)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load tools'
      setError(message)
      frontendLoggingService.error('ToolManagement', 'Failed to load tools', err)
      addNotification({
        type: 'error',
        title: 'Error',
        message
      })
    } finally {
      setLoading(false)
    }
  }

  const handleDuplicate = async (_tool: Tool) => {
    addNotification({
      type: 'info',
      title: 'Duplicate',
      message: 'Tool duplication is not yet implemented'
    })
  }

  const handleDelete = async (toolId: string) => {
    try {
      await toolService.deleteTool(toolId)
      addNotification({
        type: 'success',
        title: 'Deleted',
        message: 'Tool deleted successfully'
      })
      await loadTools()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete tool'
      addNotification({
        type: 'error',
        title: 'Error',
        message
      })
      throw err
    }
  }

  const handleSelectionChange = (selectedIds: Set<string>) => {
    setSelectedToolIds(selectedIds)
  }

  return (
    <div className="p-6 h-screen flex flex-col">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-base-content">Tool Management</h1>
          <p className="text-sm text-readout mt-1">
            Manage tools and organize them into collections
          </p>
        </div>
        <HelpButton context="tools" tooltipPosition="bottom" />
      </div>

      {error && (
        <div className="alert alert-error mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{error}</span>
          <button className="btn btn-outline btn-xs" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <span className="loading loading-spinner loading-lg"></span>
            <p className="mt-2 text-readout">Loading tools...</p>
          </div>
        </div>
      ) : (
        <ToolsTable
          tools={tools}
          selectedToolIds={selectedToolIds}
          onSelectionChange={handleSelectionChange}
          onDuplicate={handleDuplicate}
          onDelete={handleDelete}
          isLoading={loading}
        />
      )}
    </div>
  )
}