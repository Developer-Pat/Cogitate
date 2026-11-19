"""
Agent domain schemas.

Pydantic schemas for agent request/response validation.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.domain.providers.availability import STATE_UNKNOWN
from app.services.cognitive_pipeline.output_budget import BUDGET_CEILING

logger = logging.getLogger(__name__)


# THE MODEL PARAMETERS (G-I) — the sampling settings, as a SHAPE rather than a
# convention. This is what replaced the hand-written guard that refused
# `parameters.max_tokens`: a shape cannot go stale, and it refuses the NEXT stray key
# (a typo, a retired field, a client inventing one) without anyone writing a rule for
# it. The budget is NOT here — it is `llm_spec.max_output`, the field the resolver
# reads.


class AgentParameters(BaseModel):
    """The sampling settings an agent (or a template) may carry.

    `extra="forbid"` is the guard. Nothing else is a sampling setting we support, and
    a field nobody reads must not be storable: that is exactly how a retired key
    survives in a row for months.
    """

    model_config = ConfigDict(extra="forbid")

    # THE BOUNDS — here, and nowhere else. Every request validator below refuses
    # through THIS model, and the internal copy paths validate through it too, so a
    # range only ever has one home to change. The sibling surface already reads its own
    # bounds off its own model the same way (`runtime_config.schemas.RuntimeConfigBase`,
    # the same pair of numbers, on a session override); the AGENT's own sampling had
    # none, which is why the API accepted `temperature: 3.0`, `-1.0` and `top_p: 1.5`
    # and stored them. A value outside the range is refused by name, with a log line.
    temperature: Optional[float] = Field(
        None, ge=0, le=2, description="Sampling temperature (0-2)"
    )
    top_p: Optional[float] = Field(
        None, ge=0, le=1, description="Nucleus sampling probability (0-1)"
    )


# DERIVED from the model, never listed a second time: the request validators below
# name what is unknown against this set, so adding a sampling setting is a one-line
# change in the model and nothing else moves.
PARAMETER_KEYS = tuple(AgentParameters.model_fields)


def _refuse_unknown_parameters(payload: Any) -> Any:
    """Refuse an unknown parameter key — and WRITE IT DOWN (G-I).

    Two halves, and the second is the one usually missing: the request is refused
    (a guard that lets a typo through is not a guard), and the refusal is logged as an
    ERROR naming the key — so a client still sending a retired or misspelled field
    leaves a record instead of a 422 nobody reads.

    Deliberately generic: it names whatever is unknown, so the next stray needs no new
    rule here. An error line per refused request is the point (a first, loud, cheap
    signal), not noise to be rate-limited away.
    """
    if not isinstance(payload, dict):
        return payload
    unknown = sorted(set(payload) - set(PARAMETER_KEYS))
    if not unknown:
        return payload
    logger.error(
        "🚫 REFUSED model parameters: unknown key(s) %s — an agent's parameters carry "
        "%s only; the output budget is llm_spec.max_output (G-I). Refused at the door "
        "rather than stored as a value nothing reads.",
        ", ".join(unknown), " + ".join(PARAMETER_KEYS),
    )
    raise ValueError(
        f"unknown model parameter key(s): {', '.join(unknown)} — allowed: "
        f"{', '.join(PARAMETER_KEYS)} (the output budget is llm_spec.max_output)"
    )


def _refuse_out_of_range_parameters(payload: Any) -> Any:
    """Refuse a sampling value outside the model's own bound.

    The bound is NOT restated here: it is read off `AgentParameters`, so `ge`/`le` on
    that model is the one place a range lives. What this adds is the door — the
    refusal is by NAME, and it is logged as an ERROR like the unknown-key one, so a
    client sending `temperature: 3.0` leaves a record instead of a value in a row.
    """
    if not isinstance(payload, dict) or not payload:
        return payload
    try:
        AgentParameters.model_validate(payload)
    except ValidationError as exc:
        named = "; ".join(
            f"{'.'.join(str(part) for part in err['loc']) or 'value'}: {err['msg']}"
            for err in exc.errors()
        )
        logger.error(
            "🚫 REFUSED model parameters: %s — temperature is 0-2 and top_p is 0-1 "
            "(the bounds on AgentParameters).",
            named,
        )
        raise ValueError(f"model parameter out of range: {named}") from exc
    return payload


def _refuse_unusable_parameters(payload: Any) -> Any:
    """The door, both halves: a key nothing reads, then a value out of its bound.

    One entry point so a request schema and an internal copy path cannot end up
    carrying different halves of the same rule.
    """
    _refuse_unknown_parameters(payload)
    _refuse_out_of_range_parameters(payload)
    return payload


def checked_parameters(payload: Any) -> Optional[Dict[str, Any]]:
    """The parameters a ROW may carry, validated through the model (G-I).

    For the internal COPY paths — a template's parameters onto a new agent, an
    agent's onto a template — which write the JSON column directly and never meet a
    request schema. A row carrying an unknown key, or an out-of-range value, is refused
    here by name and with a log line, instead of being copied forward: a legacy row is
    a thing to fix, not a thing to propagate into every agent someone creates from it.

    NOTHING DECLARED IS `None`: an empty result and an absent one mean the same thing to
    every reader, so the column stores one shape for "declares nothing" rather than two.
    """
    _refuse_unusable_parameters(payload)
    checked = AgentParameters.model_validate(payload or {}).model_dump(exclude_none=True)
    return checked or None


def _check_budget_ceiling(llm_spec: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Refuse a stored output budget above the DERIVED ceiling (F.2, D3).

    D3's purpose is a typo guard — `200000` must not reach a provider — and no surface
    carries its own copy of the bound: the ceiling is `output_budget.BUDGET_CEILING`,
    derived from the type table. The budget is `llm_spec.max_output` (G-I): the field
    the resolver reads, which is why the bound is applied there and nowhere else. A
    missing or unreadable value is left alone, because the resolver already treats an
    unreadable number as undeclared and this is not a second interpreter of the field.

    Applied to the REQUEST schemas only: a legacy row that already stores a bigger
    number must still be readable (agent responses inherit `AgentBase`).
    """
    if not llm_spec or "max_output" not in llm_spec:
        return llm_spec
    raw = llm_spec.get("max_output")
    if raw is None or isinstance(raw, bool):
        return llm_spec
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return llm_spec
    if value < 1:
        raise ValueError(
            f"llm_spec.max_output={raw!r} is not a sendable budget (minimum 1)"
        )
    if value > BUDGET_CEILING:
        raise ValueError(
            f"llm_spec.max_output={value} is above the budget ceiling "
            f"({BUDGET_CEILING}, derived from the type table — "
            f"output_budget.BUDGET_CEILING)"
        )
    return llm_spec


