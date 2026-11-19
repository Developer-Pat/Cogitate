/**
 * ProfileService - Centralized profile state management
 *
 * Purpose:
 * - Single source of truth for profile state
 * - In-memory caching to avoid repeated API calls
 * - Reactive updates via subscriber pattern
 * - Background sync with backend
 *
 * Benefits:
 * - No stale state (components get current data)
 * - No repeated API calls (cached and shared)
 * - Easy to debug (all profile access goes through service)
 * - Decoupled from React/Zustand
 */

import { apiClient } from '../apiClient'
import { frontendLoggingService } from '../frontendLoggingService'
import {
  declaredSampling,
  type SamplingDeclaration
} from '@/utils/samplingDeclaration'

import type { Agent } from '@/types/agentInteraction'

/**
 * The archive folder's NAME (the last path segment) — the UI
 * shows the folder, not the raw stored path (legacy rows carry
 * ugly '../../..' relative forms; the name is what matters).
 */
export function archiveFolderName(archivedPath: string | null | undefined): string {
  if (!archivedPath) return 'no workspace'
  const cleaned = archivedPath.replace(/\\/g, '/').replace(/\/+/g, '/')
  const parts = cleaned.split('/').filter(Boolean)
  return parts[parts.length - 1] ?? 'no workspace'
}


/** Response shape for GET /api/v1/agents?page=...&page_size=... */
interface AgentsListResponse {
  agents: Record<string, unknown>[]
  total: number
  page: number
  page_size: number
}

/** Response shape for POST /api/v1/agents (create) and PUT /api/v1/agents/:id (update) */
interface AgentDetailResponse {
  id: string | number
  name: string
  description?: string
  provider: string
  model: string
  system_prompt?: string
  parameters?: Record<string, unknown>
  template_id?: string
  profile_image_url?: string
  image_url?: string
  [key: string]: unknown
}

/** Response shape for GET /api/v1/providers/ollama/models */
interface OllamaModelsResponse {
  models: OllamaModel[]
}

/** Response shape for GET /api/v1/agents/system-templates */
type TemplatesListResponse = SystemPromptTemplate[]

/** Response shape for POST /api/v1/agents/system-templates/apply */
interface ApplyTemplateResponse {
  prompt: string
}

/** Response shape for upload endpoint */
interface ImageUploadResponse {
  profile_image_url?: string
  image_url?: string
  [key: string]: unknown
}

/** Shape of an API error response with nested detail */
interface ApiErrorResponse {
  response?: {
    data?: {
      detail?: string
    }
  }
}

export interface Profile {
  id: string
  name: string
  description: string
  provider: string
  model: string
  system_prompt: string
  parameters?: SamplingDeclaration
  template_id?: string
  // THE PACKAGE FIELDS (2026-08-25, the package's UI half Phase 1):
  // the kit (the tool surface the agent OWNS) + the owned llm_spec +
  // the package provenance (the lineage ONLY — the agent owns its
  // copies, the package's the blueprint).
  kit_id?: string | null
  llm_spec?: {
    kind?: string
    thinking?: string
    location?: string
    min_context?: number
    // THE DECLARATION (G-I): the output budget the resolver reads. One slot —
    // the agent's own contract, which adoption copies from the package.
    max_output?: number | null
  } | null
  package_id?: string | null
  tools: string[]
  memory: boolean
  workspace_key?: string | null
  image_url?: string
  cognitive_profile_id?: number | null
  // THE DEPTH READOUT (2026-09-06): the backend derives the family
  // via the ONE canonical map (selection_service.depth_family) — the
  // UI chip shows the truth, never a hardcoded label.
  cognitive_profile_name?: string | null
  cognitive_profile_depth?: 'deep' | 'shallow' | 'balanced' | null
  // THE BUILD FIX (2026-08-25, the tsc -b): the backend's profile
  // fields the ProfileDetail reads.
  fallback_enabled?: boolean
  preferred_providers?: string[]
  health?: {
    status: 'ok' | 'warn' | 'fail'
    consecutive_failures: number
    last_error?: string | null
    last_failure_at?: string | null
    failures_7d: number
  }
  // THE CURRENT QUESTION (G5-F2's agent half): can this agent run NOW? Built by the backend from
  // the SAME rule the pre-turn refusal applies, so this badge and a REFUSED turn cannot disagree.
  // `available` is null when nothing was checked — NEVER false — so the badge can say "not
  // checked" rather than call a working agent broken. `state` carries the availability
  // vocabulary; `checked_at` owns the staleness window.
  service_availability?: {
    state: 'available' | 'down-by-occupancy' | 'down' | 'unconfigured' | 'unknown' | 'disabled'
    available: boolean | null
    reason?: string | null
    checked_at?: string | null
    provider?: string | null
    model?: string | null
  } | null
  // THE DECLARED-VS-SENT READ (Phase G.1): what the row declares and what a turn
  // would actually send, resolved by the BACKEND's resolver — the same function
  // the chat path runs at send time, so the page never re-does the arithmetic.
  // `declared` is null when the row declares nothing (the class default speaks),
  // which is a state to SHOW, not to fill in with a number.
  output_budget?: {
    declared: number | null
    effective: number
    reason: string
    path: string
    // THE OBSERVED HALF (G-A ii): what this agent's LAST turn actually carried, read
    // from that turn's own row. Absent until a turn has run since the record existed —
    // and then the page shows the prediction alone rather than inventing a reading.
    observed?: {
      sent: number
      declared: number | null
      reason: string
      path: string
      at?: string | null
    } | null
  } | null
  // The DERIVED ceiling every declaration is checked against (D3), served with
  // the agent so the form's bound READS it instead of typing a second copy.
  budget_ceiling?: number | null
}

