/**
 * CurrentSessionService - Session context provider
 *
 * Purpose:
 * - Expose current session/agent context to all services
 * - Track active session and agent
 * - Provide easy access to message context
 * - Decouple services from React/Zustand
 *
 * Benefits:
 * - Services don't need to access Zustand store directly
 * - No stale state (services get current context)
 * - Easy to test (can mock service)
 * - Clear separation of concerns
 */


import type { ConversationSession, Agent, ConversationMessage } from '@/types/agentInteraction'

type ContextSubscriber = (context: SessionContext) => void

interface SessionContext {
  currentSession: ConversationSession | null
  currentAgent: Agent | null
}

export class CurrentSessionService {
  private currentSession: ConversationSession | null = null
  private currentAgent: Agent | null = null
  private subscribers: Set<ContextSubscriber> = new Set()

  /**
   * Get current session
   */
  getCurrentSession(): ConversationSession | null {
    return this.currentSession
  }

  /**
   * Get current agent
   */
  getCurrentAgent(): Agent | null {
    return this.currentAgent
  }

  /**
   * Get first message from current session
   * Used for title generation
   */
  getFirstMessage(): string | null {
    return this.currentSession?.messages?.[0]?.content || null
  }

  /**
   * Get last assistant message from current session
   * Used for analysis and context
   */
  getLastAssistantMessage(): ConversationMessage | null {
    const messages = this.currentSession?.messages || []
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant') {
        return messages[i]
      }
    }
    return null
  }

  /**
   * Get all messages from current session
   */
  getMessages(): ConversationMessage[] {
    return this.currentSession?.messages || []
  }

  /**
   * Get message count in current session
   */
  getMessageCount(): number {
    return this.currentSession?.messages?.length || 0
  }

  /**
   * Set current session
   */
  setCurrentSession(session: ConversationSession | null): void {



    this.currentSession = session
    this.notifySubscribers()

    // traceService.trace('CurrentSessionService', 'session updated', {
      // sessionId,
      // messageCount,
      // title: session?.title
    // })
  }

  /**
   * Set current agent
   */
  setCurrentAgent(agent: Agent | null): void {



    this.currentAgent = agent
    this.notifySubscribers()

    // traceService.trace('CurrentSessionService', 'agent updated', {
      // agentId,
      // agentModel,
      // agentName: agent?.name
    // })
  }

  /**
   * Set both session and agent together
   * More efficient than calling setters separately
   */
  setContext(session: ConversationSession | null, agent: Agent | null): void {
    this.currentSession = session
    this.currentAgent = agent
    this.notifySubscribers()

    // traceService.trace('CurrentSessionService', 'context updated', {
      // sessionId: session?.id || 'null',
      // agentId: agent?.id || 'null'
    // })
  }

  /**
   * Subscribe to context changes
   *
   * @param callback - Function called when context changes
   * @returns Unsubscribe function
   */
  subscribe(callback: ContextSubscriber): () => void {
    this.subscribers.add(callback)
    // Immediately call with current state
    callback(this.getContext())
    // Return unsubscribe function
    return () => this.subscribers.delete(callback)
  }

  /**
   * Get full context
   */
  private getContext(): SessionContext {
    return {
      currentSession: this.currentSession,
      currentAgent: this.currentAgent
    }
  }

  /**
   * Notify all subscribers of context changes
   */
  private notifySubscribers(): void {
    const context = this.getContext()
    // traceService.trace('CurrentSessionService', 'notifying subscribers', {
      // subscriberCount: this.subscribers.size
    // })
    this.subscribers.forEach(cb => cb(context))
  }

  /**
   * Clear current context
   */
  clearContext(): void {
    this.currentSession = null
    this.currentAgent = null
    this.notifySubscribers()

    // traceService.trace('CurrentSessionService', 'context cleared')
  }

  /**
   * Get service status
   */
  getStatus(): {
    hasSession: boolean
    hasAgent: boolean
    sessionId: string | null
    agentId: string | null
    subscriberCount: number
  } {
    return {
      hasSession: !!this.currentSession,
      hasAgent: !!this.currentAgent,
      sessionId: this.currentSession?.id || null,
      agentId: this.currentAgent?.id || null,
      subscriberCount: this.subscribers.size
    }
  }

  /**
   * Cleanup - clear subscribers
   */
  destroy(): void {
    this.subscribers.clear()
    this.currentSession = null
    this.currentAgent = null

    // traceService.trace('CurrentSessionService', 'service destroyed')
  }
}

// Export singleton instance
export const currentSessionService = new CurrentSessionService()
