import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import { frontendLoggingService } from '../services/frontendLoggingService'

export type AgentProfilesViewMode = 'list' | 'table'

export interface AgentProfilesState {
  // UI state
  sidebarCollapsed: boolean
  viewMode: AgentProfilesViewMode
  selectedTeamId: string | 'all'
  
  // Profile selection
  selectedProfileId: string | null
  action: 'create' | 'edit'
  
  // Actions
  toggleSidebar: () => void
  setViewMode: (mode: AgentProfilesViewMode) => void
  setSelectedTeamId: (teamId: string | 'all') => void
  selectProfile: (profileId: string | null, action?: 'create' | 'edit') => void
  resetSelection: () => void
}

export const useAgentProfilesStore = create<AgentProfilesState>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        sidebarCollapsed: false,
        viewMode: 'list',
        selectedTeamId: 'all',
        selectedProfileId: null,
        action: 'create',

        // Actions
        toggleSidebar: () => {
          const newState = { sidebarCollapsed: !get().sidebarCollapsed }
          frontendLoggingService.debug('AgentProfilesStore', 'Sidebar toggled', newState)
          set(newState)
        },
        
        setViewMode: (viewMode) => {
          frontendLoggingService.debug('AgentProfilesStore', 'View mode changed', { viewMode })
          set({ viewMode })
        },
        
        setSelectedTeamId: (selectedTeamId) => {
          frontendLoggingService.debug('AgentProfilesStore', 'Team changed', { selectedTeamId })
          set({ selectedTeamId })
        },
        
        selectProfile: (selectedProfileId, action = 'edit') => {
          frontendLoggingService.info('AgentProfilesStore', 'Profile selected', { 
            selectedProfileId, 
            action 
          })
          set({ selectedProfileId, action })
        },
        
        resetSelection: () => {
          frontendLoggingService.info('AgentProfilesStore', 'Selection reset')
          set({ selectedProfileId: null, action: 'create' })
        },
      }),
      {
        name: 'agent-profiles-storage', // Key for localStorage
        partialize: (state) => ({
          // Persist these fields to localStorage
          sidebarCollapsed: state.sidebarCollapsed,
          viewMode: state.viewMode,
          selectedTeamId: state.selectedTeamId,
          selectedProfileId: state.selectedProfileId,
          action: state.action,
        }),
      }
    ),
    {
      name: 'agent-profiles-store',
      enabled: import.meta.env.DEV,
    }
  )
)
