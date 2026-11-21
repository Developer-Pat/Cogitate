"""
Database models.

Defines ORM models for all database tables.
"""

from datetime import datetime, timezone
from typing import Any, Optional, List, Dict

import time
import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    Float,
    func,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.mutable import MutableDict

from app.core.database import Base, DocumentsBase


class Agent(Base):
    """
    Agent database model.

    Represents an LLM agent configuration in the database.
    """

    __tablename__ = "agents"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Core fields
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, unique=True,
        comment="Unique — the pool addresses agents by name (ARM Phase A)",
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Execution mode (see SIMULATED_AGENT_DESIGN.md §2.2)
    # "llm" (default) | "simulated" | "hybrid"
    execution_mode: Mapped[str] = mapped_column(
        String(20), default="llm", nullable=False,
    )

    # Behavior config (JSON, engine-specific — see SIMULATED_AGENT_DESIGN.md §3.1)
    # Used by simulated agents (execution_mode="simulated") to define rules,
    # templates, state machines, etc.
    behavior_config: Mapped[Optional[Dict]] = mapped_column(
        JSON, nullable=True, default=None,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    is_builtin: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )

    # Health dismissal (F6): when set, failures BEFORE this timestamp are
    # treated as acknowledged and don't flag the agent; new failures re-flag.
    health_dismissed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Profile image
    profile_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Model parameters (JSON) — SAMPLING SETTINGS ONLY, and NOTHING BY DEFAULT.
    #
    # `max_tokens` is NOT here, and must not come back: the output budget is the
    # agent's `llm_spec.max_output` (one declaration slot), and a budget key in
    # `parameters` is refused by name at the API. A Python-side default writes AROUND
    # every guard there is — an ORM insert never meets a request schema — so a value
    # placed here rides every row the API cannot see. That is how a retired key
    # survives in rows for months, and how a sampling default lands on an agent nobody
    # chose one for. An agent that declares no sampling stores NULL, and the turn then
    # sends no sampling setting (the provider's own default applies).
    parameters: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)

    # Template reference
    template_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Delegation
    allow_delegation: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # Provider preferences (ordered list for fallback). EMPTY by default: a provider NAME here
    # (`["ollama"]` until the service-capability arc's close-out) was a service named in code, and it
    # landed as the backup list of every new agent — so a failover could walk a service nobody chose.
    # Declaring nothing must mean declaring nothing: the resolver then falls to the capability's own
    # configured chain (`capabilities.resolve`, the agent rung).
    preferred_providers: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True, default=lambda: []
    )
    fallback_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Cognitive profile (FK to CognitiveProfile)
    cognitive_profile_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("cognitive_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Skills (Phase F — the ARM card's COMPETENCE axis)
    skills: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True,
        comment="Skill names this agent advertises (ARM selection)",
    )

    # THE OWNED KIT (2026-08-24, the toolkit proposal): the agent
    # OWNS its kit — a DIRECT reference to a tool-typed collection
    # (entity_type='tool'), NOT a membership item in the collection
    # (that is the TEAM framing — the collection owns its members).
    # The kit IS the agent's surface (the policy rule); an agent
    # without a kit keeps the default surface. The user's words:
    # 'the agent owns the kit, the kit should not own the agent.'
    kit_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("collections.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="The tool-typed collection (kit) this agent OWNS",
    )

    # THE OWNED LLM CONTRACT (2026-08-24, the agent-package Phase 2):
    # the capability spec COPIED from the package at adoption — the
    # contract survives the instance. The provider/model is what the
    # agent runs NOW; llm_spec is what it NEEDS (substitution +
    # rehydration + provisioning guidance). A copy, not a live read:
    # the agent's contract shouldn't mutate when the package evolves.
    llm_spec: Mapped[Optional[Dict]] = mapped_column(
        JSON, nullable=True,
        comment="The owned LLM capability contract (kind/thinking/location/min_context)",
    )

    # THE PROVENANCE (2026-08-24, the agent-package Phase 2): the
    # package this agent was provisioned from. Lineage ONLY — the
    # agent owns its copies; the package never owns the agent.
    package_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("agent_packages.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="The package blueprint this agent was provisioned from (provenance)",
    )

    # Tags (ARM Phase B — the ROLE/DOMAIN axis)
    tags: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True,
        comment="Curated role/domain tags (the selection vocabulary)",
    )

    # Workspace (agent-lifecycle Phase A — the repository seam)
    workspace_key: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, index=True,
        comment="Stable workspace folder key (NOT the name — renames "
                "never move files; the fork boundary)",
    )

    # Soft-delete (agent-lifecycle Phase C — the recoverable delete)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True,
        comment="Soft-delete marker (the row survives — history "
                "keeps its reference)",
    )
    archived_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
        comment="Where the workspace sits on the trash's agents shelf "
                "after a delete (trash/agents/<key>-<ts>/ — recovery is "
                "DB-discoverable, and the trash page reads the same list)",
    )

    # Relationships
    cognitive_profile: Mapped[Optional["CognitiveProfile"]] = relationship(
        "CognitiveProfile",
        back_populates="agents",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation of agent."""
        return f"<Agent(id={self.id}, name='{self.name}', provider='{self.provider}')>"


class ChatSession(Base):
    """
    Chat session database model.

    Represents a conversation session with an agent.
    """

    __tablename__ = "chat_sessions"

    # THE ID-REUSE FIX (2026-09-11). `autoincrement=True` on the column is
    # the ORM's flag; SQLite only emits the AUTOINCREMENT *keyword* when the
    # TABLE carries this dialect arg. Without it, SQLite picks the next id as
    # max(rowid) + 1 — so deleting the newest rows FREES their ids and the
    # next row is handed one back. That is how a new session came back as
    # id 22 twenty seconds after 22 was deleted, and a client still holding
    # 22 collided with a different session.
    #   `AUTOINCREMENT` keeps a monotonic counter instead: ids never repeat,
    # and rows still really delete (no soft-delete, no retention cost).
    # NOTE: the SAME arg exists on chat_messages below — both are needed.
    __table_args__ = {"sqlite_autoincrement": True}

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Session metadata
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    agent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=True, index=True
    )
    #   nullable (2026-08-21): the EXTERNAL surface's sessions
    #   (Exa chats — source='exa') have no DB agent row; the DB
    #   schema always allowed null, the ORM model now matches.

    # Session status
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )

    # Source tracking (Phase D — conversation logging)
    source: Mapped[str] = mapped_column(
        String(20), default="agent", nullable=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ChatMessage.created_at",
    )

    def __repr__(self) -> str:
        """String representation of chat session."""
        return f"<ChatSession(id={self.id}, agent_id={self.agent_id}, title='{self.title}')>"


class ChatMessage(Base):
    """
    Chat message database model.

    Represents a single message in a chat session.
    """

    __tablename__ = "chat_messages"

    # See the note on ChatSession above: the column flag alone does NOT make
    # SQLite reuse-proof — the TABLE needs the dialect arg. Message ids are
    # referenced by the streaming update path, so a reused message id breaks
    # the same way a reused session id does.
    __table_args__ = {"sqlite_autoincrement": True}

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Message content
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # 'user', 'assistant', 'system'
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Message metadata
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Provider name (ollama, openai, etc.)
    total_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Generation time in milliseconds
    tokens_per_second: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Generation speed
    # THE THINKING SEGREGATION (2026-08-24): the per-message metadata
    # (the reasoning for the Thinking fold + any future fields) —
    # survives the reload.
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    session: Mapped["ChatSession"] = relationship(
        "ChatSession", back_populates="messages"
    )

    def __repr__(self) -> str:
        """String representation of chat message."""
        return f"<ChatMessage(id={self.id}, session_id={self.session_id}, role='{self.role}')>"


class ChatAttachment(Base):
    """
    Chat attachment database model.

    Represents a file uploaded and attached to a chat session.
    """

    __tablename__ = "chat_attachments"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to chat session
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # File metadata
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., 'pdf', 'md', 'txt'
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # in bytes
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)  # absolute path
    mime_type: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        """String representation of chat attachment."""
        return f"<ChatAttachment(id={self.id}, session_id={self.session_id}, filename='{self.original_filename}')>"


class RuntimeConfig(Base):
    """
    Runtime configuration database model.

    Stores per-session overrides for agent configuration.
    """

    __tablename__ = "runtime_configs"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True, unique=True
    )
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Runtime overrides
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    top_p: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    system_prompt_override: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_override: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Additional parameters (JSON for flexibility)
    additional_params: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation of runtime config."""
        return f"<RuntimeConfig(session_id={self.session_id}, agent_id={self.agent_id})>"


class Provider(Base):
    """
    Provider database model.

    Represents an LLM provider configuration (e.g., Ollama, OpenAI, Anthropic).
    """

    __tablename__ = "providers"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Provider metadata
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # API configuration (keys live in .env through EnvKeyStore;
    # no key is ever stored in this table)
    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Provider status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=99, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Provider type (ollama, openai, anthropic, etc.)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Additional configuration (JSON)
    config: Mapped[Optional[Dict]] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation of provider."""
        return f"<Provider(id={self.id}, name='{self.name}', type='{self.provider_type}')>"


class Capability(Base):
    """
    Capability database model — one row per thing in the app that needs an
    external service.

    The row names the CONSUMER ('title', 'chat', 'workflow-llm', 'stt', 'tts',
    'exa'), never the service: which service answers is the ordered candidates
    in `CapabilityService`. Consumers resolve through the one resolver
    (`domain/providers/capabilities.py`) so "which provider?" has ONE answer
    instead of four (2026-09-30, the service-capability arc).

    `key` is a slug, so a sub-genre is a ROW rather than a migration
    ('title.thinking') — the user's extension path, made cheap on purpose.
    """

    __tablename__ = "capabilities"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # The capability's slug ('title', 'title.thinking') — the resolver's key
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # Human label for the surface ('Title service')
    label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # THE TYPED KIND: llm | speech | process — decides what a caller receives
    # (a ProviderConfig→client, a TtsProvider/SttProvider, an external process)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="llm")

    # Off keeps the row (and its history) without arming it
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # The ordered candidates; ordinal 0 is the primary
    services: Mapped[List["CapabilityService"]] = relationship(
        back_populates="capability",
        cascade="all, delete-orphan",
        order_by="CapabilityService.ordinal",
    )

    def __repr__(self) -> str:
        """String representation of a capability."""
        return f"<Capability(key='{self.key}', kind='{self.kind}')>"


class CapabilityService(Base):
    """
    One ordered candidate service for a capability.

    `ordinal` 0 is the PRIMARY and the rest are the backups, tried in order —
    which is what gives "the failure of the backup service is logged" a named
    thing to log (user, 2026-09-30).

    A candidate names EITHER a specific provider row (`provider_id`) OR a
    class (`require_location`: 'local' | 'cloud'). **The class form is what
    makes "prefer local vs global" configuration rather than a hardcoded
    provider list** — and it is why the literal `DEFAULT_FALLBACK_CHAIN` that
    used to live in the executor could be deleted (the service-capability
    arc's phase 3): the order is rows now, and it survives a provider being
    renamed or re-registered. A class resolves against the live rows by
    `location`, ordered by `(Provider.priority, Provider.name)` — the first
    job `priority` has ever had (it was written and read by no selector; see
    the arc's study §1).

    FK to `providers` is CASCADE rather than SET NULL on purpose: a candidate
    whose provider row is gone is INERT, and an inert row reads as a backup
    that exists but never works. A vanished row is visible; a dead one is not.
    """

    __tablename__ = "capability_services"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # The capability this candidate serves
    capability_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("capabilities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Position in the chain: 0 = primary, 1..n = backups, in order
    ordinal: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # A specific provider row (the usual case)
    provider_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # …or a CLASS of provider: 'local' | 'cloud' (never both with provider_id)
    require_location: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # …or a NAMED engine/process that is not a provider row at all — the speech
    # engines ('piper', 'edge', 'whisper') and the external agent ('exa'). The
    # seed needs it: `tts`/`stt` resolve through their own registries TODAY, so
    # a schema that can only name provider rows could not reproduce them.
    service_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # The model/voice on that service; NULL takes the provider row's own default_model
    model: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # The thinking flavour this candidate is for (values from THINKING_LEVELS,
    # the ONE home) — NULL means "any"
    thinking: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    capability: Mapped["Capability"] = relationship(back_populates="services")

    def __repr__(self) -> str:
        """String representation of a candidate."""
        return (
            f"<CapabilityService(capability_id={self.capability_id}, "
            f"ordinal={self.ordinal}, provider_id={self.provider_id}, "
            f"location={self.require_location!r})>"
        )


class UsageLog(Base):
    """
    Usage log database model.

    Tracks LLM API usage for cost tracking and analytics.
    """

    __tablename__ = "usage_logs"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys — session_id + agent_id are NULLABLE (the
    # pipeline workers log usage without a chat session)
    session_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    agent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Provider information
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Token usage
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Cost tracking
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Response metadata
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        """String representation of usage log."""
        return f"<UsageLog(id={self.id}, session_id={self.session_id}, provider='{self.provider}', model='{self.model}')>"



class AgentTemplate(Base):
    """
    Agent template database model.

    Pre-configured agent templates for quick deployment and sharing.
    """

    __tablename__ = "agent_templates"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Template metadata
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Agent configuration
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)

    # New agent architecture configuration
    cognitive_profile_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("cognitive_profiles.id"), nullable=True
    )
    execution_mode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    behavior_config: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    preferred_providers: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    fallback_enabled: Mapped[Optional[bool]] = mapped_column(Boolean, default=True, nullable=True)
    allow_delegation: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)

    # THE CHARACTER (2026-09-10, the News Team arc): what makes an agent a
    # character rather than a chatbot. kit_ids = the tool surface; skills =
    # the names to seed from the shared library; workspace_files = a
    # generic {relative_path: content} seed (the beat sheets and anything
    # else); profile_image_url = the face. Deliberately NOT here: anything
    # carrying an agent's own FACTS — state.json is never cloned.
    kit_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    skills: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    workspace_files: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    profile_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Template metadata
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # Usage stats
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation of agent template."""
        return f"<AgentTemplate(id={self.id}, name='{self.name}', provider='{self.provider}')>"


class Log(Base):
    """
    Log database model.
    
    Stores application logs from both frontend and backend.
    """
    
    __tablename__ = "logs"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Log metadata
    timestamp: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Context and metadata
    context: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    
    # Log type (frontend/backend)
    log_type: Mapped[str] = mapped_column(String(20), nullable=False, default="backend", index=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    
    # Indexes
    __table_args__ = (
        Index('ix_logs_level_source', 'level', 'source'),
        Index('ix_logs_timestamp_level', 'timestamp', 'level'),
        Index('ix_logs_message_fulltext', 'message', postgresql_using='gin'),
    )
    
    def __repr__(self) -> str:
        """String representation of log."""
        return f"<Log(id={self.id}, timestamp='{self.timestamp}', level='{self.level}', source='{self.source}')>"


class ProviderModelCache(Base):
    """
    Provider Model Cache.

    Stores discovered models from providers to avoid repeated API calls.
    Cache is invalidated after TTL (default: 24 hours).
    """

    __tablename__ = "provider_model_cache"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to provider
    provider_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Model metadata
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pricing_prompt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pricing_completion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    top_provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Model capabilities
    architecture: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    modality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tokenizer: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    in_context_training: Mapped[bool] = mapped_column(Boolean, default=False)
    function_calling: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Cache metadata
    is_cached: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Raw data (for debugging/complete info)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index('idx_provider_model', 'provider_id', 'model_id', unique=True),
        Index('idx_cache_expiry', 'provider_id', 'expires_at'),
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<ProviderModelCache(id={self.id}, provider_id={self.provider_id}, model='{self.model_id}')>"

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if not self.expires_at:
            return True
        # Use UTC for comparison to avoid timezone issues
        now = datetime.now(timezone.utc)
        expires_at = self.expires_at
        # Make expires_at timezone-aware if it isn't
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return now > expires_at


class CuratedModel(Base):
    """
    Curated model database model.

    Represents a human-curated model recommendation for a provider. This is
    the curation layer ("what should we recommend?") separate from
    provider_model_cache ("what does the provider actually offer?").

    Users can add/delete entries via the /api/v1/curated-models API.
    """

    __tablename__ = "curated_models"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Model identity
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Provider association
    provider_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Curation metadata. `category` is an OPTIONAL one-word descriptor of what the model is
    # for, and it has NO column default: a row nobody has described stores NULL rather than a
    # value a layer below invented (the retired "recommended" default did exactly that).
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # THE COST FACT IS DERIVED (the cloud-providers arc's Phase 4), and it has a THIRD
    # state: NULL means the provider's own catalog prices this model nowhere — a different
    # statement from "it costs money". The non-nullable `default=False` that used to sit
    # here answered "paid" to a question no provider had answered.
    is_free: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # THE CAPABILITY DIMENSIONS (2026-08-24, the agent-package
    # Phase 3): the substitution matcher's axes. thinking is
    # DECLARED (the registry's tiering, not measured); location is
    # the runtime home. Both are advisory metadata.
    thinking: Mapped[str] = mapped_column(
        String(10), default="none", nullable=False,
        comment="Declared thinking level: none|low|medium|high",
    )
    location: Mapped[str] = mapped_column(
        String(10), default="cloud", nullable=False,
        comment="Runtime home: local|cloud",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("provider_id", "model_id", name="uq_curated_provider_model"),
    )

    def __repr__(self) -> str:
        """String representation of the curated model."""
        return f"<CuratedModel id={self.id} model_id={self.model_id!r}>"


class ProviderSyncSchedule(Base):
    """
    Provider sync schedule database model.

    Stores automatic model synchronization schedules for providers.
    """

    __tablename__ = "provider_sync_schedules"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to provider
    provider_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True, unique=True
    )

    # Sync schedule configuration
    sync_interval_hours: Mapped[int] = mapped_column(Integer, default=168, nullable=False)  # 7 days default

    # Sync tracking
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_sync_status: Mapped[Optional[str]] = mapped_column(String(50), default="pending")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship
    provider: Mapped["Provider"] = relationship(
        "Provider",
        back_populates="sync_schedule",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<ProviderSyncSchedule(id={self.id}, provider_id={self.provider_id}, interval={self.sync_interval_hours}h)>"


class UserSettings(Base):
    """
    User settings database model.

    Stores per-user chat settings and preferences.
    Until authentication is implemented, uses a simple user_key (e.g., "default").
    """

    __tablename__ = "user_settings"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # User identifier (e.g., "default" until auth is implemented)
    user_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True, unique=True)

    # Settings JSON blob
    settings: Mapped[Dict] = mapped_column(JSON, nullable=False, default=lambda: {})

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<UserSettings(id={self.id}, user_key='{self.user_key}')>"


class MacroSet(Base):
    """
    Macro set database model.

    Represents a collection of 5 function key macros (F1-F5) organized by topic.
    ``namespace`` was added in Phase 4 to distinguish system vs agent macros.
    """

    __tablename__ = "macro_sets"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # User identifier (e.g., "default" until auth is implemented)
    user_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Namespace discriminator ("agent" or "system")
    namespace: Mapped[str] = mapped_column(String(20), nullable=False, default="agent", server_default="agent")

    # Topic organization
    topic: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Macro definitions (F1-F5)
    f1_macro: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    f2_macro: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    f3_macro: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    f4_macro: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    f5_macro: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status and ordering
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Unique constraint
    __table_args__ = (
        Index('ix_macro_sets_user_topic_name', 'user_key', 'topic', 'name', unique=True),
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<MacroSet(id={self.id}, namespace='{self.namespace}', topic='{self.topic}', name='{self.name}')>"


class MetaTopic(Base):
    """
    Meta topic database model.

    Represents a collection of macro sets mapped to extended function key slots.
    Allows combining multiple topics into a single extended keyboard (F1-F20+).
    ``namespace`` was added in Phase 4 to distinguish system vs agent meta topics.
    """

    __tablename__ = "meta_topics"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # User identifier (e.g., "default" until auth is implemented)
    user_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Namespace discriminator ("agent" or "system")
    namespace: Mapped[str] = mapped_column(String(20), nullable=False, default="agent", server_default="agent")

    # Meta topic metadata
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Topic mappings: JSON array of {topic: str, slot_start: str}
    # Example: [{"topic": "Algebra", "slot_start": "F1"}, {"topic": "Geometry", "slot_start": "F6"}]
    topic_mappings: Mapped[Any] = mapped_column(Text, nullable=False, default="[]")

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<MetaTopic(id={self.id}, namespace='{self.namespace}', name='{self.name}')>"


class AgentList(Base):
    """
    Agent List database model.

    Represents a named collection of agents for easy switching and organization.
    """

    __tablename__ = "agent_lists"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)

    # Core fields
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_key: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, default="default"
    )

    # Agent IDs (stored as JSON array)
    agent_ids: Mapped[Optional[List[int]]] = mapped_column(
        JSON, nullable=True, server_default='[]'
    )

    # Default flag
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation of agent list."""
        return f"<AgentList(id={self.id}, name='{self.name}', user_key='{self.user_key}')>"


class WorkflowList(Base):
    """
    Workflow List database model.

    Represents a named collection of workflow templates for easy organization and filtering.
    """

    __tablename__ = "workflow_lists"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)

    # Core fields
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_key: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, default="default"
    )

    # Workflow template IDs (stored as JSON array)
    workflow_ids: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True, server_default='[]'
    )

    # Default flag
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )

    # Tags for categorization and filtering
    tags: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True, server_default='[]'
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation of workflow list."""
        return f"<WorkflowList(id={self.id}, name='{self.name}', user_key='{self.user_key}')>"


class WorkflowTrigger(Base):
    """
    Workflow Trigger database model.

    Represents an event-driven trigger that can automatically execute workflows
    based on webhooks, schedules, or database events.
    """

    __tablename__ = "workflow_triggers"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)

    # Core fields
    workflow_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # Values: 'webhook', 'schedule', 'database'

    # Configuration
    config: Mapped[Dict] = mapped_column(MutableDict.as_mutable(JSON), nullable=False)
    # Trigger-specific configuration (JSON)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        """String representation of workflow trigger."""
        return f"<WorkflowTrigger(id={self.id}, workflow_id='{self.workflow_id}', type='{self.trigger_type}')>"


class WorkflowVersion(Base):
    """
    Workflow Version database model.

    Represents a specific version of a workflow template, enabling
    version tracking and A/B testing.
    """

    __tablename__ = "workflow_versions"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)

    # Core fields
    template_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # e.g., 'v1.0', 'v1.1', 'v2.0'

    # Configuration
    config: Mapped[Dict] = mapped_column(MutableDict.as_mutable(JSON), nullable=False)
    # Workflow configuration for this version
    changelog: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint('template_id', 'version', name='uq_template_version'),
    )

    def __repr__(self) -> str:
        """String representation of workflow version."""
        return f"<WorkflowVersion(template_id='{self.template_id}', version='{self.version}')>"


