/**
 * Types and interfaces for Agent Interaction features
 */

export interface AgentHealth {
  status: 'ok' | 'warn' | 'fail'
  consecutiveFailures: number
  lastError?: string | null
  lastFailureAt?: string | null
  failures7d: number
}

export interface Agent {
  id: string;
  name: string;
  description: string;
  capabilities: string[];
  provider: string;
  model: string;
  parameters: AgentParameters;
  isAvailable: boolean;
  profileImageUrl?: string;  // Optional profile image URL
  health?: AgentHealth;      // Provider health (from usage_logs, F3)
  fallbackEnabled?: boolean;        // F4: opt-in provider failover
  preferredProviders?: string[];    // F4: fallback chain order
  // Freshness metadata - tracks data freshness to prevent stale data bugs
  loadedFrom?: 'localStorage' | 'backend';
  lastRefreshed?: string;  // ISO 8601 timestamp
  isStale?: boolean;  // True if data may be outdated
}

// The sampling settings an agent read may carry. THREE KEYS ONLY, and the list is
// the server's: `AgentParameters` (domain/agents/schemas.py, `extra="forbid"`) accepts
// exactly these two, and a request carrying anything else is refused by name. A key
// declared here that the API rejects is an invitation to send a 422.
export interface AgentParameters {
  temperature?: number;
  topP?: number;
}

export interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  timestamp: Date;
  agentId?: string;
  isStreaming?: boolean;
  metadata?: MessageMetadata;
  tool_call_id?: string;
  tool_name?: string;
  tool_result?: unknown;
  // THE EXA ACTIVITY (2026-08-29, the panel-port): the tool-call
  // titles streamed live on the page's own ws — rendered behind a
  // collapsible thinking-fold (the same pattern as the reasoning
  // metadata), NEVER pushing the answer off-screen.
  activity?: string[];
  activityDone?: boolean;  // the turn ended — the static markers
}

export interface MessageMetadata {
  tokenCount?: number;
  totalTimeMs?: number;
  tokensPerSecond?: number;
  model?: string;
  provider?: string;
  truncated?: boolean;  // True if response was cut off at max_tokens limit
  // THE SOFT-LIMIT NOTE (2026-09-22, Phase D.2): the soft lines this turn
  // crossed (`limits`, one record per crossing) and the sentence the bubble
  // shows (`limit_notice` — the backend's limit reason verbatim). Both ride the
  // done frame's metadata and the saved row, so the note survives a reload.
  // `mode` is D.3's (2026-09-23): a fired HARD plug says HOW it was handled —
  // `abort` (the turn was stopped, what had arrived is kept) or `finish` (the
  // answer was kept whole). A soft crossing carries no mode.
  limits?: Array<{ key: string; value?: number | null; threshold: number; mode?: string; reason: string }>;
  limit_notice?: string;
  reasoning?: string;  // THE THINKING SEGREGATION (2026-08-24): the
                       // chain-of-thought, rendered behind the
                       // collapsible Thinking fold — never in the bubble
  tool_calls?: ToolCall[];
  tool_execution_time?: number;
  tool_success?: boolean;
  tool_error?: string;
  // CHAT AUTHORIZATION: the permission request payload (the diff +
  // the options) — rendered as the Approve/Deny card
  request_id?: string;
  request?: unknown;
  // THE EXA-ERA FIELDS (2026-08-25, the tsc -b build fix — the
  // flicker-fix + the thinking-fold + the trace metadata land
  // here; the type lagged the runtime).
  exa_working?: boolean
  exa_meta?: Record<string, unknown>
  exa_tool?: string | null
  elapsed_ms?: number
  ctx?: Record<string, unknown>
  _done?: boolean
}

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  result?: unknown;
  execution_time?: number;
  success?: boolean;
  error?: string;
}

export interface ConversationSession {
  id: string
  title: string
  agentId: string
  messages?: ConversationMessage[]  // Optional for lazy loading
  // THE MESSAGE COUNT (2026-09-15): the sessions list is titles-only and sends
  // `messages: []`, so `messages.length` is 0 for every session you have not
  // opened — and stale for the one you have. The API now returns the real count.
  message_count?: number
  createdAt: Date
  updatedAt: Date
  isActive: boolean
  status?: 'active' | 'inactive' | 'unloaded'  // Session lifecycle status
  source?: string  // the session's origin — 'agent' | 'exa' (2026-08-28: the ExaChat's auto-session!)
  /** Per-session cognitive pipeline configuration */
  cognitiveConfig?: CognitiveSessionConfig
}

/**
 * Per-session cognitive pipeline configuration.
 * Stored on the session so config persists across session switches and page reloads.
 */
export interface CognitiveSessionConfig {
  context_builder: string
  executor: string
  memory_manager: string
  response_formatter: string
}

export interface StreamingResponse {
  type: 'chunk' | 'complete' | 'error';
  content: string;
  messageId?: string;
  sessionId?: string;
  timestamp?: Date;
}

export interface AgentInteractionState {
  selectedAgent: Agent | null;
  currentSession: ConversationSession | null;
  isStreaming: boolean;
  connectionStatus: 'idle' | 'connecting' | 'connected' | 'error' | 'closed';
  error: string | null;
  isLoadingAgents: boolean;
  isReloadingSessions?: boolean;
}

export interface ChatInputProps {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export interface AgentSelectorProps {
  agents: Agent[];
  selectedAgent: Agent | null;
  onAgentSelect: (agent: Agent) => void;
  loading?: boolean;
}

export interface ResponseStreamProps {
  messages: ConversationMessage[];
  isStreaming: boolean;
  onDeleteMessage?: (messageId: string) => void;
  // CHAT AUTHORIZATION (2026-08-21): the Approve/Deny card's
  // resolution — the user's decision on a pending permission request
  onExaApproval?: (requestId: string, optionId: string) => void;
}

export interface ConversationHistoryProps {
  sessions: ConversationSession[];
  currentSession: ConversationSession | null;
  onSessionSelect: (session: ConversationSession) => void;
  onSessionDelete: (sessionId: string) => void;
  onNewSession: () => void;
  onReloadSessions?: () => void;
  isReloadingSessions?: boolean;
}