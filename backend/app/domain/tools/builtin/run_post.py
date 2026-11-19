"""
Run POST (Power-On Self Test) Tool.

Provides the system manager with a proactive self-test capability that verifies its own
operational health across 10 checks in 4 tiers:

- **Tier 1 (Core Connectivity):** LLM provider, Database, API server health
- **Tier 2 (System Integrity):** Mode registry, Tool registry, SystemManagerConfig
- **Tier 3 (Self-Awareness):** ToolCallTracker state, iteration state,
  AutoDiagnosticsGuard state
- **Tier 4 (Peripheral):** RAG index health

Each check returns PASS / WARN / FAIL with evidence and suggestions.

Tags:
    - op:read
    - purpose:debug
    - source:system
    - safe
    - introspection
"""

from __future__ import annotations

import logging
from typing import Any, Dict


logger = logging.getLogger(__name__)


# ── Check ID Constants ─────────────────────────────────────────────────────

CHECK_LLM = "llm-connectivity"
CHECK_DATABASE = "database-access"
CHECK_API = "api-server-health"
CHECK_CONFIG = "system-config"
CHECK_TRACKER = "tool-call-tracker"
CHECK_ITERATIONS = "iteration-awareness"
CHECK_AUTO_DIAG = "auto-diagnostics-guard"
CHECK_RAG = "rag-index-health"

# Tiers
TIER_CONNECTIVITY = 1
TIER_INTEGRITY = 2
TIER_SELF_AWARENESS = 3
TIER_PERIPHERAL = 4

# ── Check Group Definitions ────────────────────────────────────────────────

CHECK_GROUPS: Dict[str, list[str]] = {
    "all": [
        CHECK_LLM, CHECK_DATABASE, CHECK_API,
        CHECK_CONFIG,
        CHECK_TRACKER, CHECK_ITERATIONS,
        CHECK_RAG,
    ],
    "connectivity": [CHECK_LLM, CHECK_DATABASE, CHECK_API],
    "self": [CHECK_TRACKER, CHECK_ITERATIONS],
}

# Map individual check shortcuts to their IDs
CHECK_SHORTCUTS: Dict[str, str] = {
    "llm": CHECK_LLM,
    "database": CHECK_DATABASE,
    "api": CHECK_API,
    "config": CHECK_CONFIG,
    "tracker": CHECK_TRACKER,
    "iterations": CHECK_ITERATIONS,
    "rag": CHECK_RAG,
}

ALL_CHECK_KEYS = set(CHECK_GROUPS["all"]) | set(CHECK_SHORTCUTS.keys()) | {"all", "connectivity", "self"}


def _resolve_checks(checks_param: Any) -> list[str]:
    """Resolve the ``checks`` parameter into a flat list of check IDs.

    Handles:
    - Single string: ``"all"``, ``"connectivity"``, ``"self"``, or an individual check name
    - List of strings: each element can be a group or individual check
    """
    if isinstance(checks_param, str):
        items = [checks_param]
    elif isinstance(checks_param, list):
        items = checks_param
    else:
        items = ["all"]

    resolved: list[str] = []
    for item in items:
        if item in CHECK_GROUPS:
            resolved.extend(CHECK_GROUPS[item])
        elif item in CHECK_SHORTCUTS:
            resolved.append(CHECK_SHORTCUTS[item])
        elif item in {CHECK_LLM, CHECK_DATABASE, CHECK_API,
                       CHECK_CONFIG,
                       CHECK_TRACKER, CHECK_ITERATIONS, CHECK_RAG}:
            resolved.append(item)
        else:
            logger.warning("Unknown check '%s' — skipping", item)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for c in resolved:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def _status_from_overall(overall: str) -> str:
    """Return a human-readable overall status string."""
    if overall == "pass":
        return "✅ All systems operational"
    elif overall == "warn":
        return "⚠️  Systems operational with warnings"
    else:
        return "❌ Systems degraded — action required"


# ═══════════════════════════════════════════════════════════════════════════════
# RunPostTool
# ═══════════════════════════════════════════════════════════════════════════════

