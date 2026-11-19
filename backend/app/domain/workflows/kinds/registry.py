"""Workflow kind registry — the canonical kind definitions (Phase A).

CODE-DEFINED by design (the hybrid decision, 2026-08-14): the kind's
BEHAVIOR lives here (builder_key → graph builder, input_schema as a
typed declaration). The DB `kinds` table is a CATALOG MIRROR for
browsing/UI — it is never the source of truth for how a kind runs.

Kinds are named for the PROCESS (verb + object), never a persona
(study page 01b, naming rule). A kind earns its place by
integrating into the system end-to-end (execute → history →
product → distribution → trigger).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class InputField:
    """One declared input of a kind's input schema."""
    name: str
    type: str  # string | number | boolean | array | object
    description: str = ""
    default: Any = None
    required: bool = False


@dataclass(frozen=True)
class WorkflowKind:
    """A canonical workflow kind (the general process shape).

    - builder_key: resolves to the graph builder via the dispatcher
      (Phase D makes it the single resolution path; today it names
      the existing builder).
    - product_type: what a completed execution delivers (the
      producer→consumer contract).
    - error_contract_name: the error behavior family — resolved via
      error_handling/taxonomy.contract_for() (Phase F).
    """
    name: str
    description: str
    builder_key: str
    product_type: str = "report"
    inputs: List[InputField] = field(default_factory=list)
    error_contract_name: str = "default"


# ── The canonical kind set (8) ────────────────────────────────────────
# Settled 2026-08-14: Simple stays a KIND (the safe default + the
# beginner template), not a degenerate Chain. Persona names are NOT
# kinds (file-clerk → File Processing; boss-agent → Batch
# Orchestration).

KIND_REGISTRY: Dict[str, WorkflowKind] = {
    "monitor": WorkflowKind(
        name="monitor",
        description=(
            "Watches something on a schedule (feeds, prices, system "
            "state), analyzes what changed, and delivers a report. "
            "The canonical kind — the flagship + E2E demonstration."
        ),
        builder_key="monitor_graph",
        product_type="report",
        error_contract_name="llm",
        inputs=[
            InputField("source_kind", "string",
                       "rss | market | readiness — picks the wiring"),
            InputField("schedule", "string",
                       "cron expression; empty = manual run", default=""),
        ],
    ),
    "file-processing": WorkflowKind(
        name="file-processing",
        description=(
            "Organizes and summarizes files: list, summarize, "
            "classify, and arrange them (the former 'file-clerk' — "
            "kinds are processes, not personas)."
        ),
        builder_key="file_clerk_graph",
        product_type="file",
        inputs=[
            InputField("directory", "string", "directory to process", required=True),
            InputField("mode", "string",
                       "clean | summarize | organize", default="organize"),
        ],
    ),
    "batch-orchestration": WorkflowKind(
        name="batch-orchestration",
        description=(
            "Runs many tasks in batches through a supervisor agent "
            "with parallel workers (the former 'boss-agent')."
        ),
        builder_key="boss_agent_graph",
        product_type="report",
    ),
    "multi-agent": WorkflowKind(
        name="multi-agent",
        description=(
            "Chains multiple agents in one workflow: each step names "
            "an agent, its tools, and the next step (Writer → Editor "
            "→ Critic; parallel workers)."
        ),
        builder_key="multi_agent_graph",
        product_type="report",
        error_contract_name="llm",
        inputs=[
            InputField("steps", "array",
                       "ordered agent steps (agent_id, input_key, tools)", required=True),
        ],
    ),
    "chain": WorkflowKind(
        name="chain",
        description=(
            "An LLM pipeline: ordered model calls, each consuming "
            "the previous output (summarize → compare → decide)."
        ),
        builder_key="advanced_graph",
        product_type="report",
        error_contract_name="llm",
        inputs=[
            InputField("chain_steps", "array",
                       "ordered LLM steps with prompts", required=True),
        ],
    ),
    "agent-task": WorkflowKind(
        name="agent-task",
        description=(
            "One agent, one goal: a single agent-execution step with "
            "declared input/output keys (the agent-testing demos' kind)."
        ),
        builder_key="agent_workflows",
        product_type="report",
        error_contract_name="llm",
        inputs=[
            InputField("agent_id", "string",
                       "which agent performs the task", required=True),
        ],
    ),
    "tag-survey": WorkflowKind(
        name="tag-survey",
        description=(
            "The FAN-OUT SURVEY (2026-08-23): surveys a corpus of "
            "files by dispatching bounded worker batches (each reads "
            "frontmatter + extracts tags) and collecting the rows "
            "into a manifest. The dispatcher is structural (no LLM); "
            "the workers are mechanical + bounded (the free Nemotron "
            "via OpenRouter); the collector assembles. The fix for "
            "the 'surveys forever, never delivers' single-agent loop."
        ),
        builder_key="tag_survey_graph",
        product_type="manifest",
        error_contract_name="llm",
        inputs=[
            InputField("directory", "string",
                       "the corpus directory (wiki/) to survey", required=True),
            InputField("worker_fn", "string",
                       "the worker node (dotted path); default = the tag extractor"),
            InputField("worker_model", "string",
                       "the worker LLM (default: the free Nemotron via OpenRouter)"),
        ],
    ),
    "context-indexing": WorkflowKind(
        name="context-indexing",
        description=(
            "Indexes documents/files into the context store for "
            "retrieval (RAG-adjacent)."
        ),
        builder_key="context_indexer_graph",
        product_type="index",
    ),
    "simple": WorkflowKind(
        name="simple",
        description=(
            "A single-step workflow — the safe default and the "
            "beginner's template. Chain of one, deliberately kept "
            "as its own kind (decision 2026-08-14)."
        ),
        builder_key="simple_graph",
        product_type="report",
    ),
    "system-audit": WorkflowKind(
        name="system-audit",
        description=(
            "Runs the system consistency audit and VERIFIES the "
            "result by re-running it (the read-back node) — the "
            "structural verification for unattended sanity checks."
        ),
        builder_key="system_audit_graph",
        product_type="report",
        error_contract_name="default",
        inputs=[
            InputField("schedule", "string",
                       "cron expression; empty = manual run", default=""),
        ],
    ),
}


