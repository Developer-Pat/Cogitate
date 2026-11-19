/**
 * Session Sync Service
 *
 * Purpose: Pure API client for session operations
 *
 * Responsibilities:
 * - HTTP requests to backend for sessions
 * - HTTP requests to backend for messages
 * - Data format conversion (backend ↔ frontend)
 *
 * NOT responsible for:
 * - State management (use SessionsService)
 * - Caching (use SessionsService)
 * - Context tracking (use CurrentSessionService)
 */

import { apiClient } from './apiClient'
import { frontendLoggingService } from './frontendLoggingService'
import type { ConversationSession, ConversationMessage } from '../types/agentInteraction'
import { IdService } from './domain/IdService'

/** THE SESSION SOURCES (2026-09-04, the exa-leak dig + the rename-
    safety call): the ONE place the surface strings live. Filtering
    keys on this constant, never a bare literal — a display rename
    of the Exa character does NOT touch these internal categories
    (the category is stable even if the label changes). */
export const SessionSource = {
  AGENT: 'agent',
  EXA: 'exa',
} as const
export type SessionSourceValue = (typeof SessionSource)[keyof typeof SessionSource]

interface SessionSyncMessage {
  id: string
  role: string
  content: string
  created_at: string
  // Backend returns these properties directly on the message object
  token_count?: number
  total_time_ms?: number
  tokens_per_second?: number
  model?: string
  provider?: string
  // Also support nested metadata format for compatibility
  metadata?: {
    tokenCount?: number
    totalTimeMs?: number
    tokensPerSecond?: number
    model?: string
    provider?: string
    limits?: LimitCrossing[]
    limit_notice?: string
    truncated?: boolean
  }
}

/**
 * THE LIMIT NOTE AND THE FLAGS (2026-09-23).
 *
 * What a turn CROSSED (`limits` — one record per crossing, `limit_notice` — the
 * sentence the bubble shows) and whether the provider CUT the answer
 * (`truncated`). The saved row carries all three, so the note survives a reload —
 * that is the whole point of the note: the toast is the moment, the note is the
 * record. Both response shapes (nested `metadata`, and the older direct fields)
 * are read, because the list path and the detail path disagree about the shape.
 */
export interface LimitCrossing {
  key: string
  value?: number | null
  threshold: number
  mode?: string
  reason: string
}

export interface CarriedLimitExtras {
  limits?: LimitCrossing[]
  limit_notice?: string
  truncated?: boolean
}

export function carriedLimitExtras(source: Record<string, unknown>): CarriedLimitExtras {
  const limits = (source.limits ?? undefined) as LimitCrossing[] | undefined
  const notice = (source.limit_notice ?? source.limitNotice) as string | undefined
  const truncated = (source.truncated ?? undefined) as boolean | undefined
  return {
    ...(limits && limits.length ? { limits } : {}),
    ...(notice ? { limit_notice: notice } : {}),
    ...(truncated ? { truncated } : {}),
  }
}


export interface SessionSyncResponse {
  id: string
  title: string
  model: string
  agent_id: string
  source?: string
  memory: boolean
  tools: string[]
  messages?: SessionSyncMessage[]
  created?: number
  updated?: number
  created_at?: string  // For compatibility with backend format
  updated_at?: string  // For compatibility with backend format
  // THE MESSAGE COUNT (2026-09-15): passed straight through from the API. The
  // list is titles-only, so `messages` is always [] here and counting it is
  // meaningless — this is the only honest count available to the UI.
  message_count?: number
}

export interface BackendSession {
  id: number
  title: string | null
  agent_id: number
  source?: string
  is_active: boolean
  created_at: string
  updated_at: string
  messages?: Array<{
    id: number
    role: string
    content: string
    created_at: string
    token_count?: number
    total_time_ms?: number
    tokens_per_second?: number
    model?: string
    provider?: string
    // THE DETAIL SHAPE (2026-09-23): the session-detail endpoint returns the
    // metrics NESTED under `metadata` (the list path returns them directly), and
    // the note + the flags ride the same object. Typed here so the carrier in
    // `carriedLimitExtras` is not reading a shape the type denies.
    metadata?: {
      token_count?: number
      total_time_ms?: number
      tokens_per_second?: number
      model?: string
      provider?: string
      reasoning?: string
      limits?: LimitCrossing[]
      limit_notice?: string
      truncated?: boolean
    }
  }>
  // THE MESSAGE COUNT (2026-09-15): the API sends the real count on the
  // titles-only list path, because `messages` is empty there and cannot be
  // counted. It was missing from this interface, so the field was silently
  // dropped in transit and the UI fell back to a stale cached count.
  message_count?: number
}

class SessionSyncService {
  private readonly basePath = '/api/v1/sessions'