export interface ProfileCreate {
  id: string
  name: string
  description: string
  provider: string
  model: string
  system_prompt: string
  // NULL IS A DECLARATION TOO (G4): an explicit `null` means "this agent declares no
  // sampling", which is a different thing from the key being absent — absent means
  // "leave it alone" on an update. The API stores NULL for it either way.
  parameters?: SamplingDeclaration | null
  template_id?: string
  tools: string[]
  memory: boolean
  workspace_key?: string | null
  image_url?: string
  cognitive_profile_id?: number | null
  fallback_enabled?: boolean
  preferred_providers?: string[]
  llm_spec?: {
    kind?: string
    thinking?: string
    location?: string
    min_context?: number
    max_output?: number | null
  } | null
}

export interface ProfileUpdate {
  name?: string
  description?: string
  provider?: string
  model?: string
  system_prompt?: string
  // `null` clears the declaration; the key ABSENT leaves it untouched (the API reads
  // `exclude_unset`). Until this accepted null, an existing agent could not be returned
  // to "declares nothing" — the update mapper dropped the key and the row kept its pair.
  parameters?: SamplingDeclaration | null
  template_id?: string
  tools?: string[]
  memory?: boolean
  image_url?: string
  cognitive_profile_id?: number | null
  fallback_enabled?: boolean
  preferred_providers?: string[]
  llm_spec?: {
    kind?: string
    thinking?: string
    location?: string
    min_context?: number
    max_output?: number | null
  } | null
}

export interface OllamaModel {
  name: string
  size: number
  size_formatted: string
  family: string
  format: string
  parameter_size: string
  quantization: string
  digest: string
  modified_at: string
}

export interface SystemPromptTemplate {
  id: string
  name: string
  description: string
  prompt: string
  variables: string[]
}

type ProfileSubscriber = (profiles: Profile[]) => void

/**
 * The resolver's reason word, in the page's own language (Phase G.1).
 *
 * The words come from the backend (`output_budget.REASON_*`) and they are the
 * half that makes two different numbers readable: "sends 16000" beside "declared
 * 8192" is a mystery, the same line with "thinking floor" is a fact. An unknown
 * word is SHOWN rather than swallowed — a new reason must not go silent by being
 * unmapped here.
 */
export function budgetReasonLabel(reason: string | null | undefined): string {
  switch (reason) {
    case 'declared': return 'as declared'
    case 'type_default': return 'class default'
    case 'thinking_floor': return 'thinking floor'
    case 'thinking_mandatory': return 'thinking required'
    case 'runtime_override': return 'session override'
    case 'window_clamp': return 'clamped to the window'
    case 'no_declared_budget': return 'nothing declared'
    case 'fast_policy': return 'fast-path policy'
    case 'deep_min': return 'deep-pass minimum'
    default: return reason || 'reason unknown'
  }
}

// Form state for unsaved changes - persisted at application level
interface ProfileFormState {
  profileId: string | null
  formData: ProfileCreate | ProfileUpdate | null
  hasUnsavedChanges: boolean
}

