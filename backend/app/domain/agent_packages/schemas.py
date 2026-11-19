"""
Agent Packages domain schemas.

The llm_spec vocabulary (the design, local/agent-package/01-design.md):
- kind:       chat | workflow        (the role)
- thinking:   none | low | medium | high   (declared, not measured)
- location:   local | cloud | any
- min_context: int                    (optional floor, e.g. 16384)
- max_output:  int                    (optional — the declared output budget)
"""

from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator


class LlmSpec(BaseModel):
    """The advisory LLM capability contract."""

    kind: Literal["chat", "workflow"] = Field("chat", description="The agent's role")
    thinking: Literal["none", "low", "medium", "high"] = Field(
        "none", description="Declared thinking level (advisory, not measured)"
    )
    location: Literal["local", "cloud", "any"] = Field(
        "any", description="Where the LLM should run"
    )
    min_context: Optional[int] = Field(None, description="Minimum context length")
    # THE DECLARED OUTPUT BUDGET (the token-limit arc, E.3 — D2's package half).
    # The schema carries it from here on: E.3's window-fit warning reads it at match
    # and provision time ("can this driver hold the prompt floor AND the answer?"),
    # and **F.1** is what makes the RESOLVER read it as the type default the agent
    # inherits. Declared, then load-bearing — not load-bearing, then declared.
    max_output: Optional[int] = Field(
        None, description="The declared output budget this package's agents run with"
    )


class AgentPackageBase(BaseModel):
    """Base schema for agent packages."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Package name", max_length=100)
    description: Optional[str] = Field(None, description="Package description")
    kit_id: Optional[str] = Field(None, description="The toolkit ref (a tool-typed collection id)")
    skills: List[str] = Field(default_factory=list, description="The recommended skillset")
    llm_spec: Optional[LlmSpec] = Field(None, description="The advisory LLM contract")


class AgentPackageCreate(AgentPackageBase):
    """Schema for creating a package."""

    @field_validator("skills")
    @classmethod
    def clean_skills(cls, v: List[str]) -> List[str]:
        return [s.strip() for s in v if s and s.strip()]


class AgentPackageUpdate(BaseModel):
    """Schema for updating a package (partial)."""

    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    kit_id: Optional[str] = None
    skills: Optional[List[str]] = None
    llm_spec: Optional[LlmSpec] = None
    is_active: Optional[bool] = None


class AgentPackageResponse(AgentPackageBase):
    """Schema for package responses."""

    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AgentPackageListResponse(BaseModel):
    """The list response."""

    packages: List[AgentPackageResponse]
    total: int
