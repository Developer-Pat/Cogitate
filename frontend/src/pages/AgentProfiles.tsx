import { useState, useEffect, useMemo, useCallback } from 'react'
import { useDomainSync } from '../hooks/useDomainSync'
import { ErrorBoundary } from '../components/ErrorBoundary'
import { usePageTitle } from '../hooks/usePageTitle'
import { profileService } from '../services/domain/ProfileService'
import type { Profile, ProfileCreate, ProfileUpdate } from '../services/domain/ProfileService'
import ProfileList from '../components/AgentProfiles/ProfileList'
import ProfileDetail from '../components/AgentProfiles/ProfileDetail'
import { AgentTable } from '../components/AgentProfiles'
import { AgentToolManager } from '../components/features/agentTools/AgentToolManager/AgentToolManager'
import { useNotificationStore } from '../stores/notificationStore'
import { apiClient } from '../services/apiClient'
import { frontendLoggingService } from '../services/frontendLoggingService'
import { teamToolService } from '../services/domain/TeamToolService'
import type { Collection } from '../types/collections'
import { useAgentProfilesStore } from '../stores/agentProfilesStore'

export default function AgentProfiles() {
  usePageTitle('Agent Profiles', 'Manage and configure AI agent profiles')

  const addNotification = useNotificationStore((state) => state.addNotification)
  
  // Use Zustand store for persistent UI state
  const sidebarCollapsed = useAgentProfilesStore((state) => state.sidebarCollapsed)
  const toggleSidebar = useAgentProfilesStore((state) => state.toggleSidebar)
  const viewMode = useAgentProfilesStore((state) => state.viewMode)
  const setViewMode = useAgentProfilesStore((state) => state.setViewMode)
  const selectedTeamId = useAgentProfilesStore((state) => state.selectedTeamId)
  const setSelectedTeamId = useAgentProfilesStore((state) => state.setSelectedTeamId)
  const selectedProfileId = useAgentProfilesStore((state) => state.selectedProfileId)
  const action = useAgentProfilesStore((state) => state.action)
  const selectProfile = useAgentProfilesStore((state) => state.selectProfile)
  const resetSelection = useAgentProfilesStore((state) => state.resetSelection)

  const [profiles, setProfiles] = useState<Profile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [deletedAgents, setDeletedAgents] = useState<Array<Record<string, unknown>>>([])
  const [showDeleted, setShowDeleted] = useState(false)
  const [showSaveAsTemplateModal, setShowSaveAsTemplateModal] = useState(false)
  const [templateName, setTemplateName] = useState('')
  const [templateDescription, setTemplateDescription] = useState('')
  const [templatePublic, setTemplatePublic] = useState(false)
  const [templateTags, setTemplateTags] = useState('')
  const [toolsModalAgent, setToolsModalAgent] = useState<{ id: string; name: string } | null>(null)

  // Team filtering state
  const [teams, setTeams] = useState<Collection[]>([])
  const [loadingTeams, setLoadingTeams] = useState(false)

  useEffect(() => {
    // Load from backend once
    profileService.loadFromBackend()
      .catch(err => {
        frontendLoggingService.error('AgentProfiles', 'Failed to load profiles', err)
        setError('Failed to load profiles')
      })
      .finally(() => {
        setLoading(false)
      })

    // Subscribe to updates
    const unsubscribe = profileService.subscribe(setProfiles)

    // THE BACKGROUND SYNC IS PAGE-OWNED (2026-09-06): the service's
    // constructor no longer self-starts it (that ticked on any page
    // importing the module — the minute-ly logs on /logs). The page
    // starts it while mounted and stops it on unmount; the tick itself
    // is visibility-gated so a backgrounded tab stays silent.
    profileService.startBackgroundSync()

    return () => {
      unsubscribe()
      profileService.stopBackgroundSync()
    }
  }, [])

  // THE CROSS-WINDOW DOMAIN SYNCS (2026-08-25, the roadmap Phase 6):
  // the registry/permissions/packages' mutations elsewhere reload
  // this page (the agents' data lives here).
  useDomainSync('agent-registry', () => {
    void profileService.loadFromBackend()
  })
  useDomainSync('tool-permission', () => {
    void profileService.loadFromBackend()
  })
  useDomainSync('agent-package', () => {
    void profileService.loadFromBackend()
  })

  // Load teams for filtering
  useEffect(() => {
    const loadTeams = async () => {
      try {
        setLoadingTeams(true)
        const loadedTeams = await teamToolService.listTeams()
        setTeams(loadedTeams)
        frontendLoggingService.debug('AgentProfiles', 'Loaded teams', { count: loadedTeams.length })
      } catch (err) {
        frontendLoggingService.error('AgentProfiles', 'Failed to load teams', err)
        // Don't set error state - teams are optional
        setTeams([])
      } finally {
        setLoadingTeams(false)
      }
    }
    
    loadTeams()
  }, [])

  useEffect(() => {
    frontendLoggingService.debug('AgentProfiles', 'State changed', {
      selectedProfileId,
      action,
      profilesCount: profiles.length
    })
  }, [selectedProfileId, action, profiles.length])

  // Filter profiles by selected team
  const filteredProfiles = useMemo(() => {
    if (selectedTeamId === 'all') {
      return profiles
    }
    
    // Find the team and get its member agent IDs
    const team = teams.find(t => t.id === selectedTeamId)
    if (!team) {
      return profiles
    }
    
    // Filter profiles to only include agents in this team
    // Team members are stored in items array with entity_id = agent ID
    const agentIds = team.items?.map(item => item.entity_id) || []
    if (agentIds.length === 0) {
      return []
    }
    
    return profiles.filter(profile => agentIds.includes(profile.id))
  }, [profiles, selectedTeamId, teams])

  const handleCreateProfile = useCallback(() => {
    resetSelection()
  }, [resetSelection])

  const handleSelectProfile = useCallback((profile: Profile) => {
    selectProfile(profile.id, 'edit')
  }, [selectProfile])

  const handleDeleteProfile = async (profileId: string): Promise<Record<string, unknown> | null> => {
    try {
      setIsSaving(true)
      setError(null)
      const report = await profileService.deleteProfile(profileId)
      resetSelection()
      // No need to manually update state - subscription handles it
      await refreshDeleted()
      return report
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete profile'
      setError(message)
      frontendLoggingService.error('AgentProfiles', 'Error deleting profile', err)
      throw err
    } finally {
      setIsSaving(false)
    }
  }

  const refreshDeleted = useCallback(async () => {
    try {
      const deleted = await profileService.listDeleted()
      setDeletedAgents(deleted)
    } catch {
      setDeletedAgents([])
    }
  }, [])

  useEffect(() => {
    refreshDeleted()
  }, [refreshDeleted])

  const handleRestore = async (agentId: string, agentName: string) => {
    try {
      const ok = await profileService.restoreProfile(agentId)
      if (ok) {
        useNotificationStore.getState().addSuccess(`Restored ${agentName} — the profile is back in the pool.`)
        await refreshDeleted()
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to restore profile'
      setError(message)
    }
  }

  // the IRREVERSIBLE scrub — typed-name confirmation (2026-08-19)
  const [hardDeleteTarget, setHardDeleteTarget] = useState<{ id: string; name: string } | null>(null)
  const [hardDeleteConfirm, setHardDeleteConfirm] = useState('')
  const [isHardDeleting, setIsHardDeleting] = useState(false)

  const handleHardDelete = async () => {
    if (!hardDeleteTarget) return
    if (hardDeleteConfirm !== hardDeleteTarget.name) return
    try {
      setIsHardDeleting(true)
      await profileService.hardDeleteProfile(hardDeleteTarget.id)
      useNotificationStore.getState().addSuccess(`${hardDeleteTarget.name} permanently deleted — scrubbed from the system.`)
      setHardDeleteTarget(null)
      setHardDeleteConfirm('')
      await refreshDeleted()
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to permanently delete'
      setError(message)
    } finally {
      setIsHardDeleting(false)
    }
  }

  const handleDuplicateProfile = async (profile: Profile) => {
    try {
      setIsSaving(true)
      setError(null)

      const duplicated = await profileService.duplicateAgent(profile.id)

      // Select the duplicated profile for editing
      selectProfile(duplicated.id, 'edit')
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to duplicate profile'
      setError(message)
      frontendLoggingService.error('AgentProfiles', 'Error duplicating profile', err)
      throw err
    } finally {
      setIsSaving(false)
    }
  }
  
  // Get selected profile object from store
  const selectedProfile = useMemo(() => {
    if (!selectedProfileId) return null
    return profiles.find(p => p.id === selectedProfileId) || null
  }, [selectedProfileId, profiles])

  const handleSaveAsTemplate = async () => {
    if (!selectedProfile || !templateName.trim()) return

    try {
      setIsSaving(true)
      
      const tagsArray = templateTags
        .split(',')
        .map(t => t.trim())
        .filter(t => t.length > 0)

      await apiClient.post(`/api/v1/agents/templates/from-agent/${selectedProfile.id}`, {
        name: templateName.trim(),
        description: templateDescription.trim() || null,
        is_public: templatePublic,
        tags: tagsArray.length > 0 ? tagsArray : null
      })

      addNotification({
        type: 'success',
        title: 'Template Created',
        message: `"${templateName}" has been saved as a template`
      })

      setShowSaveAsTemplateModal(false)
      resetTemplateForm()
    } catch (error: unknown) {
      frontendLoggingService.error('AgentProfiles', 'Failed to save as template', error)
      addNotification({
        type: 'error',
        title: 'Error',
        message: (error as {response?: {data?: {detail?: string}}})?.response?.data?.detail || 'Failed to save as template'
      })
    } finally {
      setIsSaving(false)
    }
  }

  const openSaveAsTemplateModal = () => {
    frontendLoggingService.info('AgentProfiles', 'Opening Save as Template modal', { profileName: selectedProfile?.name })
    // Pre-populate form with agent data
    setTemplateName(`${selectedProfile?.name} Template`)
    setTemplateDescription(selectedProfile?.description || '')
    setTemplateTags('')
    setTemplatePublic(false)
    setShowSaveAsTemplateModal(true)
  }

  const resetTemplateForm = () => {
    setTemplateName('')
    setTemplateDescription('')
    setTemplatePublic(false)
    setTemplateTags('')
  }

  const handleManageTools = (agentId: string) => {
    const agent = profiles.find(p => p.id === agentId)
    setToolsModalAgent({ id: agentId, name: agent?.name || agentId })
  }

  const handleToolsChanged = () => {
    // Tools changed — could trigger a refresh if needed
  }

  const handleSaveProfile = async (profileData: ProfileCreate | ProfileUpdate, imageFile?: File) => {
    try {
      setIsSaving(true)
      setError(null)

      frontendLoggingService.debug('AgentProfiles', 'handleSaveProfile called', { action, hasImageFile: !!imageFile })

      let savedProfileId: string | null = null

      if (action === 'create') {
        frontendLoggingService.info('AgentProfiles', 'Creating new profile')
        const createdProfile = await profileService.createProfile(profileData as ProfileCreate)
        savedProfileId = createdProfile.id
        frontendLoggingService.info('AgentProfiles', 'Profile created successfully', { profileId: savedProfileId })

        // Upload image if provided
        if (imageFile && savedProfileId) {
          frontendLoggingService.debug('AgentProfiles', 'Uploading image for profile', { profileId: savedProfileId })
          try {
            const imageUrl = await profileService.uploadProfileImage(savedProfileId, imageFile)
            frontendLoggingService.info('AgentProfiles', 'Image uploaded successfully', { profileId: savedProfileId, imageUrl })
          } catch (imgErr) {
            frontendLoggingService.warning('AgentProfiles', 'Image upload failed (profile was created)', { error: imgErr })
            // Don't fail the entire operation if image upload fails
          }
        }
      } else if (selectedProfile) {
        frontendLoggingService.debug('AgentProfiles', 'Updating profile', { profileId: selectedProfile.id })
        await profileService.updateProfile(selectedProfile.id, profileData as ProfileUpdate)
        frontendLoggingService.info('AgentProfiles', 'Profile updated successfully', { profileId: selectedProfile.id })

        // Upload image if provided
        if (imageFile && selectedProfile.id) {
          frontendLoggingService.debug('AgentProfiles', 'Uploading image for profile', { profileId: selectedProfile.id })
          try {
            const imageUrl = await profileService.uploadProfileImage(selectedProfile.id, imageFile)
            frontendLoggingService.info('AgentProfiles', 'Image uploaded successfully', { profileId: selectedProfile.id, imageUrl })
          } catch (imgErr) {
            frontendLoggingService.warning('AgentProfiles', 'Image upload failed (profile was updated)', { error: imgErr })
            // Don't fail the entire operation if image upload fails
          }
        }
      }

      // Update store from cache (subscription already updated the list)
      if (savedProfileId) {
        const updatedProfile = profileService.getProfile(savedProfileId)
        if (updatedProfile) {
          selectProfile(updatedProfile.id, 'edit')
          frontendLoggingService.info('AgentProfiles', 'Updated selectedProfile from cache', { profileId: updatedProfile.id })
        }
      } else if (selectedProfile) {
        const updatedProfile = profileService.getProfile(selectedProfile.id)
        if (updatedProfile) {
          selectProfile(updatedProfile.id, 'edit')
          frontendLoggingService.info('AgentProfiles', 'Updated selectedProfile from cache', { profileId: updatedProfile.id })
        }
      } else {
        resetSelection()
        frontendLoggingService.debug('AgentProfiles', 'Reset to create mode')
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save profile'
      frontendLoggingService.error('AgentProfiles', 'Error saving profile', err)
      setError(message)
      throw err
    } finally {
      setIsSaving(false)
    }
  }

  const handleCancel = useCallback(() => {
    resetSelection()
  }, [resetSelection])

  if (loading) {
    return (
      <ErrorBoundary>
        <div className="h-screen flex flex-col bg-base-50">
          {/* Header - Minimal */}
          <div className="bg-base-100 border-b border-base-300 p-2"></div>
          
          {/* Loading Layout */}
          <div className="flex-1 flex overflow-hidden">
            {/* Main Content Loading */}
            <div className="flex-1 bg-base-50 flex items-center justify-center">
              <div className="text-center">
                <div className="text-6xl mb-4 opacity-50">👤</div>
                <h2 className="text-2xl font-bold mb-2 opacity-50">Loading Profile Data</h2>
                <p className="text-readout mb-6">Please wait while profiles are loading</p>
              </div>
            </div>
            
            {/* Right Sidebar Loading */}
            <div className="relative">
              <div className="w-80 bg-base-100 border-l border-base-300 flex flex-col h-full">
                <div className="p-4 border-b border-base-300">
                  <div className="btn btn-primary btn-sm w-full rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)] opacity-50">
                    <span className="text-lg">+</span>
                    New Profile
                  </div>
                </div>
                <div className="p-4 border-b border-base-300">
                  <div className="input input-bordered input-sm w-full opacity-50 rounded-[var(--form-input-radius)] bg-[var(--form-input-bg)] border-[var(--form-input-border)] text-[var(--form-input-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]">Search profiles...</div>
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-2">
                  {[...Array(6)].map((_, index) => (
                    <div key={index} className="w-full p-3 flex gap-3 items-center">
                      <div className="w-12 h-12 rounded bg-base-300 animate-pulse"></div>
                      <div className="flex-1 space-y-1">
                        <div className="h-4 bg-base-300 rounded animate-pulse w-3/4"></div>
                        <div className="h-3 bg-base-300 rounded animate-pulse w-1/2"></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              {/* Sidebar Toggle Button - Positioned next to sidebar */}
              <button className="absolute -left-8 top-4 btn btn-ghost btn-sm btn-square opacity-50">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </ErrorBoundary>
    )
  }

  return (
    <ErrorBoundary>
      <div className="h-screen flex flex-col bg-base-50">
        {/* THE ASK-EXA BUTTON (2026-09-06): removed — no longer needed
            (the Exa agent is reachable from its own surfaces). The bar
            below now renders ONLY when an error is present. */}
        {error && (
            <div className="alert alert-error">
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span className="text-sm">{error}</span>
              <button
                className="btn btn-ghost btn-xs rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                onClick={() => setError(null)}
              >
                Dismiss
              </button>
            </div>
          )}

        {/* Master-Detail Layout */}
        <div className="flex-1 flex overflow-hidden">
          {/* Main Content - Profile Detail */}
          {selectedProfile || action === 'create' ? (
            <ProfileDetail
              profile={action === 'edit' ? selectedProfile : null}
              action={action}
              onSave={handleSaveProfile}
              onCancel={handleCancel}
              onDelete={handleDeleteProfile}
              onSaveAsTemplate={action === 'edit' ? openSaveAsTemplateModal : undefined}
              isSaving={isSaving}
            />
          ) : (
            <div className="flex-1 flex items-center justify-center bg-base-50">
              <div className="text-center w-full max-w-md px-6">
                <div className="text-6xl mb-4">👤</div>
                <h2 className="text-2xl font-bold mb-2">No Profile Selected</h2>
                <p className="text-readout mb-6">
                  Select a profile from the list or create a new one to get started
                </p>



                <button
                  onClick={handleCreateProfile}
                  className="btn btn-primary rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                >
                  Create Your First Profile
                </button>
              </div>
            </div>
          )}

          {/* Right Sidebar - Profile List (Collapsible) */}
          {!sidebarCollapsed && (
            <div className="relative">
              {viewMode === 'list' ? (
                <ProfileList
                  profiles={filteredProfiles}
                  selectedProfileId={selectedProfile?.id}
                  onSelectProfile={handleSelectProfile}
                  onCreateNew={handleCreateProfile}
                  onDuplicate={handleDuplicateProfile}
                  isLoading={loading || isSaving}
                  viewMode={viewMode}
                  onViewModeChange={setViewMode}
                  teams={teams}
                  selectedTeamId={selectedTeamId}
                  onTeamChange={setSelectedTeamId}
                  loadingTeams={loadingTeams}
                  totalProfiles={profiles.length}
                  archivedAgents={deletedAgents}
                  onRestoreAgent={handleRestore}
                  onHardDeleteAgent={(id, name) => {
                    setHardDeleteTarget({ id, name })
                    setHardDeleteConfirm('')
                  }}
                  showArchived={showDeleted}
                  onToggleArchived={() => setShowDeleted(s => !s)}
                />
              ) : (
                <AgentTable
                  profiles={filteredProfiles}
                  selectedProfileId={selectedProfile?.id}
                  onSelectProfile={handleSelectProfile}
                  onDuplicate={handleDuplicateProfile}
                  onDelete={handleDeleteProfile}
                  isLoading={loading || isSaving}
                  onViewModeChange={setViewMode}
                  onManageTools={handleManageTools}
                  teams={teams}
                  selectedTeamId={selectedTeamId}
                  onTeamChange={setSelectedTeamId}
                  loadingTeams={loadingTeams}
                  totalProfiles={profiles.length}
                />
              )}
              {/* Sidebar Toggle Button - Positioned next to sidebar */}
              <div className="tooltip tooltip-right" data-tip={sidebarCollapsed ? 'Show profiles' : 'Hide profiles'}>
                <button
                  onClick={toggleSidebar}
                  className="absolute -left-8 top-4 btn btn-ghost btn-sm btn-square"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    {sidebarCollapsed ? (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    ) : (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                    )}
                  </svg>
                </button>
              </div>
            </div>
          )}

          {/* Show toggle button when sidebar is collapsed */}
          {sidebarCollapsed && (
            <div className="relative">
              <div className="tooltip tooltip-right" data-tip="Show profiles">
                <button
                  onClick={toggleSidebar}
                  className="absolute -left-8 top-4 btn btn-ghost btn-sm btn-square"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Save as Template Modal */}
      {showSaveAsTemplateModal && selectedProfile && (
        <div className="modal modal-open" style={{ zIndex: 9999 }}>
          <div className="modal-box max-w-md bg-base-100 text-base-content" style={{ zIndex: 10000 }}>
            <div className="flex items-center justify-between mb-4 bg-info text-info-content p-4 rounded-t-lg -mx-6 -mt-6 pt-6">
              <h3 className="font-bold text-lg">Save as Template</h3>
              <button
                className="btn btn-sm btn-ghost hover:bg-info-content/20 rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                onClick={() => {
                  setShowSaveAsTemplateModal(false)
                  resetTemplateForm()
                }}
              >
                ✕
              </button>
            </div>

            <div className="alert alert-info mb-4">
              <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-5 w-5" fill="none" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>
                Save "{selectedProfile.name}" configuration as a reusable template
              </span>
            </div>

            <div className="form-control mb-4">
              <label className="label">
                <span className="label-text font-semibold text-base-content">Template Name *</span>
              </label>
              <input
                type="text"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                className="input input-bordered w-full bg-base-200 text-base-content rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                placeholder="e.g., Customer Support Bot"
                autoFocus
              />
            </div>

            <div className="form-control mb-4">
              <label className="label">
                <span className="label-text font-semibold text-base-content">Description</span>
              </label>
              <textarea
                value={templateDescription}
                onChange={(e) => setTemplateDescription(e.target.value)}
                className="textarea textarea-bordered w-full bg-base-200 text-base-content rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                placeholder="Brief description of what this template does..."
                rows={2}
              />
            </div>

            <div className="form-control mb-4">
              <label className="label">
                <span className="label-text font-semibold text-base-content">Tags (comma-separated)</span>
              </label>
              <input
                type="text"
                value={templateTags}
                onChange={(e) => setTemplateTags(e.target.value)}
                className="input input-bordered w-full bg-base-200 text-base-content rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                placeholder="e.g., support, helpful, customer-service"
              />
            </div>

            <div className="form-control mb-6">
              <label className="label cursor-pointer justify-start gap-4">
                <input
                  type="checkbox"
                  checked={templatePublic}
                  onChange={(e) => setTemplatePublic(e.target.checked)}
                  className="checkbox checkbox-primary"
                />
                <div>
                  <div className="label-text font-semibold text-base-content">Make template public</div>
                  <div className="label-text-alt text-readout">Others will be able to see and use this template</div>
                </div>
              </label>
            </div>

            <div className="modal-action">
              <button
                className="btn btn-neutral btn-ghost text-base-content rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                onClick={() => {
                  setShowSaveAsTemplateModal(false)
                  resetTemplateForm()
                }}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                onClick={handleSaveAsTemplate}
                disabled={!templateName.trim() || isSaving}
              >
                {isSaving ? (
                  <>
                    <span className="loading loading-spinner loading-sm"></span>
                    Saving...
                  </>
                ) : (
                  '💾 Save Template'
                )}
              </button>
            </div>
          </div>
          <div className="modal-backdrop"></div>
        </div>
      )}

      {/* The PERMANENT-delete confirm (2026-08-19) — typed-name
          confirmation for the irreversible scrub. The documented
          modal pattern (plain container, NOT modal-box — the
          48px-collapse trap). */}
      {hardDeleteTarget && (
        <div
          className="fixed inset-0 z-[9999] bg-black/60 flex items-center justify-center p-4"
          onClick={() => { setHardDeleteTarget(null); setHardDeleteConfirm('') }}
        >
          <div
            className="bg-base-200 rounded-lg shadow-xl p-6"
            style={{ width: 'min(var(--dialog-width-md), 95vw)' }}
            onClick={e => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold mb-2 text-error">Permanently delete {hardDeleteTarget.name}?</h3>
            <p className="text-sm text-readout mb-4">
              This is the IRREVERSIBLE delete — the agent row, its sessions,
              usage history, workspace, and memory are all scrubbed from the
              system. <span className="font-semibold">Nothing can restore it.</span>{' '}
              To confirm, type the agent's name:
            </p>
            <input
              type="text"
              value={hardDeleteConfirm}
              onChange={e => setHardDeleteConfirm(e.target.value)}
              placeholder={hardDeleteTarget.name}
              className="input input-bordered w-full mb-4"
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <button
                className="btn btn-neutral btn-ghost"
                onClick={() => { setHardDeleteTarget(null); setHardDeleteConfirm('') }}
              >
                Cancel
              </button>
              <button
                className="btn btn-error"
                disabled={hardDeleteConfirm !== hardDeleteTarget.name || isHardDeleting}
                onClick={handleHardDelete}
              >
                {isHardDeleting ? 'Deleting…' : 'Delete permanently'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manage Tools Modal */}
      {toolsModalAgent && (
        <div className="modal modal-open" style={{ zIndex: 9999 }}>
          <div className="modal-box max-w-5xl bg-base-100 text-base-content" style={{ zIndex: 10000 }}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold">Manage Tools — {toolsModalAgent.name}</h3>
              <button
                className="btn btn-sm btn-circle"
                onClick={() => setToolsModalAgent(null)}
              >
                ✕
              </button>
            </div>
            <AgentToolManager
              agentId={toolsModalAgent.id}
              onToolsChanged={handleToolsChanged}
            />
          </div>
          <div
            className="modal-backdrop"
            onClick={() => setToolsModalAgent(null)}
          ></div>
        </div>
      )}
    </ErrorBoundary>
  )
}