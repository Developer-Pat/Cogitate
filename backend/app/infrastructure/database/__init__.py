"""
Database module.

Provides database configuration, session management, and models.
"""

from app.core.database import Base, engine, AsyncSessionLocal, get_db_session, init_db, close_db

# Import all models to ensure they are registered with Base.metadata
# This is required for create_all() to work correctly
from app.infrastructure.database.models import (
    Agent,
    ChatSession,
    ChatMessage,
    RuntimeConfig,
    Provider,
    Capability,
    CapabilityService,
    UsageLog,
    AgentTemplate,
    Log,
    # Cognitive pipeline models
    SystemFlag,
    # Document management models
    Document,
    DocumentRelation,
    DocumentAnalytics,
    # Cheat sheets
)

# Import collections models
from app.domain.collections.models import (
    Collection,
    CollectionItem,
)

# Import the agent-kits join (the plural toolkit ownership)
from app.domain.agent_kits.model import AgentKit

# Import agent packages models (Phase 1 — the blueprint)
from app.domain.agent_packages.models import AgentPackage  # noqa: F401 — registers its table on Base.metadata

# Import the tools models FIRST: `team_tools` carries a foreign key into `tools`,
# and a metadata that is missing the target table cannot even be sorted — the
# whole app imports through the routers, so this only bit code that imports the
# database package on its own (alembic autogenerate, schema scripts).
from app.domain.tools.models import (  # noqa: F401 — registers its tables on Base.metadata
    AgentTool,
    AgentToolGrant,
    Tool,
    ToolCategory,
    ToolUsageLog,
)
from app.domain.tools.tool_permission_models import (  # noqa: F401
    ToolCollectionPermission,
)

# Import team tools model (resolves Collection.team_tools relationship)
from app.domain.tools.team_tools import TeamTool

__all__ = [
    # Database utilities
    'Base',
    'engine',
    'AsyncSessionLocal',
    'get_db_session',
    'init_db',
    'close_db',
    # Models
    'Agent',
    'ChatSession',
    'ChatMessage',
    'RuntimeConfig',
    'Provider',
    'Capability',
    'CapabilityService',
    'UsageLog',
    'AgentTemplate',
    'Log',
    # Cognitive pipeline models
    'SystemFlag',
    # Collections models
    'Collection',
    'CollectionItem',
    'TeamTool',
    'AgentKit',
    # Tools models
    'Tool',
    'ToolCategory',
    'AgentTool',
    'AgentToolGrant',
    'ToolUsageLog',
    'ToolCollectionPermission',
    # Document management models
    'Document',
    'DocumentRelation',
    'DocumentAnalytics',
]