class ABTestConfig(Base):
    """
    A/B Test Configuration database model.

    Represents an A/B test configuration for comparing workflow versions.
    """

    __tablename__ = "ab_test_configs"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)

    # Core fields
    template_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Configuration
    versions: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    # List of version IDs to test
    traffic_split: Mapped[Dict] = mapped_column(JSON, nullable=False)
    # version -> percentage mapping
    metrics: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    # Metrics to track

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        """String representation of A/B test config."""
        return f"<ABTestConfig(id={self.id}, template_id='{self.template_id}', name='{self.name}')>"


class ABTestResult(Base):
    """
    A/B Test Result database model.

    Stores execution results for A/B test analysis.
    """

    __tablename__ = "ab_test_results"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)

    # Core fields
    ab_test_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    template_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    execution_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # Metrics
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Optional quality metric (0.0-1.0)
    success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # Whether execution succeeded
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        """String representation of A/B test result."""
        return f"<ABTestResult(ab_test_id={self.ab_test_id}, version='{self.version}', success={self.success})>"


# Add back-reference to Provider model
Provider.sync_schedule = relationship(
    "ProviderSyncSchedule",
    back_populates="provider",
    uselist=False,
    cascade="all, delete-orphan",
)


# ============================================================================
# Document Management System Models
# ============================================================================
# Note: These models use a separate database (cogitate_docs_en.db)
# ============================================================================