  /**
   * Convert backend session to frontend format
   */
  private convertToSessionResponse(backend: BackendSession, model?: string): SessionSyncResponse {
    // FIX: Use the actual title, not a fallback
    // The title should already be unique (e.g., "New Session {timestamp}")
    const sessionTitle = backend.title || `New Session ${Date.now()}`
    
    // FIX: Log warning when model is missing instead of silent fallback
    const sessionModel = model || 'llama3.2'
    if (!model) {
      frontendLoggingService.warning('SessionSyncService', 'Session model missing, using fallback', {
        sessionId: backend.id,
        fallbackModel: sessionModel,
        agentId: backend.agent_id
      })
    }

    return {
      id: IdService.toFrontend(backend.id),
      title: sessionTitle,
      model: sessionModel,
      agent_id: IdService.toFrontend(backend.agent_id),
      // THE SOURCE (2026-09-04, the leak dig): the THIRD converter to
      // drop it — this one feeds getSessions, so the Exa panel's rows
      // never carried the tag and the source-guard filtered them out.
      source: backend.source,
      memory: backend.is_active,
      tools: [],
      // Pass the API's count through untouched (2026-09-15). `messages` below is
      // empty on the fast path, so it cannot be counted — see the type's note.
      message_count: backend.message_count,
      messages: (backend.messages || []).map(msg => {
        // Backend returns metadata fields directly on msg object (not nested)
        // Fields: token_count, total_time_ms, tokens_per_second, model, provider
        // THE NOTE AND THE FLAGS (2026-09-23): `limits`/`limit_notice` (what the
        // turn crossed) and `truncated` (the provider's cut). The session-detail
        // endpoint returns the row's meta NESTED under `metadata`; the list path
        // used to return the metrics directly. Both are read, because a note that
        // vanishes on reload is not a record. `hasMetadata` counts them too, or a
        // turn whose only metadata IS the note would lose it.
        const nested = (msg as unknown as { metadata?: Record<string, unknown> }).metadata
        const extras = carriedLimitExtras({ ...(nested || {}), ...(msg as unknown as Record<string, unknown>) })
        const hasMetadata = Boolean(
          msg.token_count || msg.total_time_ms || msg.model || msg.provider
          || Object.keys(extras).length > 0
        )

        return {
          id: IdService.toFrontend(msg.id),
          role: msg.role as 'user' | 'assistant' | 'system',
          content: msg.content,
          created_at: msg.created_at,
          metadata: hasMetadata ? {
            tokenCount: msg.token_count,
            totalTimeMs: msg.total_time_ms,
            tokensPerSecond: msg.tokens_per_second,
            model: msg.model,
            provider: msg.provider,
            ...extras
          } : undefined
        }
      }),
      created: new Date(backend.created_at).getTime(),
      updated: new Date(backend.updated_at).getTime(),
      // Also include created_at/updated_at for compatibility
      created_at: backend.created_at,
      updated_at: backend.updated_at
    }
  }

  /**
   * Create a new session on the backend
   */
  async createSession(
    _sessionId: string,
    title: string,
    _agentId: string,
    _model: string
  ): Promise<SessionSyncResponse> {
    try {
      // FIX: Use the actual title, not a fallback
      // The title should already be unique (e.g., "New Session {timestamp}")
      const sessionTitle = title || `New Session ${Date.now()}`
      
      // THE EXA SESSION (2026-08-21): the virtual participant's id
      // 'exa' has no backend agent row — the session records with
      // agent_id=null + source='exa' (the external surface).
      const isExa = _agentId === 'exa'
      const response = await apiClient.post<BackendSession>(
        this.basePath,
        {
          agent_id: isExa ? null : IdService.toBackend(_agentId),
          title: sessionTitle,
          source: isExa ? SessionSource.EXA : SessionSource.AGENT
        }
      )
      if (!response.data) {
        throw new Error('No response data from server')
      }
      frontendLoggingService.debug('SessionSyncService', 'Session created on backend', { sessionId: response.data.id })
      return this.convertToSessionResponse(response.data, _model)
    } catch (error) {
      frontendLoggingService.error('SessionSyncService', 'Failed to create session', error)
      throw error
    }
  }

  /**
   * Get a session from the backend
   */
  async getSession(sessionId: string): Promise<SessionSyncResponse> {
    try {
      const response = await apiClient.get<BackendSession>(
        `${this.basePath}/${sessionId}`
      )
      if (!response.data) {
        throw new Error('No response data from server')
      }
      return this.convertToSessionResponse(response.data)
    } catch (error) {
      frontendLoggingService.error('SessionSyncService', 'Failed to get session', error)
      throw error
    }
  }

