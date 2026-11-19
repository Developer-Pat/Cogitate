"""External agent (Hermes/OpenClaw) domain — thin ACP client.

Business logic lives in services.py (AcpClient subprocess lifecycle,
protocol, event streaming). The API router (app/api/v1/...)
transports WebSocket messages and delegates here.
"""

from app.domain.external_agent import activation
from app.domain.external_agent.schemas import (
    DEFAULT_BRAINS,
    ExaBrain,
    ExternalAgentConfig,
    ExternalAgentConfigUpdate,
    ExternalAgentStatus,
)
from app.domain.external_agent.services import (
    AcpClient,
    AcpEvent,
    DEFAULT_CONFIG,
    ExternalAgentInactive,
    command_parts,
    get_acp_client,
    get_config,
    make_client,
    probe_runnable,
    save_config,
)

__all__ = [
    "AcpClient",
    "AcpEvent",
    "DEFAULT_BRAINS",
    "DEFAULT_CONFIG",
    "ExaBrain",
    "ExternalAgentConfig",
    "ExternalAgentConfigUpdate",
    "ExternalAgentInactive",
    "ExternalAgentStatus",
    "command_parts",
    "get_acp_client",
    "get_config",
    "make_client",
    "probe_runnable",
    "save_config",
]