class Document(DocumentsBase):
    """
    Unified document model for all document types.
    
    Supports multiple document types via doc_type field:
    - 'help_page': Help documentation (Phase 1 focus)
    - 'user_guide': User guides (Phase 2)
    - 'manual': Technical manuals (Phase 2)
    - 'tutorial': Step-by-step tutorials (Phase 2)
    - 'faq': Frequently asked questions (Phase 2)
    - 'reference': Reference documentation (Phase 2)
    - 'quickstart': Quick start guides (Phase 2)
    
    Uses FTS5 for full-text search via documents_fts virtual table.
    """

    __tablename__ = "documents"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Core identification
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    doc_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default='help_page',
        index=True
    )
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    display_order: Mapped[int] = mapped_column(Integer, default=999, nullable=False, index=True)
    subtopic: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    context: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    author: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    version: Mapped[str] = mapped_column(String(20), default='1.0', nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # SEO/Discovery
    search_keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    relations: Mapped[List["DocumentRelation"]] = relationship(
        "DocumentRelation",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="DocumentRelation.document_id"
    )
    
    related_documents: Mapped[List["DocumentRelation"]] = relationship(
        "DocumentRelation",
        back_populates="related_document",
        foreign_keys="DocumentRelation.related_document_id"
    )
    
    analytics: Mapped[Optional["DocumentAnalytics"]] = relationship(
        "DocumentAnalytics",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        """String representation of document."""
        return f"<Document(id={self.id}, slug='{self.slug}', title='{self.title}', type='{self.doc_type}')>"


class DocumentRelation(DocumentsBase):
    """
    Document relation model.
    
    Links related documents together with typed relationships:
    - 'related': General related documents
    - 'see_also': Additional reading
    - 'prerequisite': Required reading before this document
    - 'next_step': Suggested next document to read
    """

    __tablename__ = "document_relations"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    document_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("documents.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    related_document_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("documents.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )

    # Relation metadata
    relation_type: Mapped[str] = mapped_column(
        String(50), 
        nullable=False, 
        default='related',
        index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="relations",
        foreign_keys=[document_id]
    )
    
    related_document: Mapped["Document"] = relationship(
        "Document",
        back_populates="related_documents",
        foreign_keys=[related_document_id]
    )

    # Unique constraint
    __table_args__ = (
        UniqueConstraint('document_id', 'related_document_id', 'relation_type', name='uq_document_relation'),
    )

    def __repr__(self) -> str:
        """String representation of document relation."""
        return f"<DocumentRelation(id={self.id}, document_id={self.document_id}, related_id={self.related_document_id}, type='{self.relation_type}')>"


class DocumentAnalytics(DocumentsBase):
    """
    Document analytics model.
    
    Tracks document views, feedback, and usage patterns for analytics.
    One record per document (enforced by UNIQUE constraint).
    """

    __tablename__ = "document_analytics"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True
    )

    # View tracking
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unique_views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Feedback tracking
    helpful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    not_helpful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    feedback_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Last viewed timestamp
    last_viewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="analytics"
    )

    def __repr__(self) -> str:
        """String representation of document analytics."""
        return f"<DocumentAnalytics(document_id={self.document_id}, views={self.view_count}, score={self.feedback_score})>"


