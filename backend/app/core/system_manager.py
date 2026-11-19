"""
System Manager Configuration.

Provides a self-contained configuration object for the system manager
(the system manager agent), eliminating the need for a database Agent record. The system manager
is not an "agent" in the traditional sense — it is a singleton orchestration
layer that dispatches to modes and resolves tools
multi-agent workflow.

Config may be loaded from the database at runtime (via ``from_db()``) so
that users can change the provider/model.  If no DB
record exists yet, the default code-level values are used.

Key constraint: No silent fallback to default LLM.  If the configured LLM is
unreachable, the system returns 503.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── System Manager Identity ───────────────────────────────────────────────────
# This is the default/fallback system prompt.
# Mode-specific prompts may override this at runtime.

SYSTEM_MANAGER_PROMPT = """\
You are the System Manager for the Cogitate application.

Your current task is to write and maintain the macro system — creating macro sets,
configuring meta topics, and ensuring macros are well-organized and useful.

## Your Capabilities

You can create, read, update, delete, and list:
- **macro-sets**: Collections of 5 prompt slots (F1-F5) organized by topic.
  Each slot contains a short prompt text inserted into the chat input when
  the user clicks the corresponding key.
- **meta-topics**: Hierarchical groupings that combine multiple macro sets
  into an extended keyboard layout (F1-F25+).

## Tools Available

- **file-display**: Display rich markdown content (reports, documentation,
  analysis, formatted output) to the user in a dedicated browser tab. The content
  is rendered with full markdown formatting. Use this when you want to show the
  user a clean, full-page view of generated content. Call it with `content`
  (required), optionally `header` text, a `filename` hint, and `footer_links`.
  The viewer URL opens automatically in a new tab on the frontend.

## General Operating Principles

These principles apply to ALL operations regardless of mode:

### 1. Always Explain Your Actions Verbally

Every time you call a tool, you MUST also produce conversational text explaining:
- What you are about to do (before calling the tool)
- What you found or what happened (after getting the result)
- Never make a tool call without accompanying text.

### 2. Pagination — Get Complete Results

When using action="list" to browse entities, the API returns paginated results
(default: 10 items per page). To see ALL items in one response, pass:
filters: {page_size: 100}

### 3. Coordinate with the User

