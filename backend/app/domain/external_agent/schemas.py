"""External agent domain — configuration schemas.

The Agent Integration page persists its config here; the AcpClient
reads it when spawning the subprocess.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExaBrain(BaseModel):
    """One TESTED BRAIN — a model + provider + endpoint the page can switch Exa to.

    The quick-switch fills its fields from one entry and SAVES it, so an entry carries the
    endpoint as well: Exa's own config states model, provider AND base_url.
    """

    label: str = Field(description="What the dropdown shows.")
    model: str = Field(description="The model id as the provider expects it on the wire.")
    provider: str = Field(description="The provider NAME — a provider row's name.")
    base_url: str = Field(
        default="",
        description="The endpoint Exa dials for it; empty = the provider's own default.",
    )
    vision: bool = Field(
        default=False,
        description="Takes images — the page's vision picker lists only these entries.",
    )


# THE SHIPPED BRAIN LIST — a CONFIG DEFAULT, not a code literal.
#
# The service-literals arc's ruling (2026-10-10, the user): a literal that decides WHICH
# SERVICE DOES THE WORK must be resolved from config, never written into code — "not even as
# a backup". This is the config field's own default and it is served and replaced through
# `GET|PUT /api/v1/external-agent/config`, so which brains the page offers changes with a
# config write and no rebuild. That is the whole difference between this and the `const` it
# replaced in `AgentIntegration.tsx`.
#
# Its home is the EXTERNAL AGENT's config rather than the app's `curated_models` catalog:
# these are the brains TESTED against Exa, not the app's model recommendations (the user's
# ruling, 2026-10-10). Editing lists in the UI is a known gap, still open.
DEFAULT_BRAINS: list[ExaBrain] = [
    ExaBrain(
        label="DeepSeek V4 Flash (fast chat)",
        model="deepseek/deepseek-v4-flash",
        provider="deepseek",
        base_url="https://api.deepseek.com",
    ),
    ExaBrain(
        label="DeepSeek V4 Flash Vision (image-capable)",
        model="deepseek/deepseek-v4-flash-vision-exp",
        provider="deepseek",
        base_url="https://api.deepseek.com",
        vision=True,
    ),
    ExaBrain(
        label="Nemotron 3 Ultra (free, reasoning)",
        model="nvidia/nemotron-3-ultra-550b-a55b:free",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
    ),
    ExaBrain(
        label="Gemini 3.1 Flash Lite (proven vision, GA)",
        model="google/gemini-3.1-flash-lite",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        vision=True,
    ),
]


class ExternalAgentConfig(BaseModel):
    """Persisted external-agent connection config."""

    enabled: bool = Field(
        default=False,
        description="THE ACTIVATION (2026-11-18) — Exa ships INCLUDED but DE-ACTIVATED. "
        "A fresh install has no runtime and no key, and nothing is spawned: reaching Exa "
        "returns a plain 'not active' instead of a missing-binary error. Activating it is "
        "the user's decision (POST /activate), never a side effect of installing.",
    )
    command: str = Field(
        default="hermes acp",
        description="ACP backend command (shlex-split at spawn time). "
        "Hermes-first; pluralize later by pointing elsewhere.",
    )
    cwd: str = Field(
        default="",
        description="Working directory for the agent subprocess. "
        "Empty = the backend's own cwd (project root).",
    )
    permission_tier: str = Field(
        default="chat",
        description="THE PERMISSION TIER (2026-08-21) — the 3-way "
        "selector replaces the old fix_mode bool. 'chat' (default) = "
        "per-edit approval in the chat (the Approve/Deny card); 'fix' = "
        "auto-approve inside cwd (the old fix_mode); 'yolo' = "
        "auto-approve EVERYTHING (the adapter's 'session' policy — "
        "except the secret-file guard: .env/.ssh/.git still ask). The "
        "break button (the chat Stop) bounds yolo's runaway risk.",
    )
    @property
    def fix_mode(self) -> bool:
        """Compat view: the old bool == the fix tier (the persisted
        JSON and the badge read it)."""
        return self.permission_tier == "fix"

    max_turn_seconds: int = Field(
        # 900 since 2026-08-22: the reasoning-model era (ox-alpha ~180s
        # TTFB, nemotron audits 5-10 min) makes 300s a turn-killer — the
        # audit prompt-4 run hit the 300s cap mid-work. 900 = 15 min of
        # whole-turn agent work. 0 = unlimited.
        default=900,
        ge=0,
        description="Whole-turn duration cap for panel runs (2026-08-14). "
        "0 = unlimited (the panel keeps working until the agent finishes "
        "or the user stops it). Any positive value auto-halts a turn that "
        "exceeds it (gentle cancel → grace → kill, the same two-stage "
        "path as the Stop button) and reports a 'time_limit' status. "
        "The 120s per-event wait is unchanged — this caps the TOTAL turn.",
    )
    image: str = Field(
        default="",
        description="Exa's FACE (2026-08-21): the chat participant's "
        "avatar image — a URL/path (an asset like alien-01.png) or empty "
        "for the default. Configurable on the Exa Agent page; the chat "
        "shows it when Exa is selected as a participant.",
    )
    max_tool_calls_per_turn: int = Field(
        # 2026-09-08 (the layer-3 teeth): the runaway-turn
        # class — silent 50+-call turns crash and hang (the 09-08 crash +
        # the exercise hang). The hermes's own guardrails are failure-based;
        # the successful rabbit-hole needs the COUNT. The router counts the
        # tool calls per turn and HALTS at this cap via the same two-stage
        # path as Stop, reporting 'tool_call_limit'. 0 = unlimited.
        default=75,
        ge=0,
        description="Per-turn tool-call cap for panel runs (2026-09-08). "
        "0 = unlimited. Any positive value auto-halts a turn that exceeds "
        "it (the same two-stage path as the Stop button) and reports a "
        "'tool_call_limit' status.",
    )
    tool_call_checkin_every: int = Field(
        # 2026-09-08 (the enforced check-in): every N tool calls the router
        # sends a 'working' status beacon — the user SEES the runaway
        # building instead of discovering it at the crash.
        default=15,
        ge=0,
        description="Tool-call check-in cadence (2026-09-08): every N tool "
        "calls the router emits a 'working' status beacon so the turn's "
        "progress is visible. 0 = no beacons.",
    )
    brains: list[ExaBrain] = Field(
        # A COPY per instance: the default is module-level data, and a config object that
        # mutated the shipped list in place would leak across every reader.
        default_factory=lambda: [b.model_copy(deep=True) for b in DEFAULT_BRAINS],
        description="THE TESTED BRAINS (2026-10-10): the quick-switch list the Exa Agent page "
        "offers — pick one and it fills the model card, Save applies it. CONFIG, not bundle "
        "code: served by GET /config and replaced by PUT /config, so offering a different "
        "brain never needs a frontend rebuild.",
    )


class ExternalAgentStatus(BaseModel):
    """Live connection status for the integration page."""

    connected: bool
    # THE TWO FACTS BEHIND "not active", kept apart on purpose: `enabled` is the
    # user's decision, `runnable` is whether the box can honour it. A surface that
    # renders only one of them cannot tell "you haven't turned it on" from
    # "you turned it on and nothing here can run it".
    enabled: bool = False
    runnable: bool = False
    blocked_reason: str | None = None
    session_id: str | None = None
    command: str = "hermes acp"
    cwd: str = ""
    permission_tier: str = "chat"
    max_turn_seconds: int = 900
    max_tool_calls_per_turn: int = 75
    tool_call_checkin_every: int = 15
    image: str = ""
    model: str | None = None
    provider: str | None = None
    error: str | None = None


class ExternalAgentConfigUpdate(BaseModel):
    enabled: bool | None = Field(
        default=None,
        description="The activation decision. Prefer POST /activate and /deactivate — they "
        "answer with whether the box can actually run the configured command.",
    )
    command: str | None = None
    cwd: str | None = None
    permission_tier: str | None = Field(
        default=None,
        description="'chat' | 'fix' | 'yolo' — the 3-way permission tier.",
    )
    fix_mode: bool | None = Field(
        default=None,
        description="DEPRECATED compat (pre-2026-08-21): the old bool. "
        "Maps to permission_tier ('fix' when True, 'chat' when False) "
        "only when permission_tier is absent — the tier wins.",
    )
    max_turn_seconds: int | None = Field(default=None, ge=0)
    max_tool_calls_per_turn: int | None = Field(default=None, ge=0)
    tool_call_checkin_every: int | None = Field(default=None, ge=0)
    image: str | None = None
    brains: list[ExaBrain] | None = Field(
        default=None,
        description="Replace the quick-switch brain list. Absent = keep the current list.",
    )