class SystemFlag(Base):
    """
    Simple key-value store for system-level boolean flags.

    Flags (e.g. ``external_access_enabled``) survive server restarts
    because they are persisted in this table rather than in-memory.
    """

    __tablename__ = "system_flags"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(
        String(500), nullable=False, server_default=sa.text("''")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<SystemFlag(key='{self.key}', value='{self.value}')>"


class ShutdownRecord(Base):
    """The two-phase shutdown record (2026-09-12) — a message from a dying
    process to its successor.

    Written twice per shutdown: ``draining`` when the drain begins, then
    ``complete`` when it ends. A row still reading ``draining`` at the next
    boot is PROOF the previous exit died mid-shutdown — which is the entire
    reason for two phases. A single "last shutdown was clean" row could not
    tell a crash from a clean exit, because a crash leaves the PREVIOUS clean
    row sitting there and the successor reads it happily.

    THE RULE THIS HONOURS: nothing is abandoned silently, and a silence is
    itself reportable. If the dying process cannot speak at all, the missing
    completion is still the message.

    Retention: the newest ``SHUTDOWN_RECORD_KEEP`` rows; older pruned on
    write, so the table stays bounded without a TTL job.
    """

    __tablename__ = "shutdown_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    phase: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # NAMED, never counted: "2 things were abandoned" gives an operator nothing
    # to act on. These hold labels, not tallies.
    in_flight_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sa.text("'[]'")
    )
    completed_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sa.text("'[]'")
    )
    abandoned_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=sa.text("'[]'")
    )
    reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    def __repr__(self) -> str:
        return f"<ShutdownRecord(id={self.id}, phase='{self.phase}')>"