Before making changes (create, update, delete), show the user your plan and
confirm. After completing an operation, summarize what was done.
"""


@dataclass
class SystemManagerConfig:
    """Self-contained configuration for the system manager.

    Replaces the need for a database Agent record. Values may be loaded from
    the DB at runtime (``from_db()``) or defaulted from code
    constants / application Settings.

    The system manager is a singleton orchestration layer:
    - It is NOT visible in agent listings
    - It is NOT selectable for normal agent chat
    - It is NOT modifiable via agent CRUD APIs
    - It operates purely from this config + mode registry + tool table

    Attributes:
        name: Display name for the system manager.
        provider: LLM provider — VESTIGIAL: no consumer reads it (see the field's own
            note). "Which provider answers?" is resolved per capability.
        model: LLM model name — VESTIGIAL, exactly like `provider`.
        system_prompt: Default system prompt. Mode-specific prompts in the
            mode registry may override this at runtime.
        parameters: Default model parameters (temperature, max_tokens, etc.).
            Mode-specific overrides may be applied at runtime.
        is_enabled: Whether the system manager agent is active.
        show_tool_output: Whether pass-through tool output events are sent
            to the frontend. When False, summaries are still injected into
            LLM context but no SSE ``tool_output`` events are yielded.
        allowed_tool_slugs: Tool slugs that the system manager is permitted
            to use. Populated at runtime from the active mode's tool_slugs
            configuration and/or a base set of built-in tools.
        embedding_batch_size: Batch size for embedding chunk sequences.
        doc_index_path: Filesystem path to the sqlite-vec vector index database.
        reindex_on_startup: Whether to automatically re-index documents on startup.
        tool_result_max_chars: Max characters for tool result truncation
            in stream service (replaces TOOL_RESULT_MAX_CHARS).
        step_preview_max_chars: Max characters for step result preview
            in planner (replaces STEP_RESULT_PREVIEW_MAX_CHARS).
        max_context_tokens: Token budget for conversation history selection
            (replaces DEFAULT_MAX_CONTEXT_TOKENS).
        max_step_retries: Max retries for planner steps
            (replaces MAX_STEP_RETRIES).
        llm_retry_count: LiteLLM retry count for LLM calls
            (replaces litellm.num_retries).
        llm_retry_delay_sec: LiteLLM retry delay in seconds
            (replaces litellm.retry_delay).
        max_iterations: Max execution iterations. 0 = auto
            (use formula max(5, steps+2)), positive int = fixed max.
        max_stack_depth: Maximum depth of the mode-stack. When exceeded,
            push attempts are rejected with a clear error message to the LLM.
        max_mode_switches_per_turn: Maximum number of mode-switches
            allowed per conversation turn. When exceeded, the system manager is forced
            into introspection mode and a critical warning is logged.
    """

    name: str = "System Manager"
    # VESTIGIAL (the capability arc's phase 4, C2): these two fields feed nothing —
    # every `SystemManagerConfig` consumer reads the RAG/embedding fields, and the
    # table that persisted them is retired. They used to default from
    # `Settings.default_llm_provider` / `Settings.default_llm_model`, whose code
    # defaults were the literals "ollama" and "llama3.2". Those literals are gone, and
    # the fields no longer borrow from Settings: "which provider?" is a capability's
    # answer now, never a config default.
    provider: str = ""
    model: str = ""
    system_prompt: str = SYSTEM_MANAGER_PROMPT
    parameters: Dict = field(
        default_factory=lambda: {
            "temperature": 0.1,
            "max_tokens": 8192,
            "top_p": 0.5,
        },
    )
    is_enabled: bool = True
    show_tool_output: bool = True
    allowed_tool_slugs: List[str] = field(default_factory=list)

    # --- Embedding / Semantic Search config ---
    # NO PROVIDER, MODEL OR DIMS HERE (the service-literals arc's model half, 2026-10-10). These three
    # fields used to carry `"ollama"`, `"nomic-embed-text"` and `768` as "code-level defaults", and
    # every RAG route LOADED them (`api/v1/rag/router.py::_load_config` → `defaults()`), so the
    # literal was the live value — three copies of a decision the `embeddings` capability now owns.
    # The same shape as `provider`/`model` above: "which service?" is a capability's answer, never a
    # config default. What stays here is what is genuinely this config's own: the batch size and
    # where the index lives.
    embedding_batch_size: int = 16
    doc_index_path: str = "data/system_docs_vector.db"
    reindex_on_startup: bool = False

    # --- Truncation / Context Budget ---
    tool_result_max_chars: int = 16000
    step_preview_max_chars: int = 16000
    max_context_tokens: int = 16000

    # --- Retry / Error Handling ---
    max_step_retries: int = 2
    llm_retry_count: int = 3
    llm_retry_delay_sec: int = 2

    # --- Iteration Limits ---
    # 0 = auto (use formula: max(5, steps+2)), positive int = fixed max
    max_iterations: int = 0

    # --- Mode-Stack Limits ---
    max_stack_depth: int = 3
    max_mode_switches_per_turn: int = 3

    @classmethod
    def defaults(cls) -> "SystemManagerConfig":
        """Return a new instance with all code-level defaults."""
        return cls()

    @classmethod
    def from_db(
        cls,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        is_enabled: Optional[bool] = None,
        show_tool_output: Optional[bool] = None,
        embedding_batch_size: Optional[int] = None,
        doc_index_path: Optional[str] = None,
        reindex_on_startup: Optional[bool] = None,
        # --- Truncation / Context Budget ---
        tool_result_max_chars: Optional[int] = None,
        step_preview_max_chars: Optional[int] = None,
        max_context_tokens: Optional[int] = None,
        # --- Retry / Error Handling ---
        max_step_retries: Optional[int] = None,
        llm_retry_count: Optional[int] = None,
        llm_retry_delay_sec: Optional[int] = None,
        # --- Iteration Limits ---
        max_iterations: Optional[int] = None,
        # --- Mode-Stack Limits ---
        max_stack_depth: Optional[int] = None,
        max_mode_switches_per_turn: Optional[int] = None,
    ) -> "SystemManagerConfig":
        """Build a config from DB values, falling back to defaults.

        Any ``None`` field is replaced with the default code-level value,
        ensuring the system always has valid configuration even if the DB
        record is missing or partially populated.
        """
        defaults = cls.defaults()
        # Merge DB parameters with defaults so missing keys (e.g. top_p)
        # are filled in even when partial parameters are persisted in the DB.
        merged_parameters: Dict[str, Any] = {}
        if parameters is not None:
            merged_parameters.update(defaults.parameters)
            merged_parameters.update(parameters)
        else:
            merged_parameters = defaults.parameters
        return cls(
            provider=provider if provider is not None else defaults.provider,
            model=model if model is not None else defaults.model,
            system_prompt=system_prompt if system_prompt is not None else defaults.system_prompt,
            parameters=merged_parameters,
            is_enabled=is_enabled if is_enabled is not None else defaults.is_enabled,
            show_tool_output=show_tool_output if show_tool_output is not None else defaults.show_tool_output,
            embedding_batch_size=embedding_batch_size if embedding_batch_size is not None else defaults.embedding_batch_size,
            doc_index_path=doc_index_path if doc_index_path is not None else defaults.doc_index_path,
            reindex_on_startup=reindex_on_startup if reindex_on_startup is not None else defaults.reindex_on_startup,
            # --- Truncation / Context Budget ---
            tool_result_max_chars=tool_result_max_chars if tool_result_max_chars is not None else defaults.tool_result_max_chars,
            step_preview_max_chars=step_preview_max_chars if step_preview_max_chars is not None else defaults.step_preview_max_chars,
            max_context_tokens=max_context_tokens if max_context_tokens is not None else defaults.max_context_tokens,
            # --- Retry / Error Handling ---
            max_step_retries=max_step_retries if max_step_retries is not None else defaults.max_step_retries,
            llm_retry_count=llm_retry_count if llm_retry_count is not None else defaults.llm_retry_count,
            llm_retry_delay_sec=llm_retry_delay_sec if llm_retry_delay_sec is not None else defaults.llm_retry_delay_sec,
            # --- Iteration Limits ---
            max_iterations=max_iterations if max_iterations is not None else defaults.max_iterations,
            # --- Mode-Stack Limits ---
            max_stack_depth=max_stack_depth if max_stack_depth is not None else defaults.max_stack_depth,
            max_mode_switches_per_turn=max_mode_switches_per_turn if max_mode_switches_per_turn is not None else defaults.max_mode_switches_per_turn,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict (for API responses)."""
        return {
            "name": self.name,
            "provider": self.provider,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "parameters": self.parameters,
            "is_enabled": self.is_enabled,
            "show_tool_output": self.show_tool_output,
            "embedding_batch_size": self.embedding_batch_size,
            "doc_index_path": self.doc_index_path,
            "reindex_on_startup": self.reindex_on_startup,
            # --- Truncation / Context Budget ---
            "tool_result_max_chars": self.tool_result_max_chars,
            "step_preview_max_chars": self.step_preview_max_chars,
            "max_context_tokens": self.max_context_tokens,
            # --- Retry / Error Handling ---
            "max_step_retries": self.max_step_retries,
            "llm_retry_count": self.llm_retry_count,
            "llm_retry_delay_sec": self.llm_retry_delay_sec,
            # --- Iteration Limits ---
            "max_iterations": self.max_iterations,
            # --- Mode-Stack Limits ---
            "max_stack_depth": self.max_stack_depth,
            "max_mode_switches_per_turn": self.max_mode_switches_per_turn,
        }
