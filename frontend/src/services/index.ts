/**
 * Services Index - Domain-based API Abstraction Layer
 *
 * This module exports all domain-based services organized by business domain.
 * It provides a clean interface for accessing API functionality with proper
 * abstraction and domain boundaries.
 */

// Import domain services
import { agentService } from './domains/llm/agentService';
import { workflowService } from './domains/llm/workflowService';
import { sessionService } from './domains/llm/sessionService';
import { chatService } from './domains/llm/chatService';
import { healthService } from './domains/system/healthService';
import { logsService as domainLogsService } from './domains/system/logsService';
import { sessionSyncService } from './sessionSyncService';
import { frontendLoggingService } from './frontendLoggingService';
import { logsService } from './logsService'; // In-memory logs service

// Import legacy services for backward compatibility
import * as legacyAgentService from './agentService';
// THE ONE CLIENT (2026-09-04, the _34 consolidation): the canonical
// domains/shared/apiClient.ts is DELETED — this barrel exports the
// consolidated client (the machinery was ported INTO it).
import { apiClient } from './apiClient';

// Import types
import type { IAgentService } from './domains/llm/agentService';
import type { IWorkflowService } from './domains/llm/workflowService';
import type { ISessionService } from './domains/llm/sessionService';
import type { IChatService } from './domains/llm/chatService';
import type { IHealthService } from './domains/system/healthService';
import type { ILogsService } from './domains/system/logsService';

// Export domain services
export {
  agentService,
  workflowService,
  sessionService,
  chatService,
  healthService,
  logsService,
  apiClient,
  sessionSyncService,
  frontendLoggingService
};

// Export legacy services for backward compatibility
export {
  legacyAgentService
};

// Export domain logs service for backward compatibility
export { domainLogsService };

// Export types for service interfaces
export type {
  IAgentService,
  IWorkflowService,
  ISessionService,
  IChatService,
  IHealthService,
  ILogsService
};

// Service factory for dependency injection
export class ServiceFactory {
  static getAgentService(): IAgentService {
    return agentService;
  }

  static getWorkflowService(): IWorkflowService {
    return workflowService;
  }

  static getSessionService(): ISessionService {
    return sessionService;
  }

  static getChatService(): IChatService {
    return chatService;
  }

  static getHealthService(): IHealthService {
    return healthService;
  }

  static getLogsService(): ILogsService {
    return logsService;
  }

  static getApiClient() {
    return apiClient;
  }
}