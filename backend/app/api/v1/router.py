"""
API v1 router aggregator.

Combines all feature routers under the /api/v1 prefix.
"""

from fastapi import APIRouter

from app.api.v1.health.router import router as health_router
from app.api.v1.agents.router import router as agents_router
from app.api.v1.images_router import router as images_router
from app.api.v1.tts_router import router as tts_router
from app.api.v1.stt_router import router as stt_router
from app.api.v1.sounds_router import router as sounds_router
from app.api.v1.notifications_router import router as notifications_router
from app.api.v1.skills_router import router as skills_router
from app.api.v1.workflow_kinds_router import router as workflow_kinds_router
from app.api.v1.agents.provisioning_router import router as agents_provisioning_router
from app.api.v1.chat.router import router as chat_router
from app.api.v1.chat.title_router import router as chat_title_router
from app.api.v1.chat.attachments_router import router as chat_attachments_router
from app.api.v1.sessions.router import router as sessions_router
from app.api.v1.dashboard.router import router as dashboard_router
from app.api.v1.system.router import router as system_router
from app.api.v1.logs.router import router as logs_router
from app.api.v1.providers.router import router as providers_router
from app.api.v1.providers.management_router import router as provider_management_router
from app.api.v1.providers.completion_router import router as provider_completion_router
from app.api.v1.providers.config_router import router as provider_config_router
from app.api.v1.providers.usage_router import router as provider_usage_router
from app.api.v1.providers.scheduler_router import router as provider_scheduler_router
from app.api.v1.providers.occupancy_router import router as provider_occupancy_router
from app.api.v1.providers.models_router import router as provider_models_router
from app.api.v1.providers.capabilities_router import router as provider_capabilities_router
from app.api.v1.curated_models_router import router as curated_models_router
from app.api.v1.runtime_config.router import router as runtime_config_router
from app.api.v1.analytics.router import router as analytics_router
from app.api.v1.settings.router import router as settings_router
from app.api.v1.debug.router import router as debug_router
from app.api.v1.diagnostics.router import router as diagnostics_router
from app.api.v1.testing.router import router as testing_router
from app.api.v1.trash.router import router as trash_router
from app.api.v1.tools.router import router as tools_router
from app.api.v1.collections.router import router as collections_router
from app.api.v1.agent_packages.router import router as agent_packages_router
from app.api.v1.teams.router import router as teams_router
from app.api.v1.agent_lists.router import router as agent_lists_router
from app.api.v1.tool_permissions.router import router as tool_permissions_router
from app.api.v1.workflow_lists.router import router as workflow_lists_router
from app.api.v1.messaging.router import router as messaging_router

# Import Agent Chat (JSON Adapter) router
from app.api.v1.agent_chat.router import router as agent_chat_router
from app.api.v1.external_agent_router import router as external_agent_router

# Import workflow API routers (Phase 2)
from app.workflows.api.workflow_router import router as workflows_router
from app.workflows.api.template_router import router as templates_router
from app.workflows.api.multi_agent_router import router as multi_agent_router
from app.workflows.agent_versioning.api.router import router as workflow_agents_router

# Import workflow API routers (Phase 4A)
from app.workflows.api.composition_router import router as compositions_router
from app.workflows.api.approval_router import router as approvals_router

# Import workflow API routers (Phase 4B - Triggers)
from app.workflows.api.triggers_router import router as triggers_router
from app.workflows.api.webhooks_router import router as webhooks_router

# Import workflow API routers (Phase 4B - Versioning & A/B Testing)
from app.api.v1.versions_router import router as versions_router
from app.api.v1.ab_tests_router import router as ab_tests_router

from app.api.v1.wiki.router import router as wiki_router
from app.api.v1.knowledge.router import router as knowledge_router
from app.api.v1.setup.router import router as setup_router

router = APIRouter(prefix="/api/v1")

from app.api.v1.macros.router import router as macros_router
router.include_router(wiki_router)  # /api/v1/wiki/*
router.include_router(knowledge_router)  # /api/v1/knowledge/* (the expertise wiring)
router.include_router(macros_router)  # /api/v1/macros/*