class CognitivePreset(Base):
    """
    Saved cognitive pipeline configuration preset.

    Presets define a named set of strategy overrides for the four pipeline
    components (context_builder, executor, memory_manager, response_formatter)
    plus optional metadata like temperature, memory settings, etc.

    Built-in presets (``is_builtin=True``) are seeded by the application and
    cannot be modified or deleted by users. User-created presets are fully
    editable.

    Preset Examples:
        - **fast**: Minimal context, no memory, direct response
        - **thorough**: Full context, memory enabled, multi-step reasoning
        - **creative**: High temperature, diverse context, associative memory
    """

    __tablename__ = "cognitive_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, unique=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Pipeline component strategy overrides
    context_builder: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=sa.text("'default'")
    )
    executor: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=sa.text("'default'")
    )
    memory_manager: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=sa.text("'default'")
    )
    response_formatter: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=sa.text("'default'")
    )

    # Extended configuration (temperature, memory settings, etc.)
    config_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="JSON blob for extended config (temperature, memory settings, etc.)",
    )

    # Metadata
    is_builtin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<CognitivePreset(id={self.id}, name='{self.name}', "
            f"is_builtin={self.is_builtin})>"
        )


class MemoryProfile(Base):
    """
    Memory profile database model.

    Defines a named memory configuration including strategy, window size,
    persistence backend, compaction, and summarization settings.

    Built-in profiles (``is_builtin=True``) are seeded by migrations and
    cannot be modified or deleted by users. User-created profiles are fully
    editable.

    Cognitive profiles reference a MemoryProfile via ``memory_profile_id``
    to compose full pipeline configurations.
    """

    __tablename__ = "memory_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, unique=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Strategy and parameters
    strategy: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=sa.text("'default'")
    )
    window_size: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=sa.text("50")
    )
    persistence: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=sa.text("'memory'")
    )
    compaction_threshold: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=None
    )
    summarization: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("false")
    )

    # Extended configuration
    config_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="JSON blob for extended memory config",
    )

    # Metadata
    is_builtin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    cognitive_profiles: Mapped[List["CognitiveProfile"]] = relationship(
        "CognitiveProfile",
        back_populates="memory_profile",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<MemoryProfile(id={self.id}, name='{self.name}', "
            f"strategy='{self.strategy}', is_builtin={self.is_builtin})>"
        )


class CognitiveProfile(Base):
    """
    Cognitive profile database model.

    Defines a named cognitive pipeline configuration that bundles strategy
    selectors (context_builder, executor, response_formatter) with a
    reference to a MemoryProfile.

    Built-in profiles (``is_builtin=True``) are seeded by migrations and
    cannot be modified or deleted by users. User-created profiles are fully
    editable.

    Agents reference a CognitiveProfile via ``cognitive_profile_id`` to
    determine their effective pipeline configuration.
    """

    __tablename__ = "cognitive_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, unique=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Pipeline component strategy overrides
    context_builder: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=sa.text("'default'")
    )
    executor: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=sa.text("'default'")
    )
    response_formatter: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=sa.text("'default'")
    )

    # FK to memory profile
    memory_profile_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("memory_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Extended configuration
    config_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="JSON blob for extended cognitive config",
    )

    # Metadata
    is_builtin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    memory_profile: Mapped[Optional["MemoryProfile"]] = relationship(
        "MemoryProfile",
        back_populates="cognitive_profiles",
        lazy="selectin",
    )
    agents: Mapped[List["Agent"]] = relationship(
        "Agent",
        back_populates="cognitive_profile",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<CognitiveProfile(id={self.id}, name='{self.name}', "
            f"is_builtin={self.is_builtin})>"
        )


class FrontendAgentPackage(Base):
    """
    Frontend agent package database model.

    Stores agent packages (code, prompts, tools) in database rows
    for the Agent Registry and Nucleus loader.

    Supports lifecycle status: active, experimental, archived, deprecated.
    Supports versioning via parent_version_id lineage.
    """

    __tablename__ = "frontend_agent_packages"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Core identification
    name: Mapped[str] = mapped_column(
        String(200), unique=True, nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(100), nullable=False, default="generic")
    version: Mapped[str] = mapped_column(
        String(50), nullable=False, default="1.0.0"
    )

    # Lifecycle status
    # Values: 'active', 'experimental', 'archived', 'deprecated'
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="experimental", index=True
    )

    # Agent content
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    code: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Python function as string — executed by Nucleus harness",
    )
    tools_schema: Mapped[Optional[Dict]] = mapped_column(
        JSON, nullable=True,
        comment="JSON schema describing available tools",
    )

    # Versioning lineage
    parent_version_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("frontend_agent_packages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Points to the previous version this was derived from",
    )

    # Package metadata (JSON — flexible evaluation scores, experiment groups, etc.)
    package_metadata: Mapped[Optional[Dict]] = mapped_column(
        JSON, nullable=True, default=dict,
        comment="Flexible JSON: evaluation scores, experiment groups, notes",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Self-referential relationship for lineage
    parent: Mapped[Optional["FrontendAgentPackage"]] = relationship(
        "FrontendAgentPackage",
        remote_side="FrontendAgentPackage.id",
        back_populates="children",
        lazy="selectin",
    )
    children: Mapped[List["FrontendAgentPackage"]] = relationship(
        "FrontendAgentPackage",
        back_populates="parent",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<FrontendAgentPackage(id={self.id}, name='{self.name}', "
            f"version='{self.version}', status='{self.status}')>"
        )


class AgentTimer(Base):
    """The external agent's one-shot timers (the EXA-TIMER v2, 2026-08-28).

    The DB-records so the pending timers survive the backend restarts —
    the scheduler's rebuilt from the records on boot.
    """

    __tablename__ = "agent_timers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timer_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    fires_at: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[float] = mapped_column(Float, default=time.time, nullable=False)


# ============================================================================
# The nine tables that existed only as migration DDL
# ============================================================================
#
# Before these classes existed, `create_all` built 45 of the live database's
# 56 tables: every workflow surface, agent versioning, the system-manager
# config and prompt templates were absent on every fresh database, and the
# migration chain that defined them could not be executed past revision 3.
# These classes are now the single definition of those tables;
# `alembic/versions/0001_baseline.py` is generated from them, and create_all
# and alembic agree by construction.
#
# Types, nullability, defaults and index names mirror the live schema exactly
# (`sqlite_master` DDL), including the TEXT-typed timestamps that
# `workflow_templates` uses. Five of the nine have no creating DDL anywhere in
# the repository — for those the live schema was the only record, and it is
# reproduced here column for column.


class WorkflowKind(Base):
    """The workflow kinds catalog — the browsable mirror of the code registry.

    Behaviour lives in `app/domain/workflows/kinds/registry.py`; this table
    carries the display fields (name, description, builder_key, product_type)
    per kind. `workflow_templates.kind_id` joins to it.
    """

    __tablename__ = "workflow_kinds"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    builder_key: Mapped[str] = mapped_column(String(128), nullable=False)
    product_type: Mapped[str] = mapped_column(String(32), nullable=False, default="report")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self) -> str:
        return f"<WorkflowKind(id='{self.id}', name='{self.name}')>"


class WorkflowTemplate(Base):
    """A workflow template — the saved, runnable workflow definition.

    The one table whose timestamps are TEXT rather than DATETIME: it was
    created by a migration that predates the convention, and every reader uses
    raw SQL, so the shape is preserved rather than modernised.
    """

    __tablename__ = "workflow_templates"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(Text, server_default=sa.text("'test'"))
    version: Mapped[Optional[str]] = mapped_column(Text, server_default=sa.text("'1.0.0'"))
    author: Mapped[Optional[str]] = mapped_column(Text, server_default=sa.text("'system'"))
    tags: Mapped[Optional[str]] = mapped_column(Text, server_default=sa.text("'[]'"))
    workflow_type: Mapped[Optional[str]] = mapped_column(Text, server_default=sa.text("'simple'"))
    config: Mapped[Optional[str]] = mapped_column(Text, server_default=sa.text("'{}'"))
    is_public: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=sa.text("1"))
    is_customizable: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=sa.text("1"))
    created_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    inputs: Mapped[Optional[str]] = mapped_column(Text, server_default=sa.text("'[]'"))
    kind_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<WorkflowTemplate(id='{self.id}', name='{self.name}')>"


