"""
Cognitive Pipeline — the central orchestrator.

The pipeline runs four composable components in sequence:
    1. Context Builder  → assembles execution context
    2. Agent Executor   → executes agent logic (LLM call + tools)
    3. Memory Manager   → stores/compacts conversation memory
    4. Response Formatter → formats the final output

Each component is resolved from its registry at runtime based on the
``PipelineConfig``, making the pipeline fully pluggable.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Mapping, Optional, Sequence

from .context_builder import (
    ContextBuilderRegistry,
    create_default_registry as _default_context_registry,
    run_context_builder,
)
from .executor import (
    ExecutorRegistry,
    create_default_registry as _default_executor_registry,
    run_executor,
)
from .memory_manager import (
    MemoryManagerRegistry,
    create_default_registry as _default_memory_registry,
    run_memory_manager,
)
from .vector_store import create_default_vector_store_registry
from app.domain.providers.embeddings import EmbeddingService
from .models import (
    AgentDescriptor,
    CognitiveMetrics,
    CognitiveResult,
    CognitiveTrace,
    MemoryDelta,
    PipelineConfig,
)
from .response_formatter import (
    ResponseFormatterRegistry,
    create_default_registry as _default_formatter_registry,
    run_response_formatter,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # the resolver's answer type — annotation only, so the pipeline stays light
    from app.domain.providers.capabilities import ServiceCandidate


def _finalize_metrics(metrics: CognitiveMetrics, trace: CognitiveTrace) -> CognitiveMetrics:
    """Populate metrics on ANY exit path (2026-08-13 — the dead-trace
    instrumentation fix; finding: Exa_dialog_03).

    Before this, duration/tokens were only set on the FULL SUCCESS
    path (pipeline.py:315-316) — every early return left metrics
    all-zeros. Now the trace's computed properties (which sum
    whatever components actually ran) feed the metrics on every
    return:

    - ``total_duration_ms`` / ``total_tokens`` — summed from the
      component traces that completed (a failed early stage still
      contributes its own duration).
    - ``llm_calls`` — 1 when the executor ran (the executor makes
      exactly one real LLM call per run; fallback attempts are
      separate). Failures before the executor leave it 0.
    - ``tool_calls`` / ``cache_hits`` — NO source exists in the
      cognitive pipeline today (executors call acompletion without
      ``tools=``; nothing reads cache info). They remain 0 by
      design — reserved for when the pipeline gains tool execution.
    """
    metrics.total_duration_ms = trace.total_duration_ms
    metrics.total_tokens = trace.total_tokens
    if trace.executor.strategy != "unknown":
        metrics.llm_calls = 1
    return metrics


class CognitivePipeline:
    """The cognitive pipeline orchestrator.

    Usage::

        pipeline = CognitivePipeline()
        result = await pipeline.run(
            user_message="Tell me about Newton",
            agent=agent_descriptor,
            session_history=[...],
        )
        print(result.response)
        print(result.trace.executor.duration_ms)
    """

    def __init__(
        self,
        context_builders: Optional[ContextBuilderRegistry] = None,
        executors: Optional[ExecutorRegistry] = None,
        memory_managers: Optional[MemoryManagerRegistry] = None,
        response_formatters: Optional[ResponseFormatterRegistry] = None,
        embedding: Optional[EmbeddingService] = None,
    ) -> None:
        self.context_builders = context_builders or _default_context_registry()
        self.executors = executors or _default_executor_registry()
        self.memory_managers = memory_managers or _default_memory_registry()
        self.response_formatters = response_formatters or _default_formatter_registry()
        # The embedding service is the CALLER's to resolve: this constructor is sync and holds no
        # session, exactly like `Context.capability_chains`. It is what the `turn` vector store embeds
        # with, and an unresolved one registers NO store — the recall step then skips, loudly, instead
        # of embedding with a model nobody configured (the service-literals arc's model half).
        self.vector_stores = create_default_vector_store_registry(embedding)

    async def run(
        self,
        user_message: str,
        agent: AgentDescriptor,
        session_history: Optional[List[dict]] = None,
        config: Optional[PipelineConfig] = None,
        memory_delta: Optional[MemoryDelta] = None,
        capability_chains: Optional[Mapping[str, Sequence["ServiceCandidate"]]] = None,
    ) -> CognitiveResult:
        """Execute the full cognitive pipeline.

        Args:
            user_message: The raw message from the user.
            agent: Descriptor of the agent being invoked.
            session_history: Previous turns in the session.
            config: Pipeline configuration (which strategies to use).
            memory_delta: Optional memory changes from a previous run.
            capability_chains: The chains the CALLER resolved, keyed by capability slug — this
                pipeline holds no database session, so it cannot resolve one and carries the caller's
                answer instead (see ``Context.capability_chains``).

        Returns:
            A ``CognitiveResult`` with the response, trace, metrics, and
            memory delta.
        """
        config = config or PipelineConfig()
        session_history = session_history or []
        trace = CognitiveTrace()
        metrics = CognitiveMetrics()

        # ------------------------------------------------------------------
        # 1. Context Builder
        # ------------------------------------------------------------------
        try:
            context_builder = self.context_builders.get(config.context_builder)
        except KeyError:
            return CognitiveResult(
                response="",
                trace=trace,
                metrics=_finalize_metrics(metrics, trace),
                error=(
                    f"Context builder '{config.context_builder}' not registered. "
                    f"Available: {', '.join(self.context_builders.list())}"
                ),
            )

        try:
            context, trace.context_builder = await run_context_builder(
                builder=context_builder,
                user_message=user_message,
                agent=agent,
                session_history=session_history,
                memory_delta=memory_delta,
            )
        except Exception as exc:
            return CognitiveResult(
                response="",
                trace=trace,
                metrics=_finalize_metrics(metrics, trace),
                error=f"ContextBuilder failed: {exc}",
            )

        # The chains THIS run was resolved with, keyed by capability. The CALLER resolved them (the
        # pipeline holds no session, so it cannot); the Context carries them to the components that need
        # one and have no session of their own — the memory manager above all (a registered singleton;
        # see `memory_manager._via_memory_chain`).
        if capability_chains:
            context.capability_chains.update(
                {key: tuple(chain) for key, chain in capability_chains.items()}
            )

        # ------------------------------------------------------------------
        # 1b. Cross-session memory recall
        # ------------------------------------------------------------------
        try:
            summaries = await self.memory_managers.get(
                config.memory_manager
            ).recall_summaries(agent=agent, max_count=5)
            if summaries:
                summary_text = "\n".join(
                    f"- {s}" for s in summaries
                )
                context.system_prompt += (
                    "\n\n[From previous conversations:"
                    f"\n{summary_text}"
                    "\n]"
                )
            # Also inject user facts
            try:
                facts = await self.memory_managers.get(
                    config.memory_manager
                ).recall_facts(agent=agent)
                if facts:
                    facts_text = "\n".join(f"- {f}" for f in facts)
                    context.system_prompt += (
                        "\n\n[Known facts about the user:"
                        f"\n{facts_text}"
                        "\n]"
                    )
            except Exception:
                pass
        except Exception:
            pass  # Non-critical — summaries are best-effort

        # ------------------------------------------------------------------
        # 1c. Vector memory recall
        # ------------------------------------------------------------------
        try:
            agent_folder = getattr(agent, "folder", None)
            if agent_folder:
                vs_name = config.vector_store or "turn"
                try:
                    vs = self.vector_stores.get(vs_name)
                except KeyError:
                    vs = None
                if vs is not None and hasattr(vs, "agent_folder"):
                    vs.agent_folder = agent_folder
                if vs is not None:
                    query = f"{context.user_message}"
                    vector_results = vs.search(query, top_k=3)
                    if vector_results:
                        vec_text = "\n".join(
                            f"[{r['role']}]: {r['content'][:200]} (relevance: {1 - r['distance']:.2f})"
                            for r in vector_results
                        )
                        context.system_prompt += (
                            "\n\n[Relevant past turns:]"
                            f"\n{vec_text}"
                            "\n[/Relevant past turns]"
                        )
        except Exception:
            pass  # Vector memory is best-effort

        # ------------------------------------------------------------------
        # 2. Agent Executor
        # ------------------------------------------------------------------
        try:
            executor = self.executors.get(config.executor)
        except KeyError:
            return CognitiveResult(
                response="",
                trace=trace,
                metrics=_finalize_metrics(metrics, trace),
                error=(
                    f"Executor '{config.executor}' not registered. "
                    f"Available: {', '.join(self.executors.list())}"
                ),
            )

        try:
            response, trace.executor = await run_executor(
                executor=executor,
                context=context,
                agent=agent,
            )
        except Exception as exc:
            # the LLM call was ATTEMPTED (and failed) — record it so
            # metrics count it and the trace carries the error +
            # strategy (run_executor raised before assigning the
            # component trace, so set the fields we know)
            trace.executor.strategy = type(executor).__name__
            trace.executor.error = str(exc)
            return CognitiveResult(
                response="",
                trace=trace,
                metrics=_finalize_metrics(metrics, trace),
                error=f"Executor failed: {exc}",
            )

        metrics.llm_calls = 1
        metrics.total_tokens = trace.executor.tokens_used

        # ------------------------------------------------------------------
        # 3. Memory Manager
        # ------------------------------------------------------------------
        try:
            memory_manager = self.memory_managers.get(config.memory_manager)
        except KeyError:
            return CognitiveResult(
                response=response,
                trace=trace,
                metrics=_finalize_metrics(metrics, trace),
                error=(
                    f"Memory manager '{config.memory_manager}' not registered. "
                    f"Available: {', '.join(self.memory_managers.list())}"
                ),
            )

        # Derive per-agent db_path if persistence is sqlite
        mem_db_path = None
        if config.memory_profile_persistence == "sqlite" and config.agent_folder:
            from app.core.config import Paths, get_settings
            mem_db_path = str(Paths.from_settings(get_settings()).agents_dir / config.agent_folder / "cognitive_memory.db")
            # If the manager supports db_path override, use it
            if hasattr(memory_manager, '_db_path'):
                memory_manager._db_path = mem_db_path
                memory_manager._is_deep = True
                # Reinitialize connection with new path
                memory_manager._init_db()

        try:
            memory_delta_result, trace.memory_manager = await run_memory_manager(
                manager=memory_manager,
                context=context,
                response=response,
                agent=agent,
                session_id=getattr(agent, 'session_id', None),
            )
        except Exception as exc:
            return CognitiveResult(
                response=response,
                trace=trace,
                metrics=_finalize_metrics(metrics, trace),
                error=f"MemoryManager failed: {exc}",
            )

        # ------------------------------------------------------------------
        # 4. Response Formatter
        # ------------------------------------------------------------------
        try:
            formatter = self.response_formatters.get(config.response_formatter)
        except KeyError:
            return CognitiveResult(
                response=response,
                trace=trace,
                metrics=_finalize_metrics(metrics, trace),
                memory_delta=memory_delta_result,
                error=(
                    f"Response formatter '{config.response_formatter}' not registered. "
                    f"Available: {', '.join(self.response_formatters.list())}"
                ),
            )

        try:
            formatted_response, trace.response_formatter = await run_response_formatter(
                formatter=formatter,
                response=response,
                context=context,
                agent=agent,
                trace=trace,
                metrics=metrics,
                memory_delta=memory_delta_result,
            )
        except Exception as exc:
            return CognitiveResult(
                response=response,
                trace=trace,
                metrics=_finalize_metrics(metrics, trace),
                memory_delta=memory_delta_result,
                error=f"ResponseFormatter failed: {exc}",
            )

        # ------------------------------------------------------------------
        # Aggregate metrics (ALL exit paths now finalize — 2026-08-13)
        # ------------------------------------------------------------------
        return CognitiveResult(
            response=formatted_response,
            trace=trace,
            metrics=_finalize_metrics(metrics, trace),
            memory_delta=memory_delta_result,
        )
