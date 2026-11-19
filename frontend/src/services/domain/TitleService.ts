/**
 * TitleService - Background title generation
 *
 * Manages title generation as a background process.
 * Decouples title generation from chat streaming workflow.
 *
 * Features:
 * - Runs title generation asynchronously in background
 * - Doesn't block chat workflow
 * - Supports multiple concurrent title generations
 * - Automatic retry on failure
 * - Queue-based processing
 *
 * @example
 * ```typescript
 * const titleService = new TitleService()
 * titleService.generateTitleInBackground(sessionId, firstMessage, model)
 * ```
 */

import { apiClient } from '../apiClient'
import { isPlaceholderTitle } from '@/utils/sessionTitles'
import { frontendLoggingService } from '../frontendLoggingService'
import { useCognitiveHubStore } from '@/stores/cognitiveHubStore'
import { useNotificationStore } from '@/stores/notificationStore'
import { currentSessionService } from './CurrentSessionService'
import { sessionSyncService } from '../sessionSyncService'

interface TitleGenerationJob {
  sessionId: string
  assistantMessage: string
  model: string | null
  userEnabled: boolean
  retryCount: number
  createdAt: number
}

export class TitleService {
  private processingJobs: Set<string>
  private pendingJobs: Map<string, TitleGenerationJob>

  constructor() {
    this.processingJobs = new Set()
    this.pendingJobs = new Map()
  }

  /**
   * Queue a title generation job to run in background
   *
   * @param sessionId - The session ID to generate title for
   * @param assistantMessage - The assistant message to use for title generation
   * @param model - Optional model override (e.g., "ollama/llama3.2"). Uses backend default if null.
   * @param userEnabled - Whether the user has enabled auto-title generation in settings.
   */
  generateTitleInBackground(
    sessionId: string,
    assistantMessage: string,
    model: string | null = null,
    userEnabled: boolean = true
  ): void {
    frontendLoggingService.info('TitleService', 'generateTitleInBackground called', {
      sessionId,
      assistantMessageLength: assistantMessage.length,
      model,
      userEnabled
    })

    // Don't queue if already processing
    if (this.processingJobs.has(sessionId) || this.pendingJobs.has(sessionId)) {
      frontendLoggingService.debug('TitleService', 'Title generation already in progress', {
        sessionId
      })
      return
    }

    const job: TitleGenerationJob = {
      sessionId,
      assistantMessage,
      model,
      userEnabled,
      retryCount: 0,
      createdAt: Date.now()
    }

    this.pendingJobs.set(sessionId, job)

    frontendLoggingService.info('TitleService', 'Title generation job queued', {
      sessionId,
      pendingCount: this.pendingJobs.size
    })

    // traceService.trace('TitleService', 'job queued, will process after timeout', {
      // sessionId,
      // pendingCount: this.pendingJobs.size
    // })

    // Defer processing to allow React to settle after stream completion
    // Use 100ms delay to ensure UI has updated before title generation runs
    setTimeout(() => {
      // traceService.trace('TitleService', 'timeout complete, calling processJob', { sessionId })
      this.processJob(sessionId)
    }, 100)
  }