export class ProfileService {
  private profiles: Profile[] = []
  private subscribers: Set<ProfileSubscriber> = new Set()

  /**
   * The DERIVED budget ceiling the server last served (G.1, D3).
   *
   * The form's bound reads THIS instead of typing a copy of the constant —
   * D3's whole point is one number, derived from the type table, shared by the
   * API validation and the UI. The copy is how the form came to cap every
   * budget at 8192 while the real ceiling is 49152, refusing legal values.
   *
   * `null` until something has been served, and then the input carries no `max`
   * attribute at all: the API is the guard, and an invented bound is worse than
   * no bound.
   */
  private budgetCeilingServed: number | null = null

  /** The ceiling the server has served this session (see above). */
  get budgetCeiling(): number | null {
    return this.budgetCeilingServed
  }
  private isLoading: boolean = false
  private lastSyncTime: Date | null = null
  private syncInterval: ReturnType<typeof setInterval> | null = null
  private basePath = '/api/v1/agents'
  private providersPath = '/api/v1/providers'
  // (the old `baseUrl` prefixing of image urls is gone — it baked the dev
  //  origin into stored values; images stay relative and the browser resolves)
  
  // Application-level form state persistence
  private formState: ProfileFormState = {
    profileId: null,
    formData: null,
    hasUnsavedChanges: false
  }

  constructor() {
    // NOTE (2026-09-06): NO auto-start here. The old constructor kicked
    // off the 60s background sync on MODULE IMPORT — any page whose
    // bundle imported ProfileService (transitively: /logs too) ticked
    // loadFromBackend + logged 'API response' every minute forever.
    // The sync is now page-owned: AgentProfiles starts it on mount and
    // stops it on unmount (see the page's mount effect).
    // traceService.trace('ProfileService', 'initialized', {}, ['lifecycle', 'sync'])
  }

  /**
   * DEPRECATED(2026-09-17) — NO CALLERS.
   *
   * Dismiss an agent's health warning (F6): acknowledge failures up to now so the
   * badge clears until the next failure, then refresh the cache.
   *
   * Its ONLY caller was the AgentSelector's health badge, which was removed — the
   * same information lives on the AGENT PROFILES surface (AgentHealthCell), and the
   * selector was a second place to read one thing. Kept rather than deleted because
   * the backend endpoint (`.../health/dismiss`) still exists and the profiles surface
   * may want a dismiss of its own later. `grep DEPRECATED(2026-09-17)` finds this pair.
   */
  async dismissAgentHealth(agentId: string | number): Promise<void> {
    await apiClient.post(`${this.basePath}/${agentId}/health/dismiss`)
    await this.loadFromBackend()
  }

  /**
   * DEPRECATED(2026-09-17) — NO CALLERS (it had none before the removal either).
   *
   * Clear an agent's health dismissal so warnings re-evaluate fully (F6). The
   * counterpart to `dismissAgentHealth` above, and deprecated with it.
   */
  async undismissAgentHealth(agentId: string | number): Promise<void> {
    await apiClient.delete(`${this.basePath}/${agentId}/health/dismiss`)
    await this.loadFromBackend()
  }

  /**
   * Get all profiles from cache
   */
  getProfiles(): Profile[] {
    return [...this.profiles]
  }

  /**
   * Get single profile from cache by ID
   */
  getProfile(profileId: string): Profile | null {
    return this.profiles.find(p => p.id === profileId) || null
  }

  /**
   * Subscribe to profile changes
   *
   * @param callback - Function called when profiles change
   * @returns Unsubscribe function
   */
  subscribe(callback: ProfileSubscriber): () => void {
    this.subscribers.add(callback)
    // Immediately call with current state
    callback(this.profiles)
    // Return unsubscribe function
    return () => this.subscribers.delete(callback)
  }

  /**
   * Notify all subscribers of profile changes
   */
  private notifySubscribers(): void {
    // traceService.trace('ProfileService', 'notifiedSubscribers', {
      // subscriberCount: this.subscribers.size,
      // profileCount: this.profiles.length
    // }, ['state-change'])
    this.subscribers.forEach(cb => cb(this.profiles))
  }