class AgentBase(BaseModel):
    """Base agent schema with common fields."""

    name: str = Field(..., min_length=1, max_length=100, description="Agent name")
    description: Optional[str] = Field(
        default=None, max_length=500, description="Agent description"
    )
    provider: str = Field(..., description="LLM provider (e.g., ollama, openai)")
    model: str = Field(..., description="Model name (e.g., llama3.2, gpt-4)")
    system_prompt: Optional[str] = Field(
        default=None, max_length=5000, description="System prompt for the agent"
    )
    is_active: bool = Field(default=True, description="Whether agent is active")
    is_builtin: bool = Field(
        default=False, description="Whether this is a system-built-in agent (protected from deletion)"
    )

    # Model parameters
    parameters: Optional[Dict[str, Any]] = Field(
        # NOTHING IS DECLARED BY DEFAULT. This factory used to write
        # `{"temperature": 0.7, "top_p": 0.9}`, which put a value nobody chose on every
        # create that omitted the field — and every API create omits it, so an external
        # agent could not create an agent that declares no sampling at all. Omitted now
        # stores nothing: the row carries no sampling, the turn sends no sampling
        # setting, and the provider's own default applies (`runtime_config/sampling.py`).
        default=None,
        description="Model parameters (temperature, top_p) — absent means this agent declares no sampling"
    )

    # Template reference
    template_id: Optional[str] = Field(
        default=None, description="Reference to system prompt template"
    )

    # Provider preferences (ordered list for fallback)
    preferred_providers: Optional[list[str]] = Field(
        default=None,
        description="Ordered list of preferred providers for fallback"
    )
    fallback_enabled: bool = Field(
        default=False,
        description=(
            "Enable automatic fallback to next provider on failure. "
            "Opt-in (F4): default False so failures surface visibly — "
            "fallback must never silently mask a broken provider/model."
        )
    )

    # Delegation
    allow_delegation: bool = Field(
        default=True,
        description="Whether this agent can receive delegated tasks from other agents"
    )

    # Execution mode (see SIMULATED_AGENT_DESIGN.md §2.2)
    # "llm" (default) | "simulated" | "hybrid"
    execution_mode: str = Field(
        default="llm",
        description="Execution mode: llm (standard), simulated (programmatic), or hybrid",
    )

    # Behavior config (JSON, engine-specific — see SIMULATED_AGENT_DESIGN.md §3.1)
    behavior_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Behavior configuration for simulated/hybrid agents (rules, templates, etc.)",
    )

    # Cognitive profile assignment
    cognitive_profile_id: Optional[int] = Field(
        default=None,
        description="ID of the CognitiveProfile assigned to this agent",
    )

    # THE PROFILE READOUT (2026-09-06 — the ProfileDetail chip was a
    # hardcoded 'deep' for ANY agent with a workspace; the UI must show
    # the truth). The depth family is derived server-side via the ONE
    # canonical map (selection_service.depth_family).
    cognitive_profile_name: Optional[str] = Field(
        default=None,
        description="The cognitive profile's name (chat-skill, research-pro, ...)",
    )
    cognitive_profile_depth: Optional[str] = Field(
        default=None,
        description="The cognitive-profile depth family: deep (memory/pipeline), "
        "shallow (lean), or balanced — None when no profile",
    )

    # Skills (Phase F — the ARM card's COMPETENCE axis)
    skills: Optional[List[str]] = Field(
        default_factory=list,
        description="Skill names this agent advertises (the ARM "
        "resource card's competence axis — e.g. ['fiction-craft', "
        "'web-research']). The user sees the persona; ARM sees the "
        "skills when selecting agents for orchestration. NULL/absent "
        "= no declared skills (valid).",
    )

    # THE FACE + TAGS (2026-09-10, the News Team arc). These live on the
    # BASE so AgentCreate and AgentResponse both carry them. NOTE: the
    # update schema below re-declares its fields by hand rather than
    # inheriting — it must list them too. scripts/audit_agent_schema.py
    # fails when the two drift, so a new field cannot be forgotten
    # silently again.
    profile_image_url: Optional[str] = Field(
        default=None,
        description="The agent's face — a /static/<name>.png url from "
        "the curated pool (assets/agent-images/) or an upload.",
    )
    tags: Optional[List[str]] = Field(
        default=None, description="Free-form tags for the agent",
    )

    # Workspace (agent-lifecycle Phase B — the repository seam)
    workspace_key: Optional[str] = Field(
        default=None,
        description="The agent's stable workspace folder key (the "
        "disk identity — NOT the name; renames never move files).",
    )

    # THE OWNED KIT + PACKAGE (2026-08-24, the toolkit + agent-package):
    # the agent OWNS its kit (the tool surface) + its package
    # provenance. The kit is set by the ADOPT action (Phase 2) or
    # directly; package_id is lineage ONLY (the agent owns its copies).
    kit_id: Optional[str] = Field(
        default=None,
        description="The tool-typed collection (kit) this agent OWNS",
    )
    llm_spec: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The OWNED LLM capability contract (kind/thinking/"
        "location/min_context/max_output) — copied from the package at adoption; "
        "`max_output` is the output budget the resolver reads (G-I)",
    )
    package_id: Optional[str] = Field(
        default=None,
        description="The package blueprint this agent was provisioned from (provenance)",
    )