  /**
   * Get all sessions for an agent (titles only, without messages for performance)
   * Uses lazy loading - messages are loaded on demand when session is selected
   */
  async getSessions(source?: SessionSourceValue): Promise<SessionSyncResponse[]> {
    try {
      // Load titles only (lazy loading) - much faster!
      // THE SOURCE FILTER (2026-09-04, the exa-leak dig): the agent
      // chat was listing EVERY session including Exa's (source='exa').
      // The backend now filters by source; the agent page passes
      // 'agent', the Exa page 'exa' (or omits = all, for the tools).
      const qs = source
        ? `?include_messages=false&source=${encodeURIComponent(source)}`
        : '?include_messages=false'
      const response = await apiClient.get<{ sessions: BackendSession[] }>(
        `${this.basePath}${qs}`
      )
      const sessions = response.data?.sessions || []
      return sessions.map((s: BackendSession) => this.convertToSessionResponse(s))
    } catch (error) {
      frontendLoggingService.error('SessionSyncService', 'Failed to get sessions', error)
      return []
    }
  }

  /**
   * Reload all sessions with their full message history from the database
   * 
   * Note: This is for initial load only. For cached sessions, use SessionsService.
   * This method fetches directly from the backend and should not be called frequently.
   */
  async reloadSessionsWithMessages(source?: SessionSourceValue): Promise<SessionSyncResponse[]> {
    try {
      frontendLoggingService.debug('SessionSyncService', 'Reloading all sessions with messages from database...')

      // First get the session list without messages (source-scoped
      // since 2026-09-04 — the reload must respect the same surface
      // filter the list does)
      const sessions = await this.getSessions(source)

      // Load all sessions in parallel with concurrency limit to prevent overwhelming the backend
      const CONCURRENCY_LIMIT = 5
      const sessionsWithMessages: SessionSyncResponse[] = []

      // Process sessions in batches to balance parallelism with backend load
      for (let i = 0; i < sessions.length; i += CONCURRENCY_LIMIT) {
        const batch = sessions.slice(i, i + CONCURRENCY_LIMIT)
        frontendLoggingService.debug('SessionSyncService', `Loading batch ${Math.floor(i / CONCURRENCY_LIMIT) + 1}, sessions ${i + 1}-${Math.min(i + CONCURRENCY_LIMIT, sessions.length)}`)

        const batchResults = await Promise.all(
          batch.map(async (session) => {
            try {
              const fullSession = await this.getSession(session.id)
              frontendLoggingService.debug('SessionSyncService', 'Loaded session', { sessionId: session.id, messageCount: fullSession.messages?.length || 0 })
              return fullSession
            } catch (sessionError) {
              frontendLoggingService.warning('SessionSyncService', `Failed to load session ${session.id}`, { error: sessionError })
              // Return session without messages rather than failing entirely
              return session
            }
          })
        )

        sessionsWithMessages.push(...batchResults)
      }

      frontendLoggingService.debug('SessionSyncService', 'Successfully reloaded sessions with messages', { count: sessionsWithMessages.length })
      return sessionsWithMessages
    } catch (error) {
      frontendLoggingService.error('SessionSyncService', 'Failed to reload sessions with messages', { error })
      throw error
    }
  }

  /**
   * Add a message to a session
   * Note: Backend doesn't support adding individual messages yet
   * Messages are added automatically when chatting
   */
  async addMessage(
    _sessionId: string,
    _role: 'user' | 'assistant',
    _content: string,
    _messageId?: string
  ): Promise<void> {
    frontendLoggingService.debug('SessionSyncService', 'addMessage called but backend auto-saves messages during chat')
    // Backend automatically saves messages when chat endpoint is called
    // This is a no-op for now
  }

  /**
   * Delete a session
   */
  async deleteSession(sessionId: string): Promise<void> {
    try {
      await apiClient.delete(`${this.basePath}/${sessionId}`)
    } catch (error) {
      frontendLoggingService.error('SessionSyncService', 'Failed to delete session', error)
      throw error
    }
  }

  /**
   * Delete a specific message from a session
   * Note: Backend doesn't support individual message deletion yet
   */
  async deleteMessage(sessionId: string, messageId: string): Promise<void> {
    frontendLoggingService.warning('SessionSyncService', `deleteMessage not implemented on backend`, { sessionId, messageId })
    // No-op for now - backend doesn't support this
  }

