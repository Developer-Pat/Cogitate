---
tags: [type/dev-notes]
---

# Wiki Change Log

| Date | Action | Page | Notes |
|------|--------|------|-------|
| 2026-07-27 | created | SCHEMA.md, index.md, log.md | Wiki initialization |
| 2026-07-28 | created | backend-architecture | Entity page — backend structure and router layers |
| 2026-07-28 | created | agent-orchestration | Entity page — agent registry, pipeline, folders |
| 2026-07-28 | created | memory-system | Entity page — KVStore, facts, per-agent DBs |
| 2026-07-28 | created | chat-system | Entity page — stream handler, sessions, SSE |
| 2026-07-28 | created | conduit-routing | Entity page — SHALLOW/HYBRID routing modes |
| 2026-07-28 | created | provider-management | Entity page — providers, model caching |
| 2026-07-28 | created | tool-system | Entity page — registry, handlers, linking |
| 2026-07-28 | created | cognitive-profiles | Concept page — part codes, profile catalogue |
| 2026-07-28 | created | frontend-architecture | Entity page — stores, routing, components |
| 2026-07-28 | created | database-schema | Entity page — core tables, memory DBs |
| 2026-07-28 | created | configuration | Entity page — config surface, key paths |
| 2026-07-28 | created | workflow-system | Entity page — macros, meta-topics |
| 2026-07-28 | created | references/system-architecture.html | SVG architecture diagram |
| 2026-07-28 | created | references/agent-pipeline-flow.html | SVG pipeline flow diagram |
| 2026-07-28 | created | references/memory-architecture.html | SVG memory architecture diagram |
| 2026-07-28 | linked | entities/backend-architecture.md | Added diagram link to System Architecture |
| 2026-07-28 | linked | entities/agent-orchestration.md | Added diagram link to Pipeline Flow |
| 2026-07-28 | linked | entities/memory-system.md | Added diagram link to Memory Architecture |
| 2026-07-28 | moved | references/system-architecture.html → diagrams/ | Relocated diagram folder |
| 2026-07-28 | moved | references/agent-pipeline-flow.html → diagrams/ | Relocated diagram folder |
| 2026-07-28 | moved | references/memory-architecture.html → diagrams/ | Relocated diagram folder |
| 2026-07-28 | reverted | entities/backend-architecture.md | Removed diagram links per user preference |
| 2026-07-28 | reverted | entities/agent-orchestration.md | Removed diagram links per user preference |
| 2026-07-28 | reverted | entities/memory-system.md | Removed diagram links per user preference |
| 2026-07-29 | created | wiki/help/ | 11 help pages seeded | Phase 1 of help convergence |
| 2026-09-17 | created | wiki/dev-notes/frontend/streaming-render.md | The streaming render — the block-wise markdown path, its contract and its pitfalls | External developer reference; the arc's measurements stay in local/reports |
| 2026-09-17 | created | wiki/atlas/ui/components/BuildModeBadge.md, BuildModeSwitch.md | The two frontend builds — the `DEV`/`PROD` badge and the switch dialog | The switch page documents the entry-module detection |
| 2026-09-17 | created | wiki/dev-notes/lessons-learned/optimization-discipline.md | Measure before changing; a library's default configuration is often the slow one | New rule-class page |
| 2026-09-17 | updated | wiki/atlas/api/routers/system.md | Added `GET` and `POST /api/v1/system/mode`, with their contract | The endpoint was undocumented entirely |
| 2026-09-17 | updated | wiki/dev-notes/lifecycle/starting.md | The two frontend modes — the switch, the supervisor trap, and the badge | The modes live on the "Launching" page |
| 2026-09-17 | updated | wiki/help/dashboard.md, chat.md, sessions.md | The build-mode badge and switch; the History tab's ordering and inline delete; the bulk-delete labels | The in-app Help reads these files directly |
| 2026-09-17 | updated | wiki/dev-notes/frontend/tooltip-clipping.md | A clipping ancestor is not a clipped tip — and how to test which you have | Corrected: the page implied any scroll ancestor loses the tip |
| 2026-09-17 | updated | the UI atlas — pages/Dashboard, pages/AgentInteraction, components/features/agentInteraction/{AgentSelector, CognitiveIndicator, PromptHistoryList, ResponseStream, SessionManager}, stores/promptHistoryStore | The arc's UI changes, current-state | Validator ALL PASS before and after |
| 2026-09-19 | created | wiki/help/search.md, wiki/atlas/ui/components/features/agentInteraction/{NavSearchSection, NavSearchHotkey}.md | The nav sidebar's Search box — the verbs and their two landings, the local answers, the two mount components | Validator ALL PASS after |
| 2026-09-19 | renamed | wiki/dev-notes/frontend/ask-exa-command-box.md → wiki/dev-notes/frontend/command-box.md | The Command Box — the two surfaces: the nav sidebar's Search box is a navigator, the header flyout keeps the Exa path; one hook, one panel, one per-mount option (`exaFallthrough`); a Navigation section lists the command keys | Cross-references updated in wiki/dev-notes/frontend/Frontend Index.md, wiki/dev-notes/Dev Notes.md, wiki/dev-notes/frontend/navigation-routing.md, wiki/atlas/ui/components/features/agentInteraction/ExaPromptFlyout.md, wiki/atlas/ui/pages/AgentInteraction.md. Validator ALL PASS before and after |
| 2026-09-20 | created | wiki/help/testing.md | The Testing page's help — the tabs, what Run takes, the lock, what the counts mean, and where a deleted run goes | The page's Help button had no context page at all |
| 2026-09-20 | created | wiki/atlas/api/routers/testing.md | The `/api/v1/testing` surface: the derived catalog, the runs on disk, the lock's answer, the SSE event stream, and one run started/stopped/retired | Registered in atlas/api/API Atlas.md; the surface had no page before |
| 2026-09-20 | created | wiki/atlas/ui/hooks/useRunStream.md, wiki/atlas/ui/components/features/testing/{LiveRunPanel,DeleteRunModal}.md | The live feed's hook (raw EventSource, the terminal frame, why), the Run tab's panel, and the delete confirmation | Testing Index + Hooks Index updated; validator ALL PASS after |
| 2026-09-20 | updated | wiki/atlas/ui/pages/TestingDashboard.md | Rewritten to the page as it is: five tabs, Run/Cancel under the runner's lock, the live counts, delete-to-trash | It still described the DELETED simulation (TestSuiteManager/TestRunner, "no backend API calls") |
| 2026-09-20 | updated | wiki/dev-notes/testing/README.md | The four `events.jsonl` line kinds, the two sources for the collected total, the `ui` group's envelope-only gap, and delete-as-a-move | The runner-side authority for the page's data |