class AgentCreate(AgentBase):
    """Schema for creating a new agent."""

    # THE SHAPE IS THE GUARD (G-I): a created agent's parameters are sampling
    # settings — anything else is refused by name, and the refusal is logged. The
    # field itself stays a mapping (the row stores JSON), so the guard is the
    # validator plus `AgentParameters`'s own `extra="forbid"` where the model is used.
    @field_validator("parameters", mode="before")
    @classmethod
    def _only_known_parameters(cls, v):
        return _refuse_unusable_parameters(v)

    @field_validator("llm_spec")
    @classmethod
    def _within_the_budget_ceiling(cls, v):
        """F.2: a created agent's budget is bounded like every other surface."""
        return _check_budget_ceiling(v)


class AgentUpdate(BaseModel):
    """Schema for updating an existing agent.

    THE DECLARATION IS WRITABLE HERE (G-I). `llm_spec` used to be create-only — it
    was declared on `AgentBase`, which this schema does not inherit — so an existing
    agent could only take a new contract by being RE-ADOPTED from its package. That
    is the gap the token arc's last step closes: the field that decides the budget is
    editable through the API like every other field that decides behaviour.
    """

    @field_validator("parameters", mode="before")
    @classmethod
    def _only_known_parameters(cls, v):
        return _refuse_unusable_parameters(v)

    @field_validator("llm_spec")
    @classmethod
    def _within_the_budget_ceiling(cls, v):
        """F.2: an edited budget is bounded like a created one — the profile form's
        number is the same number the API validates."""
        return _check_budget_ceiling(v)

    name: Optional[str] = Field(
        default=None, min_length=1, max_length=100, description="Agent name"
    )
    description: Optional[str] = Field(
        default=None, max_length=500, description="Agent description"
    )
    provider: Optional[str] = Field(default=None, description="LLM provider")
    model: Optional[str] = Field(default=None, description="Model name")
    system_prompt: Optional[str] = Field(
        default=None, max_length=5000, description="System prompt"
    )
    is_active: Optional[bool] = Field(default=None, description="Active status")
    parameters: Optional[Dict[str, Any]] = Field(
        default=None, description="Model parameters (temperature, top_p)"
    )
    llm_spec: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "The agent's OWN LLM contract — the declaration slot (G-I). Its "
            "`max_output` is the output budget the resolver reads; adoption copies the "
            "package's contract here, and this is the field the profile form edits."
        ),
    )
    template_id: Optional[str] = Field(
        default=None, description="Template reference"
    )
    preferred_providers: Optional[list[str]] = Field(
        default=None, description="Ordered list of preferred providers"
    )
    fallback_enabled: Optional[bool] = Field(
        default=None, description="Enable automatic fallback"
    )
    allow_delegation: Optional[bool] = Field(
        default=None, description="Whether this agent can receive delegated tasks"
    )
    execution_mode: Optional[str] = Field(
        default=None, description="Execution mode: llm, simulated, or hybrid"
    )
    behavior_config: Optional[Dict[str, Any]] = Field(
        default=None, description="Behavior configuration for simulated/hybrid agents"
    )
    # THE FACE, THE SKILLS, THE TAGS (2026-09-10): these were on the model
    # but absent here, so a PUT carrying them was SILENTLY DROPPED — the
    # image-assignment bug the user hit. Keep in step with AgentBase.
    profile_image_url: Optional[str] = Field(
        default=None,
        description="The agent's face — a /static/<name>.png url from "
        "the curated pool (assets/agent-images/) or an upload.",
    )
    skills: Optional[List[str]] = Field(
        default=None, description="Skill names the agent advertises",
    )
    tags: Optional[List[str]] = Field(
        default=None, description="Free-form tags for the agent",
    )
    cognitive_profile_id: Optional[int] = Field(
        default=None, description="ID of the CognitiveProfile assigned to this agent"
    )


