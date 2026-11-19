---
title: Agent Templates
type: atlas-page
path: frontend/src/pages/AgentTemplates.tsx
confidence: high
updated: 2026-09-25
tags: [type/page, domain/atlas-ui]
---
# Agent Templates

**Component**: `frontend/src/pages/AgentTemplates.tsx`
**Route**: `/agents/templates` (defined in `frontend/src/config/routes.ts`; `requiresAuth: true`, icon `template`, breadcrumb `Agent Templates`; lazy-loaded)
**Last Updated**: 2026-09-10

## Purpose

Standalone page for browsing, creating, and applying reusable agent templates. Templates capture a provider/model pair, system prompt, generation parameters, and — for the new agent architecture — a cognitive profile id, execution mode, and fallback/delegation flags, so users can spin up a pre-configured agent in one step. The page is read-heavy: it lists templates from the backend, lets users create new templates via a modal form, and applies a template to instantiate an agent (redirecting to the agent list on success).

## Key Features

- **Header with back navigation** — a "← Back to Agents" button navigates to `/agent-profiles`; page title set via `usePageTitle('Agent Templates', 'Browse and use agent templates')`.
- **Filter tabs (All / Public / Mine)** — a daisyUI `join` button group controlling the `filter` state; `All` and `Mine` send no filter param, `Public` adds `public=true` to the list request.
- **Server-side search** — the search input appends `search=<url-encoded>` to the list request; the list re-fetches whenever `filter` or `search` changes (effect deps).
- **Template card grid** — responsive 1/2/3-column grid; each card shows the template name, an optional 🌍 public badge, a 2-line-clamped description, badges for provider (primary), model (ghost), execution mode (secondary), and `profile #<id>` (info), up to 5 tags with a `+N` overflow badge, usage count, and created date.
- **Use Template modal** — prompts for agent name (required, prefilled with `<template name> Agent`) and an optional description; shows a read-only summary of provider / model / execution mode / cognitive profile; submits via the apply endpoint and navigates to `/agent-profiles` on success.
- **Create Template modal** — form with name (required), provider select (deepseek / openrouter / ollama / openai / anthropic), description, model, comma-separated tags, Execution Mode select (Hybrid / Shallow), Cognitive Profile select (Default plus ids 1–7: Conversational, Quick Response, Research Standard, Balanced Chat, Code Gen, Research Pro, System Admin), system prompt (required), and a "Make template public" checkbox.
- **Create defaults** — the create payload sends `fallback_enabled: true` and `allow_delegation: false`, and declares **no sampling and no budget**: `parameters` is not sent at all (this form has no sampling control, and a template that carried a pair would hand it to every agent created from it), and the budget's declaration is `llm_spec.max_output`, which this page does not set either. `behavior_config` and `preferred_providers` are not sent by this page.
- **Empty states** — a spinner while loading; a "No templates found / No templates available" empty state with a Create Template CTA (hidden while searching).
- **Feedback** — success/error toasts via `useNotificationStore.addNotification` (backend `detail` surfaced on error); all failures also recorded through `frontendLoggingService.error`.

## Components Used

The page is a single self-contained component — it imports no custom child components. All UI is inline JSX using daisyUI utility classes:

| Component | Path | Purpose |
|---|---|---|
| (none — self-contained) | — | Card grid, badges, `modal modal-open` + `modal-backdrop` overlays, `join` button group, alerts, and form controls are all inline daisyUI-styled JSX |
| `Helmet` | `react-helmet-async` (via `usePageTitle`) | Sets the document `<title>` and meta description |

## Hooks Used

