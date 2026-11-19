/**
 * Chat Service - LLM Domain
 *
 * Service abstraction layer for chat module functionality with proper domain boundaries.
 */

import { apiClient } from '@/services/apiClient';
import { frontendLoggingService } from '@/services/frontendLoggingService';
import type { ApiResponse } from '@/types';

/**
 * Chat Health Response Interface
 */
export interface ChatHealthResponse {
  status: string;
  timestamp: string;
  version: string;
  module: string;
  dependencies: {
    llm_provider: string;
    session_manager: string;
  };
}

/**
 * Detailed Chat Health Response Interface
 */
export interface DetailedChatHealthResponse {
  status: string;
  timestamp: string;
  module: string;
  services: {
    llm_provider: {
      status: string;
      provider: string;
      models_available: number;
    };
    session_manager: {
      status: string;
      active_sessions: number;
    };
  };
}

/**
 * Chat Message Interface
 */
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

/**
 * Chat Completion Request Interface
 */
export interface ChatCompletionRequest {
  model: string;
  messages: ChatMessage[];
  stream?: boolean;
  profile?: string;
  session_id?: number;  // Session ID for backend
  generate_title?: boolean;  // Auto-generate session title
  attachment_ids?: number[];  // Attachment IDs to include in message context
  options?: {
    temperature?: number;
    max_tokens?: number;
    top_p?: number;
  };
}

/**
 * Chat Completion Response Interface
 */
export interface ChatCompletionResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: Array<{
    index: number;
    message: ChatMessage;
    finish_reason: string;
  }>;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

/**
 * Chat Service Interface
 */
export interface IChatService {
  getChatHealth(): Promise<ApiResponse<ChatHealthResponse>>;
  getDetailedChatHealth(): Promise<ApiResponse<DetailedChatHealthResponse>>;
  checkChatConnectivity(): Promise<ApiResponse<ChatHealthResponse>>;
  createChatCompletion(request: ChatCompletionRequest, options?: { timeout?: number }): Promise<ApiResponse<ChatCompletionResponse>>;
  createStreamingChatCompletion(request: ChatCompletionRequest, options?: { signal?: AbortSignal }): Promise<Response>;
}

/**
 * Chat Service Implementation
 */
class ChatService implements IChatService {
  private readonly basePath = '/api/v1/chat';

  /**
   * Get basic chat module health status
   * Note: Backend endpoint /chat/health not implemented yet
   */
  async getChatHealth(): Promise<ApiResponse<ChatHealthResponse>> {
    return await apiClient.get<ChatHealthResponse>(`${this.basePath}/health`);
  }

  /**
   * Get detailed chat module health status
   * Note: Backend endpoint /chat/health/detailed not implemented yet
   */
  async getDetailedChatHealth(): Promise<ApiResponse<DetailedChatHealthResponse>> {
    return await apiClient.get<DetailedChatHealthResponse>(`${this.basePath}/health/detailed`);
  }

  /**
   * Check chat module connectivity (alias for getChatHealth)
   */
  async checkChatConnectivity(): Promise<ApiResponse<ChatHealthResponse>> {
    return this.getChatHealth();
  }

  /**
   * Create a non-streaming chat completion
   */
  async createChatCompletion(request: ChatCompletionRequest, options?: { timeout?: number }): Promise<ApiResponse<ChatCompletionResponse>> {
    try {
      const response = await apiClient.post<ChatCompletionResponse>(
        `${this.basePath}/completions`,
        request,
        { timeout: options?.timeout }
      );
      return response;
    } catch (error) {
      frontendLoggingService.error('ChatService', 'Chat completion failed', error);
      throw error;
    }
  }

  /**
   * Create a streaming chat completion
   */
  async createStreamingChatCompletion(request: ChatCompletionRequest, options?: { signal?: AbortSignal }): Promise<Response> {
    try {
      // Map request to backend format
      // Find the LAST user message (the current one being sent)
      const userMessages = request.messages.filter(m => m.role === 'user');
      const currentMessage = userMessages.length > 0 ? userMessages[userMessages.length - 1] : { content: '' };

      const backendRequest = {
        agent_id: parseInt(request.profile || '1'),
        message: currentMessage.content || '',
        session_id: request.session_id || null,
        stream: true,
        attachment_ids: request.attachment_ids || null,
      };

      frontendLoggingService.debug('ChatService', 'Backend request', backendRequest);
      frontendLoggingService.debug('ChatService', 'Total messages in request', { count: request.messages.length });
      frontendLoggingService.debug('ChatService', 'Current message being sent', { content: currentMessage.content });

      // Use apiClient streaming method
      const response = await apiClient.stream(
        `${this.basePath}/stream`,
        backendRequest,
        { signal: options?.signal }
      );

      return response;
    } catch (error) {
      frontendLoggingService.error('ChatService', 'Streaming chat completion failed', error);
      throw error;
    }
  }
}

// Create and export singleton instance
export const chatService: IChatService = new ChatService();

// Export for dependency injection
export default chatService;
