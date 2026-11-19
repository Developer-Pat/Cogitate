---
title: Tool System
type: atlas-entity
path: wiki/entities/tool-system.md
confidence: medium
updated: 2026-08-05
tags: [type/entity, domain/entities]
---

# Tool System

## Overview

Tools give agents capabilities. Pattern: ToolDefinition →
ToolRegistry → builtin handlers → execution service.

## Components

- **ToolDefinition** + **ToolRegistry** (domain/tools/registry.py):
  register/get/list/execute + decorator. BuiltinToolRegistrar
  registers ~35 builtin handlers (builtin/ dir).
- **ToolExecutionService** (execution_service.py): resolve config →
  validate args → execute → ToolExecutionResult (to_llm_message /
  to_user_message).
- **ToolRegistryService / ToolCategoryService** (services.py): DB
  CRUD for tool records + categories.
- **AgentToolService**: per-agent enablement (agent_tools).
- **ToolPermissionService**: access control (per-tool +
  collection-scoped default_tool_permission).

## Details

See [[dev-notes/tools/tools-architecture]] for the full handler
catalog and [[dev-notes/tools/capability-error-handling]] for
error semantics.