# Include all feature routers
# Note: Order matters! More specific routes must be registered before dynamic routes
router.include_router(health_router)
router.include_router(setup_router)  # /api/v1/setup/readiness — the install's one verdict
router.include_router(settings_router)
router.include_router(agent_lists_router)  # Before agents_router (has /agent-lists routes)
router.include_router(agents_router)
router.include_router(images_router)
router.include_router(tts_router)
router.include_router(stt_router)
router.include_router(sounds_router)
router.include_router(notifications_router)  # /api/v1/notifications/config
router.include_router(skills_router)
router.include_router(workflow_kinds_router)
router.include_router(agents_provisioning_router)  # /api/v1/agents/{name}/provision
router.include_router(chat_router)
router.include_router(chat_title_router)  # Title service endpoints (/api/v1/chat/*)
router.include_router(chat_attachments_router)  # Attachment endpoints (/api/v1/chat/{session_id}/attachments)
router.include_router(sessions_router)
router.include_router(dashboard_router)
router.include_router(system_router)
router.include_router(testing_router)
router.include_router(trash_router)  # /api/v1/trash/* (the shelf registry's one surface)
router.include_router(logs_router)
router.include_router(debug_router)
router.include_router(diagnostics_router)
router.include_router(provider_config_router)  # Before providers_router (has /providers/config routes)
router.include_router(provider_usage_router)  # Before providers_router (has /providers/usage routes)
router.include_router(provider_occupancy_router)  # /providers/local/occupancy (the A3 read)
router.include_router(provider_scheduler_router)  # Before providers_router (has /providers/sync-schedule routes)
router.include_router(provider_management_router)  # Before providers_router (has /providers/managed routes)
router.include_router(provider_completion_router)  # Before providers_router (has /providers/health, /complete, etc.)
router.include_router(provider_models_router)  # Before providers_router (has /providers/{id}/models routes)
router.include_router(provider_capabilities_router)  # /providers/capabilities (the capability read-out)
router.include_router(providers_router)  # Has /{provider_id} dynamic route - must be last
router.include_router(curated_models_router)  # /curated-models - own prefix, no shadowing
router.include_router(runtime_config_router)
router.include_router(analytics_router)
router.include_router(tools_router)
router.include_router(collections_router)
router.include_router(agent_packages_router)  # /api/v1/agent-packages/* (the package blueprints)
router.include_router(teams_router)
router.include_router(tool_permissions_router)
router.include_router(workflow_lists_router)
router.include_router(messaging_router)  # /api/v1/messaging/* (the SSE bridge)

# Include Agent Chat (JSON Adapter) router
router.include_router(agent_chat_router)  # /api/v1/agent-chat/*

# Include External Agent (ACP side panel) router
router.include_router(external_agent_router)  # /api/v1/external-agent/*

# Include RAG API router
from app.api.v1.rag.router import rag_router
router.include_router(rag_router, prefix="/rag")

# Include workflow API routers (Phase 2)
# Note: Specific routes (templates, multi-agent) MUST be included before the
# generic workflows_router, otherwise /workflows/templates gets captured by
# /workflows/{workflow_id}/status.
router.include_router(templates_router)  # /api/v1/workflows/templates/* (specific)
router.include_router(multi_agent_router)  # /api/v1/workflows/multi-agent/* (specific)
router.include_router(workflows_router)  # /api/v1/workflows/* (generic — must be last)
router.include_router(workflow_agents_router)  # /api/v1/agents/* (agent versioning)

# Include workflow API routers (Phase 4A)
router.include_router(compositions_router)  # /api/v1/compositions/*
router.include_router(approvals_router)  # /api/v1/approvals/*

# Include workflow API routers (Phase 4B - Triggers)
router.include_router(triggers_router)  # /api/v1/triggers/*
router.include_router(webhooks_router)  # /api/v1/webhooks/*

# Include workflow API routers (Phase 4B - Versioning & A/B Testing)
router.include_router(versions_router)  # /api/v1/workflows/{template_id}/versions/*
router.include_router(ab_tests_router)  # /api/v1/ab-tests/*

# Import Cognitive Pipeline routers
from app.api.v1.cognitive_pipeline.memory_profiles import router as memory_profiles_router
from app.api.v1.cognitive_pipeline.cognitive_profiles import router as cognitive_profiles_router
from app.api.v1.cognitive_memory.router import memory_router
from app.api.v1.cognitive_vectors.router import router as vectors_router

# Include Cognitive Pipeline routers
router.include_router(memory_profiles_router)  # /api/v1/memory-profiles/*
router.include_router(cognitive_profiles_router)  # /api/v1/cognitive-profiles/*
router.include_router(memory_router)  # /api/v1/cognitive/memory/*
router.include_router(vectors_router)  # /api/v1/cognitive/vectors/*

# Include Agent Registry router (Phase 3)
from app.api.v1.agent_registry.router import router as agent_registry_router
router.include_router(agent_registry_router)  # /api/v1/agent-registry/*
