import type { ConversationMessage, ConversationSession } from '@/types/agentInteraction'
import { sessionSyncService } from '../sessionSyncService'
import { frontendLoggingService } from '../frontendLoggingService'
import { MetricsService } from './MetricsService'


/**
 * MessageService - Manage conversation messages
 *
 * Handles message CRUD operations, streaming updates, and backend sync.
 * Works with cognitiveHubStore for state management.
 *
 * @example
 * ```typescript
 * const messageService = new MessageService()
 * await messageService.sendMessage(session, 'Hello', agent)
 * messageService.updateMessage(session, messageId, 'Updated content', metadata)
 * await messageService.deleteMessage(sessionId, messageId)
 * ```
 */
export class MessageService {
  private metricsService: MetricsService

  constructor() {
    this.metricsService = new MetricsService()
  }

  /**
   * Add a message to a session
   * Updates both the session in the list and the active session
   *
   * @param session - The session to add the message to
   * @param message - The message to add
   * @returns Updated session
   */
  addMessageToSession(session: ConversationSession, message: ConversationMessage): ConversationSession {
    const updatedSession: ConversationSession = {
      ...session,
      messages: [...(session.messages || []), message],
      updatedAt: new Date()
    }

    frontendLoggingService.debug('MessageService', 'Added message to session', {
      sessionId: session.id,
      messageId: message.id,
      role: message.role,
      messageCount: updatedSession.messages?.length
    })

    return updatedSession
  }

  /**
   * Update a message in a session
   * Updates both the session in the list and the active session
   *
   * @param session - The session containing the message
   * @param messageId - The ID of the message to update
   * @param content - New content for the message
   * @param metadata - Optional metadata (metrics, truncation info, etc.)
   * @returns Updated session, or null if message not found
   */
  updateMessageInSession(
    session: ConversationSession,
    messageId: string,
    content: string,
    metadata?: Record<string, unknown>
  ): ConversationSession | null {
    const messageIndex = (session.messages || []).findIndex(msg => msg.id === messageId)

    if (messageIndex === -1) {
      frontendLoggingService.warning('MessageService', 'Message not found for update', {
        sessionId: session.id,
        messageId
      })
      return null
    }

    const updatedMessage = {
      ...(session.messages || [])[messageIndex],
      content,
      ...(metadata ? { metadata } : {})
    }

    const updatedMessages = [
      ...(session.messages || []).slice(0, messageIndex),
      updatedMessage,
      ...(session.messages || []).slice(messageIndex + 1)
    ]

    const updatedSession: ConversationSession = {
      ...session,
      messages: updatedMessages,
      updatedAt: new Date()
    }

    frontendLoggingService.debug('MessageService', 'Updated message in session', {
      sessionId: session.id,
      messageId,
      hasMetadata: !!metadata,
      metadataKeys: metadata ? Object.keys(metadata) : []
    })

    return updatedSession
  }

  /**
   * Remove a message from a session
   *
   * @param session - The session to remove the message from
   * @param messageId - The ID of the message to remove
   * @returns Updated session, or null if message not found
   */
  removeMessageFromSession(session: ConversationSession, messageId: string): ConversationSession | null {
    const messageIndex = (session.messages || []).findIndex(msg => msg.id === messageId)

    if (messageIndex === -1) {
      frontendLoggingService.warning('MessageService', 'Message not found for removal', {
        sessionId: session.id,
        messageId
      })
      return null
    }

    const updatedMessages = [
      ...(session.messages || []).slice(0, messageIndex),
      ...(session.messages || []).slice(messageIndex + 1)
    ]

    const updatedSession: ConversationSession = {
      ...session,
      messages: updatedMessages,
      updatedAt: new Date()
    }

    frontendLoggingService.debug('MessageService', 'Removed message from session', {
      sessionId: session.id,
      messageId
    })

    return updatedSession
  }

