import { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import type { Profile, ProfileCreate, ProfileUpdate, OllamaModel } from '@/services/domain/ProfileService'
import { profileService, archiveFolderName, budgetReasonLabel } from '@/services/domain/ProfileService'
import ProfileImageUpload from './ProfileImageUpload'
import { useNotificationStore } from '@/stores/notificationStore'
import { frontendLoggingService } from '@/services/frontendLoggingService'
import { getCuratedModelsForProvider, type CuratedModel } from '@/config/curatedModels'
import { fetchCuratedModels } from '@/services/domains/providers/curatedModelsService'
import { modelBrowserService } from '@/services/domains/providers/modelBrowserService'
import type { ModelInfo } from '@/services/domains/providers/modelBrowserService'
import { useProviderConfig } from '@/hooks/useProviderConfig'
import CollectionsTab from './CollectionsTab'
import AgentToolsTab from './AgentToolsTab'
import CognitiveProfileSelector from '../features/cognitive/CognitiveProfileSelector'
import PackageTab from './PackageTab'
import ToggleSwitch from '../ui/ToggleSwitch'
import {
  SAMPLING_BOUNDS,
  SAMPLING_PRESETS,
  SAMPLING_SLIDER_REST,
  declaredSampling,
  describeSampling,
  hasDeclaredSampling,
  type SamplingDeclaration
} from '@/utils/samplingDeclaration'

interface Template {
  id: string
  name: string
  description: string
  prompt: string
  variables: string[]
}

interface ProfileDetailProps {
  profile?: Profile | null
  action: 'create' | 'edit'
  onSave: (profileData: ProfileCreate | ProfileUpdate, imageFile?: File) => Promise<void>
  onCancel: () => void
  onDelete?: (profileId: string) => Promise<Record<string, unknown> | null>
  onSaveAsTemplate?: () => void
  onUpdated?: () => void
  isSaving?: boolean
}

export default function ProfileDetail({
  profile,
  action,
  onSave,
  onCancel,
  onDelete,
  onSaveAsTemplate,
  onUpdated,
  isSaving = false
}: ProfileDetailProps) {
  const { addSuccess, addError } = useNotificationStore()
  // THE DELETE-DIALOG's DONE (2026-08-25, the tsc -b fix): the
  // resetSelection was referenced but never defined — the selection
  // lives in the PARENT (the AgentProfiles page); the dialog's Done
  // just closes here, the parent's own state handles the rest.
  const resetSelection = () => {}
  const navigate = useNavigate()
  const location = useLocation()
  const importFileInputRef = useRef<HTMLInputElement>(null)
  const [formData, setFormData] = useState<ProfileCreate>({
    id: '',
    name: '',
    description: '',
    provider: 'ollama',
    model: 'llama3.2:latest',
    system_prompt: '',
    // NOTHING IS DECLARED BY DEFAULT (the agent-init arc, G4): this form used to start at
    // 0.7/0.9 and post them on Save, which put a sampling pair nobody chose on every new
    // agent. Sampling starts UNDECLARED; the switch in the Advanced tab declares it.
    parameters: undefined,
    // NO BUDGET BY DEFAULT (G-I): the declaration is the agent's own llm_spec, and a
    // form that prefilled a number would put a silent default back on every new agent.
    llm_spec: {},
    tools: [],
    memory: false,
    image_url: '',
    cognitive_profile_id: null,
    fallback_enabled: false,
    preferred_providers: []
  })

  const [error, setError] = useState<string | null>(null)
  const [selectedImageFile, setSelectedImageFile] = useState<File | null>(null)
  // THE FORM'S BOUND (G.1/D3) — the DERIVED ceiling, taken from the agent the
  // page is editing, or from the last read the service made (so the CREATE form
  // is bounded too). Nothing is typed here: D3 makes the ceiling one number,
  // derived from the type table and shared with the API's own validation. With
  // nothing served the input carries no bound at all — the API is the guard,
  // and an invented bound is what made this form refuse legal budgets.
  const budgetCeiling = profile?.budget_ceiling ?? profileService.budgetCeiling
  const [activeTab, setActiveTab] = useState<'basic' | 'provider' | 'behavior' | 'advanced' | 'collections' | 'tools' | 'cognitive' | 'package' | 'tools' | 'cognitive'>('basic')
  const [resetCounter, setResetCounter] = useState(0)
  // THE DECLARATION SWITCH (G4) — UI state, because `{}` and `undefined` cannot express it
  // on their own: the switch ON with nothing set yet is a real, transient state, and the
  // Save refuses it rather than storing an empty dict.
  const [declareSampling, setDeclareSampling] = useState(false)
  // WHAT THE FORM SAYS ABOUT ITSELF (G4) — one plain line, naming only what is declared, so
  // the state is readable without inferring it from a slider's position.
  const samplingSummary = describeSampling(formData.parameters)
  const samplingState = !declareSampling
    ? 'Nothing declared — the provider’s own default applies.'
    : samplingSummary
      ? `Sends ${samplingSummary} with every turn.`
      : 'Set a value below, or click a preset.'
  const [deleteDialog, setDeleteDialog] = useState<{
    open: boolean
    deleting: boolean
    report: Record<string, unknown> | null
  }>({ open: false, deleting: false, report: null })
  const [availableModels, setAvailableModels] = useState<(OllamaModel | ModelInfo | CuratedModel)[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [modelError, setModelError] = useState<string | null>(null)
  const [templates, setTemplates] = useState<Template[]>([])
  const [loadingTemplates, setLoadingTemplates] = useState(false)
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('')

  // Phase 4: Fetch dynamic provider list from database
  const { providers: dbProviders, loading: providersLoading } = useProviderConfig()

  // Fetch available templates on mount
  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        setLoadingTemplates(true)
        const fetchedTemplates = await profileService.getTemplates()
        setTemplates(Array.isArray(fetchedTemplates) ? fetchedTemplates : [])
      } catch (err) {
        frontendLoggingService.error('ProfileDetail:fetchTemplates', 'Error fetching templates', err)
        setTemplates([])
      } finally {
        setLoadingTemplates(false)
      }
    }

    fetchTemplates()
  }, [])

  // THE PROVIDER MAPS COME FROM THE DB.
  //
  // These were hard-coded as {ollama:1, openrouter:2, deepseek:3, groq:4} — four
  // entries against a DB that has SIX (plus ollama_cloud and llama). The failure
  // was silent and cost a real debugging session:
  //   - `providerNameToId['llama']` was undefined, so `if (pid)` skipped the
  //     model browse entirely and the picker fell through to a manual text box;
  //   - the Browse button was DISABLED with a tooltip naming only four providers;
  //   - and the text box kept the PREVIOUS provider's model, so switching
  //     provider and saving would write a model from the wrong provider.
  // Meanwhile the BACKEND had served llama browsing since 2026-09-09
  // (management_router: the keyless local row). A frontend fix could never see it.
  //
  // Reading the list the DB actually holds means adding a provider needs no
  // frontend edit — which is the point. `dbProviders` is already loaded above.
  const providerNameToId: Record<string, number> = useMemo(() => {
    const m: Record<string, number> = {}
    for (const p of dbProviders) m[p.name] = p.id
    return m
  }, [dbProviders])

  const providerIdToName: Record<string, string> = useMemo(() => {
    const m: Record<string, string> = {}
    for (const p of dbProviders) m[String(p.id)] = p.name
    return m
  }, [dbProviders])

  // Unified model fetching — CURATED-FIRST (2026-09-08, exercise 1:
  // the 09-08 cache-warm flip made the full-catalog browse win and the
  // curated subset disappear from the picker). Resolution order:
  //   Tier 1 — curated models (the human-vetted list) when the provider
  //            has an ACTIVE curated set (OpenRouter today). This is the
  //            star: the picker recommends, the Browse button explores.
  //   Tier 2 — the model browser (the FULL live catalog) when curated is
  //            empty — local Ollama's installed models, and cloud
  //            providers without an active curated set, are live
  //            discovery by nature (pre-July intent).
  //   Tier 3 — the static config seed, ONLY when both live sources fail
  //            (DB/API unreachable — its documented purpose).
  //   Tier 4 — manual text input when nothing resolves.
  useEffect(() => {
    const pid = providerNameToId[formData.provider]

    const fetchModels = async () => {
      setLoadingModels(true)
      setModelError(null)

      // Tier 1: Curated models — API first (the DB is the source of truth)
      try {
        const curated = await fetchCuratedModels(formData.provider)
        if (curated.length > 0) {
          setAvailableModels(curated)
          setLoadingModels(false)
          return
        }
      } catch (err) {
        frontendLoggingService.warning('ProfileDetail',
          `Curated models API failed for ${formData.provider}, trying live browse`, { error: err })
      }

      // Tier 2: Model browser (full live catalog) — for providers with
      // browser support AND no active curated set (local Ollama lists the
      // installed models; cloud providers without curated rows browse live)
      if (pid) {
        try {
          const response = await modelBrowserService.browseModels(pid, { page_size: 50 })
          if (response.data?.models && response.data.models.length > 0) {
            setAvailableModels(response.data.models)
            setLoadingModels(false)
            return
          }
        } catch (err) {
          frontendLoggingService.warning('ProfileDetail',
            `Model browser failed for ${formData.provider}, falling back to config seed`, { error: err })
        }
      }

      // Tier 3: static config seed (DB not reachable / no entries / no live browse)
      const curatedConfig = getCuratedModelsForProvider(formData.provider)
      setAvailableModels(curatedConfig.length > 0 ? curatedConfig : [])

      // Tier 4: If no models at all, show manual input (handled by render logic)
      if (curatedConfig.length === 0) {
        setModelError(`No curated models for ${formData.provider}. Enter model name manually.`)
      }

      setLoadingModels(false)
    }

    fetchModels()
  }, [formData.provider, providerNameToId])

  // Handle model selection from browser
  useEffect(() => {
    if (location.state?.modelSelected) {
      const selection = sessionStorage.getItem('selectedModel')
      if (selection) {
        try {
          const parsed = JSON.parse(selection)
          frontendLoggingService.info('ProfileDetail', 'Model selected from browser', parsed)
          
          // Update form data with selected model using provider ID map
          setFormData(prev => ({
            ...prev,
            provider: providerIdToName[parsed.providerId] || prev.provider,
            model: parsed.modelId,
          }))
          
          // Clear the selection
          sessionStorage.removeItem('selectedModel')
          
          // Clear navigation state
          navigate(location.pathname, { replace: true, state: {} })
        } catch (error) {
          frontendLoggingService.error('ProfileDetail', 'Failed to parse selected model', error)
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state])

  useEffect(() => {
    frontendLoggingService.debug('ProfileDetail:useEffect', 'useEffect triggered', { action, profileId: profile?.id, imageUrl: profile?.image_url })
    if (action === 'edit' && profile) {
      // Check if we have unsaved changes for this profile
      const formState = profileService.getFormState(profile.id)
      
      if (formState.hasUnsavedChanges && formState.formData) {
        // Restore unsaved changes
        frontendLoggingService.info('ProfileDetail:useEffect', 'Restoring unsaved form state', { profileId: profile.id })
        setFormData(formState.formData as ProfileCreate)
      } else {
        // Load from profile
        frontendLoggingService.debug('ProfileDetail:useEffect', 'Setting formData for edit mode with image_url', { image_url: profile.image_url })
        const initialData: ProfileCreate = {
          id: profile.id,
          name: profile.name,
          description: profile.description,
          provider: profile.provider,
          model: profile.model,
          system_prompt: profile.system_prompt,
          // THE ROW'S OWN DECLARATION, carried as it is (G4): a row that declares nothing
          // must reach the form as nothing, or opening and saving it would write a pair
          // nobody chose — the defect this arc removed from the API's create path.
          parameters: declaredSampling(profile.parameters) ?? undefined,
          // THE DECLARATION (G-I): the form edits the agent's OWN spec — the field
          // the resolver reads — so the contract rides into the form unchanged.
          llm_spec: profile.llm_spec || {},
          tools: profile.tools,
          memory: profile.memory,
          image_url: profile.image_url || '',
          cognitive_profile_id: profile.cognitive_profile_id ?? null,
          fallback_enabled: profile.fallback_enabled ?? false,
          preferred_providers: profile.preferred_providers ?? []
        }
        setFormData(initialData)
        setDeclareSampling(hasDeclaredSampling(profile.parameters))
        // Save initial form state
        profileService.saveFormState(profile.id, initialData)
      }
      
      // Clear the selected image file when switching profiles
      // This ensures the ProfileImageUpload component will show the database image
      setSelectedImageFile(null)
      setResetCounter(prev => prev + 1)
    } else if (action === 'create') {
      // For new profiles, start with empty form
      // ID will be generated on submit based on the name
      frontendLoggingService.debug('ProfileDetail:useEffect', 'Setting formData for create mode')
      setFormData({
        id: '',
        name: '',
        description: '',
        provider: 'ollama',
        model: 'llama3.2:latest',
        system_prompt: '',
        parameters: undefined,
        llm_spec: {},
        tools: [],
        memory: false,
        image_url: ''
      })
      setDeclareSampling(false)
      // Clear the selected image file when creating a new profile
      setSelectedImageFile(null)
      setResetCounter(prev => prev + 1)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile?.id, action])
  // Deps = [profile?.id, action], NOT [profile, action] (2026-09-06, the
  // 30s-refetch cycle the logs surfaced): the agents list refetches every
  // 30s -> a NEW profile object each time -> the old deps re-ran this
  // load/restore effect on every refetch, logging + setFormData'ing in a
  // loop (the 'Restoring unsaved form state' info spam). The id is stable
  // across refetches, so the form loads once per profile switch — and
  // refetches can't clobber in-progress edits.

  const handleInputChange = (field: string, value: unknown) => {
    const updatedData = {
      ...formData,
      [field]: value
    }
    setFormData(updatedData)
    
    // Save form state for persistence
    const profileId = action === 'edit' && profile ? profile.id : null
    profileService.saveFormState(profileId, updatedData)
    
    setError(null)
  }

  const handleParametersChange = (field: string, value: unknown) => {
    const updatedData = {
      ...formData,
      parameters: {
        ...formData.parameters,
        [field]: value === '' ? undefined : value
      }
    }
    setFormData(updatedData)
    
    // Save form state for persistence
    const profileId = action === 'edit' && profile ? profile.id : null
    profileService.saveFormState(profileId, updatedData)

    // A DRAG ANSWERS THE COMPLAINT (G4): the refusals above name the control the user has
    // to touch, so touching it clears the banner — the same rule the other inputs follow,
    // and without it the form would keep saying "nothing is set" over a set value.
    setError(null)
  }

  // THE DECLARATION'S EDIT PATH (G-I): the output budget lives in the agent's own
  // llm_spec, so the form writes THAT field — the one the resolver reads. An empty
  // input removes the key rather than storing a zero, because "undeclared" is a real
  // state and the API refuses anything below 1.
  const handleSpecChange = (field: string, value: unknown) => {
    const spec = { ...(formData.llm_spec || {}) }
    if (value === '' || value === undefined) {
      delete spec[field as keyof typeof spec]
    } else {
      spec[field as keyof typeof spec] = value as never
    }
    const updatedData = { ...formData, llm_spec: spec }
    setFormData(updatedData)

    const profileId = action === 'edit' && profile ? profile.id : null
    profileService.saveFormState(profileId, updatedData)
  }

  // THE DECLARATION, AS ONE ACT (G4). A preset click and the switch both land here:
  //  · a preset DECLARES its pair (and so turns the switch on);
  //  · the switch turns ON with no value — the sliders become usable and NOTHING is
  //    written until one is dragged, so flipping it cannot invent a pair;
  //  · "Declare nothing" clears the pair and the switch together.
  // Nothing on this path writes a value the user did not choose.
  const applySamplingDeclaration = (declaration: SamplingDeclaration | undefined) => {
    setDeclareSampling(declaration !== undefined)
    const updatedData = { ...formData, parameters: declaration }
    setFormData(updatedData)

    const profileId = action === 'edit' && profile ? profile.id : null
    profileService.saveFormState(profileId, updatedData)

    // Declaring, clearing or preset-clicking all ANSWER the refusal above — the banner
    // goes the moment the state it complained about changes.
    setError(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // Validation
    if (!formData.name.trim()) {
      setError('Profile name is required')
      return
    }
    if (!formData.model.trim()) {
      setError('Model is required')
      return
    }

    // THE DECLARATION MUST BE A DECISION (G4): the switch ON with nothing set is a
    // half-made choice — refused here, by name, rather than saved as an empty dict.
    const declaredNow = declaredSampling(formData.parameters)
    if (declareSampling && !declaredNow) {
      setError('Sampling is on but nothing is set — drag Temperature or Top P, or click a preset.')
      return
    }

    try {
      // For new profiles, generate ID from name if not already set
      const dataToSave = { ...formData }
      // A DECLARED PAIR RIDES AS ITSELF; "declares nothing" is sent as null rather than an
      // empty object (G4), so the row keeps ONE shape for it. `declaredNow` counts a 0 as
      // declared, so a temperature of 0 is never mistaken for an absent field.
      dataToSave.parameters = declaredNow ?? null
      if (action === 'create' && !dataToSave.id) {
        const nameSlug = formData.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
        const randomSuffix = Math.random().toString(36).substr(2, 6)
        dataToSave.id = nameSlug ? `${nameSlug}-${randomSuffix}` : `profile-${randomSuffix}`
        frontendLoggingService.info('ProfileDetail:handleSubmit', 'Generated ID for new profile', { id: dataToSave.id })
      }

      frontendLoggingService.info('ProfileDetail:handleSubmit', 'Submitting profile', dataToSave)
      frontendLoggingService.info('ProfileDetail:handleSubmit', 'Image file status', { hasImage: !!selectedImageFile })
      await onSave(dataToSave, selectedImageFile || undefined)
      frontendLoggingService.info('ProfileDetail:handleSubmit', 'Profile saved successfully')
      
      // Clear form state after successful save
      profileService.clearFormState()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save profile'
      frontendLoggingService.error('ProfileDetail:handleSubmit', 'Error saving profile', err)
      setError(message)
    }
  }

  const handleDelete = async () => {
    if (!profile || !onDelete) return
    // the BOM dialog: what the agent HAS, disclosed before deletion
    setDeleteDialog({ open: true, deleting: false, report: null })
  }

  const confirmDelete = async () => {
    if (!profile || !onDelete) return
    setDeleteDialog(d => ({ ...d, deleting: true }))
    try {
      // the delete response IS the result report (BOM + archive)
      const report = await onDelete(profile.id)
      setDeleteDialog({ open: true, deleting: false, report: report })
      if (report) {
        addSuccess('Profile deleted — the workspace was archived.')
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete profile'
      setError(message)
      setDeleteDialog({ open: false, deleting: false, report: null })
    }
  }

  // RESET MEMORY (2026-08-19): the deep agent's watch-it-learn
  // restarts fresh — memory + sessions cleared, identity kept.
  const [resetDialog, setResetDialog] = useState(false)
  const [isResetting, setIsResetting] = useState(false)

  const handleResetMemory = async () => {
    if (!profile) return
    try {
      setIsResetting(true)
      await profileService.resetMemory(profile.id)
      addSuccess('Memory reset — the agent restarts fresh (identity kept).')
      setResetDialog(false)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to reset memory'
      setError(message)
      setResetDialog(false)
    } finally {
      setIsResetting(false)
    }
  }

  if (!profile && action === 'edit') {
    return (
      <div className="flex-1 flex items-center justify-center bg-base-50">
        <div className="text-center">
          <p className="text-readout">Select a profile to edit</p>
        </div>
      </div>
    )
  }

  frontendLoggingService.debug('ProfileDetail:render', 'ProfileDetail rendering', { profile: profile?.id, action, activeTab, name: formData.name, image_url: formData.image_url })

  return (
    <div className="flex-1 bg-base-50 overflow-y-auto">
      <form onSubmit={handleSubmit} className="p-6 w-full max-w-none">
        <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
          {action === 'create' ? 'Create New Profile' : 'Edit Profile'}
          {action === 'edit' && profile?.cognitive_profile_depth && (
            <span
              className="tooltip tooltip-bottom"
              data-tip={`${profile.cognitive_profile_name ?? 'profile'} — ${
                profile.cognitive_profile_depth === 'deep'
                  ? 'the memory + pipeline family'
                  : profile.cognitive_profile_depth === 'shallow'
                    ? 'the lean family (no persistent memory)'
                    : 'the in-between family'
              }`}
            >
              <span className="badge badge-sm badge-info badge-outline">
                {profile.cognitive_profile_depth}
              </span>
            </span>
          )}
        </h2>

        {error && (
          <div className="alert alert-error mb-4">
            <span>{error}</span>
          </div>
        )}

        {/* Tabs */}
        <div className="tabs tabs-bordered mb-6">
          <button
            type="button"
            className={`tab ${activeTab === 'basic' ? 'tab-active' : ''}`}
            onClick={() => {
              frontendLoggingService.debug('ProfileDetail:tabs', 'Switching to Basic Info tab')
              setActiveTab('basic')
            }}
          >
            Basic Info
          </button>
          <button
            type="button"
            className={`tab ${activeTab === 'provider' ? 'tab-active' : ''}`}
            onClick={() => {
              frontendLoggingService.debug('ProfileDetail:tabs', 'Switching to Provider Settings tab')
              setActiveTab('provider')
            }}
          >
            Provider Settings
          </button>
          <button
            type="button"
            className={`tab ${activeTab === 'behavior' ? 'tab-active' : ''}`}
            onClick={() => {
              frontendLoggingService.debug('ProfileDetail:tabs', 'Switching to Behavior tab')
              setActiveTab('behavior')
            }}
          >
            Behavior
          </button>
          <button
            type="button"
            className={`tab ${activeTab === 'advanced' ? 'tab-active' : ''}`}
            onClick={() => {
              frontendLoggingService.debug('ProfileDetail:tabs', 'Switching to Advanced tab')
              setActiveTab('advanced')
            }}
          >
            Advanced
          </button>
          {action === 'edit' && profile && (
            <button
              type="button"
              className={`tab ${activeTab === 'collections' ? 'tab-active' : ''}`}
              onClick={() => {
                frontendLoggingService.debug('ProfileDetail:tabs', 'Switching to Collections tab')
                setActiveTab('collections')
              }}
            >
              Collections
            </button>
          )}
          {action === 'edit' && profile && (
            <button
              type="button"
              className={`tab ${activeTab === 'tools' ? 'tab-active' : ''}`}
              onClick={() => {
                frontendLoggingService.debug('ProfileDetail:tabs', 'Switching to Tools tab')
                setActiveTab('tools')
              }}
            >
              🛠️ Tools
            </button>
          )}
          {action === 'edit' && profile && (
            <button
              type="button"
              className={`tab ${activeTab === 'cognitive' ? 'tab-active' : ''}`}
              onClick={() => {
                frontendLoggingService.debug('ProfileDetail:tabs', 'Switching to Cognitive tab')
                setActiveTab('cognitive')
              }}
            >
              🧠 Cognitive
            </button>
          )}
          {action === 'edit' && profile && (
            <button
              type="button"
              className={`tab ${activeTab === 'package' ? 'tab-active' : ''}`}
              onClick={() => {
                frontendLoggingService.debug('ProfileDetail:tabs', 'Switching to Package tab')
                setActiveTab('package')
              }}
            >
              Package
            </button>
          )}
        </div>

        {/* Basic Info Tab */}
        {activeTab === 'basic' && (
          <div className="space-y-6">
            {/* Image Upload */}
            <div>
              <ProfileImageUpload
                profileId={profile?.id}
                currentImageUrl={formData.image_url}
                onImageUrlChange={(url) => {
                  frontendLoggingService.debug('ProfileDetail:ProfileImageUpload', 'Image URL changed', { url })
                  handleInputChange('image_url', url)
                }}
                onImageFileChange={(file) => setSelectedImageFile(file)}
                isLoading={isSaving}
                resetTrigger={resetCounter}
                health={profile?.health}
                serviceAvailability={profile?.service_availability}
              />
            </div>

            {/* Name */}
            <div className="form-control">
              <label className="label">
                <span className="label-text font-semibold">Profile Name *</span>
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => handleInputChange('name', e.target.value)}
                disabled={isSaving}
                className="input input-bordered rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-input-bg)] border-[var(--form-input-border)] text-[var(--form-input-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                placeholder="e.g., Creative Writer"
              />
            </div>

            {/* Description */}
            <div className="form-control">
              <label className="label">
                <span className="label-text font-semibold">Description</span>
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => handleInputChange('description', e.target.value)}
                disabled={isSaving}
                className="textarea textarea-bordered rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-textarea-bg)] border-[var(--form-textarea-border)] text-[var(--form-textarea-text)] focus:border-[var(--form-textarea-focus-border)] transition-all duration-[var(--button-transition)]"
                placeholder="Brief description of this profile"
                rows={3}
              />
            </div>
          </div>
        )}

        {/* Provider Settings Tab */}
        {activeTab === 'provider' && (
          <div className="space-y-6">
            {/* Provider & Model */}
            <div className="grid grid-cols-2 gap-4">
              <div className="form-control">
                <label className="label">
                  <span className="label-text font-semibold">Provider *</span>
                </label>
                <div className="tooltip tooltip-top" data-tip="Select the AI provider for this profile">
                  <select
                    value={formData.provider}
                    onChange={(e) => handleInputChange('provider', e.target.value)}
                    disabled={isSaving}
                    className="select select-bordered rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-select-bg)] border-[var(--form-select-border)] text-[var(--form-select-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                  >
                    {providersLoading ? (
                      <option value="">Loading providers...</option>
                    ) : dbProviders.length > 0 ? (
                      <>
                        <option value="">Select a provider...</option>
                        {dbProviders.map((p: any) => ( // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
                          <option key={p.id} value={p.name ?? p.id}>
                            {p.display_name || p.name}
                          </option>
                        ))}
                      </>
                    ) : (
                      <>
                        <option value="ollama">Ollama (Local)</option>
                        <option value="openrouter">OpenRouter (Cloud)</option>
                        <option value="openai">OpenAI (Cloud)</option>
                        <option value="anthropic">Anthropic (Cloud)</option>
                        <option value="deepseek">Deepseek (Cloud)</option>
                        <option value="groq">Groq (Cloud)</option>
                      </>
                    )}
                  </select>
                </div>
              </div>
              <div className="form-control">
                <label className="label">
                  <span className="label-text font-semibold">Model *</span>
                </label>
                <div className="flex gap-2">
                  {/* Unified model dropdown — handles all providers via three-tier resolution */}
                  {availableModels.length > 0 && !loadingModels ? (
                    <div className="tooltip tooltip-top" data-tip="Select a model">
                      <select
                        value={formData.model}
                        onChange={(e) => handleInputChange('model', e.target.value)}
                        disabled={isSaving || loadingModels}
                        className="select select-bordered flex-1 rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-select-bg)] border-[var(--form-select-border)] text-[var(--form-select-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                      >
                        {loadingModels ? (
                          <option>Loading models...</option>
                        ) : (
                          <>
                            <option value="">Select a model...</option>
                            {availableModels.map((model) => {
                              // Handle different model types (OllamaModel, ModelInfo, CuratedModel)
                              // VALUE = the string saved to the agent. Curated rows carry the
                              // API model id in `id` ('qwen/qwen3.8-flash') and the display
                              // name in `name` ('Qwen: Qwen3.8 Flash'); the value MUST be the
                              // id — saving the display name breaks the runtime (2026-09-08
                              // live: Bob got saved as 'Qwen: Qwen3.8 Flash', the runtime
                              // built 'openrouter/Qwen: Qwen3.8 Flash', and the agent failed).
                              const key = 'category' in model
                                ? (model as CuratedModel).id
                                : 'name' in model
                                  ? (model as OllamaModel).name
                                  : (model as ModelInfo).id
                              const label = 'display_name' in model && (model as ModelInfo).display_name
                                ? (model as ModelInfo).display_name
                                : 'name' in model
                                  ? (model as OllamaModel | CuratedModel).name
                                  : (model as ModelInfo).id
                              const sizeInfo = 'size_formatted' in model ? ` (${(model as OllamaModel).size_formatted})` : ''
                              const isFree = 'isFree' in model ? (model as CuratedModel).isFree : false
                              const verified = 'verified' in model ? (model as CuratedModel).verified : false
                              return (
                                <option key={key} value={key}>
                                  {label}{sizeInfo}{isFree ? ' (Free)' : ''}{verified ? ' ✓' : ''}
                                </option>
                              )
                            })}
                          </>
                        )}
                      </select>
                    </div>
                  ) : loadingModels ? (
                    <div className="tooltip tooltip-top" data-tip="Loading models...">
                      <select
                        disabled
                        className="select select-bordered flex-1 rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-select-bg)] border-[var(--form-select-border)] text-[var(--form-select-text)]"
                      >
                        <option>Loading models...</option>
                      </select>
                    </div>
                  ) : (
                    // Tier 3: Manual text input when no models available
                    <div className="tooltip tooltip-top" data-tip="Enter the model name manually">
                      <input
                        type="text"
                        value={formData.model}
                        onChange={(e) => handleInputChange('model', e.target.value)}
                        disabled={isSaving}
                        className="input input-bordered flex-1 rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-input-bg)] border-[var(--form-input-border)] text-[var(--form-input-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                        placeholder="e.g., gpt-4, claude-3"
                      />
                    </div>
                  )}

                  {/* Unified Browse Models button — all providers with browser support */}
                  {formData.provider in providerNameToId ? (
                    <button
                      type="button"
                      onClick={() => {
                        const providerId = providerNameToId[formData.provider]
                        sessionStorage.setItem('returnToProfile', 'true')
                        sessionStorage.setItem('selectedModel', JSON.stringify({
                          providerId,
                          modelId: formData.model,
                          modelName: formData.model,
                        }))
                        navigate(`/providers/${providerId}/models`)
                      }}
                      disabled={isSaving}
                      className="btn btn-sm btn-primary rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                    >
                      <div className="tooltip tooltip-top" data-tip="Browse available models">
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          className="h-4 w-4 mr-2"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"
                          />
                        </svg>
                        Browse Models
                      </div>
                    </button>
                  ) : (
                    <div className="tooltip tooltip-top" data-tip="This provider is not registered yet — it cannot be browsed">
                      <button
                        type="button"
                        disabled={true}
                        className="btn btn-sm btn-ghost rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          className="h-4 w-4 opacity-50"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M4 6h16M4 12h16M4 18h16"
                          />
                        </svg>
                        Browse
                      </button>
                    </div>
                  )}
                </div>
                {modelError && (
                  <label className="label">
                    <span className="label-text-alt text-warning">{modelError}</span>
                  </label>
                )}
              </div>
            </div>
            
            {/* Fallback Configuration (F4) — opt-in per agent */}
            <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)] mt-4">
              <div className="card-body p-[var(--card-padding)]">
                <h3 className="card-title text-sm font-semibold flex items-center gap-2">
                  <span>🔄 Provider Fallback</span>
                  <span className="badge badge-ghost badge-xs">optional</span>
                </h3>
                <p className="text-xs text-readout">
                  If the primary provider fails, try a fallback provider before showing an
                  error. Disabled by default — failures surface visibly. When enabled, each
                  fallback is logged so you always know when a failover happened.
                </p>

                {/* Toggle */}
                <div className="form-control mt-2">
                  <label className="label cursor-pointer justify-start gap-3">
                    <input
                      type="checkbox"
                      className="toggle toggle-primary"
                      checked={formData.fallback_enabled ?? false}
                      onChange={(e) => handleInputChange('fallback_enabled', e.target.checked)}
                      disabled={isSaving}
                    />
                    <span className="label-text">Enable automatic fallback on provider failure</span>
                  </label>
                </div>

                {/* Preferred providers picker */}
                {formData.fallback_enabled && (
                  <div className="form-control mt-2">
                    <label className="label">
                      <span className="label-text font-semibold">Fallback order (optional)</span>
                    </label>
                    <p className="text-xs text-readout mb-1">
                      Providers tried in order after the primary fails. Leave empty to use the
                      default chain (OpenRouter → DeepSeek → Ollama).
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {(dbProviders.length > 0 ? dbProviders : [
                        { id: 1, name: 'ollama', display_name: 'Ollama (Local)' },
                        { id: 2, name: 'openrouter', display_name: 'OpenRouter (Cloud)' },
                        { id: 3, name: 'deepseek', display_name: 'Deepseek (Cloud)' },
                      ]).filter((p: any) => p.name !== formData.provider).map((p: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
                        const selected = (formData.preferred_providers ?? []).includes(p.name ?? p.id)
                        return (
                          <button
                            key={p.id}
                            type="button"
                            className={`btn btn-sm btn-outline rounded-[var(--button-radius)] px-[var(--button-padding)] ${
                              selected ? 'btn-primary' : ''
                            }`}
                            onClick={() => {
                              const current = formData.preferred_providers ?? []
                              const name = p.name ?? p.id
                              const next = selected
                                ? current.filter((x) => x !== name)
                                : [...current, name]
                              handleInputChange('preferred_providers', next)
                            }}
                            disabled={isSaving}
                          >
                            {p.display_name || p.name}
                            {selected ? ' ✓' : ''}
                          </button>
                        )
                      })}
                    </div>
                    {formData.preferred_providers && formData.preferred_providers.length > 0 && (
                      <p className="text-xs text-readout mt-1">
                        Order: {formData.preferred_providers.join(' → ')}
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Model Info Card — only shown for Ollama models which have OllamaModel details */}
            {formData.provider === 'ollama' && (() => {
              const ollamaModel = availableModels.find(
                (m): m is OllamaModel => 'name' in m && 'size_formatted' in m && m.name === formData.model
              )
              if (!ollamaModel) return null
              return (
                <div className="card bg-base-200 shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)]">
                  <div className="card-body p-[var(--card-padding)]">
                    <h4 className="card-title text-sm">{ollamaModel.name} Details</h4>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>
                        <span className="text-readout">Family:</span>{' '}
                        {ollamaModel.family}
                      </div>
                      <div>
                        <span className="text-readout">Parameters:</span>{' '}
                        {ollamaModel.parameter_size}
                      </div>
                      <div>
                        <span className="text-readout">Quantization:</span>{' '}
                        {ollamaModel.quantization}
                      </div>
                      <div>
                        <span className="text-readout">Size:</span>{' '}
                        {ollamaModel.size_formatted}
                      </div>
                    </div>
                  </div>
                </div>
              )
            })()}
          </div>
        )}

        {/* Behavior Tab */}
        {activeTab === 'behavior' && (
          <div className="space-y-6">
            {/* Template Selector */}
            <div className="form-control w-full">
              <label className="label pb-0">
                <span className="label-text font-semibold">System Prompt Template</span>
              </label>
              <div className="tooltip tooltip-top" data-tip="Select a pre-written system prompt to quickly configure this agent's behavior. Or write your own custom prompt below.">
                <select
                  value={selectedTemplateId}
                  onChange={async (e) => {
                    const templateId = e.target.value
                    setSelectedTemplateId(templateId)

                    if (templateId) {
                      // Apply template with default variables
                      const rendered = await profileService.applyTemplate(templateId, {
                        assistant_name: formData.name || 'Assistant',
                        role: 'helpful',
                        tone: 'friendly',
                        user_name: 'User',
                        style: 'clear',
                        focus: 'helpful'
                      })

                      if (rendered) {
                        handleInputChange('system_prompt', rendered)
                      }
                    }
                  }}
                  disabled={isSaving || loadingTemplates}
                  className="select select-bordered rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-select-bg)] border-[var(--form-select-border)] text-[var(--form-select-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                >
                  <option value="">— Choose a template (optional) —</option>
                  {loadingTemplates ? (
                    <option>Loading templates...</option>
                  ) : (
                    templates?.map((template) => (
                      <option key={template.id} value={template.id}>
                        {template.name}
                      </option>
                    ))
                  )}
                </select>
              </div>
              {selectedTemplateId && templates?.find(t => t.id === selectedTemplateId) && (
                <label className="label">
                  <span className="label-text-alt text-readout">
                    {templates?.find(t => t.id === selectedTemplateId)?.description}
                  </span>
                </label>
              )}
            </div>

            {/* System Prompt */}
            <div className="form-control w-full">
              <label className="label pb-0">
                <span className="label-text font-semibold">System Prompt</span>
              </label>
              <textarea
                value={formData.system_prompt}
                onChange={(e) => handleInputChange('system_prompt', e.target.value)}
                disabled={isSaving}
                className="textarea textarea-bordered font-mono text-sm w-full rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-textarea-bg)] border-[var(--form-textarea-border)] text-[var(--form-textarea-text)] focus:border-[var(--form-textarea-focus-border)] transition-all duration-[var(--button-transition)]"
                placeholder="Define the role and behavior of this profile"
                rows={10}
              />
              <label className="label pt-1">
                <span className="label-text-alt text-readout">
                  Tip: Use templates above for quick setup, or write your own custom prompt
                </span>
              </label>
            </div>

            {/* Memory Toggle */}
            <div className="form-control">
              <div className="tooltip tooltip-top" data-tip="Long-term memory (coming soon)">
                <label className="label cursor-pointer justify-between">
                  <div>
                    <span className="label-text font-semibold">Enable Memory</span>
                    <span className="label-text-alt text-warning ml-2">(Coming Soon)</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={formData.memory}
                    onChange={(e) => handleInputChange('memory', e.target.checked)}
                    disabled={isSaving}
                    className="toggle toggle-primary"
                  />
                </label>
              </div>
              <label className="label">
                <span className="label-text-alt text-readout">
                  Allow this profile to remember conversations across sessions (not yet implemented)
                </span>
              </label>
            </div>
          </div>
        )}

        {/* Advanced Tab */}
        {activeTab === 'advanced' && (
          <div className="space-y-6">
            {/* Parameters */}
            <div className="space-y-6">
              {/* THE SAMPLING DECLARATION (the agent-init arc, G4).
                  A new agent declares NOTHING until this switch is turned on — and turning
                  it on still sets no value: the pair is written only by a drag or a preset
                  click. "Nothing declared" is a real state, not an empty slot, and it has a
                  named consequence one field down from the budget's: the turn sends no
                  sampling setting and the provider's own default applies. */}
              <div className="form-control">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <span className="label-text font-semibold">Sampling</span>
                  <div className="tooltip tooltip-top" data-tip="Send temperature and top_p with this agent's turns, or declare neither">
                    <ToggleSwitch
                      checked={declareSampling}
                      onChange={(on) =>
                        applySamplingDeclaration(
                          on ? (declaredSampling(formData.parameters) ?? {}) : undefined
                        )
                      }
                      label="Declare sampling"
                      disabled={isSaving}
                    />
                  </div>
                </div>
                <div className="text-xs text-readout mt-1" aria-label={samplingState}>
                  {samplingState}
                </div>
              </div>

              {/* Temperature Slider */}
              <div className="form-control">
                <label className="label">
                  <span className="label-text font-semibold">Temperature</span>
                  <span className="label-text-alt font-mono bg-base-200 px-2 py-1 rounded">
                    {formData.parameters?.temperature ?? 'not set'}
                  </span>
                </label>
                <div className="tooltip tooltip-top" data-tip={declareSampling ? 'Controls randomness: lower = more focused, higher = more creative' : 'Turn sampling on to set a temperature'}>
                  <input
                    type="range"
                    min={SAMPLING_BOUNDS.temperature.min}
                    max={SAMPLING_BOUNDS.temperature.max}
                    step={SAMPLING_BOUNDS.temperature.step}
                    value={formData.parameters?.temperature ?? SAMPLING_SLIDER_REST.temperature}
                    onChange={(e) => handleParametersChange('temperature', parseFloat(e.target.value))}
                    disabled={isSaving || !declareSampling}
                    className="range range-primary range-sm"
                    aria-label={`Temperature ${formData.parameters?.temperature ?? 'not set'}`}
                  />
                </div>
                <div className="flex justify-between text-xs text-readout px-1">
                  <span>Precise (0)</span>
                  <span>Balanced (1)</span>
                  <span>Creative (2)</span>
                </div>
              </div>

              {/* Top P Slider */}
              <div className="form-control">
                <label className="label">
                  <span className="label-text font-semibold">Top P</span>
                  <span className="label-text-alt font-mono bg-base-200 px-2 py-1 rounded">
                    {formData.parameters?.top_p ?? 'not set'}
                  </span>
                </label>
                <div className="tooltip tooltip-top" data-tip={declareSampling ? 'Nucleus sampling: diversity of token selection' : 'Turn sampling on to set top_p'}>
                  <input
                    type="range"
                    min={SAMPLING_BOUNDS.top_p.min}
                    max={SAMPLING_BOUNDS.top_p.max}
                    step={SAMPLING_BOUNDS.top_p.step}
                    value={formData.parameters?.top_p ?? SAMPLING_SLIDER_REST.top_p}
                    onChange={(e) => handleParametersChange('top_p', parseFloat(e.target.value))}
                    disabled={isSaving || !declareSampling}
                    className="range range-secondary range-sm"
                    aria-label={`Top P ${formData.parameters?.top_p ?? 'not set'}`}
                  />
                </div>
                <div className="flex justify-between text-xs text-readout px-1">
                  <span>Focused (0)</span>
                  <span>Diverse (1)</span>
                </div>
              </div>

              {/* Max Tokens Input */}
              <div className="form-control">
                <label className="label">
                  <span className="label-text font-semibold">Max Tokens</span>
                  <span className="label-text-alt font-mono bg-base-200 px-2 py-1 rounded">
                    {formData.llm_spec?.max_output ?? '—'}
                  </span>
                </label>
                <div className="tooltip tooltip-top" data-tip={budgetCeiling ? `Maximum length of the AI response (ceiling ${budgetCeiling})` : 'Maximum length of the AI response'}>
                  <input
                    type="number"
                    min="1"
                    max={budgetCeiling ?? undefined}
                    value={formData.llm_spec?.max_output ?? ''}
                    onChange={(e) => handleSpecChange('max_output', e.target.value === '' ? undefined : (parseInt(e.target.value) || 0))}
                    disabled={isSaving}
                    className="input input-bordered input-sm rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] bg-[var(--form-input-bg)] border-[var(--form-input-border)] text-[var(--form-input-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                    placeholder="undeclared"
                  />
                </div>
                {/* THE DECLARED-VS-SENT READ (G.1) — the number this field sets
                    beside the number a turn actually sends, both resolved by the
                    BACKEND's own resolver (the one the chat path runs), so they
                    are the numbers the wire carries and not a second arithmetic.
                    The reason is not decoration: two different numbers without it
                    read as a bug. A row that declares nothing says so rather than
                    borrowing a number to fill the slot. */}
                {profile?.output_budget && (
                  <div
                    className="text-xs text-readout flex flex-wrap items-baseline gap-x-2 mt-1"
                    aria-label={`This agent declares ${profile.output_budget.declared ?? 'nothing'} and a turn sends ${profile.output_budget.effective} tokens — ${budgetReasonLabel(profile.output_budget.reason)}`}
                  >
                    <span>Sends</span>
                    <span className="font-mono font-semibold">{profile.output_budget.effective}</span>
                    <span>·</span>
                    <span>
                      {profile.output_budget.declared === null
                        ? 'nothing declared'
                        : <>declared <span className="font-mono">{profile.output_budget.declared}</span></>}
                    </span>
                    <span>·</span>
                    <span className="font-semibold">{budgetReasonLabel(profile.output_budget.reason)}</span>
                  </div>
                )}
                {/* THE OBSERVED HALF (G-A ii) — what the LAST turn actually carried,
                    from that turn's own record. It sits under the prediction because
                    the two answer different questions: the line above says what WOULD
                    go out, this one says what DID. A reading with no date would
                    pretend to be current, so the time rides it. */}
                {profile?.output_budget?.observed && (
                  <div
                    className="text-xs text-readout flex flex-wrap items-baseline gap-x-2 mt-0.5"
                    aria-label={`The last turn carried ${profile.output_budget.observed.sent} tokens — ${budgetReasonLabel(profile.output_budget.observed.reason)}, on the ${profile.output_budget.observed.path} pass`}
                  >
                    <span>Last turn carried</span>
                    <span className="font-mono font-semibold">{profile.output_budget.observed.sent}</span>
                    <span>·</span>
                    <span>{budgetReasonLabel(profile.output_budget.observed.reason)}</span>
                    <span>·</span>
                    <span>{profile.output_budget.observed.path} pass</span>
                    {profile.output_budget.observed.at && (
                      <>
                        <span>·</span>
                        <span>
                          {new Date(profile.output_budget.observed.at).toLocaleString([], {
                            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                          })}
                        </span>
                      </>
                    )}
                  </div>
                )}
                <label className="label">
                  <span className="label-text-alt text-readout">
                    {budgetCeiling
                      ? `Maximum response length (1-${budgetCeiling})`
                      : 'Maximum response length'}
                  </span>
                </label>
              </div>
            </div>

            {/* Quick Presets — a click IS the decision: it declares the pair (and so turns
                the switch on). "Declare nothing" is the clear, the verb this row was
                missing: it used to be a "Reset to Defaults" that wrote Balanced's own
                numbers, which is a preset wearing a default's name. */}
            <div className="divider">Quick Presets</div>
            <div className="flex flex-wrap gap-2">
              {SAMPLING_PRESETS.map((preset) => (
                <div key={preset.id} className="tooltip tooltip-top" data-tip={preset.tip}>
                  <button
                    type="button"
                    disabled={isSaving}
                    className="btn btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)] btn-outline"
                    onClick={() => applySamplingDeclaration({ ...preset.values })}
                  >
                    {preset.emoji} {preset.label} (Temp: {preset.values.temperature})
                  </button>
                </div>
              ))}
              <div className="tooltip tooltip-top" data-tip="Clear the pair — this agent declares no sampling">
                <button
                  type="button"
                  disabled={isSaving}
                  className="btn btn-sm rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)] btn-outline"
                  onClick={() => applySamplingDeclaration(undefined)}
                >
                  🔄 Declare nothing
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Collections Tab (Edit mode only) */}
        {activeTab === 'collections' && profile && (
          <CollectionsTab profileId={profile.id} profileName={profile.name} />
        )}

        {/* Tools Tab (Edit mode only) */}
        {activeTab === 'tools' && profile && (
          <div className="p-6">
            <AgentToolsTab agentId={profile.id} agentName={profile.name} />
          </div>
        )}

        {/* Cognitive Tab (Edit mode only) */}
        {activeTab === 'package' && profile && (
          <PackageTab profile={profile} />
        )}

        {activeTab === 'cognitive' && profile && (
          <div className="space-y-4">
            <div className="p-[var(--card-padding)]">
              <p className="text-sm text-readout mb-4">
                Assign a cognitive profile to this agent. The profile defines
                the pipeline strategies (context builder, executor, memory, response formatter)
                used when running this agent.
              </p>
              <CognitiveProfileSelector
                value={formData.cognitive_profile_id}
                onChange={(id) => setFormData(prev => ({ ...prev, cognitive_profile_id: id }))}
              />
            </div>
          </div>
        )}

        {/* Buttons - Always visible */}
        <div className="flex gap-3 justify-between mt-8 pt-6 border-t border-base-300">
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={isSaving}
              className="btn btn-primary rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
            >
              {isSaving ? (
                <>
                  <span className="loading loading-spinner loading-sm"></span>
                  Saving...
                </>
              ) : (
                'Save Profile'
              )}
            </button>
            {onSaveAsTemplate && (
              <div className="tooltip tooltip-top" data-tip="Save current configuration as a template">
                <button
                  type="button"
                  onClick={onSaveAsTemplate}
                  disabled={isSaving}
                  className="btn btn-ghost rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                >
                  Save as Template
                </button>
              </div>
            )}
            <button
              type="button"
              onClick={onCancel}
              disabled={isSaving}
              className="btn btn-ghost rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
            >
              Cancel
            </button>
          </div>
          {action === 'edit' && (
            <button
              type="button"
              onClick={async () => {
                try {
                  const resp = await fetch(`/api/v1/agents/${profile?.id || ''}/export`);
                  if (resp.ok) {
                    const blob = await resp.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `agent-${profile?.name || 'export'}.json`;
                    a.click();
                    URL.revokeObjectURL(url);
                    addSuccess('Agent exported successfully');
                  } else {
                    addError('Failed to export agent');
                  }
                } catch {
                  addError('Failed to export agent');
                }
              }}
              disabled={isSaving}
              className="btn btn-transfer btn-outline rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
            >
              Export Agent
            </button>
          )}
          {action === 'edit' && (
            <>
            <input
              type="file"
              accept=".json"
              ref={importFileInputRef}
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                try {
                  const text = await file.text();
                  const bundle = JSON.parse(text);
                  const resp = await fetch('/api/v1/agents/import', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(bundle),
                  });
                  if (resp.ok) {
                    const result = await resp.json();
                    // The backend owns the sentence: a bundle that names no service reports which
                    // service it landed on, so the user reads it here instead of opening the agent.
                    addSuccess(result.message || 'Agent imported successfully');
                    if (onUpdated) onUpdated();
                  } else {
                    const errText = await resp.text();
                    addError('Failed to import agent: ' + errText);
                  }
                } catch {
                  addError('Failed to import agent');
                }
                e.target.value = '';
              }}
            />
            <button
              type="button"
              onClick={() => importFileInputRef.current?.click()}
              disabled={isSaving}
              className="btn btn-transfer btn-outline rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
            >
              Import Agent
            </button>
            </>
          )}
          {action === 'edit' && onDelete && (
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleteDialog.deleting || isSaving}
              className="btn btn-error btn-outline rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]">
              Delete Profile
            </button>
          )}
          {action === 'edit' && profile && (
            <button
              type="button"
              onClick={() => setResetDialog(true)}
              disabled={isSaving}
              className="btn btn-warning btn-outline rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
              title="Clear the agent's memory + chat sessions (the identity stays)">
              Reset Memory
            </button>
          )}
        </div>
      </form>

      {/* The reset-memory confirm (2026-08-19) — destructive-ish
          (memory is lost), NOT deletion: the agent survives. */}
      {resetDialog && (
        <div className="fixed inset-0 z-[9999] bg-black/60 flex items-center justify-center p-4"
             onClick={() => setResetDialog(false)}>
          <div className="bg-base-200 rounded-lg shadow-xl p-6"
               style={{ width: 'min(var(--dialog-width-sm), 95vw)' }}
               onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold mb-2 text-warning">Reset {profile?.name}'s memory?</h3>
            <p className="text-sm text-readout mb-4">
              The agent's learned memory and chat sessions are cleared.
              The agent itself stays — its identity, skills, and
              workspace are untouched. The deep agent restarts fresh.
            </p>
            <div className="flex justify-end gap-2">
              <button className="btn btn-ghost" onClick={() => setResetDialog(false)}>
                Cancel
              </button>
              <button
                className="btn btn-warning"
                disabled={isResetting}
                onClick={handleResetMemory}>
                {isResetting ? 'Resetting…' : 'Reset memory'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* The delete dialog — the BOM disclosed (Phase D) */}
      {deleteDialog.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
             onClick={() => !deleteDialog.deleting && setDeleteDialog({ open: false, deleting: false, report: null })}>
          <div className="card bg-base-100 w-full max-w-md shadow-2xl"
               onClick={e => e.stopPropagation()}>
            <div className="card-body">
              {!deleteDialog.report ? (
                <>
                  <h3 className="card-title">Delete {profile?.name}?</h3>
                  <p className="text-sm text-readout">
                    This removes the profile and its workspace:
                  </p>
                  <ul className="list-disc list-inside text-sm space-y-1">
                    <li>{profile?.tools?.length ?? 0} tool link(s)</li>
                    <li>Memory {profile?.memory ? 'store' : '(none)'}</li>
                    {profile?.workspace_key ? (
                      <li>Workspace folder (agent.json, skills)</li>
                    ) : (
                      <li>No workspace folder</li>
                    )}
                  </ul>
                  <p className="text-xs text-readout mt-1">
                    The workspace is archived (agents/.archived/) and can
                    be restored later — the profile record is recoverable.
                  </p>
                  <div className="card-actions justify-end mt-3">
                    <button className="btn btn-ghost btn-sm"
                            onClick={() => setDeleteDialog({ open: false, deleting: false, report: null })}>
                      Cancel
                    </button>
                    <button className="btn btn-error btn-sm"
                            onClick={confirmDelete} disabled={deleteDialog.deleting}>
                      {deleteDialog.deleting ? 'Deleting…' : 'Delete Profile'}
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <h3 className="card-title">Profile deleted</h3>
                  <p className="text-sm text-readout">
                    Removed: {String((deleteDialog.report.bom as Record<string, number> | undefined)?.tool_links ?? 0)} tool link(s),{' '}
                    {String((deleteDialog.report.bom as Record<string, number> | undefined)?.collections ?? 0)} collection(s),{' '}
                    {String((deleteDialog.report.bom as Record<string, number> | undefined)?.chat_sessions ?? 0)} chat session(s).
                  </p>
                  {deleteDialog.report.archived_path ? (
                    <p className="text-xs text-readout break-all mt-2">
                      Archived at: {archiveFolderName(String(deleteDialog.report.archived_path ?? ''))}
                    </p>
                  ) : (
                    <p className="text-xs text-readout mt-2">
                      No workspace to archive (the profile had none).
                    </p>
                  )}
                  <div className="card-actions justify-end mt-3">
                    <button className="btn btn-primary btn-sm"
                            onClick={() => { setDeleteDialog({ open: false, deleting: false, report: null }); resetSelection() }}>
                      Done
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