  /**
   * Convert backend session response to frontend format
   */
  convertToFrontendSession(backendSession: SessionSyncResponse): ConversationSession {
    return {
      id: backendSession.id,
      title: backendSession.title,
      agentId: backendSession.agent_id,
      // THE SOURCE (2026-09-04, the leak dig): was dropped here too —
      // the agent page's hub cache could hold exa rows without a tag.
      source: backendSession.source,
      messages: (backendSession.messages || []).map((msg) => {
        // Handle both backend format (fields directly on msg) and frontend format (nested in metadata)
        const msgRecord = msg as unknown as Record<string, unknown>
        const nestedMetadata = msgRecord.metadata as Record<string, unknown> | undefined
        const metadata = nestedMetadata || msgRecord

        const tokenCount = (metadata.token_count ?? metadata.tokenCount) as number | undefined
        const totalTimeMs = (metadata.total_time_ms ?? metadata.totalTimeMs) as number | undefined
        const tokensPerSecond = (metadata.tokens_per_second ?? metadata.tokensPerSecond) as number | undefined
        const model = (metadata.model as string) || msg.model || undefined
        const provider = (metadata.provider as string) || msg.provider || undefined
        // THE THINKING FOLD (2026-08-24): the reasoning rides the
        // message metadata — the fold survives the reload.
        const reasoning = (nestedMetadata?.reasoning as string) || undefined
        // THE NOTE AND THE FLAGS (2026-09-23): the same three keys the fast path
        // above carries — nested here, direct there. See `carriedLimitExtras`.
        const extras = carriedLimitExtras({ ...(nestedMetadata || {}), ...msgRecord })

        return {
          id: msg.id,
          role: msg.role as 'user' | 'assistant' | 'system',
          content: msg.content,
          timestamp: this.parseTimestamp(msg.created_at),
          agentId: backendSession.agent_id,
          // Include metadata if available (for assistant messages)
          // FIX: Support both nested metadata and direct fields on message
          metadata: (tokenCount || totalTimeMs || model || provider || reasoning
            || Object.keys(extras).length) ? {
            tokenCount,
            totalTimeMs,
            tokensPerSecond,
            model,
            provider,
            ...(reasoning ? { reasoning } : {}),
            ...extras,
          } : undefined
        }
      }),
      // Handle both timestamp formats: created/updated (numbers) or created_at/updated_at (strings)
      createdAt: backendSession.created
        ? new Date(backendSession.created)
        : backendSession.created_at
          ? new Date(backendSession.created_at)
          : new Date(),
      updatedAt: backendSession.updated
        ? new Date(backendSession.updated)
        : backendSession.updated_at
          ? new Date(backendSession.updated_at)
          : new Date(),
      isActive: true
    }
  }

  /**
   * Parse timestamp from backend
   */
  private parseTimestamp(timestamp: number | string): Date {
    if (typeof timestamp === 'string') {
      return new Date(timestamp)
    } else if (typeof timestamp === 'number') {
      return new Date(timestamp)
    } else {
      frontendLoggingService.warning('SessionSyncService', 'Unknown timestamp format', { timestamp })
      return new Date()
    }
  }

  /**
   * Sync a message to the backend after it's been added locally
   */
  async syncMessage(
    _sessionId: string,
    message: ConversationMessage
  ): Promise<void> {
    frontendLoggingService.debug('SessionSyncService', 'syncMessage called but backend auto-saves', { messageId: message.id })
    // Backend automatically saves messages when chat endpoint is called
  }

  /**
   * Sync all messages in a session to the backend
   */
  async syncAllMessages(
    _sessionId: string,
    _messages: ConversationMessage[]
  ): Promise<void> {
    // No-op - backend auto-saves
  }

  /**
   * Update session title on the backend
   */
  async updateSessionTitle(
    sessionId: string,
    newTitle: string
  ): Promise<void> {
    try {
      // Convert frontend string ID to backend integer ID
      const backendSessionId = IdService.toBackend(sessionId)
      
      frontendLoggingService.info('SessionSyncService', `Updating session title for ${sessionId}`, { 
        newTitle,
        backendSessionId 
      })

      const response = await apiClient.put(
        `${this.basePath}/${backendSessionId}`,
        {
          title: newTitle
        }
      )

      frontendLoggingService.info('SessionSyncService', 'API response received', {
        sessionId,
        backendSessionId,
        status: response.status,
        hasError: 'error' in response && !!response.error,
        hasData: !!response.data
      })

      // Check if response has error
      if ('error' in response && response.error) {
        frontendLoggingService.error('SessionSyncService', 'Backend returned error', {
          sessionId,
          backendSessionId,
          error: response.error
        })
        throw new Error(`Backend error: ${response.error.message}`)
      }

      frontendLoggingService.info('SessionSyncService', 'Session title updated successfully', {
        sessionId,
        backendSessionId,
        newTitle,
        responseStatus: response.status
      })
    } catch (error) {
      frontendLoggingService.error('SessionSyncService', `Failed to update session title for ${sessionId}`, error as Error, {
        newTitle
      })
      throw error
    }
  }
}

export const sessionSyncService = new SessionSyncService()
export default sessionSyncService

