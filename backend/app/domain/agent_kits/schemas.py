from typing import Optional

from pydantic import BaseModel, Field


class KitSummary(BaseModel):
    """The toolkit as the UI shows it (a tool-typed collection)."""

    id: str
    name: str
    description: Optional[str] = None
    color: str = "#3B82F6"
    icon: str = "folder"


class AgentKitAttach(BaseModel):
    """The attach request body."""

    kit_id: str = Field(..., description="The tool-typed collection (kit) to attach")


class AgentKitsResponse(BaseModel):
    """The agent's toolkits (the kits-for-agent direction)."""

    agent_id: int
    kits: list[KitSummary]


class AgentOwnerSummary(BaseModel):
    """An agent that owns a kit (the agents-for-kit direction)."""

    id: int
    name: str


class AgentOwnersResponse(BaseModel):
    """The agents that own a kit."""

    kit_id: str
    agents: list[AgentOwnerSummary]
