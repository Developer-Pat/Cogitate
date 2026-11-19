import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePageTitle } from '../hooks/usePageTitle'
import { apiClient } from '../services/apiClient'
import { claimDeclaredPrimaryInput } from '../services/focusContract'
import { useNotificationStore } from '../stores/notificationStore'
import { frontendLoggingService } from '../services/frontendLoggingService'
import { HelpButton } from '../components/help';
import { ClipboardList } from 'lucide-react';

interface Template {
  id: number
  name: string
  description: string
  provider: string
  model: string
  system_prompt: string
  parameters: Record<string, unknown> | null
  cognitive_profile_id: number | null
  execution_mode: string | null
  behavior_config: Record<string, unknown> | null
  preferred_providers: string[] | null
  fallback_enabled: boolean | null
  allow_delegation: boolean | null
  is_public: boolean
  created_by: string | null
  tags: string[] | null
  usage_count: number
  created_at: string
  updated_at: string
}

export default function AgentTemplates() {
  usePageTitle('Agent Templates', 'Browse and use agent templates')
  
  const navigate = useNavigate()
  const addNotification = useNotificationStore((state) => state.addNotification)

  const [templates, setTemplates] = useState<Template[]>([])
  const [newTemplateMode, setNewTemplateMode] = useState<string>('hybrid')
  const [newTemplateProfileId, setNewTemplateProfileId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'public' | 'mine'>('all')
  const [search, setSearch] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showUseModal, setShowUseModal] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null)
  const [agentName, setAgentName] = useState('')
  const [agentDescription, setAgentDescription] = useState('')

  // Create template form state
  const [newTemplateName, setNewTemplateName] = useState('')
  const [newTemplateDescription, setNewTemplateDescription] = useState('')
  const [newTemplateProvider, setNewTemplateProvider] = useState('deepseek')
  const [newTemplateModel, setNewTemplateModel] = useState('deepseek-v4-flash')
  const [newTemplatePrompt, setNewTemplatePrompt] = useState('')
  const [newTemplateTags, setNewTemplateTags] = useState('')
  const [newTemplatePublic, setNewTemplatePublic] = useState(false)

  // Load templates
  /**
   * THE PAGE'S OWN HALF OF THE FOCUS CONTRACT (2026-09-19) — see
   * services/focusContract: the declaration is a YIELD, so somebody has to act on
   * it, and on a cold load (a lazy route) that somebody is this page.
   */
  useEffect(() => {
    claimDeclaredPrimaryInput();
  }, []);

  useEffect(() => {
    loadTemplates()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter, search])

  const loadTemplates = async () => {
    setLoading(true)
    try {
      let url = '/api/v1/agents/templates?'
      
      if (filter === 'public') {
        url += 'public=true&'
      }
      
      if (search) {
        url += `search=${encodeURIComponent(search)}&`
      }

      const response = await apiClient.get<{ templates: Template[] }>(url)
      setTemplates(response.data?.templates || [])
    } catch (error) {
      frontendLoggingService.error('AgentTemplates', 'Failed to load templates', error as Error)
      addNotification({
        type: 'error',
        title: 'Error',
        message: 'Failed to load templates'
      })
    } finally {
      setLoading(false)
    }
  }

  const handleUseTemplate = (template: Template) => {
    setSelectedTemplate(template)
    setAgentName(`${template.name} Agent`)
    setAgentDescription('')
    setShowUseModal(true)
  }

  const handleConfirmUseTemplate = async () => {
    if (!selectedTemplate || !agentName.trim()) return

    try {
      await apiClient.post(`/api/v1/agents/templates/${selectedTemplate.id}/apply`, {
        name: agentName.trim(),
        description: agentDescription.trim() || null
      })

      addNotification({
        type: 'success',
        title: 'Agent Created',
        message: `"${agentName}" has been created from template`
      })

      setShowUseModal(false)
      navigate('/agent-profiles')
    } catch (error: unknown) {
      frontendLoggingService.error('AgentTemplates', 'Failed to create agent from template', error as Error)
      addNotification({
        type: 'error',
        title: 'Error',
        message: (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to create agent from template'
      })
    }
  }

  const handleCreateTemplate = async () => {
    if (!newTemplateName.trim() || !newTemplatePrompt.trim()) return

    try {
      const tagsArray = newTemplateTags
        .split(',')
        .map(t => t.trim())
        .filter(t => t.length > 0)

      await apiClient.post('/api/v1/agents/templates', {
        name: newTemplateName.trim(),
        description: newTemplateDescription.trim() || null,
        provider: newTemplateProvider,
        model: newTemplateModel,
        system_prompt: newTemplatePrompt,
        // NO SAMPLING IS DECLARED (the agent-init arc, G2): this form has no sampling
        // control, so the pair it used to post was invented here and then copied onto
        // every agent made from the template. A template declares none, and the agent's
        // own page is where sampling is decided.
        is_public: newTemplatePublic,
        tags: tagsArray.length > 0 ? tagsArray : null,
        cognitive_profile_id: newTemplateProfileId,
        execution_mode: newTemplateMode,
        fallback_enabled: true,
        allow_delegation: false
      })

      addNotification({
        type: 'success',
        title: 'Template Created',
        message: `"${newTemplateName}" has been created`
      })

      setShowCreateModal(false)
      resetCreateForm()
      loadTemplates()
    } catch (error: unknown) {
      frontendLoggingService.error('AgentTemplates', 'Failed to create template', error as Error)
      addNotification({
        type: 'error',
        title: 'Error',
        message: (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to create template'
      })
    }
  }

  const resetCreateForm = () => {
    setNewTemplateName('')
    setNewTemplateDescription('')
    setNewTemplateProvider('ollama')
    setNewTemplateModel('llama3.2')
    setNewTemplatePrompt('')
    setNewTemplateTags('')
    setNewTemplatePublic(false)
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  }

  return (
    <div className="min-h-screen bg-base-100">
      {/* Header */}
      <div className="bg-base-200 border-b border-base-300">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-4">
            <div>
              <button
                onClick={() => navigate('/agent-profiles')}
                className="btn btn-neutral btn-ghost btn-sm mb-2"
              >
                Back to Agents
              </button>
              <h1 className="text-3xl font-bold">Agent Templates</h1>
              <p className="text-readout mt-1">
                Browse and use pre-configured agent templates
              </p>
            </div>

            <button
              className="btn btn-primary whitespace-nowrap"
              onClick={() => setShowCreateModal(true)}
            >
              Create Template
            </button>
          </div>

          {/* Filters and Search */}
          <div className="flex flex-wrap items-center gap-4">
            {/* Filter Tabs */}
            <div className="join">
              <button
                className={`join-item btn btn-sm ${filter === 'all' ? 'btn-active btn-selected' : 'btn-outline'}`}
                onClick={() => setFilter('all')}
              >
                All
              </button>
              <button
                className={`join-item btn btn-sm ${filter === 'public' ? 'btn-active btn-selected' : 'btn-outline'}`}
                onClick={() => setFilter('public')}
              >
                Public
              </button>
              <button
                className={`join-item btn btn-sm ${filter === 'mine' ? 'btn-active btn-selected' : 'btn-outline'}`}
                onClick={() => setFilter('mine')}
              >
                Mine
              </button>
            </div>

            {/* Search */}
            <div className="form-control flex-1 min-w-64">
              <div className="relative">
                <input
                  data-autofocus
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search templates..."
                  aria-label="Search templates"
                  className="input input-bordered w-full pl-10 rounded-[var(--form-input-radius)] bg-[var(--form-input-bg)] border-[var(--form-input-border)] text-[var(--form-input-text)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                />
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 absolute left-3 top-1/2 -translate-y-1/2 text-readout" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
                     <HelpButton context="agents" tooltipPosition="bottom" />
        </div>
          </div>
        </div>
      </div>

      {/* Template Grid */}
      <div className="container mx-auto px-4 py-8">
        {loading ? (
          <div className="flex justify-center py-12">
            <span className="loading loading-spinner loading-lg"></span>
          </div>
        ) : templates.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-readout mb-4 flex justify-center">
              <ClipboardList className="h-16 w-16" />
            </div>
            <h2 className="text-2xl font-bold mb-2">
              {search ? 'No templates found' : 'No templates available'}
            </h2>
            <p className="text-readout mb-4">
              {search 
                ? 'Try adjusting your search or filters'
                : 'Create your first template to get started'}
            </p>
            {!search && (
              <button
                className="btn btn-primary rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                onClick={() => setShowCreateModal(true)}
              >
                Create Template
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {templates.map((template) => (
              <div
                key={template.id}
                className="card bg-base-100 shadow-lg shadow-[var(--card-shadow)] rounded-[var(--card-radius)] p-[var(--card-padding)] hover:shadow-xl transition-all border border-base-300"
              >
                <div className="card-body gap-[var(--card-gap)]">
                  {/* Header */}
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <h3 className="card-title text-lg">{template.name}</h3>
                    {template.is_public && (
                      <span className="tooltip tooltip-top" data-tip="Public template — visible to all users">
                        <span className="badge badge-sm badge-outline">Public</span>
                      </span>
                    )}
                  </div>

                  {/* Description */}
                  <p className="text-sm text-readout mb-3 line-clamp-2">
                    {template.description}
                  </p>

                  {/* Provider & Model badges */}
                  <div className="flex flex-wrap gap-2 mb-3">
                    <span className="badge badge-sm badge-outline">
                      {template.provider}
                    </span>
                    <span className="badge badge-sm badge-ghost">
                      {template.model}
                    </span>
                    {template.execution_mode && (
                      <span className="badge badge-sm badge-outline">
                        {template.execution_mode}
                      </span>
                    )}
                    {template.cognitive_profile_id != null && (
                      <span className="badge badge-sm badge-outline">
                        profile #{template.cognitive_profile_id}
                      </span>
                    )}
                  </div>

                  {/* Tags */}
                  {template.tags && template.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-3">
                      {template.tags.slice(0, 5).map((tag, idx) => (
                        <span key={idx} className="badge badge-outline badge-xs">
                          {tag}
                        </span>
                      ))}
                      {template.tags.length > 5 && (
                        <span className="badge badge-outline badge-xs">
                          +{template.tags.length - 5}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Usage stats */}
                  <div className="text-xs text-readout mb-4">
                    <span>Used {template.usage_count} time{template.usage_count !== 1 ? 's' : ''}</span>
                    <span className="ml-3">{formatDate(template.created_at)}</span>
                  </div>

                  {/* Actions */}
                  <div className="card-actions justify-end mt-2">
                    <button
                      className="btn btn-primary btn-outline btn-sm w-full"
                      onClick={() => handleUseTemplate(template)}
                    >
                      Use Template
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Use Template Modal */}
      {showUseModal && selectedTemplate && (
        <div className="modal modal-open">
          <div className="modal-box max-w-md bg-base-100 text-base-content">
            <div className="flex items-center justify-between mb-4 bg-info text-base-content p-4 rounded-t-lg -mx-6 -mt-6 pt-6">
              <h3 className="font-bold text-lg text-base-content">Use Template</h3>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => setShowUseModal(false)}
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            <div className="alert alert-info mb-4 bg-info text-base-content">
              <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-5 w-5" fill="none" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-base-content">
                This will create a new agent using the "{selectedTemplate.name}" configuration
              </span>
            </div>

            <div className="form-control mb-4">
              <label className="label">
                <span className="label-text font-semibold text-base-content">Agent Name *</span>
              </label>
              <input
                type="text"
                value={agentName}
                onChange={(e) => setAgentName(e.target.value)}
                className="input input-bordered w-full bg-base-200 text-base-content rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                placeholder="e.g., My Support Agent"
                autoFocus
              />
            </div>

            <div className="form-control mb-6">
              <label className="label">
                <span className="label-text font-semibold text-base-content">Description (optional)</span>
              </label>
              <textarea
                value={agentDescription}
                onChange={(e) => setAgentDescription(e.target.value)}
                className="textarea textarea-bordered w-full bg-base-200 text-base-content rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                placeholder="Optional description..."
                rows={2}
              />
            </div>

            <div className="divider mb-4"></div>

            <div className="text-sm text-readout mb-4">
              <div className="font-semibold mb-2">Template Configuration:</div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-xs">Provider:</span>
                  <div className="font-medium">{selectedTemplate.provider}</div>
                </div>
                <div>
                  <span className="text-xs">Model:</span>
                  <div className="font-medium">{selectedTemplate.model}</div>
                </div>
                <div>
                  <span className="text-xs">Execution Mode:</span>
                  <div className="font-medium">{selectedTemplate.execution_mode || 'default'}</div>
                </div>
                <div>
                  <span className="text-xs">Cognitive Profile:</span>
                  <div className="font-medium">{selectedTemplate.cognitive_profile_id != null ? `#${selectedTemplate.cognitive_profile_id}` : 'default'}</div>
                </div>
              </div>
            </div>

            <div className="modal-action">
              <button
                className="btn btn-neutral btn-ghost"
                onClick={() => setShowUseModal(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                onClick={handleConfirmUseTemplate}
                disabled={!agentName.trim()}
              >
                Create Agent
              </button>
            </div>
          </div>
          <div className="modal-backdrop"></div>
        </div>
      )}

      {/* Create Template Modal */}
      {showCreateModal && (
        <div className="modal modal-open">
          <div className="modal-box max-w-2xl bg-base-100 text-base-content">
            <div className="flex items-center justify-between mb-4 bg-info text-base-content p-4 rounded-t-lg -mx-6 -mt-6 pt-6">
              <h3 className="font-bold text-lg text-base-content">Create New Template</h3>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  setShowCreateModal(false)
                  resetCreateForm()
                }}
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            <div className="alert alert-info mb-4 bg-info text-base-content">
              <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-5 w-5" fill="none" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-base-content">
                Create a reusable template that others can use to quickly create agents
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="form-control">
                <label className="label">
                  <span className="label-text font-semibold text-base-content">Template Name *</span>
                </label>
                <input
                  type="text"
                  value={newTemplateName}
                  onChange={(e) => setNewTemplateName(e.target.value)}
                  className="input input-bordered w-full bg-base-200 text-base-content rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                  placeholder="e.g., Customer Support Bot"
                  autoFocus
                />
              </div>

              <div className="form-control">
                <label className="label">
                  <span className="label-text font-semibold text-base-content">Provider *</span>
                </label>
                <select
                  value={newTemplateProvider}
                  onChange={(e) => setNewTemplateProvider(e.target.value)}
                  className="select select-bordered w-full bg-base-200 text-base-content rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                >
                  <option value="deepseek">DeepSeek</option>
                  <option value="openrouter">OpenRouter</option>
                  <option value="ollama">Ollama</option>
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                </select>
              </div>
            </div>

            <div className="form-control mb-4">
              <label className="label">
                <span className="label-text font-semibold text-base-content">Description</span>
              </label>
              <input
                type="text"
                value={newTemplateDescription}
                onChange={(e) => setNewTemplateDescription(e.target.value)}
                className="input input-bordered w-full bg-base-200 text-base-content rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                placeholder="Brief description of what this template does"
              />
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="form-control">
                <label className="label">
                  <span className="label-text font-semibold text-base-content">Model *</span>
                </label>
                <input
                  type="text"
                  value={newTemplateModel}
                  onChange={(e) => setNewTemplateModel(e.target.value)}
                  className="input input-bordered w-full bg-base-200 text-base-content rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                  placeholder="e.g., llama3.2"
                />
              </div>

              <div className="form-control">
                <label className="label">
                  <span className="label-text font-semibold text-base-content">Tags (comma-separated)</span>
                </label>
                <input
                  type="text"
                  value={newTemplateTags}
                  onChange={(e) => setNewTemplateTags(e.target.value)}
                  className="input input-bordered w-full bg-base-200 text-base-content rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                  placeholder="e.g., support, helpful, customer-service"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="form-control">
                <label className="label">
                  <span className="label-text font-semibold text-base-content">Execution Mode</span>
                </label>
                <select
                  value={newTemplateMode}
                  onChange={(e) => setNewTemplateMode(e.target.value)}
                  className="select select-bordered w-full bg-base-200 text-base-content rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                >
                  <option value="hybrid">Hybrid</option>
                  <option value="shallow">Shallow</option>
                </select>
              </div>

              <div className="form-control">
                <label className="label">
                  <span className="label-text font-semibold text-base-content">Cognitive Profile</span>
                </label>
                <select
                  value={newTemplateProfileId ?? ''}
                  onChange={(e) => setNewTemplateProfileId(e.target.value === '' ? null : Number(e.target.value))}
                  className="select select-bordered w-full bg-base-200 text-base-content rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                >
                  <option value="">Default</option>
                  <option value="1">Conversational</option>
                  <option value="2">Quick Response</option>
                  <option value="3">Research Standard</option>
                  <option value="4">Balanced Chat</option>
                  <option value="5">Code Gen</option>
                  <option value="6">Research Pro</option>
                  <option value="7">System Admin</option>
                </select>
              </div>
            </div>

            <div className="form-control mb-4">
              <label className="label">
                <span className="label-text font-semibold text-base-content">System Prompt *</span>
              </label>
              <textarea
                value={newTemplatePrompt}
                onChange={(e) => setNewTemplatePrompt(e.target.value)}
                className="textarea textarea-bordered w-full bg-base-200 text-base-content rounded-[var(--form-input-radius)] px-[var(--form-input-padding)] focus:border-[var(--form-input-focus-border)] transition-all duration-[var(--button-transition)]"
                placeholder="You are a helpful AI assistant..."
                rows={5}
              />
              <label className="label">
                <span className="label-text-alt text-readout">This defines the agent's behavior and personality</span>
              </label>
            </div>

            <div className="form-control mb-6">
              <label className="label cursor-pointer justify-start gap-4">
                <input
                  type="checkbox"
                  checked={newTemplatePublic}
                  onChange={(e) => setNewTemplatePublic(e.target.checked)}
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
                className="btn btn-neutral btn-ghost"
                onClick={() => {
                  setShowCreateModal(false)
                  resetCreateForm()
                }}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary rounded-[var(--button-radius)] px-[var(--button-padding)] transition-all duration-[var(--button-transition)]"
                onClick={handleCreateTemplate}
                disabled={!newTemplateName.trim() || !newTemplatePrompt.trim()}
              >
                Create Template
              </button>
            </div>
          </div>
          <div className="modal-backdrop"></div>
        </div>
      )}
    </div>
  )
}