  /**
   * Load profiles from backend and update cache
   */
  async loadFromBackend(): Promise<void> {
    if (this.isLoading) {
      // traceService.trace('ProfileService', 'loadFromBackend:already loading', {}, ['sync'])
      return
    }

    this.isLoading = true

    try {
      const response = await apiClient.get<AgentsListResponse>(`${this.basePath}?page=1&page_size=100`)

      // Log response for debugging
      frontendLoggingService.debug('ProfileService', 'API response', {
        hasData: !!response.data,
        hasError: !!response.error,
        dataKeys: response.data ? Object.keys(response.data) : [],
        agentsCount: response.data?.agents?.length ?? 0,
        status: response.status
      })

      // Backend returns {agents: [], total, page, page_size}
      const agents = response.data?.agents || []

      // Convert backend agents to frontend profile format
      this.profiles = agents.map((agent: Record<string, unknown>) => this.convertToProfile(agent))
      this.lastSyncTime = new Date()
      this.notifySubscribers()

      // traceService.trace('ProfileService', 'loadFromBackend:success', {
        // count: this.profiles.length,
        // syncTime: this.lastSyncTime.toISOString()
      // }, ['lifecycle', 'api-call', 'sync'])

      // TODO: Re-enable when debugging is needed - clogs logs
      // frontendLoggingService.info('ProfileService', 'Profiles loaded from backend', {
      //   count: this.profiles.length
      // })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error)
      frontendLoggingService.error('ProfileService', 'Failed to load profiles from backend', {
        error: errorMessage
      })

      // traceService.trace('ProfileService', 'loadFromBackend:error', {
        // error: errorMessage
      // }, ['error'])

      throw error
    } finally {
      this.isLoading = false
    }
  }

  /**
   * Create a new profile
   */
  async createProfile(profileData: ProfileCreate): Promise<Profile> {
    try {
      frontendLoggingService.info('ProfileService', 'Creating profile', {
        name: profileData.name,
        provider: profileData.provider,
        model: profileData.model
      })

      // Map frontend format to backend format
      const backendData: Record<string, unknown> = {
        name: profileData.name,
        description: profileData.description,
        provider: profileData.provider,
        model: profileData.model,
        system_prompt: profileData.system_prompt,
        is_active: true,
        // NO SAMPLING IS DECLARED BY DEFAULT (the agent-init arc, G2): this fallback
        // wrote `{temperature: 0.7, top_p: 0.9}` for a create that carried none, which
        // is the server-side factory's defect repeated on the transport. Nothing
        // declared sends nothing; the API stores no sampling and the turn then leaves
        // the provider's own default in place.
        parameters: profileData.parameters ?? null,
        // No budget by default (G-I): the declaration is the agent's own spec, and a
        // create that typed a number would put a silent default on every new agent —
        // the defect F.1 removed on the server side, kept out of the client too.
        llm_spec: profileData.llm_spec ?? null,
        template_id: profileData.template_id || null,
        cognitive_profile_id: profileData.cognitive_profile_id ?? null
      }

      const response = await apiClient.post<AgentDetailResponse>(`${this.basePath}`, backendData)

      if (!response.data) {
        throw new Error('Failed to create profile')
      }

      const newProfile = this.convertToProfile(response.data as unknown as Record<string, unknown>)
      this.profiles = [newProfile, ...this.profiles]
      this.notifySubscribers()

      frontendLoggingService.info('ProfileService', 'Profile created successfully', {
        profileId: newProfile.id,
        name: newProfile.name
      })

      return newProfile
    } catch (error) {
      frontendLoggingService.error('ProfileService', 'Failed to create profile', error)
      const message = (error as ApiErrorResponse)?.response?.data?.detail || 'Failed to create profile'
      throw new Error(message)
    }
  }