def get_kind(name: str) -> Optional[WorkflowKind]:
    return KIND_REGISTRY.get(name)


def list_kinds() -> List[WorkflowKind]:
    return sorted(KIND_REGISTRY.values(), key=lambda k: k.name)


# ── Kind → graph factory (Phase D: the registry resolves graphs) ──────
# Kinds with ONE generic graph map kind → (module, factory_name).
# Kinds whose graphs are per-template (monitor's source variants,
# agent-task's per-agent graphs, multi-agent's per-config chains)
# are resolved via the legacy template table in the workflow router
# (Phase D keeps behavior identical; the kind model matures in F/G).

KIND_GRAPH_FACTORIES: Dict[str, tuple[str, str]] = {
    # kind_name: (module, factory)
    # agent-task: the GENERIC agent graph (the deep-agent-job — the
    # agent_invoke_node reads agent_id + the task from the config, so
    # ANY agent runs ANY task through the ReAct loop). Registered here
    # (the canonical path) NOT in the router's legacy per-template
    # table (the user's 'no legacy' call, 2026-08-23).
    "agent-task": ("app.workflows.graphs.agent_workflows", "create_agent_task_graph"),
    "file-processing": ("app.workflows.graphs.file_clerk_graph", "create_file_clerk_graph"),
    "batch-orchestration": ("app.workflows.graphs.boss_agent_graph", "create_boss_agent_graph"),
    "context-indexing": ("app.workflows.graphs.context_indexer_graph", "create_context_indexer_graph"),
    "tag-survey": ("app.workflows.graphs.tag_survey_graph", "create_tag_survey_graph"),
    "chain": ("app.workflows.graphs.advanced_workflow", "create_advanced_workflow"),
    "simple": ("app.workflows.graphs.simple_workflow", "create_simple_workflow"),
    "system-audit": ("app.workflows.graphs.system_audit_graph", "create_system_audit_graph"),
}


def resolve_kind_graph_factory(kind_name: str):
    """Lazily import + call the kind's graph factory (or None)."""
    entry = KIND_GRAPH_FACTORIES.get(kind_name)
    if not entry:
        return None
    module_name, factory_name = entry
    import importlib
    module = importlib.import_module(module_name)
    factory = getattr(module, factory_name)
    return factory



def error_contract_for(kind_name: str):
    """The kind's declared error contract (Phase F taxonomy)."""
    from app.workflows.error_handling.taxonomy import contract_for
    return contract_for(kind_name)