class WorkflowComposition(Base):
    """A named, parameterized composition of workflows used as a building block.

    `config_json` holds the WorkflowComposition schema: id, name,
    workflows[order, workflow_id, input_mapping, output_mapping], version,
    tags. A composition is a capability, never a kind.
    """

    __tablename__ = "workflow_compositions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=sa.text("''"))
    config_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, server_default=sa.text("'{}'")
    )
    version: Mapped[Optional[str]] = mapped_column(String(20), server_default=sa.text("'1.0'"))
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=sa.text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("idx_workflow_compositions_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowComposition(id='{self.id}', name='{self.name}')>"


class WorkflowApproval(Base):
    """One approval request raised by a running workflow execution."""

    __tablename__ = "workflow_approvals"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    workflow_execution_id: Mapped[str] = mapped_column(Text, nullable=False)
    composition_id: Mapped[Optional[str]] = mapped_column(
        Text,
        ForeignKey("workflow_compositions.id", ondelete="SET NULL"),
        nullable=True,
    )
    template_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=sa.text("'pending'")
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    )
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approver_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approver_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timeout_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    auto_escalate: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default=sa.text("0")
    )
    # The column is literally named `metadata`, which declarative reserves —
    # the attribute is `meta`, as on ChatMessage.
    meta: Mapped[dict] = mapped_column(
        "metadata", JSON, nullable=False, server_default=sa.text("'{}'")
    )

    __table_args__ = (
        Index("idx_workflow_approvals_workflow", "workflow_execution_id"),
        Index("idx_workflow_approvals_composition", "composition_id"),
        Index("idx_workflow_approvals_status", "status"),
        Index("idx_workflow_approvals_requested", "requested_at"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowApproval(id='{self.id}', status='{self.status}')>"


class WorkflowExecutionHistory(Base):
    """The execution record of one workflow run — step progress, input, output."""

    __tablename__ = "workflow_execution_history"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    composition_id: Mapped[Optional[str]] = mapped_column(
        Text,
        ForeignKey("workflow_compositions.id", ondelete="SET NULL"),
        nullable=True,
    )
    template_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_execution_id: Mapped[Optional[str]] = mapped_column(
        Text,
        ForeignKey("workflow_execution_history.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=sa.text("'running'")
    )
    current_step: Mapped[Optional[int]] = mapped_column(Integer, server_default=sa.text("0"))
    total_steps: Mapped[Optional[int]] = mapped_column(Integer, server_default=sa.text("0"))
    input_data: Mapped[dict] = mapped_column(
        JSON, nullable=False, server_default=sa.text("'{}'")
    )
    output_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    elapsed_seconds: Mapped[Optional[float]] = mapped_column(
        Float, server_default=sa.text("0.0")
    )
    meta: Mapped[dict] = mapped_column(
        "metadata", JSON, nullable=False, server_default=sa.text("'{}'")
    )

    __table_args__ = (
        Index("idx_workflow_execution_history_composition", "composition_id"),
        Index("idx_workflow_execution_history_template", "template_id"),
        Index("idx_workflow_execution_history_parent", "parent_execution_id"),
        Index("idx_workflow_execution_history_status", "status"),
        Index("idx_workflow_execution_history_started", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowExecutionHistory(id='{self.id}', status='{self.status}')>"


class AgentVersion(Base):
    """A snapshot of an agent's configuration — the version history row."""

    __tablename__ = "agent_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    )

    def __repr__(self) -> str:
        return f"<AgentVersion(agent_id={self.agent_id}, v{self.version_number})>"


class SystemManagerConfig(Base):
    """The system-manager's LLM configuration and limit knobs (the single row)."""

    __tablename__ = "system_manager_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
        onupdate=func.now(),
    )
    show_tool_output: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("1")
    )
    tool_result_max_chars: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=sa.text("16000")
    )
    step_preview_max_chars: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=sa.text("16000")
    )
    max_context_tokens: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=sa.text("16000")
    )
    max_step_retries: Mapped[Optional[int]] = mapped_column(Integer, server_default=sa.text("2"))
    llm_retry_count: Mapped[Optional[int]] = mapped_column(Integer, server_default=sa.text("3"))
    llm_retry_delay_sec: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=sa.text("2")
    )
    max_iterations: Mapped[Optional[int]] = mapped_column(Integer, server_default=sa.text("0"))
    max_stack_depth: Mapped[Optional[int]] = mapped_column(Integer, server_default=sa.text("3"))
    max_mode_switches_per_turn: Mapped[Optional[int]] = mapped_column(
        Integer, server_default=sa.text("3")
    )

    def __repr__(self) -> str:
        return f"<SystemManagerConfig(id={self.id}, model='{self.model}')>"