  /**
   * Delete a message from backend and update local state
   *
   * @param sessionId - The session ID
   * @param messageId - The message ID to delete
   * @throws Error if backend deletion fails
   */
  async deleteMessage(sessionId: string, messageId: string): Promise<void> {
    try {
      frontendLoggingService.debug('MessageService', 'Deleting message from backend', {
        sessionId,
        messageId
      })

      await sessionSyncService.deleteMessage(sessionId, messageId)

      frontendLoggingService.info('MessageService', 'Message deleted successfully', {
        sessionId,
        messageId
      })
    } catch (error) {
      frontendLoggingService.error('MessageService', 'Failed to delete message', error)
      throw new Error(`Failed to delete message: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  /**
   * Create a user message
   *
   * @param content - The message content
   * @param agentId - The agent ID
   * @returns New user message
   */
  createUserMessage(content: string, agentId: string): ConversationMessage {
    return {
      id: `msg-${Date.now()}-user`,
      role: 'user',
      content,
      timestamp: new Date(),
      agentId
    }
  }

  /**
   * Create an assistant message placeholder for streaming
   *
   * @param agentId - The agent ID
   * @param isStreaming - Whether the message is being streamed (default: true)
   * @returns New assistant message
   */
  createAssistantMessage(agentId: string, isStreaming = true): ConversationMessage {
    return {
      id: `msg-${Date.now()}-assistant`,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      agentId,
      isStreaming
    }
  }

  /**
   * Finalize a streaming message with content and metadata
   *
   * @param message - The streaming message to finalize
   * @param content - The complete content
   * @param durationMs - Streaming duration in milliseconds
   * @param model - Model name (optional)
   * @param provider - Provider name (optional)
   * @param truncated - Whether the response was truncated (optional)
   * @returns Finalized message with metadata
   */
  finalizeStreamingMessage(
    message: ConversationMessage,
    content: string,
    durationMs: number,
    model?: string,
    provider?: string,
    truncated?: boolean
  ): ConversationMessage {
    const metadata = this.metricsService.calculateStreamMetrics(content, durationMs, model, provider)

    if (truncated) {
      metadata.truncated = true
    }

    return {
      ...message,
      content,
      isStreaming: false,
      metadata
    }
  }

  /**
   * Export conversation messages to a format suitable for LLM context
   * Filters out streaming messages and formats for API consumption
   *
   * @param messages - Array of conversation messages
   * @param limit - Maximum number of messages to include (default: 20)
   * @returns Formatted chat messages for LLM API
   */
  formatMessagesForLLM(messages: ConversationMessage[], limit = 20): Array<{
    role: 'user' | 'assistant' | 'system'
    content: string
  }> {
    // Filter out streaming messages and take the most recent messages up to the limit
    const validMessages = messages
      .filter(msg => !msg.isStreaming)
      .slice(-limit)

    return validMessages.map(msg => ({
      role: msg.role as 'user' | 'assistant' | 'system',
      content: msg.content
    }))
  }

  /**
   * Export entire conversation as a structured object
   *
   * @param session - The session to export
   * @param format - Export format (default: 'json')
   * @returns Formatted conversation data
   */
  exportConversation(
    session: ConversationSession,
    format: 'json' | 'markdown' | 'text' = 'json'
  ): string {
    switch (format) {
      case 'markdown': {
        let markdown = `# ${session.title}\n\n`
        markdown += `**Agent:** ${session.agentId}\n`
        markdown += `**Created:** ${session.createdAt.toISOString()}\n`
        markdown += `**Updated:** ${session.updatedAt.toISOString()}\n\n`
        markdown += `---\n\n`

        for (const message of session.messages || []) {
          markdown += `### ${message.role.toUpperCase()}\n\n`
          markdown += `${message.content}\n\n`
          if (message.metadata) {
            markdown += `*Tokens: ${message.metadata.tokenCount || 'N/A'}, `
            markdown += `Time: ${message.metadata.totalTimeMs || 'N/A'}ms*\n\n`
          }
          markdown += `---\n\n`
        }

        return markdown
      }

      case 'text': {
        let text = `Conversation: ${session.title}\n`
        text += `Agent: ${session.agentId}\n`
        text += `Date: ${session.updatedAt.toLocaleString()}\n\n`
        text += `=${'='.repeat(50)}\n\n`

        for (const message of session.messages || []) {
          text += `[${message.role.toUpperCase()}]\n`
          text += `${message.content}\n\n`
        }

        return text
      }

      case 'json':
      default: {
        return JSON.stringify({
          title: session.title,
          agentId: session.agentId,
          createdAt: session.createdAt.toISOString(),
          updatedAt: session.updatedAt.toISOString(),
          messages: (session.messages || []).map(msg => ({
            id: msg.id,
            role: msg.role,
            content: msg.content,
            timestamp: msg.timestamp.toISOString(),
            metadata: msg.metadata
          }))
        }, null, 2)
      }
    }
  }
}