class RunPostTool:
    """
    Power-On Self Test tool.

    The system manager runs this to verify its own operational health.
    Returns structured PASS/WARN/FAIL results for each check.

    Tags:
        - op:read
        - purpose:debug
        - source:system
        - safe
        - introspection
    """

    name: str = "Run POST"
    slug: str = "run-post"
    capability: str = "system-diag"
    description: str = (
        "Run a Power-On Self Test (POST) to check the system manager's own operational health "
        "across 10 checks in 4 tiers: connectivity, integrity, self-awareness, "
        "and peripheral systems. Returns structured PASS/WARN/FAIL results."
    )
    tags: list[str] = [
        "op:read",
        "purpose:debug",
        "source:system",
        "safe",
        "introspection",
    ]
    icon: str = "activity"
    color: str = "#28A745"  # Green — health check

    config_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {},
    }

    arguments_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "checks": {
                "oneOf": [
                    {
                        "type": "string",
                        "enum": [
                            "all",
                            "connectivity",
                            "self",
                            "llm",
                            "database",
                            "api",
                            "modes",
                            "tools",
                            "config",
                            "tracker",
                            "iterations",
                            "auto-diag",
                            "rag",
                        ],
                    },
                    {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "all",
                                "connectivity",
                                "self",
                                "llm",
                                "database",
                                "api",
                                "modes",
                                "tools",
                                "config",
                                "tracker",
                                "iterations",
                                "auto-diag",
                                "rag",
                            ],
                        },
                    },
                ],
                "description": (
                    "Which checks to run. "
                    "Use ``\"all\"`` for all 10 checks. "
                    "Use ``\"connectivity\"`` for Tier 1 (LLM, DB, API). "
                    "Use ``\"self\"`` for Tier 3 (tracker, iterations, auto-diag). "
                    "Or specify individual checks by name. "
                    "Default: ``\"all\"``."
                ),
            },
        },
        "required": ["checks"],
    }

    def __init__(self) -> None:
        """Initialize the POST tool.

        Internal state holders for injected runtime context (set by
        ``run_post_internal()``, not by the tool execution framework).
        """
        # Injected state for self-awareness checks (Tier 3)
        self._tracker: Any = None
        self._iteration: int = 0
        self._max_iterations: int = 5
        self._estimated_context_tokens: int = 0
        self._context_budget: int = 8000

    # ── Internal state injection (for stream engine integration) ──────────

    def inject_runtime_state(
        self,
        tracker: Any = None,
        iteration: int = 0,
        max_iterations: int = 5,
        estimated_context_tokens: int = 0,
        context_budget: int = 8000,
    ) -> None:
        """Inject runtime state for self-awareness checks.

        Called by ``run_post_internal()`` before executing checks so that
        Tier 3 checks can access the current ``ToolCallTracker`` and iteration
        state without requiring them as formal tool arguments.
        """
        self._tracker = tracker
        self._iteration = iteration
        self._max_iterations = max_iterations
        self._estimated_context_tokens = estimated_context_tokens
        self._context_budget = context_budget

    # ── Main execute ──────────────────────────────────────────────────────

    async def execute(
        self,
        config: Dict[str, Any],
        checks: Any = "all",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute the POST checks.

        Args:
            config: Tool configuration (unused by this tool).
            checks: Which checks to run — ``"all"`` (default),
                ``"connectivity"``, ``"self"``, or individual check names.
            **kwargs: Additional keyword arguments (may include injected
                state from ``run_post_internal()``).

        Returns:
            Dict with ``success``, ``summary`` (total/passed/warnings/failed/
            overall), and ``checks`` (list of individual check results).
        """
        # Accept injected state via kwargs (from run_post_internal())
        if "_tracker" in kwargs:
            self._tracker = kwargs["_tracker"]
        if "_iteration" in kwargs:
            self._iteration = kwargs["_iteration"]
        if "_max_iterations" in kwargs:
            self._max_iterations = kwargs["_max_iterations"]
        if "_estimated_context_tokens" in kwargs:
            self._estimated_context_tokens = kwargs["_estimated_context_tokens"]
        if "_context_budget" in kwargs:
            self._context_budget = kwargs["_context_budget"]

        # Resolve which checks to run
        check_ids = _resolve_checks(checks)
        if not check_ids:
            return {
                "success": False,
                "error": "No valid checks specified. Use ``\"all\"`` or one of: "
                         "connectivity, self, llm, database, api, modes, tools, "
                         "config, tracker, iterations, auto-diag, rag.",
            }

        # Dispatch to individual check methods
        check_dispatch: Dict[str, Any] = {
            CHECK_LLM: self._check_llm_connectivity,
            CHECK_DATABASE: self._check_database_access,
            CHECK_API: self._check_api_server_health,
            CHECK_CONFIG: self._check_system_config,
            CHECK_TRACKER: self._check_tool_call_tracker,
            CHECK_ITERATIONS: self._check_iteration_awareness,
                    CHECK_RAG: self._check_rag_index_health,
        }

        results: list[Dict[str, Any]] = []
        for check_id in check_ids:
            method = check_dispatch.get(check_id)
            if method is None:
                logger.warning("No handler for check '%s' — skipping", check_id)
                continue
            try:
                result = await method()
                results.append(result)
            except Exception as e:
                logger.error("POST check '%s' failed with exception: %s", check_id, e, exc_info=True)
                results.append({
                    "id": check_id,
                    "name": _check_name(check_id),
                    "tier": _check_tier(check_id),
                    "status": "fail",
                    "detail": f"Check threw an exception: {e}",
                    "evidence": "",
                    "suggestion": "Review the application logs for details.",
                })

        # Compute summary
        passed = sum(1 for r in results if r["status"] == "pass")
        warnings = sum(1 for r in results if r["status"] == "warn")
        failed = sum(1 for r in results if r["status"] == "fail")
        total = len(results)

        if failed > 0:
            overall = "fail"
        elif warnings > 0:
            overall = "warn"
        else:
            overall = "pass"

        return {
            "success": True,
            "summary": {
                "total": total,
                "passed": passed,
                "warnings": warnings,
                "failed": failed,
                "overall": overall,
                "status_text": _status_from_overall(overall),
            },
            "checks": results,
        }

    # ══════════════════════════════════════════════════════════════════════
    # Tier 1: Core Connectivity
    # ══════════════════════════════════════════════════════════════════════

    async def _check_llm_connectivity(self) -> Dict[str, Any]:
        """Check 1: LLM Provider Connectivity.

        Verifies that the system manager has a valid provider and model
        configured. Does NOT make an actual LLM call to avoid latency/cost.
        """
        # Read default provider config from the main database
        from app.core.database import AsyncSessionLocal
        from app.domain.providers.config_service import DefaultProviderService

        try:
            async with AsyncSessionLocal() as db:
                pcs = DefaultProviderService()
                pcfg = await pcs.get_default_provider(db)

            provider = pcfg.provider_type if pcfg else ""
            # THE MODEL COMES FROM THE ROW THAT ANSWERED (the capability arc's phase 4,
            # C1). This used to read `Settings.default_llm_model` — an env knob whose code
            # default was the literal "llama3.2" — so the evidence line could name a model
            # that was neither this row's model nor reachable.
            model = pcfg.default_model if pcfg else ""

            if not provider:
                return {
                    "id": CHECK_LLM,
                    "name": "LLM Provider Connectivity",
                    "tier": TIER_CONNECTIVITY,
                    "status": "fail",
                    "detail": "No LLM provider configured in SystemManagerConfig",
                    "evidence": "SystemManagerConfig.provider is empty",
                    "suggestion": "Configure a provider via the provider management UI or API.",
                }

            if not model:
                return {
                    "id": CHECK_LLM,
                    "name": "LLM Provider Connectivity",
                    "tier": TIER_CONNECTIVITY,
                    "status": "warn",
                    "detail": f"Provider '{provider}' configured but no model set",
                    "evidence": f"SystemManagerConfig: provider={provider}, model=(empty)",
                    "suggestion": "Set a default model for the provider.",
                }

            return {
                "id": CHECK_LLM,
                "name": "LLM Provider Connectivity",
                "tier": TIER_CONNECTIVITY,
                "status": "pass",
                "detail": f"Provider '{provider}' configured with model '{model}'",
                "evidence": f"SystemManagerConfig: provider={provider}, model={model}",
            }
        except Exception as e:
            return {
                "id": CHECK_LLM,
                "name": "LLM Provider Connectivity",
                "tier": TIER_CONNECTIVITY,
                "status": "fail",
                "detail": f"Failed to load system manager config: {e}",
                "evidence": str(e),
                "suggestion": "Check the application logs."
            }

    async def _check_database_access(self) -> Dict[str, Any]:
        """Check 2: Database Access.

        Verifies that the main app database is reachable and responding.
        """
        from sqlalchemy import func, select

        from app.core.database import AsyncSessionLocal

        issues: list[str] = []
        details: list[str] = []

        # Main database
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(select(func.now()))
            details.append("Main DB: healthy")
        except Exception as e:
            issues.append(f"Main DB: {e}")
            details.append("Main DB: unhealthy")

        if not issues:
            return {
                "id": CHECK_DATABASE,
                "name": "Database Access",
                "tier": TIER_CONNECTIVITY,
                "status": "pass",
                "detail": "; ".join(details),
                "evidence": "SQLAlchemy session query (SELECT now()) succeeded",
            }
        elif len(issues) < 2:
            return {
                "id": CHECK_DATABASE,
                "name": "Database Access",
                "tier": TIER_CONNECTIVITY,
                "status": "warn",
                "detail": "; ".join(details),
                "evidence": "; ".join(issues),
                "suggestion": "Check the failing database connection and logs.",
            }
        else:
            return {
                "id": CHECK_DATABASE,
                "name": "Database Access",
                "tier": TIER_CONNECTIVITY,
                "status": "fail",
                "detail": "; ".join(details),
                "evidence": "; ".join(issues),
                "suggestion": "Database unreachable. Check database server and connection configuration.",
            }

    async def _check_api_server_health(self) -> Dict[str, Any]:
        """Check 3: API Server Health.

        Calls the local health endpoint to verify the FastAPI backend is
        responding.
        """
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://localhost:8000/api/v1/health")
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "unknown")
                    if status == "healthy":
                        return {
                            "id": CHECK_API,
                            "name": "API Server Health",
                            "tier": TIER_CONNECTIVITY,
                            "status": "pass",
                            "detail": f"Health endpoint returned status='{status}'",
                            "evidence": f"GET /health -> {response.status_code}: {data}",
                        }
                    else:
                        return {
                            "id": CHECK_API,
                            "name": "API Server Health",
                            "tier": TIER_CONNECTIVITY,
                            "status": "warn",
                            "detail": f"Health endpoint returned non-healthy status: '{status}'",
                            "evidence": f"GET /health -> {response.status_code}: {data}",
                            "suggestion": "Check the application logs for service degradation.",
                        }
                else:
                    return {
                        "id": CHECK_API,
                        "name": "API Server Health",
                        "tier": TIER_CONNECTIVITY,
                        "status": "fail",
                        "detail": f"Health endpoint returned HTTP {response.status_code}",
                        "evidence": f"GET /health -> {response.status_code}",
                        "suggestion": "The backend may be partially down. Check application logs.",
                    }
        except ImportError:
            return {
                "id": CHECK_API,
                "name": "API Server Health",
                "tier": TIER_CONNECTIVITY,
                "status": "warn",
                "detail": "Cannot check: httpx not available",
                "evidence": "httpx library not installed",
                "suggestion": "Install httpx to enable API health checks.",
            }
        except Exception as e:
            return {
                "id": CHECK_API,
                "name": "API Server Health",
                "tier": TIER_CONNECTIVITY,
                "status": "fail",
                "detail": f"Cannot reach health endpoint: {e}",
                "evidence": str(e),
                "suggestion": "The backend server may not be running. Start with './cogitate.sh start'.",
            }

    # ══════════════════════════════════════════════════════════════════════
    # Tier 2: System Integrity
    # ══════════════════════════════════════════════════════════════════════



    async def _check_system_config(self) -> Dict[str, Any]:
        """Check 6: SystemManagerConfig.

        Verifies that a default provider is configured with valid provider/model.
        """
        from app.core.database import AsyncSessionLocal
        from app.domain.providers.config_service import DefaultProviderService

        try:
            async with AsyncSessionLocal() as db:
                pcs = DefaultProviderService()
                pcfg = await pcs.get_default_provider(db)

            if pcfg is None:
                return {
                    "id": CHECK_CONFIG,
                    "name": "Default Provider Config",
                    "tier": TIER_INTEGRITY,
                    "status": "warn",
                    "detail": "No default provider configured",
                    "evidence": "no provider marked as default in providers table",
                    "suggestion": "Set a default provider via the provider management UI or API.",
                }

            # The row's OWN model, not a Settings literal (C1 — see check 1).
            _default_model = pcfg.default_model
            issues: list[str] = []
            if not pcfg.provider_type:
                issues.append("provider is empty")
            if not _default_model:
                issues.append("model is empty")

            if issues:
                return {
                    "id": CHECK_CONFIG,
                    "name": "Default Provider Config",
                    "tier": TIER_INTEGRITY,
                    "status": "warn",
                    "detail": f"Provider config has issues: {'; '.join(issues)}",
                    "evidence": f"provider={pcfg.provider_type}, model={_default_model}",
                    "suggestion": "Set provider and model via the provider management UI or API.",
                }

            return {
                "id": CHECK_CONFIG,
                "name": "Default Provider Config",
                "tier": TIER_INTEGRITY,
                "status": "pass",
                "detail": f"Provider config valid: provider={pcfg.provider_type}, model={_default_model}",
                "evidence": f"default provider: {pcfg.provider_type}, model={_default_model}",
            }
        except Exception as e:
            return {
                "id": CHECK_CONFIG,
                "name": "Default Provider Config",
                "tier": TIER_INTEGRITY,
                "status": "fail",
                "detail": f"Failed to read provider config: {e}",
                "evidence": str(e),
                "suggestion": "Check the providers table and database connection.",
            }

    # ══════════════════════════════════════════════════════════════════════
    # Tier 3: Self-Awareness
    # ══════════════════════════════════════════════════════════════════════

    async def _check_tool_call_tracker(self) -> Dict[str, Any]:
        """Check 7: Tool Call Tracker State.

        Examines the ToolCallTracker for consecutive repeats, total calls,
        and potential loops.
        """
        tracker = self._tracker
        if tracker is None:
            return {
                "id": CHECK_TRACKER,
                "name": "Tool Call Tracker State",
                "tier": TIER_SELF_AWARENESS,
                "status": "warn",
                "detail": "ToolCallTracker not available (not in streaming context)",
                "evidence": "No tracker instance injected",
                "suggestion": "Run POST from within a streaming session for tracker data.",
            }

        try:
            consecutive = dict(tracker.consecutive_counts)  # type: ignore[union-attr]
            total_calls = dict(tracker.total_calls)  # type: ignore[union-attr]

            # Find tools with high consecutive calls
            high_consecutive = {
                tool: count for tool, count in consecutive.items()
                if count >= 2
            }

            if high_consecutive:
                worst_tool = max(high_consecutive, key=lambda k: high_consecutive[k])  # type: ignore[arg-type]
                worst_count = high_consecutive[worst_tool]
                return {
                    "id": CHECK_TRACKER,
                    "name": "Tool Call Tracker State",
                    "tier": TIER_SELF_AWARENESS,
                    "status": "fail" if worst_count >= 3 else "warn",
                    "detail": f"Tool '{worst_tool}' called {worst_count} times consecutively. "
                              f"Total calls by tool: {total_calls}",
                    "evidence": f"ToolCallTracker: consecutive_counts={consecutive}, total_calls={total_calls}",
                    "suggestion": (
                        "You are in a potential loop. "
                        "Try switching to a different tool or responding without tool calls."
                    ),
                }

            return {
                "id": CHECK_TRACKER,
                "name": "Tool Call Tracker State",
                "tier": TIER_SELF_AWARENESS,
                "status": "pass",
                "detail": f"No consecutive repeats detected. Total calls by tool: {total_calls}",
                "evidence": f"ToolCallTracker: consecutive_counts={consecutive}, total_calls={total_calls}",
            }
        except Exception as e:
            return {
                "id": CHECK_TRACKER,
                "name": "Tool Call Tracker State",
                "tier": TIER_SELF_AWARENESS,
                "status": "fail",
                "detail": f"Failed to read ToolCallTracker state: {e}",
                "evidence": str(e),
                "suggestion": "Check the ToolCallTracker implementation for errors.",
            }

    async def _check_iteration_awareness(self) -> Dict[str, Any]:
        """Check 8: Iteration State.

        Reports the current iteration progress and estimated context usage.
        """
        try:
            current = self._iteration
            maximum = self._max_iterations
            context_tokens = self._estimated_context_tokens
            context_budget = self._context_budget

            if maximum <= 0:
                return {
                    "id": CHECK_ITERATIONS,
                    "name": "Iteration State",
                    "tier": TIER_SELF_AWARENESS,
                    "status": "warn",
                    "detail": "Iteration state indicates no max iterations configured",
                    "evidence": f"_max_iterations={maximum}",
                    "suggestion": "This is unusual. Check the stream engine configuration.",
                }

            context_pct = (context_tokens / context_budget * 100) if context_budget > 0 else 0

            # Determine status
            is_last_iteration = current >= maximum
            context_critical = context_pct > 90

            if is_last_iteration or context_critical:
                return {
                    "id": CHECK_ITERATIONS,
                    "name": "Iteration State",
                    "tier": TIER_SELF_AWARENESS,
                    "status": "fail" if is_last_iteration else "warn",
                    "detail": (
                        f"Iteration {current}/{maximum}, "
                        f"estimated context: {context_tokens} tokens ({context_pct:.0f}% of {context_budget})"
                    ),
                    "evidence": f"iteration={current}, max_iterations={maximum}, context_tokens={context_tokens}, context_budget={context_budget}, context_pct={context_pct:.1f}%",
                    "suggestion": (
                        "You are near or at the iteration limit. "
                        "Consider wrapping up the current task or requesting mode continuation."
                        if is_last_iteration else
                        "Context usage is high. Consider summarizing or trimming context."
                    ),
                }
            elif current >= maximum - 1 or context_pct > 70:
                return {
                    "id": CHECK_ITERATIONS,
                    "name": "Iteration State",
                    "tier": TIER_SELF_AWARENESS,
                    "status": "warn",
                    "detail": (
                        f"Iteration {current}/{maximum}, "
                        f"estimated context: {context_tokens} tokens ({context_pct:.0f}% of {context_budget})"
                    ),
                    "evidence": f"iteration={current}, max_iterations={maximum}, context_tokens={context_tokens}, context_budget={context_budget}, context_pct={context_pct:.1f}%",
                    "suggestion": "You have limited iterations remaining. Prioritize completing the current task.",
                }
            else:
                return {
                    "id": CHECK_ITERATIONS,
                    "name": "Iteration State",
                    "tier": TIER_SELF_AWARENESS,
                    "status": "pass",
                    "detail": (
                        f"Iteration {current}/{maximum}, "
                        f"estimated context: {context_tokens} tokens ({context_pct:.0f}% of {context_budget})"
                    ),
                    "evidence": f"iteration={current}, max_iterations={maximum}, context_tokens={context_tokens}, context_budget={context_budget}, context_pct={context_pct:.1f}%",
                }
        except Exception as e:
            return {
                "id": CHECK_ITERATIONS,
                "name": "Iteration State",
                "tier": TIER_SELF_AWARENESS,
                "status": "fail",
                "detail": f"Failed to read iteration state: {e}",
                "evidence": str(e),
                "suggestion": "Check the stream engine's iteration tracking.",
            }

    async def _check_rag_index_health(self) -> Dict[str, Any]:
        """Check 10: RAG Index Health.

        Checks whether the document/RAG index is accessible and populated.
        """
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "http://localhost:8000/api/v1/doc-index/status"
                )

                if response.status_code == 200:
                    data = response.json()
                    doc_count = data.get("indexed_documents", data.get("document_count", 0))
                    last_indexed = data.get("last_indexed", data.get("last_updated", "unknown"))

                    if doc_count and doc_count > 0:
                        return {
                            "id": CHECK_RAG,
                            "name": "RAG Index Health",
                            "tier": TIER_PERIPHERAL,
                            "status": "pass",
                            "detail": f"Document index has {doc_count} documents (last indexed: {last_indexed})",
                            "evidence": f"GET /api/v1/doc-index/status -> {data}",
                        }
                    else:
                        return {
                            "id": CHECK_RAG,
                            "name": "RAG Index Health",
                            "tier": TIER_PERIPHERAL,
                            "status": "warn",
                            "detail": "Document index is accessible but has 0 documents",
                            "evidence": f"GET /api/v1/doc-index/status -> {data}",
                            "suggestion": "Run the document ingestion script to populate the index.",
                        }
                elif response.status_code == 404:
                    return {
                        "id": CHECK_RAG,
                        "name": "RAG Index Health",
                        "tier": TIER_PERIPHERAL,
                        "status": "warn",
                        "detail": "Document index endpoint not found (404)",
                        "evidence": "GET /api/v1/doc-index/status returned 404",
                        "suggestion": "The doc-index endpoint may not be registered in the router.",
                    }
                else:
                    return {
                        "id": CHECK_RAG,
                        "name": "RAG Index Health",
                        "tier": TIER_PERIPHERAL,
                        "status": "fail",
                        "detail": f"Document index endpoint returned HTTP {response.status_code}",
                        "evidence": f"GET /api/v1/doc-index/status -> {response.status_code}",
                        "suggestion": "Check the doc-index service and application logs.",
                    }
        except ImportError:
            return {
                "id": CHECK_RAG,
                "name": "RAG Index Health",
                "tier": TIER_PERIPHERAL,
                "status": "warn",
                "detail": "Cannot check RAG index: httpx not available",
                "evidence": "httpx library not installed",
                "suggestion": "Install httpx to enable RAG health checks.",
            }
        except Exception as e:
            return {
                "id": CHECK_RAG,
                "name": "RAG Index Health",
                "tier": TIER_PERIPHERAL,
                "status": "warn",
                "detail": f"Cannot reach document index endpoint: {e}",
                "evidence": str(e),
                "suggestion": "The document index API may not be running. This is non-critical.",
            }


# ═══════════════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════════════

_CHECK_NAMES: Dict[str, str] = {
    CHECK_LLM: "LLM Provider Connectivity",
    CHECK_DATABASE: "Database Access",
    CHECK_API: "API Server Health",
    CHECK_CONFIG: "SystemManagerConfig",
    CHECK_TRACKER: "Tool Call Tracker State",
    CHECK_ITERATIONS: "Iteration State",
    CHECK_RAG: "RAG Index Health",
}

_CHECK_TIERS: Dict[str, int] = {
    CHECK_LLM: TIER_CONNECTIVITY,
    CHECK_DATABASE: TIER_CONNECTIVITY,
    CHECK_API: TIER_CONNECTIVITY,
    CHECK_CONFIG: TIER_INTEGRITY,
    CHECK_TRACKER: TIER_SELF_AWARENESS,
    CHECK_ITERATIONS: TIER_SELF_AWARENESS,
    CHECK_RAG: TIER_PERIPHERAL,
}


def _check_name(check_id: str) -> str:
    """Return the human-readable name for a check ID."""
    return _CHECK_NAMES.get(check_id, check_id)


def _check_tier(check_id: str) -> int:
    """Return the tier number for a check ID."""
    return _CHECK_TIERS.get(check_id, 0)