  /**
   * Process a single title generation job
   */
  private async processJob(sessionId: string): Promise<void> {
    const startTime = Date.now()

    const job = this.pendingJobs.get(sessionId)
    if (!job) {
      frontendLoggingService.debug('TitleService', 'processJob: no job found', { sessionId })
      return
    }

    frontendLoggingService.info('TitleService', 'processJob started', {
      sessionId,
      model: job.model,
      userEnabled: job.userEnabled,
      retryCount: job.retryCount
    })

    this.processingJobs.add(sessionId)
    this.pendingJobs.delete(sessionId)

    // THE BACKEND-TITLE GUARD (2026-09-09, B1): the backend's
    // finalization now generates the title itself and its event is
    // applied to the store session — if a real title already landed
    // (or the session was swapped to one that has it), this
    // frontend job is redundant. Skip it: no double LLM call, no
    // rename-notification spam.
    try {
      const hubState = useCognitiveHubStore.getState()
      const target =
        hubState.sessions.find(s => s.id === sessionId) ||
        hubState.activeSession
      // The placeholder class has ONE definition now (2026-09-26,
      // `utils/sessionTitles`): "New Session…", "Untitled" AND the Exa panel's
      // "Exa Chat", which this guard read as a real title — so the job that
      // exists to name an Exa session skipped itself and the panel kept
      // "Exa Chat" forever.
      const existing = target?.title?.trim()
      if (!isPlaceholderTitle(existing)) {
        frontendLoggingService.info('TitleService', 'processJob: title already set — skipping (the backend titled it)', {
          sessionId,
          title: existing,
        })
        this.processingJobs.delete(sessionId)
        return
      }
    } catch {
      // The guard is best-effort — a failure falls through to the job.
    }

    // Show toast notification - title generation started
    useNotificationStore.getState().addNotification({
      type: 'info',
      title: 'Generating Title',
      message: 'Creating a descriptive title for this session...',
      duration: 3000
    })

    // traceService.trace('TitleService', 'processJob: calling generateTitleWithFallback', {
      // sessionId,
      // retryCount: job.retryCount,
      // assistantMessageLength: job.assistantMessage.length,
      // model: job.model
    // })

    try {
      frontendLoggingService.info('TitleService', 'Generating title via backend API', {
        sessionId,
        retryCount: job.retryCount,
        assistantMessagePreview: job.assistantMessage.substring(0, 50)
      })

      const llmStartTime = Date.now()

      const requestBody = {
        assistant_message: job.assistantMessage,
        model: job.model || undefined,
        user_enabled: job.userEnabled
      }

      frontendLoggingService.info('TitleService', 'Calling backend API for title generation', {
        sessionId,
        model: requestBody.model,
        userEnabled: requestBody.user_enabled,
        assistantMessagePreview: job.assistantMessage.substring(0, 50)
      })

      // Call backend title generation endpoint
      const response = await apiClient.post<{ title: string }>(
        '/api/v1/chat/generate-title',
        requestBody
      )

      const llmDuration = Date.now() - llmStartTime

      if (response.error) {
        throw new Error(response.error.message || 'Backend title generation failed')
      }

      const title = response.data?.title

      if (title && title.trim()) {
        // Update session title in store and persist to backend
        await this.updateSessionTitle(sessionId, title)

        const totalDuration = Date.now() - startTime
        frontendLoggingService.info('TitleService', 'Title generated successfully', {
          sessionId,
          title,
          totalDurationMs: totalDuration,
          llmDurationMs: llmDuration
        })

        // Show toast notification - title generation complete
        useNotificationStore.getState().addNotification({
          type: 'success',
          title: 'Title Generated',
          message: `Session titled "${title}"`,
          duration: 3000
        })
        
        // traceService.trace('TitleService', 'title generation complete', {
          // sessionId,
          // title,
          // totalDurationMs: totalDuration,
          // llmDurationMs: llmDuration
        // })
      } else {
        // traceService.trace('TitleService', 'title is empty, throwing error', { sessionId })
        throw new Error('Generated title is empty')
      }
    } catch (error) {

      frontendLoggingService.error('TitleService', 'Title generation failed', error, {
        sessionId,
        retryCount: job.retryCount
      })

      // traceService.trace('TitleService', 'Title generation failed', {
        // sessionId,
        // error: errorMessage,
        // retryCount: job.retryCount
      // })

      // Show toast notification - title generation failed (no fallback, no retry)
      useNotificationStore.getState().addNotification({
        type: 'warning',
        title: 'Title Generation Failed',
        message: 'Could not generate session title',
        duration: 3000
      })

      // No retries - one failure is enough
      frontendLoggingService.warning('TitleService', 'Title generation failed, not retrying', {
        sessionId,
        model: job.model
      })
    } finally {
      this.processingJobs.delete(sessionId)

      // Process next job if available
      const nextJobId = Array.from(this.pendingJobs.keys())[0]
      if (nextJobId) {
        // traceService.trace('TitleService', 'processing next job in queue', {
          // nextJobId
        // })
        this.processJob(nextJobId)
      } else {
        // traceService.trace('TitleService', 'no more jobs in queue', { sessionId })
      }
    }
  }


  /**
   * Update session title in CognitiveHubStore and persist to backend
   */
  private async updateSessionTitle(sessionId: string, title: string): Promise<void> {
    const { renameSessionById } = useCognitiveHubStore.getState()

    // Update frontend store first (immediate UI feedback)
    renameSessionById(sessionId, title)

    // Persist to backend
    try {
      await sessionSyncService.updateSessionTitle(sessionId, title)
      frontendLoggingService.info('TitleService', 'Session title persisted to backend', {
        sessionId,
        title
      })
    } catch (error) {
      frontendLoggingService.error('TitleService', 'Failed to persist session title to backend', error as Error, {
        sessionId,
        title
      })
      // Don't throw - frontend store is already updated, backend sync can retry later
    }

    // Verify the update worked using CurrentSessionService
    const currentSession = currentSessionService.getCurrentSession()
    const sessionFromStore = useCognitiveHubStore.getState().sessions.find(s => s.id === sessionId)

    frontendLoggingService.debug('TitleService', 'Session title updated in store', {
      sessionId,
      title,
      verified: sessionFromStore?.title === title,
      currentSessionId: currentSession?.id
    })
  }

  /**
   * Cancel a pending or processing title generation job
   *
   * @param sessionId - The session ID to cancel
   */
  cancelJob(sessionId: string): void {
    const wasPending = this.pendingJobs.delete(sessionId)
    const wasProcessing = this.processingJobs.delete(sessionId)

    if (wasPending || wasProcessing) {
      frontendLoggingService.info('TitleService', 'Title generation cancelled', {
        sessionId
      })
    }
  }

  /**
   * Get the number of pending jobs
   */
  getPendingCount(): number {
    return this.pendingJobs.size
  }

  /**
   * Get the number of currently processing jobs
   */
  getProcessingCount(): number {
    return this.processingJobs.size
  }

  /**
   * Clear all pending jobs
   */
  clearAllJobs(): void {
    this.pendingJobs.clear()
    this.processingJobs.clear()

    frontendLoggingService.info('TitleService', 'All title generation jobs cleared')
  }
}

// Export singleton instance
export const titleService = new TitleService()
