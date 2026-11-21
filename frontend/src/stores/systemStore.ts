import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import type { SystemHealth, ActiveSession, AgentConfig } from '../types'

// Default system health state
const defaultSystemHealth: SystemHealth = {
  status: 'unhealthy',
  timestamp: new Date().toISOString(),
  services: [],
  metrics: {
    cpu: { usage: 0, cores: 0, loadAverage: [0, 0, 0] },
    memory: { total: 0, used: 0, free: 0, usage: 0 },
    disk: { total: 0, used: 0, free: 0, usage: 0 },
    network: { bytesIn: 0, bytesOut: 0, connections: 0 },
  },
  uptime: 0,
  version: 'unknown',
}

interface SystemStore {
  // System state
  systemHealth: SystemHealth
  activeSessions: ActiveSession[]
  agentConfigurations: AgentConfig[]
  
  // Actions
  updateSystemHealth: (health: SystemHealth) => void
  setActiveSessions: (sessions: ActiveSession[]) => void
  addActiveSession: (session: ActiveSession) => void
  removeActiveSession: (sessionId: string) => void
  setAgentConfigurations: (configs: AgentConfig[]) => void
  updateAgentConfiguration: (config: AgentConfig) => void
}

export const useSystemStore = create<SystemStore>()(
  devtools(
    (set) => ({
      // Initial state
      systemHealth: defaultSystemHealth,
      activeSessions: [],
      agentConfigurations: [],

      // Actions
      updateSystemHealth: (systemHealth: SystemHealth) => set({ systemHealth }),
      
      setActiveSessions: (activeSessions: ActiveSession[]) => set({ activeSessions }),
      
      addActiveSession: (session: ActiveSession) => 
        set((state) => ({ 
          activeSessions: [...state.activeSessions, session] 
        })),
      
      removeActiveSession: (sessionId: string) =>
        set((state) => ({
          activeSessions: state.activeSessions.filter(session => session.id !== sessionId)
        })),
      
      setAgentConfigurations: (agentConfigurations: AgentConfig[]) => set({ agentConfigurations }),
      
      updateAgentConfiguration: (config: AgentConfig) =>
        set((state) => ({
          agentConfigurations: state.agentConfigurations.map(ac => 
            ac.id === config.id ? config : ac
          )
        })),
    }),
    {
      name: 'system-store',
      enabled: import.meta.env.DEV,
    }
  )
)

// Selectors for derived state
export const useSystemHealth = () => useSystemStore((state) => state.systemHealth)
export const useActiveSessions = () => useSystemStore((state) => state.activeSessions)
export const useAgentConfigurations = () => useSystemStore((state) => state.agentConfigurations)

// Action hooks
export const useSystemActions = () => useSystemStore((state) => ({
  updateSystemHealth: state.updateSystemHealth,
  setActiveSessions: state.setActiveSessions,
  addActiveSession: state.addActiveSession,
  removeActiveSession: state.removeActiveSession,
  setAgentConfigurations: state.setAgentConfigurations,
  updateAgentConfiguration: state.updateAgentConfiguration,
}))