class AgentHealth(BaseModel):
    """Agent provider-health summary (derived from usage_logs).

    Built by AgentService.health_for_agents — the same logic as the
    check_agent_health.py scan, so UI badges match sweep findings.
    """

    status: str = "ok"  # ok | warn | fail
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    last_failure_at: Optional[datetime] = None
    failures_7d: int = 0


class AgentServiceAvailability(BaseModel):
    """Whether this agent's service can answer RIGHT NOW — the resolver + the availability read.

    **A QUESTION OF ITS OWN, and the copy keeps it separate from `AgentHealth`.** Health is
    HISTORICAL — `usage_logs`, *"failing lately"*; this is CURRENT — *"cannot run now"*. Built by
    `domain.providers.refusal.chat_readiness`, which applies the SAME rule the pre-turn refusal
    applies, so this badge and a REFUSED turn can never disagree about one agent.

    `available` is None when nothing was checked — **never False** — because "we do not know" is a
    state to show rather than a verdict to invent. `state` is the availability vocabulary
    (`available` | `down-by-occupancy` | `down` | `unconfigured` | `unknown`), or `disabled` when
    the capability itself is switched off. `checked_at` rides with it so the copy owns the
    staleness window.
    """

    state: str = STATE_UNKNOWN
    available: Optional[bool] = None
    reason: Optional[str] = None
    checked_at: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class AgentOutputBudget(BaseModel):
    """What an agent DECLARES beside what a turn would actually SEND (Phase G.1).

    Built by `AgentService.output_budget_for_agents`, which calls the SAME
    resolver the chat path calls at send time — so the page shows the number
    that runs and the reason it is that number, never a second arithmetic over
    the declaration. `reason` is the resolver's own vocabulary (`declared` |
    `type_default` | `thinking_floor` | `thinking_mandatory` | `window_clamp` |
    `no_declared_budget`), which is the half that makes two different numbers
    readable instead of confusing.

    `path` names the run path the number belongs to. It is the ordinary chat
    path; `/agent-chat` runs the cognitive pipeline on its own and is not
    described by this read.
    """

    declared: Optional[int] = Field(
        default=None, description="The number the agent's own row declares"
    )
    effective: int = Field(..., description="The number the resolver sends")
    reason: str = Field(..., description="Why the two differ (the resolver's own word)")
    path: str = Field(..., description="The run path this number belongs to")
    # THE OBSERVED HALF (G-A ii): what the agent's LAST turn actually carried, read
    # from that turn's own row — the app's record of the wire, not a second reading of
    # it. `None` means no turn has run since the record existed (a state to show, never
    # to fill in with the prediction).
    observed: Optional["AgentObservedBudget"] = None


