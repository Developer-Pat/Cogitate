---
title: Tool Troubleshooting
type: atlas-devnote
category: tools
order: 3
confidence: stub
updated: 2026-09-10
tags: [type/dev-notes, domain/tools]
---

# Tool Troubleshooting

Checklist for tools that fail or misbehave.

## Quick checks

1. **Is the tool enabled for the agent?** — AgentToolService
   enable_tool_for_agent; check the agent's enabled tools.
2. **Is it permitted?** — ToolPermissionService.check_permission;
   collection-scoped permissions (default_tool_permission).
3. **Are arguments valid?** — execution_service._validate_arguments
   against the tool's JSON schema (llm_schema).
4. **Does the handler need external access?** — wikipedia/duckduckgo/
   jina need network; jina needs an API key; VPN can block (see
   providers-reference.md Groq quirk — same network layer).
5. **Is a store/service missing?** — sqlite_query needs the DB path;
   doc_vector_store needs the documents DB; code_vector_store needs
   the code index built.

## Verified failure modes (checked against current code)

1. **Tool not enabled for the agent** — `agent_tools` junction
   row missing/disabled → "not enabled for this agent" error.
   Fix: enable via the agent tools UI/API.
2. **Tool not in DB** — slug absent from `tools` table → "not
   found in database". Fix: registry sync (the startup
   verify_tool_invariants check logs missing slugs).
3. **Provider/tool execution failure** — handler error → visible
   tool message. Fix: inspect the error text; retry.
4. **RAG tools need their stores** — doc_reader needs the
   documents DB; doc_vector_store needs the vector index built
   (run `POST /api/v1/rag/ingest`); code_vector_store needs the
   code index. Missing stores → retrieval errors, not tool
   failures.
5. **DB-path issues** — tools that open SQLite directly fail if
   the path is wrong (check `data/*.db` existence).