  /**
   * Update an existing profile
   */
  async updateProfile(profileId: string, updates: ProfileUpdate): Promise<void> {
    try {
      // Map frontend format to backend format
      const backendData: Record<string, unknown> = {}
      if (updates.name !== undefined) backendData.name = updates.name
      if (updates.description !== undefined) backendData.description = updates.description
      if (updates.provider !== undefined) backendData.provider = updates.provider
      if (updates.model !== undefined) backendData.model = updates.model
      if (updates.system_prompt !== undefined) backendData.system_prompt = updates.system_prompt
      // THE DECLARATION, INCLUDING ITS ABSENCE (G4): a pair rides; an explicit null
      // CLEARS it. The old test (`!== undefined`) dropped the null on the floor, so
      // "declare nothing" on an existing agent was not expressible — the row kept the
      // pair, and clearing it needed a DB edit.
      if ('parameters' in updates) backendData.parameters = updates.parameters ?? null
      if (updates.template_id !== undefined) backendData.template_id = updates.template_id
      if (updates.tools !== undefined) backendData.tools = updates.tools
      if (updates.memory !== undefined) backendData.memory = updates.memory
      // the backend field is profile_image_url; sending `image_url` was
      // silently ignored (Pydantic drops unknown fields) — the image
      // never stuck. Keep the frontend's name, map it here.
      if (updates.image_url !== undefined) {
        // store the RELATIVE url — an absolute one bakes this browser's
        // origin into the row and breaks the avatar elsewhere
        backendData.profile_image_url = String(updates.image_url).replace(/^https?:\/\/[^/]+/, '')
      }
      if (updates.cognitive_profile_id !== undefined) backendData.cognitive_profile_id = updates.cognitive_profile_id
      // THE DECLARATION (G-I): the spec — and with it the budget — is a writable
      // field on the update, which is what makes the form's Max Tokens control
      // able to change the number the resolver actually reads.
      if (updates.llm_spec !== undefined) backendData.llm_spec = updates.llm_spec

      const response = await apiClient.put<AgentDetailResponse>(`${this.basePath}/${profileId}`, backendData)

      if (!response.data) {
        throw new Error(`Failed to update profile ${profileId}`)
      }

      // Update cache FROM THE RESPONSE (G4): the row the server just wrote is the truth,
      // and spreading the REQUEST into a Profile would put the transport's `null`
      // declaration in the cache where a read never has one.
      const updated = this.convertToProfile(
        response.data as unknown as Record<string, unknown>
      )
      this.profiles = this.profiles.map(p => (p.id === profileId ? updated : p))
      this.notifySubscribers()

      // traceService.trace('ProfileService', 'profile updated', {
        // profileId,
        // updates: Object.keys(updates)
      // })
    } catch (error) {
      frontendLoggingService.error('ProfileService', `Failed to update profile ${profileId}`, error)
      const message = (error as ApiErrorResponse)?.response?.data?.detail || `Failed to update profile ${profileId}`
      throw new Error(message)
    }
  }

  /**
   * Soft-deleted profiles — the restore view's data (Phase D).
   * Recovery is DB-discoverable: each entry carries its archive
   * path.
   */
  async listDeleted(): Promise<Array<Record<string, unknown>>> {
    const resp = await apiClient.get(`${this.basePath}/deleted`)
    const data = (resp?.data ?? {}) as { deleted?: Array<Record<string, unknown>> }
    return data.deleted ?? []
  }

  /**
   * Restore a soft-deleted profile (Phase D) — ADDITIVE, explicit,
   * never automatic.
   */
  async restoreProfile(profileId: string): Promise<boolean> {
    const resp = await apiClient.post(`${this.basePath}/${profileId}/restore`)
    if (resp && resp.status >= 200 && resp.status < 300) {
      await this.loadFromBackend()
      return true
    }
    return false
  }

  /**
   * Delete a profile
   */
  async deleteProfile(profileId: string): Promise<Record<string, unknown> | null> {
    try {
      const profileIndex = this.profiles.findIndex(p => p.id === profileId)

      if (profileIndex === -1) {
        return null
      }

      // the recoverable delete (Phase C): the response is the
      // result report — what was removed + where the archive lives
      const resp = await apiClient.delete(`${this.basePath}/${profileId}`)

      // Remove from cache
      this.profiles = this.profiles.filter(p => p.id !== profileId)
      this.notifySubscribers()

      // the delete report (BOM + archive path) for the UI to show
      if (resp && resp.data) {
        return resp.data as Record<string, unknown>
      }
      return null

      // traceService.trace('ProfileService', 'profile deleted', {
        // profileId
      // })
    } catch (error) {
      frontendLoggingService.error('ProfileService', `Failed to delete profile ${profileId}`, error)
      const message = (error as ApiErrorResponse)?.response?.data?.detail || `Failed to delete profile ${profileId}`
      throw new Error(message)
    }
  }

