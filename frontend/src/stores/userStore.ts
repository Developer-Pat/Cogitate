import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import type { User } from '../types'

interface UserStore {
  // User state
  user: User | null
  permissions: string[]
  
  // Actions
  setUser: (user: User) => void
  clearUser: () => void
}

export const useUserStore = create<UserStore>()(
  devtools(
    (set) => ({
      // Initial state
      user: null,
      permissions: [],

      // Actions
      setUser: (user: User) => set({ user, permissions: user.permissions }),
      
      clearUser: () => set({ user: null, permissions: [] }),
    }),
    {
      name: 'user-store',
      enabled: import.meta.env.DEV,
    }
  )
)

// Selectors for derived state
export const useUser = () => useUserStore((state) => state.user)
export const usePermissions = () => useUserStore((state) => state.permissions)

// Action hooks
export const useUserActions = () => useUserStore((state) => ({
  setUser: state.setUser,
  clearUser: state.clearUser,
}))