| Hook | Path | Purpose |
|---|---|---|
| `useState` | `react` | Local state: `templates`, `loading`, `filter`, `search`, modal visibility (`showCreateModal`, `showUseModal`), `selectedTemplate`, agent name/description, and create-form fields |
| `useEffect` | `react` | Calls `loadTemplates()` on mount and whenever `filter` or `search` changes (eslint-disabled exhaustive-deps) |
| `useNavigate` | `react-router-dom` | Back-to-agents navigation and the post-apply redirect to `/agent-profiles` |
| `usePageTitle` | `frontend/src/hooks/usePageTitle.tsx` | Sets the document title via `formatPageTitle` and meta description; restores the previous title on unmount |

## Data Flow

1. **Loading templates (read path)**: `useEffect` → `loadTemplates()` builds `GET /api/v1/agents/templates?` plus `public=true` (Public tab) and/or `search=<encoded>` (search box). The `Mine` tab sends the same request as `All` — no owner-filter param is appended. The response (`{ templates: Template[], total }`) is stored in local state via `setTemplates(response.data?.templates || [])`.
2. **Creating a template (write path)**: create-modal form state → `handleCreateTemplate()` → `POST /api/v1/agents/templates` with the payload described above; on success a toast fires, the modal closes, the form resets (`resetCreateForm()` — which restores provider/model to `ollama`/`llama3.2`), and the list reloads.
3. **Applying a template (write path)**: `handleUseTemplate()` captures the clicked template and prefills the agent name; `handleConfirmUseTemplate()` → `POST /api/v1/agents/templates/{id}/apply` with `{name, description}` → success toast → `navigate('/agent-profiles')`. The backend increments the template's `usage_count`.
4. **Error handling**: every request failure logs via `frontendLoggingService.error(source='AgentTemplates', ...)` and shows an error toast whose message falls back to the backend `response.data.detail`.
5. **Transport**: all requests go through the `apiClient` singleton (`frontend/src/services/apiClient.ts`) — base URL from `VITE_API_URL` (default `http://localhost:8000`), JSON content type, `Authorization: Bearer <auth_token from localStorage>`, 10 s timeout, up to 3 retries with exponential backoff (429 honors `Retry-After`), and 401 clears auth and redirects to `/login`.

> **Source note**: the Execution Mode and Cognitive Profile selects in the create modal bind to `newTemplateMode` (default `'hybrid'`) and `newTemplateProfileId` (default `null`), and `handleCreateTemplate` posts them as `execution_mode` / `cognitive_profile_id`. (An earlier July-2026 note claimed these two state variables were undeclared and the page could not compile — they are declared now; that note is obsolete.) The list/detail endpoints also return `behavior_config`, `preferred_providers`, `fallback_enabled`, and `allow_delegation`, which this page does not send.

## State Management

| Store | Read/Write | Usage |
|---|---|---|
| `useNotificationStore` (`frontend/src/stores/notificationStore.ts`) | Write (`addNotification`) | Success/error toasts for load, create, and apply operations; auto-dismiss after `duration` (default 5000 ms) |
| (no other stores) | — | Templates, filters, search, and all form state are local `useState`; nothing is cached globally or shared with other pages |

## API Endpoints Called

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/agents/templates?public=&search=` | List templates with optional public and search filters (server-side, paginated) |
| POST | `/api/v1/agents/templates` | Create a new template from the modal form |
| POST | `/api/v1/agents/templates/{template_id}/apply` | Create an agent from a template (`{name, description}`); increments the template's `usage_count` |

Backend surface **not called by this page** (defined in `backend/app/api/v1/agents/templates_router.py`): `GET / PUT / DELETE /api/v1/agents/templates/{template_id}` (detail CRUD) and `POST /api/v1/agents/templates/from-agent/{agent_id}` (save an agent as a template — used by [[AgentProfiles]]).

## Related Pages

- [[AgentProfiles]] — the agent list page; back-navigation target, post-apply redirect destination, and host of the "save agent as template" flow (`from-agent` endpoint)
- [[CognitivePipeline]] — cognitive profiles are referenced by `template.cognitive_profile_id` and offered as select options in the create modal
- [[Dashboard]] — main navigation hub that links to this page
