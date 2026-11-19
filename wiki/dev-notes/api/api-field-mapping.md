---
title: API Field Mapping
type: atlas-devnote
category: api
order: 2
confidence: stub
updated: 2026-08-05
tags: [type/dev-notes, domain/api]
---

# API Field Mapping

Frontend↔backend field naming conventions across the API
(create/update schemas, response DTOs, camelCase vs snake_case
transforms in the frontend services).

## Canonical mapping rules

- **Pydantic response DTOs**: routers return `XxxResponse.model_validate(orm)` —
  the schema is the API contract (agents router: AgentResponse,
  etc.). DB column names map to schema fields by ORM attribute.
- **Naming**: backend snake_case (DB + Pydantic), frontend
  camelCase in services/stores; the apiClient applies transforms
  where needed (no global auto-transform — verify per service).
- **Rule of thumb**: check the response schema for the field name;
  check the frontend service for any explicit transform; when in
  doubt, the API docs (/openapi.json) are the source of truth.fore inclusion.