  /**
   * Reset an agent's learned state (2026-08-19): the memory DB +
   * the chat sessions are cleared; the agent survives (identity,
   * skills, workspace stay). The deep agent restarts fresh.
   */
  async resetMemory(profileId: string): Promise<Record<string, unknown> | null> {
    try {
      const resp = await apiClient.post(`${this.basePath}/${profileId}/reset-memory`)
      return (resp?.data as Record<string, unknown>) ?? null
    } catch (error) {
      const message = (error as ApiErrorResponse)?.response?.data?.detail || `Failed to reset memory for profile ${profileId}`
      throw new Error(message)
    }
  }

  /**
   * Permanently delete a profile (2026-08-19) — the IRREVERSIBLE
   * scrub: the row + every reference + the workspace + memory all
   * go. NOTHING can restore it — the caller must confirm.
   */
  async hardDeleteProfile(profileId: string): Promise<Record<string, unknown> | null> {
    try {
      const resp = await apiClient.delete(`${this.basePath}/${profileId}`, {
        params: { hard: true },
      })
      // remove from the caches (active + deleted lists)
      this.profiles = this.profiles.filter(p => p.id !== profileId)
      this.notifySubscribers()
      return (resp?.data as Record<string, unknown>) ?? null
    } catch (error) {
      const message = (error as ApiErrorResponse)?.response?.data?.detail || `Failed to permanently delete profile ${profileId}`
      throw new Error(message)
    }
  }

  /**
   * Upload profile image
   */
  async uploadProfileImage(profileId: string, file: File): Promise<string> {
    try {
      // Validate file type
      const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp']
      if (!allowedTypes.includes(file.type)) {
        throw new Error('Only PNG, JPEG, and WebP files are supported')
      }

      frontendLoggingService.debug('ProfileService', 'Uploading image for profile', {
        profileId,
        fileName: file.name,
        fileType: file.type,
        fileSize: file.size
      })

      // Create FormData for file upload
      const formData = new FormData()
      formData.append('file', file)

      const response = await apiClient.upload<ImageUploadResponse>(
        `${this.basePath}/${profileId}/image`,
        formData
      )

      frontendLoggingService.info('ProfileService', 'Image uploaded successfully', {
        profileId,
        responseData: response.data
      })

      // Extract image URL from response
      const imageUrl = response.data?.profile_image_url || response.data?.image_url

      if (!imageUrl) {
        frontendLoggingService.error('ProfileService', 'No profile_image_url in response data', {
          responseData: response.data
        })
        throw new Error('No profile_image_url in response')
      }

      // Convert relative image URL to absolute URL
      if (imageUrl.startsWith('/')) {
        // relative only — see convertToProfile (the origin trick is the bug)
      }

      // Update cache
      this.profiles = this.profiles.map(p =>
        p.id === profileId ? { ...p, image_url: imageUrl } : p
      )
      this.notifySubscribers()

      frontendLoggingService.info('ProfileService', 'Image URL updated', {
        imageUrl
      })

      return imageUrl
    } catch (error) {
      frontendLoggingService.error('ProfileService', `Failed to upload image for profile ${profileId}`, error)
      const message = (error as ApiErrorResponse)?.response?.data?.detail || (error instanceof Error ? error.message : 'Failed to upload image')
      throw new Error(message)
    }
  }

  /**
   * Get list of available Ollama models
   */
  async getOllamaModels(): Promise<OllamaModel[]> {
    try {
      const response = await apiClient.get<OllamaModelsResponse>(`${this.providersPath}/ollama/models`)
      return response.data?.models || []
    } catch (error) {
      frontendLoggingService.error('ProfileService', 'Failed to fetch Ollama models', error)
      return []
    }
  }

  /**
   * Get list of available system prompt templates
   */
  async getTemplates(): Promise<SystemPromptTemplate[]> {
    try {
      const response = await apiClient.get<TemplatesListResponse>(`${this.basePath}/system-templates`)
      return response.data || []
    } catch (error) {
      frontendLoggingService.error('ProfileService', 'Failed to fetch templates', error)
      return []
    }
  }

  /**
   * Apply a template with variables
   */
  async applyTemplate(templateId: string, variables: Record<string, string>): Promise<string> {
    try {
      const response = await apiClient.post<ApplyTemplateResponse>(`${this.basePath}/system-templates/apply`, {
        template_id: templateId,
        variables
      })
      return response.data?.prompt || ''
    } catch (error) {
      frontendLoggingService.error('ProfileService', 'Failed to apply template', error)
      return ''
    }
  }

