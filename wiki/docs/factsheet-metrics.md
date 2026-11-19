---
title: Factsheet Metrics
type: atlas-docs
path: wiki/docs/factsheet-metrics.md
confidence: medium
updated: 2026-11-17
tags: [type/docs, domain/docs]
---

# Cogitate Factsheet Metrics

Generated: 2026-11-17 22:07:44 UTC

---

## Development Environment

| Attribute | Value |
|-----------|-------|
| OS | Linux 6.14.0-37-generic |
| Python | 3.14.0 (uv pin: 3.14) |
| Node | v20.19.6 |
| npm | 10.8.2 |
| uv | uv 0.9.7 |

## Tech Stack

APScheduler · Alembic · FastAPI · LangChain · LangGraph · Langfuse · LiteLLM · Mermaid · React · React Router · Recharts · SQLAlchemy · Tailwind CSS · TanStack Query · Uvicorn · Zod · Zustand

*See [Detailed Tech Stack](#detailed-tech-stack) at end of report for full dependency tables.*

## Source Code Metrics

**Total source files:** 2,200
**Total source lines of code:** 436,150

### By Extension

| Extension | Files | Lines of Code |
|-----------|-------|--------------|
| .py | 783 | 199,788 |
| .tsx | 288 | 68,823 |
| .md | 762 | 66,907 |
| .ts | 239 | 53,559 |
| .json | 99 | 41,141 |
| .css | 3 | 1,422 |
| .sh | 7 | 1,367 |
| .cjs | 5 | 1,017 |
| .html | 4 | 742 |
| .js | 3 | 378 |
| .mjs | 1 | 356 |
| .sql | 1 | 239 |
| .yaml | 2 | 230 |
| .toml | 2 | 153 |
| .mako | 1 | 28 |
| **Total** | **2,200** | **436,150** |

### Largest Hand-Written Source Files

| # | File | LOC | Size |
|---|------|-----|------|
| 1 | `.hermes/cache/openrouter_model_metadata.json` | 15,155 | 312.8 KB |
| 2 | `backend/app/api/v1/chat/router.py` | 4,675 | 160.4 KB |
| 3 | `backend/tests/fixtures/cogitate_fixtures.json` | 4,087 | 205.4 KB |
| 4 | `.hermes/cache/reasoning_caps.json` | 2,970 | 46.1 KB |
| 5 | `backend/app/infrastructure/database/models.py` | 2,293 | 86.2 KB |
| 6 | `backend/app/workflows/api/workflow_router.py` | 2,050 | 78.5 KB |
| 7 | `backend/app/domain/agents/services.py` | 1,839 | 69.7 KB |
| 8 | `backend/app/domain/tools/registry.py` | 1,736 | 72.5 KB |
| 9 | `frontend/src/components/AgentProfiles/ProfileDetail.tsx` | 1,549 | 72.1 KB |
| 10 | `backend/app/domain/providers/availability.py` | 1,394 | 65.1 KB |
| 11 | `wiki/dev-notes/known-issues.md` | 1,370 | 67.9 KB |
| 12 | `scripts/bench/run_bench.py` | 1,331 | 62.5 KB |
| 13 | `backend/app/api/v1/agent_chat/router.py` | 1,301 | 45.2 KB |
| 14 | `backend/tests/conftest.py` | 1,288 | 54.8 KB |
| 15 | `.hermes/cache/tool_discovery_cache.json` | 1,277 | 24.7 KB |
| 16 | `backend/app/domain/tools/builtin/code_vector_store.py` | 1,155 | 42.6 KB |
| 17 | `backend/app/domain/chat/services.py` | 1,152 | 43.5 KB |
| 18 | `backend/alembic/versions/0001_baseline.py` | 1,147 | 79.1 KB |
| 19 | `frontend/src/services/domain/StreamingService.ts` | 1,133 | 40.5 KB |
| 20 | `backend/app/api/v1/external_agent_router.py` | 1,106 | 54.0 KB |

### Largest Generated Files ⚙️

These files are auto-generated (lockfiles, API types, indexes) and are not hand-maintained by developers.

| # | File | LOC | Size |
|---|------|-----|------|
| 1 | `frontend/package-lock.json` | 10,700 | 376.2 KB |
| 2 | `frontend/src/types/api.generated.ts` | 7,027 | 201.9 KB |
| 3 | `.hermes/lsp/package-lock.json` | 410 | 13.2 KB |

*Runtime artifacts (databases, logs, backups) and binaries are excluded.*

### Most Complex Frontend Files

| # | File | LOC | Size |
|---|------|-----|------|
| 1 | `frontend/src/types/api.generated.ts` | 7,027 | 201.9 KB |
| 2 | `frontend/src/components/AgentProfiles/ProfileDetail.tsx` | 1,549 | 72.1 KB |
| 3 | `frontend/src/services/domain/StreamingService.ts` | 1,133 | 40.5 KB |
| 4 | `frontend/src/components/features/agentInteraction/useCommandBox.ts` | 1,078 | 47.2 KB |
| 5 | `frontend/src/services/appNavigation.ts` | 1,032 | 43.6 KB |
| 6 | `frontend/src/services/domain/ProfileService.ts` | 1,021 | 36.2 KB |
| 7 | `frontend/src/pages/ExaChat.tsx` | 1,014 | 44.4 KB |
| 8 | `frontend/src/pages/TestingDashboard.tsx` | 1,001 | 40.1 KB |
| 9 | `frontend/src/components/features/agentInteraction/__tests__/NavSearchSection.test.tsx` | 991 | 40.9 KB |
| 10 | `frontend/src/components/agentPanel/AgentPanel.tsx` | 972 | 42.4 KB |
| 11 | `frontend/src/hooks/useAgentInteraction.ts` | 951 | 36.5 KB |
| 12 | `frontend/src/pages/ProviderDashboard.tsx` | 930 | 35.1 KB |
| 13 | `frontend/src/components/features/agentInteraction/__tests__/ExaPromptFlyout.test.tsx` | 907 | 35.0 KB |
| 14 | `frontend/src/components/features/providers/CuratedModelsManager.tsx` | 869 | 40.1 KB |
| 15 | `frontend/src/components/features/debugging/TraceAnalysis.tsx` | 840 | 29.9 KB |

---

## Detailed Tech Stack

### Backend (Python/FastAPI)

Description: Cogitate Backend - Multi-agent LLM orchestration platform

| Dependency | Version Spec |
|------------|-------------|
| aiosqlite | >=0.22.1 |
| alembic | >=1.16.5 |
| apscheduler | >=3.11.2 |
| blinker | >=1.9.0 |
| click | >=8.1.0 |
| cryptography | >=46.0.5 |
| ddgs | >=9.13.0 |
| duckduckgo-search | >=8.1.1 |
| fastapi | >=0.116.1 |
| httpx | >=0.28.1 |
| langchain | >=0.3.27 |
| langchain-community | >=0.3.29 |
| langchain-core | >=0.3.11 |
| langchain-ollama | >=1.0.1 |
| langchain-openai | >=0.3.33 |
| langfuse | >=4.0.1 |
| langgraph | >=0.6.7 |
| langgraph-checkpoint-sqlite | >=3.0.3 |
| litellm | >=1.96.0 |
| markdown-it-py | >=4.0.0 |
| mistune | >=3.2.0 |
| psutil | >=7.1.0 |
| pydantic-settings | >=2.10.1 |
| python-dotenv | >=1.1.1 |
| python-multipart | >=0.0.20 |
| pytz | >=2025.2 |
| sqlalchemy[asyncio] | >=2.0.53,<2.1 |
| sqlite-vec | >=0.1.0 |
| sse-starlette | >=3.4.8 |
| uvicorn[standard] | >=0.35.0 |

### Frontend (React/TypeScript)

| Dependency | Version |
|------------|---------|
| @dnd-kit/core | ^6.3.1 |
| @dnd-kit/sortable | ^10.0.0 |
| @dnd-kit/utilities | ^3.2.2 |
| @hookform/resolvers | ^5.2.2 |
| @tailwindcss/typography | ^0.5.20 |
| @tanstack/react-query | ^5.90.5 |
| @tanstack/react-query-devtools | ^5.90.2 |
| highlight.js | ^11.11.1 |
| lucide-react | ^1.7.0 |
| mermaid | ^11.12.0 |
| react | ^19.1.1 |
| react-dom | ^19.1.1 |
| react-helmet-async | ^3.0.0 |
| react-hook-form | ^7.65.0 |
| react-markdown | ^10.1.0 |
| react-router-dom | ^7.8.2 |
| recharts | ^3.8.0 |
| rehype-highlight | ^7.0.2 |
| remark-gfm | ^4.0.1 |
| zod | ^4.1.12 |
| zustand | ^5.0.8 |

### Frontend Dev Dependencies

| Dependency | Version |
|------------|---------|
| @eslint/js | ^9.33.0 |
| @storybook/react-vite | ^9.1.13 |
| @tailwindcss/vite | ^4.2.1 |
| @testing-library/jest-dom | ^6.9.1 |
| @testing-library/react | ^16.3.0 |
| @types/node | ^25.9.1 |
| @types/react | ^19.1.12 |
| @types/react-dom | ^19.1.9 |
| @vitejs/plugin-react | ^5.0.0 |
| @vitest/coverage-v8 | ^3.2.4 |
| daisyui | ^5.1.10 |
| eslint | ^9.33.0 |
| eslint-plugin-react-hooks | ^5.2.0 |
| eslint-plugin-react-refresh | ^0.4.20 |
| eslint-plugin-storybook | ^9.1.13 |
| globals | ^16.3.0 |
| jsdom | ^27.0.1 |
| openapi-typescript | ^7.13.0 |
| storybook | ^9.1.13 |
| tailwindcss | ^4.1.13 |
| typedoc | ^0.28.14 |
| typescript | ~5.8.3 |
| typescript-eslint | ^8.39.1 |
| vite | ^7.1.2 |
| vitest | ^3.2.4 |

---

## Database

| Metric | Count |
|--------|-------|
| Alembic migration files | 1 |
| Manual migration scripts | 0 |
| SQLAlchemy model files found | 79 |

### Core Tables

The main model file defines these tables:

- `ABTestConfig`
- `ABTestResult`
- `Agent`
- `AgentList`
- `AgentTemplate`
- `AgentTimer`
- `AgentVersion`
- `Capability`
- `CapabilityService`
- `ChatAttachment`
- `ChatMessage`
- `ChatSession`
- `CognitivePreset`
- `CognitiveProfile`
- `CuratedModel`
- `FrontendAgentPackage`
- `Log`
- `MacroSet`
- `MemoryProfile`
- `MetaTopic`
- `PromptTemplate`
- `Provider`
- `ProviderModelCache`
- `ProviderSyncSchedule`
- `RuntimeConfig`
- `ShutdownRecord`
- `SystemFlag`
- `SystemManagerConfig`
- `SystemManagerConfigRecord`
- `UsageLog`
- `UserSettings`
- `WorkflowApproval`
- `WorkflowComposition`
- `WorkflowExecutionHistory`
- `WorkflowKind`
- `WorkflowList`
- `WorkflowTemplate`
- `WorkflowTrigger`
- `WorkflowVersion`

### SQLAlchemy Model Files

| File | Classes Found |
|------|-------------|
| `scripts/diagnostics/langfuse_sink.py` | _Handler |
| `local/agent-init/capture-server.py` | Handler |
| `local/agent-init/passthrough-proxy.py` | Handler |
| `_archive/cleanup-2026-11-17/app/domain/workflows/schemas/routing_config.py` | ClassificationRule, RoutingRule, RoutingConfig, RoutingConfigCreate, RoutingConfigUpdate, RoutingConfigResponse, RoutingResult, ClassificationResult, SimpleRoutingConfig |
| `backend/tests/unit/test_sampling_merge.py` | TestTheAgentValuesAreThe |
| `backend/tests/workflows/test_parallel_templates.py` | TestSequential |
| `backend/app/core/access_evidence.py` | AccessEvidenceMiddleware |
| `backend/app/core/database.py` | Base, DocumentsBase |
| `backend/app/core/config.py` | Settings |
| `backend/app/workflows/retention.py` | RetentionPolicy, RetentionReport |
| `backend/app/workflows/state/workflow_state.py` | LLMResolution, RunMetadata |
| `backend/app/workflows/agent_versioning/registry.py` | AgentConfig, AgentVersion |
| `backend/app/workflows/agent_versioning/ab_testing.py` | ABTestVariant, ABTestConfig |
| `backend/app/workflows/api/triggers_router.py` | TriggerCreateRequest, TriggerUpdateRequest, TriggerInfo, ScheduleTriggerConfig, WebhookTriggerConfig, ScheduleInfo |
| `backend/app/workflows/api/composition_router.py` | CompositionCreateRequest, CompositionExecuteRequest, CompositionExecuteResponse, CompositionInfo |
| `backend/app/workflows/api/workflow_router.py` | WorkflowToolGrant, ExecuteWorkflowRequest, ExecuteWorkflowResponse, WorkflowStatusResponse, ApproveWorkflowRequest, ApproveWorkflowResponse, RetentionPolicyUpdate, WorkflowStateInspectionResponse, RollbackRequest, RollbackResponse, RecoveryRequest, RecoveryResponse |
| `backend/app/workflows/api/template_router.py` | TemplateCategoryResponse, TemplateTagResponse, CategoriesResponse, TemplateListResponse, TemplateCreateRequest, TemplateUpdateRequest, TemplateValidateRequest, ValidateResponse, ValidateExecutionRequest |
| `backend/app/workflows/api/approval_router.py` | ApprovalResponse, ApproveRequest, RejectRequest, RequestChangesRequest, ApprovalInfo |
| `backend/app/workflows/api/multi_agent_router.py` | MultiAgentExecuteRequestModel, AgentOutput, MultiAgentExecuteResponse, MultiAgentTemplateInfo, MultiAgentTemplateDetail |
| `backend/app/workflows/agent_versioning/api/router.py` | CreateAgentRequest, CreateAgentResponse, AgentDetailResponse, AgentVersionResponse, UpdateAgentStatusRequest, CreateABTestRequest, CreateABTestResponse, ABTestDetailResponse, RouteAgentRequest, RouteAgentResponse |
| `backend/app/api/v1/workflow_kinds_router.py` | KindInputResponse, KindResponse, KindListResponse |
| `backend/app/api/v1/curated_models_router.py` | CuratedModelCreate, CuratedModelUpdate, VerifyWindowBody, SpecMatchBody |
| `backend/app/api/v1/stt_router.py` | SttConfigUpdate |
| `backend/app/api/v1/tts_router.py` | TtsConfigUpdate |
| `backend/app/api/v1/notifications_router.py` | NotificationsConfigUpdate, NotificationsTestPayload |
| `backend/app/api/v1/wiki/router.py` | WikiPageResponse, WikiIndexResponse, WikiHelpListResponse, WikiSearchResponse |
| `backend/app/api/v1/agent_chat/schemas.py` | CreateSessionRequest, SendMessageRequest, UpdateStatusRequest, ComponentTraceSchema, CognitiveTraceSchema, CognitiveMetricsSchema, MemoryDeltaSchema, MessageResponse, SessionResponse, SendMessageResponse, TraceResponse, PresetCreateRequest, PresetUpdateRequest, PresetResponse, PresetExportData, StatusResponse, UIStateUpdateRequest, UIStateResponse, UINavigateRequest, UINavigateResponse, WSMessage |
| `backend/app/api/v1/agent_chat/router.py` | TracesListResponse, MetricsResponse |
| `backend/app/api/v1/cognitive_vectors/router.py` | SearchRequest, IndexRequest |
| `backend/app/api/v1/system/router.py` | LifecycleRequest, ModeRequest, ScrubConfirm, ScrubRequest |
| `backend/app/api/v1/rag/router.py` | RagSearchResponse, RagSearchRequest |
| `backend/app/api/v1/agents/provisioning_router.py` | AgentProvisionRequest |
| `backend/app/api/v1/chat/attachments_router.py` | AttachmentMetadata, AttachmentListResponse |
| `backend/app/api/v1/chat/title_router.py` | TitleGenerationRequest, TitleGenerationResponse |
| `backend/app/api/v1/chat/router.py` | ChatRequestModel, DelegateRequestModel, CompletionRequestModel |
| `backend/app/api/v1/sessions/router.py` | TitleGenerationBody |
| `backend/app/api/v1/cognitive_pipeline/memory_profiles.py` | MemoryProfileResponse, MemoryProfileCreate, MemoryProfileUpdate |
| `backend/app/api/v1/cognitive_pipeline/cognitive_profiles.py` | CognitiveProfileResponse, CognitiveProfileCreate, CognitiveProfileUpdate |
| `backend/app/api/v1/agent_packages/router.py` | AgentPackageProvisionResponse, ProvisionBody |
| `backend/app/api/v1/cognitive_memory/router.py` | PruneRequest, MemoryStatusResponse, ClearSessionRequest, ClearAgentRequest |
| `backend/app/api/v1/testing/router.py` | RunRequest, RetireRequest, SaveRequest |
| `backend/app/api/v1/knowledge/router.py` | GraphQueryResponse |
| `backend/app/api/v1/providers/config_router.py` | ProviderConfigCreate, ProviderConfigUpdate, ProviderConfigResponse, ProviderConfigListResponse, ApiKeyRequest, ProviderTestResponse |
| `backend/app/api/v1/providers/capabilities_router.py` | CandidateOut, CapabilityOut, CapabilitiesResponse, CandidateIn, CapabilityUpdate |
| `backend/app/api/v1/providers/usage_router.py` | UsageSummaryResponse, UsageByProviderResponse, ModelUsageResponse, UsageTrendResponse, CostBreakdownResponse |
| `backend/app/api/v1/providers/scheduler_router.py` | SyncScheduleRequest, SyncScheduleResponse, SyncStatusResponse |
| `backend/app/api/v1/providers/management_router.py` | ProviderConfig, ProviderResponse, ProviderTestResponse, ProviderListResponse, DefaultProviderResponse, SetDefaultProviderRequest |
| `backend/app/api/v1/agent_registry/router.py` | NucleusExecuteRequest |
| `backend/app/infrastructure/database/models.py` | Agent, ChatSession, ChatMessage, ChatAttachment, RuntimeConfig, Provider, Capability, CapabilityService, UsageLog, AgentTemplate, Log, ProviderModelCache, CuratedModel, ProviderSyncSchedule, UserSettings, MacroSet, MetaTopic, AgentList, WorkflowList, WorkflowTrigger, WorkflowVersion, ABTestConfig, ABTestResult, SystemFlag, ShutdownRecord, CognitivePreset, MemoryProfile, CognitiveProfile, FrontendAgentPackage, AgentTimer, WorkflowKind, WorkflowTemplate, WorkflowComposition, WorkflowApproval, WorkflowExecutionHistory, AgentVersion, SystemManagerConfig, SystemManagerConfigRecord, PromptTemplate |
| `backend/app/domain/agent_lists/schemas.py` | AgentListBase, AgentListUpdate, AgentListListResponse, AgentInListResponse, AgentListAgentsResponse |
| `backend/app/domain/macros/schemas.py` | MacroSetBase, SystemMacroSetCreate, MacroSetUpdate, MacroSetListResponse, TopicMapping, MetaTopicBase, MetaTopicUpdate, MetaTopicListResponse, MetaTopicLoadResponse, TopicListResponse |
| `backend/app/domain/rag/schemas.py` | RagHealthConfig, RagStatusResponse, IngestRequest, IngestResponse, IngestProgress, IngestResult, IngestJobStatusResponse, IngestStatusFile |
| `backend/app/domain/settings/schemas.py` | UserSettingsSchema, UserSettingsRequest, UserSettingsResponse |
| `backend/app/domain/agents/schemas.py` | AgentParameters, AgentBase, AgentUpdate, AgentHealth, AgentServiceAvailability, AgentOutputBudget, AgentObservedBudget, AgentListResponse, SystemPromptTemplate, TemplateApplyRequest, TemplateApplyResponse, AgentTemplateCreate, AgentTemplateUpdate, AgentTemplateResponse, AgentTemplateListResponse, AgentTemplateApplyRequest, AgentTemplateSaveFromAgentRequest, DuplicateAgentInfo, DuplicateGroup, DuplicatesRequest, DuplicatesResponse, AgentSkill, AgentCapabilities, AgentCard, AgentArmCard, AgentSelectRequest, AgentSelectResponse, AgentStatsResponse |
| `backend/app/domain/runtime_config/schemas.py` | RuntimeConfigBase, RuntimeConfigApplyRequest |
| `backend/app/domain/agent_kits/model.py` | AgentKit |
| `backend/app/domain/agent_kits/schemas.py` | KitSummary, AgentKitAttach, AgentKitsResponse, AgentOwnerSummary, AgentOwnersResponse |
| `backend/app/domain/chat/schemas.py` | ChatRequest, ChatResponse, ChatMessageSchema, ChatSessionSchema, ChatSessionListResponse, StreamChunk |
| `backend/app/domain/external_agent/schemas.py` | ExaBrain, ExternalAgentConfig, ExternalAgentStatus, ExternalAgentConfigUpdate |
| `backend/app/domain/sessions/schemas.py` | SessionCreate, MessageCreate, SessionUpdate, SessionResponse, SessionListResponse |
| `backend/app/domain/collections/models.py` | Collection, CollectionItem |
| `backend/app/domain/collections/schemas.py` | CollectionBase, CollectionUpdate, CollectionItemSummary, CollectionListResponse, CollectionItemCreate, CollectionItemResponse, CollectionContainsResponse, CollectionListQuery |
| `backend/app/domain/workflow_lists/schemas.py` | WorkflowListBase, WorkflowListUpdate, WorkflowListListResponse, WorkflowInListResponse, WorkflowListWorkflowsResponse |
| `backend/app/domain/agent_packages/models.py` | AgentPackage |
| `backend/app/domain/agent_packages/schemas.py` | LlmSpec, AgentPackageBase, AgentPackageUpdate, AgentPackageListResponse |
| `backend/app/domain/tools/models.py` | ToolCategory, AgentToolGrant, Tool, AgentTool, ToolUsageLog |
| `backend/app/domain/tools/team_tools.py` | TeamTool |
| `backend/app/domain/tools/tool_permission_schemas.py` | ToolCollectionPermissionBase, ToolCollectionPermissionUpdate, CollectionSummary, ToolPermissionSummary, ToolPermissionsResponse, ToolPermissionsUpdateRequest, PermissionCheckResponse, AccessibleToolSummary, AccessibleToolsResponse, PermissionListQuery, AccessibleToolsQuery |
| `backend/app/domain/tools/team_tools_schemas.py` | TeamToolBase, TeamToolUpdate, ToolSummary, TeamToolListResponse, TeamSyncRequest, TeamSyncResult, ConflictInfo |
| `backend/app/domain/tools/schemas.py` | ToolCategoryBase, ToolCategoryUpdate, ToolCategoryListResponse, ToolBase, ToolUpdate, CategorySummary, ToolListResponse, AgentToolBase, AgentToolUpdate, ToolSummary, AgentToolListResponse, AgentToolEnableRequest, ToolUsageLogBase, ToolUsageLogListResponse, ToolUsageStats, ToolUsageStatsResponse, ToolExecutionRequest, ToolExecutionResponse |
| `backend/app/domain/tools/tool_permission_models.py` | ToolCollectionPermission |
| `backend/app/domain/providers/schemas.py` | OllamaModel, OllamaModelListResponse, ModelDetail |
| `backend/app/domain/agent_registry/schemas.py` | AgentPackageCreate, AgentPackageUpdate, AgentPackageResponse, AgentPackageListResponse, AgentPackageVersionResponse, AgentPackageLineageResponse |
| `backend/app/domain/workflows/schemas/composition_config.py` | WorkflowReference, WorkflowComposition, CompositionExecutionResult |
| `backend/app/domain/workflows/schemas/multi_agent_config.py` | AgentStep, MultiAgentConfig |
| `backend/app/domain/workflows/schemas/version_config.py` | WorkflowVersion, VersionCreate, VersionUpdate, VersionCompare, VersionResponse, VersionListResponse, VersionComparisonResult, ABTestConfig, ABTestCreate, ABTestUpdate, ABTestResult, ABTestResultRecord, ABTestResponse, ABTestListResponse, ABTestResultsSummary, ABTestComparison |
| `backend/app/domain/workflows/schemas/trigger_config.py` | WebhookConfig, ScheduleConfig, DatabaseTriggerConfig, WorkflowTrigger, WorkflowTriggerCreate, WorkflowTriggerUpdate, WorkflowTriggerResponse, TriggerExecutionResult |
| `backend/app/domain/workflows/services/orchestration_service.py` | WorkflowResult, MultiAgentExecuteRequest |
| `backend/app/domain/workflows/services/approval_service.py` | ApprovalRecord |

---

*Report generated by `scripts/dev/generate_factsheet_metrics.py`*