class AgentObservedBudget(BaseModel):
    """The budget one turn ACTUALLY carried — {sent, declared, reason, path}.

    The same object the done frame and the message row carry (one nested `budget`
    key), read back for the page so the declaration is shown beside what went out
    rather than beside a prediction. `at` is when that turn finished, because a
    reading with no date is a number pretending to be current.
    """

    sent: int = Field(..., description="What the wire carried")
    declared: Optional[int] = Field(default=None, description="What the row declared then")
    reason: str = Field(default="", description="The resolver's word for why")
    path: str = Field(default="", description="The run path that sent it")
    at: Optional[datetime] = Field(default=None, description="When that turn finished")


class AgentResponse(AgentBase):
    """Schema for agent response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    health: Optional[AgentHealth] = None
    # THE CURRENT QUESTION (phase 6, G5-F2's agent half) — "can this agent run NOW?", beside
    # `health`'s "has it been failing lately?". Its own field because the two ANSWER DIFFERENT
    # THINGS and one badge for both would have to lie about one of them.
    service_availability: Optional["AgentServiceAvailability"] = None
    # THE DECLARED-VS-SENT READ (Phase G.1) — the same shape as `health`: a
    # read-out computed for the read, never stored on the row. `None` when the
    # caller did not ask for it (a create/delete response, a write that returns
    # the record without resolving anything).
    output_budget: Optional[AgentOutputBudget] = None
    # THE CEILING (D3) — the DERIVED bound every declaration is checked against,
    # served here so a UI bound can READ it instead of typing a second copy
    # (which is how the profile form came to refuse legal budgets above 8192).
    budget_ceiling: int = Field(
        default=BUDGET_CEILING,
        description="The derived maximum output budget (output_budget.BUDGET_CEILING)",
    )


class AgentListResponse(BaseModel):
    """Schema for listing agents with pagination."""

    agents: list[AgentResponse]
    total: int
    page: int = 1
    page_size: int = 10


class SystemPromptTemplate(BaseModel):
    """Schema for system prompt template."""

    id: str = Field(..., description="Template identifier")
    name: str = Field(..., description="Template display name")
    description: str = Field(..., description="Template description")
    prompt: str = Field(..., description="Template prompt text")
    variables: list[str] = Field(
        default_factory=list,
        description="List of template variables (e.g., ['user_name', 'tone'])"
    )


class TemplateApplyRequest(BaseModel):
    """Schema for applying a template with variables."""

    template_id: str = Field(..., description="Template identifier")
    variables: Dict[str, str] = Field(
        default_factory=dict,
        description="Variable values to substitute in template"
    )


class TemplateApplyResponse(BaseModel):
    """Schema for template apply response."""

    template_id: str = Field(..., description="Template identifier")
    prompt: str = Field(..., description="Rendered prompt with variables applied")


# ============================================================================
# Agent Template Schemas
# ============================================================================


class AgentTemplateCreate(BaseModel):
    """Schema for creating a new agent template."""

    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    description: str = Field(..., max_length=500, description="Template description")
    provider: str = Field(..., description="LLM provider (e.g., ollama, openai)")
    model: str = Field(..., description="Model name (e.g., llama3.2, gpt-4)")
    system_prompt: str = Field(..., max_length=5000, description="System prompt template")
    parameters: Optional[Dict[str, Any]] = Field(
        # NOTHING IS DECLARED BY DEFAULT — see `AgentBase.parameters`. A template that
        # declares no sampling hands the agent it creates no sampling, and the agent's
        # own page is where sampling is decided.
        default=None,
        description="Default model parameters (temperature, top_p) — absent means this template declares none"
    )

    @field_validator("parameters", mode="before")
    @classmethod
    def _only_known_parameters(cls, v):
        """G-I: a template carries no budget. It has no `llm_spec` column to declare
        one in, and `parameters.max_tokens` was a copy of the silent 2000 default — so
        a template is sampling parameters only, and the agent it fills in starts
        UNDECLARED (its package or the profile form is what declares a budget). An
        unknown key is refused by name, and the refusal is logged."""
        return _refuse_unusable_parameters(v)
    is_public: bool = Field(
        default=False,
        description="Whether template is publicly visible"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="List of tags for categorization"
    )
    cognitive_profile_id: Optional[int] = Field(
        default=None, description="Cognitive profile ID (research-pro, system-admin, etc.)"
    )
    execution_mode: Optional[str] = Field(
        default=None, description="Execution mode: hybrid or shallow"
    )
    behavior_config: Optional[Dict[str, Any]] = Field(
        default=None, description="Agent behavior configuration"
    )
    preferred_providers: Optional[List[str]] = Field(
        default=None, description="Preferred provider list"
    )
    fallback_enabled: Optional[bool] = Field(
        default=True, description="Whether fallback is enabled"
    )
    allow_delegation: Optional[bool] = Field(
        default=False, description="Whether delegation is allowed"
    )
    # THE CHARACTER (2026-09-10, the News Team arc): what makes the applied
    # agent a character rather than a chatbot. A template clones the
    # character — never the instance (an agent's state.json is its own).
    kit_ids: Optional[List[str]] = Field(
        default=None, description="Kit ids (tool-typed collection ids) to attach"
    )
    skills: Optional[List[str]] = Field(
        default=None, description="Skill names to seed from the shared library"
    )
    workspace_files: Optional[Dict[str, Any]] = Field(
        default=None,
        description="A {relative_path: content} seed for the workspace (beat sheets, notes)",
    )
    profile_image_url: Optional[str] = Field(
        default=None, description="The agent's face (the profile image url)"
    )


class AgentTemplateUpdate(BaseModel):
    """Schema for updating an existing template."""

    name: Optional[str] = Field(
        default=None, min_length=1, max_length=100, description="Template name"
    )
    description: Optional[str] = Field(
        default=None, max_length=500, description="Template description"
    )
    provider: Optional[str] = Field(default=None, description="LLM provider")
    model: Optional[str] = Field(default=None, description="Model name")
    system_prompt: Optional[str] = Field(
        default=None, max_length=5000, description="System prompt"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None, description="Model parameters (temperature, top_p)"
    )

    @field_validator("parameters", mode="before")
    @classmethod
    def _only_known_parameters(cls, v):
        """G-I: the shape guard applies to a template edit too — refused by name,
        and logged."""
        return _refuse_unusable_parameters(v)
    is_public: Optional[bool] = Field(default=None, description="Public visibility")
    tags: Optional[List[str]] = Field(default=None, description="Tags")
    cognitive_profile_id: Optional[int] = Field(default=None, description="Cognitive profile ID")
    execution_mode: Optional[str] = Field(default=None, description="Execution mode: hybrid or shallow")
    behavior_config: Optional[Dict[str, Any]] = Field(default=None, description="Behavior configuration")
    preferred_providers: Optional[List[str]] = Field(default=None, description="Preferred providers")
    fallback_enabled: Optional[bool] = Field(default=None, description="Fallback enabled")
    allow_delegation: Optional[bool] = Field(default=None, description="Delegation allowed")
    # the character (see AgentTemplateCreate)
    kit_ids: Optional[List[str]] = Field(default=None, description="Kit ids to attach")
    skills: Optional[List[str]] = Field(default=None, description="Skill names to seed")
    workspace_files: Optional[Dict[str, Any]] = Field(
        default=None, description="{relative_path: content} workspace seed"
    )
    profile_image_url: Optional[str] = Field(default=None, description="The agent's face")


class AgentTemplateResponse(BaseModel):
    """Schema for agent template response."""

    id: int
    name: str
    description: str
    provider: str
    model: str
    system_prompt: str
    parameters: Optional[dict]
    cognitive_profile_id: Optional[int]
    execution_mode: Optional[str]
    behavior_config: Optional[dict]
    preferred_providers: Optional[list[str]]
    fallback_enabled: Optional[bool]
    allow_delegation: Optional[bool]
    # the character
    kit_ids: Optional[list[str]] = None
    skills: Optional[list[str]] = None
    workspace_files: Optional[dict] = None
    profile_image_url: Optional[str] = None
    is_public: bool
    created_by: Optional[str]
    tags: Optional[list[str]]
    usage_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentTemplateListResponse(BaseModel):
    """Schema for listing agent templates."""

    templates: List[AgentTemplateResponse]
    total: int


class AgentTemplateApplyRequest(BaseModel):
    """Schema for applying a template to create an agent."""

    name: str = Field(..., min_length=1, max_length=100, description="Name for the new agent")
    description: Optional[str] = Field(
        default=None, max_length=500, description="Optional description"
    )


class AgentTemplateSaveFromAgentRequest(BaseModel):
    """Schema for saving an agent as a template."""

    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    description: Optional[str] = Field(
        default=None, max_length=500, description="Template description"
    )
    is_public: bool = Field(
        default=False,
        description="Whether template is publicly visible"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="List of tags for categorization"
    )
    cognitive_profile_id: Optional[int] = Field(
        default=None, description="Cognitive profile ID (research-pro, system-admin, etc.)"
    )
    execution_mode: Optional[str] = Field(
        default=None, description="Execution mode: hybrid or shallow"
    )
    behavior_config: Optional[Dict[str, Any]] = Field(
        default=None, description="Agent behavior configuration"
    )
    preferred_providers: Optional[List[str]] = Field(
        default=None, description="Preferred provider list"
    )
    fallback_enabled: Optional[bool] = Field(
        default=True, description="Whether fallback is enabled"
    )
    allow_delegation: Optional[bool] = Field(
        default=False, description="Whether delegation is allowed"
    )


# ============================================================================
# Duplicate Detection Schemas
# ============================================================================


class DuplicateAgentInfo(BaseModel):
    """Summary info for an agent within a duplicate group."""

    id: int
    name: str
    provider: str
    model: str
    created_at: datetime


class DuplicateGroup(BaseModel):
    """A group of agents that are duplicates of each other."""

    criteria: str = Field(
        description="The criteria that matched (direct_copy, config_twin, functional_twin, name_similar)"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence score for this duplicate detection (0.0-1.0)"
    )
    agents: list[DuplicateAgentInfo] = Field(
        description="The agents in this duplicate group (sorted by creation date)"
    )
    match_reason: str = Field(
        description="Human-readable explanation of why these agents match"
    )
    group_name: str = Field(
        description="Descriptive, human-readable name for this duplicate group (e.g., 'Configuration Twin: ollama/llama3.2 (4 agents)')"
    )


class DuplicatesRequest(BaseModel):
    """Query parameters for duplicate detection."""

    criteria: str = Field(
        default="all",
        description="Duplicate criteria: 'direct_copy', 'config_twin', 'functional_twin', 'name_similar', or 'all'"
    )
    min_confidence: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Minimum confidence threshold (0.0-1.0)"
    )


class DuplicatesResponse(BaseModel):
    """Response from duplicate detection endpoint."""

    duplicate_groups: list[DuplicateGroup] = Field(
        default_factory=list,
        description="List of duplicate groups found"
    )
    total_agents_analyzed: int = Field(
        description="Total number of agents analyzed"
    )
    duplicate_groups_found: int = Field(
        description="Number of duplicate groups detected"
    )
    total_agents_in_duplicates: int = Field(
        description="Total number of agents that appear in at least one duplicate group"
    )


# ============================================================================
# A2A / AgentCard Schemas
# ============================================================================


class AgentSkill(BaseModel):
    """A single skill that an agent advertises via AgentCard."""

    id: str = Field(..., description="Unique skill identifier")
    name: str = Field(..., description="Skill display name")
    description: str = Field(..., description="Skill description")
    examples: list[str] = Field(
        default_factory=list,
        description="Example task prompts for this skill",
    )


class AgentCapabilities(BaseModel):
    """Capabilities an agent supports per the A2A AgentCard spec."""

    streaming: bool = Field(
        default=True,
        description="Whether the agent supports SSE streaming responses",
    )
    push_notifications: bool = Field(
        default=False,
        description="Whether the agent supports webhook push notifications",
    )
    delegation: bool = Field(
        default=False,
        description="Whether this agent can receive delegated tasks from other agents",
    )


class AgentCard(BaseModel):
    """
    A2A AgentCard — standardized agent discovery document.

    Maps to the A2A protocol's AgentCard specification for agent-to-agent
    discovery and capability advertisement. Derived from agent DB records.
    """

    name: str = Field(..., description="Agent name")
    description: Optional[str] = Field(
        default=None, description="Agent description"
    )
    agent_id: int = Field(..., description="Cogitate internal agent ID")
    provider: str = Field(..., description="LLM provider (e.g., ollama, openai)")
    model: str = Field(..., description="Model name (e.g., llama3.2, gpt-4)")
    skills: list[AgentSkill] = Field(
        default_factory=list,
        description="Skills this agent can perform",
    )
    capabilities: AgentCapabilities = Field(
        default_factory=AgentCapabilities,
        description="Protocol-level capabilities",
    )
    version: str = Field(
        default="1.0",
        description="AgentCard schema version",
    )
    arm: Optional["AgentArmCard"] = Field(
        default=None,
        description="ARM resource card (Phase F) — the selection "
        "surface Exa/the resource manager reads when composing "
        "orchestrations. Separate from the user-facing persona: "
        "depth, competence, spec, capability.",
    )


class AgentArmCard(BaseModel):
    """The ARM resource card (study 09) — agent SELECTION data.

    Two-audience principle: the user sees the persona (name,
    avatar, description); ARM sees this card. All fields are
    derived or declared, never user-entered at runtime:
    - depth: the cognitive profile (deep = research/memory,
      shallow = quick-response)
    - competence: the declared skills (AgentCreate.skills)
    - spec: provider location + size (the classifier)
    - capability: the enabled tool slugs (capability vocabulary)
    """

    depth: Optional[str] = Field(
        default=None, description="Cognitive profile name (deep/shallow axis)"
    )
    competence: List[str] = Field(
        default_factory=list, description="Declared skills"
    )
    spec: Dict[str, str] = Field(
        default_factory=dict,
        description="{'location': local|cloud, 'size': small|medium|big}",
    )
    capability: List[str] = Field(
        default_factory=list, description="Enabled tool slugs (capability vocabulary)"
    )


# ============================================================================
# Agent Selection Schemas (ARM Phase B — the yellow pages)
# ============================================================================


class AgentSelectRequest(BaseModel):
    """The selection criteria (study 13).

    All fields AND-ed; capability is OR-within-field. Empty =
    the whole pool (discovery). GRAS — never grants.
    """

    capability: Optional[List[str]] = Field(
        default=None, description="Any-of enabled tool slugs (e.g. ['web-search'])"
    )
    role: Optional[str] = Field(default=None, description="Curated role (writer, researcher...)")
    domain: Optional[str] = Field(default=None, description="Curated domain (fiction, math...)")
    depth: Optional[str] = Field(
        default=None, description="deep | shallow | balanced (cognitive profile family)"
    )
    provider: Optional[str] = Field(default=None, description="Provider name")
    spec: Optional[str] = Field(
        default=None, description="local | cloud (where it runs)"
    )
    collective: Optional[str] = Field(
        default=None, description="Collection name — a picker FILTER, never a routing target"
    )
    min_tools: Optional[int] = Field(
        default=None, ge=0, description="Minimum enabled tool count"
    )


class AgentSelectResponse(BaseModel):
    """Ranked ARM cards + transparency."""

    agents: List[Dict[str, Any]] = Field(
        default_factory=list, description="Ranked matching agents (ARM cards)"
    )
    total: int = Field(0, description="Number of matches")


# ============================================================================
# Agent Stats Schemas
# ============================================================================


class AgentStatsResponse(BaseModel):
    """
    Aggregate agent statistics for system management.

    Provides an overview of the agent ecosystem — counts, provider/model
    distribution, delegation status, and tool assignments. Designed for
    the meta-tool's introspection capabilities.
    """

    total_agents: int = Field(..., description="Total number of agents in the system")
    active_agents: int = Field(..., description="Number of active agents")
    inactive_agents: int = Field(..., description="Number of inactive agents")
    agents_with_delegation_enabled: int = Field(
        ..., description="Agents that can receive delegated tasks"
    )
    agents_with_delegation_disabled: int = Field(
        ..., description="Agents with allow_delegation=False"
    )
    agents_with_tools: int = Field(
        ..., description="Agents that have at least one tool assigned"
    )
    agents_without_tools: int = Field(
        ..., description="Agents with no tools assigned"
    )
    by_provider: dict[str, int] = Field(
        default_factory=dict,
        description="Agent count grouped by provider (e.g., {'ollama': 3, 'openai': 1})",
    )
    by_model: dict[str, int] = Field(
        default_factory=dict,
        description="Agent count grouped by model (e.g., {'llama3.2': 2, 'gpt-4': 1})",
    )