  /**
   * Duplicate an existing agent
   */
  async duplicateAgent(agentId: string): Promise<Profile> {
    try {
      const response = await apiClient.post<AgentDetailResponse>(`${this.basePath}/${agentId}/duplicate`, {})

      if (!response.data) {
        throw new Error('Failed to duplicate agent')
      }

      const newProfile = this.convertToProfile(response.data as unknown as Record<string, unknown>)
      this.profiles = [newProfile, ...this.profiles]
      this.notifySubscribers()

      return newProfile
    } catch (error) {
      frontendLoggingService.error('ProfileService', `Failed to duplicate agent ${agentId}`, error)
      const errorObj = error as { response?: { data?: { detail?: string } } } | undefined
      const message = errorObj?.response?.data?.detail ?? `Failed to duplicate agent ${agentId}`
      throw new Error(message)
    }
  }

  /**
   * Convert backend agent to frontend profile format
   */
  private convertToProfile(agent: Record<string, unknown>): Profile {
    // Extract parameters from backend (new format) or use defaults
    const params = agent.parameters as Record<string, unknown> || {}

    // THE IMAGE STAYS RELATIVE (/static/<name>.png). The browser resolves
    // it against whatever origin serves the page. Prefixing API_BASE_URL
    // here baked the DEV origin (http://localhost:5173) into the value,
    // which then round-tripped back into the DB on the next save — so the
    // avatar broke for anyone reaching the app by another host or port
    // (the initials fallback, "LO" for Lois).
    const imageUrl = agent.profile_image_url as string | undefined

    // Remember the served ceiling (G.1/D3): every wire agent carries it, and
    // the form's bound reads it from here rather than typing a second copy.
    // Done in the mapper because this is the ONE place every agent read passes
    // through — a create form (no agent yet) still gets the bound.
    const servedCeiling = agent.budget_ceiling as number | undefined
    if (typeof servedCeiling === 'number') this.budgetCeilingServed = servedCeiling

    return {
      id: String(agent.id),
      name: agent.name as string,
      description: (agent.description as string) || '',
      provider: agent.provider as string,
      model: agent.model as string,
      system_prompt: (agent.system_prompt as string) || '',
      // THE ROW'S OWN DECLARATION, OR NOTHING (G4): this mapper used to answer `?? 0.7`
      // and `?? 0.9`, so a row that declares nothing reached the form as a pair — and
      // pressing Save wrote it. An absent field stays absent here; the form's switch is
      // what shows it, in words.
      parameters: declaredSampling(params) ?? undefined,
      // THE DECLARATION (G-I): carried through so the form edits the field the
      // resolver reads. The mapper used to DROP llm_spec entirely — the page could
      // not see the contract that decides the budget.
      llm_spec: (agent.llm_spec as Profile['llm_spec']) ?? null,
      template_id: (agent.template_id as string) || undefined,
      tools: [],
      memory: false,
      fallback_enabled: (agent.fallback_enabled as boolean) ?? false,
      preferred_providers: (agent.preferred_providers as string[]) || [],
      health: agent.health as Profile['health'],
      // The current-availability read rides through untouched, like `health` (G5-F2): the wire
      // names it `service_availability` and the page reads it from the profile it holds.
      service_availability:
        (agent.service_availability as Profile['service_availability']) ?? null,
      // The declared-vs-sent read and the ceiling ride through untouched (G.1):
      // the wire names them `output_budget` / `budget_ceiling`, the page reads
      // them from the profile it already holds.
      output_budget: (agent.output_budget as Profile['output_budget']) ?? null,
      budget_ceiling: (agent.budget_ceiling as number) ?? null,
      image_url: imageUrl,
      cognitive_profile_id: (agent.cognitive_profile_id as number) ?? null,
      cognitive_profile_name: (agent.cognitive_profile_name as string | null) ?? null,
      cognitive_profile_depth: (agent.cognitive_profile_depth as Profile['cognitive_profile_depth']) ?? null,
      workspace_key: (agent.workspace_key as string) ?? null
    }
  }