class SystemManagerConfigRecord(Base):
    """A single key/value setting for the system manager.

    No code in the repository creates or reads this table — it exists in the
    live database and is modelled only so create_all and the baseline build the
    schema the live database actually has.
    """

    __tablename__ = "system_manager_config_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<SystemManagerConfigRecord(key='{self.key}')>"


class PromptTemplate(Base):
    """A stored prompt template, addressed by slug and versioned in place."""

    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_prompt_templates_active_slug", "is_active", "slug"),
    )

    def __repr__(self) -> str:
        return f"<PromptTemplate(slug='{self.slug}', v{self.version})>"


class SetupPick(Base):
    """One packaged configuration a fresh install can adopt in ONE press.

    THE PACKAGED FILE IS THE AUTHORITY (2026-11-21, the user's ruling): ``express_setup.json``
    ships in the repository and this table is its LOADED COPY — ``express_setup.load_packaged()``
    upserts it on every start, so a fresh install has picks without anyone running a command, and
    a row a user adds is never deleted by the loader.

    A pick names a MODEL, not a capability set. A model strong enough to drive the box answers
    chat, titles, summaries, workflows and memory alike; the five-capability split is legacy
    plumbing (2026-11-21). ``tier`` carries the honesty instead: ``strong`` is what we would run
    the box on, ``grab bag`` is a local model we cannot vouch for.

    ``needs_kind`` is the ONE thing that decides applicability: ``key`` (an env var that must be
    set), ``local`` (a server that must answer), ``none``.
    """

    __tablename__ = "setup_picks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # The packaged id — the stable handle a URL, a CLI flag and a user's note can all name
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)

    label: Mapped[str] = mapped_column(String(120), nullable=False)

    # The provider this pick dials: a NAME and a TYPE, because the row may not exist yet and the
    # address comes from PROVIDER_ENDPOINTS, never from this table
    provider_name: Mapped[str] = mapped_column(String(60), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(60), nullable=False)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)

    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="strong")

    needs_kind: Mapped[str] = mapped_column(String(10), nullable=False, default="key")
    needs_env: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    needs_url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    why: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # EVIDENCE, never an adjective: when it was proved and how. A null date is a pick nobody has
    # driven end to end yet, and every surface must say so rather than hide the row
    verified_on: Mapped[Optional[Any]] = mapped_column(Date, nullable=True)
    verified_how: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<SetupPick(key='{self.key}', {self.provider_name}/{self.model_id})>"