  /**
   * Convert Profile to Agent format (for AgentService)
   */
  convertProfileToAgent(profile: Profile): Agent {
    // Map backend snake_case health to the frontend camelCase AgentHealth
    let health: Agent['health']
    if (profile.health) {
      health = {
        status: profile.health.status,
        consecutiveFailures: profile.health.consecutive_failures,
        lastError: profile.health.last_error,
        lastFailureAt: profile.health.last_failure_at,
        failures7d: profile.health.failures_7d
      }
    }

    return {
      id: profile.id,
      name: profile.name,
      description: profile.description,
      capabilities: [],
      provider: profile.provider,
      model: profile.model,
      parameters: {
        // NOTHING DECLARED CARRIES NOTHING (G4): these two used to answer `?? 0.7` /
        // `?? 0.9`, inventing a pair one layer along the read path. The only consumer of
        // this shape's sampling was a request `options` block that the transport drops, and
        // that block is gone — so an undeclared field stays undeclared here too.
        temperature: declaredSampling(profile.parameters)?.temperature,
        topP: declaredSampling(profile.parameters)?.top_p
      },
      isAvailable: true,
      profileImageUrl: profile.image_url,
      health,
      fallbackEnabled: profile.fallback_enabled ?? false,
      preferredProviders: profile.preferred_providers ?? []
    }
  }

  /**
   * Clear all profiles from cache
   */
  clearAll(): void {
    this.profiles = []
    this.notifySubscribers()

    // traceService.trace('ProfileService', 'clearAll', {}, ['state-change'])
  }

  /**
   * Start background sync with backend
   * Syncs every 60 seconds to keep cache fresh.
   *
   * 2026-09-06: public (the AgentProfiles page owns the lifecycle now)
   * + visibility-gated — the tick skips while the document is hidden,
   * so an idle backgrounded tab goes silent (the minute-ly
   * ProfileService + re-render log spam the user caught).
   */
  startBackgroundSync(): void {
    if (this.syncInterval) return
    this.syncInterval = setInterval(async () => {
      if (typeof document !== 'undefined' && document.hidden) {
        return // backgrounded tab: no sync, no chatter
      }
      // traceService.trace('ProfileService', 'background sync:started', {}, ['sync'])
      await this.loadFromBackend()
      // traceService.trace('ProfileService', 'background sync:completed', {}, ['sync'])
    }, 60000) // Sync every 60 seconds

    // traceService.trace('ProfileService', 'background sync:initialized', {
      // intervalMs: 60000
    // }, ['sync'])
  }

  /**
   * Stop background sync
   * Call this when unmounting to prevent memory leaks
   */
  stopBackgroundSync(): void {
    if (this.syncInterval) {
      clearInterval(this.syncInterval)
      this.syncInterval = null

      // traceService.trace('ProfileService', 'background sync:stopped', {}, ['sync'])
    }
  }

  /**
   * Cleanup - stop background sync and clear subscribers
   */
  destroy(): void {
    this.stopBackgroundSync()
    this.subscribers.clear()

    // traceService.trace('ProfileService', 'destroyed', {}, ['lifecycle'])
  }

  /**
   * Get service status
   */
  getStatus(): {
    profileCount: number
    subscriberCount: number
    isLoading: boolean
    lastSyncTime: Date | null
  } {
    return {
      profileCount: this.profiles.length,
      subscriberCount: this.subscribers.size,
      isLoading: this.isLoading,
      lastSyncTime: this.lastSyncTime
    }
  }

  /**
   * Save form state for a profile (application-level persistence)
   * Stores unsaved changes so they persist when switching between profiles
   */
  saveFormState(profileId: string | null, formData: ProfileCreate | ProfileUpdate | null): void {
    this.formState = {
      profileId,
      formData,
      hasUnsavedChanges: formData !== null
    }
    frontendLoggingService.debug('ProfileService', 'Form state saved', {
      profileId,
      hasUnsavedChanges: formData !== null
    })
  }

  /**
   * Get form state for the current profile
   * Returns the unsaved changes for the specified profile
   */
  getFormState(profileId: string | null): ProfileFormState {
    if (profileId === this.formState.profileId) {
      return this.formState
    }
    // Return empty state if switching to a different profile
    return {
      profileId: null,
      formData: null,
      hasUnsavedChanges: false
    }
  }

  /**
   * Clear form state after successful save
   */
  clearFormState(): void {
    this.formState = {
      profileId: null,
      formData: null,
      hasUnsavedChanges: false
    }
    frontendLoggingService.debug('ProfileService', 'Form state cleared')
  }

  /**
   * Check if there are unsaved changes
   */
  hasUnsavedChanges(): boolean {
    return this.formState.hasUnsavedChanges
  }
}

// Export singleton instance
export const profileService = new ProfileService()
