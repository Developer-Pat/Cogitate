"""The agent write-schema contract tests.

The bug: the user assigned a profile image, the UI said it worked, and
the image never stuck. Two silent failures compounded:

  1. the frontend PUT `image_url`; the backend declares
     `profile_image_url` — Pydantic drops unknown fields without a word;
  2. even with the right name, `AgentUpdate` did not declare the field,
     so the value was dropped again on the way in.

Both directions are silent, which is why this needs a test rather than
care. scripts/audit_agent_schema.py does the analysis; these are the
guards that keep it true.
"""

import sys
from pathlib import Path

# resolve from THIS file so the suite runs from any cwd
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[3]
sys.path.insert(0, str(_ROOT / "backend"))
sys.path.insert(0, str(_ROOT / "backend" / "scripts"))

from app.domain.agents.schemas import AgentCreate, AgentUpdate  # noqa: E402
from app.infrastructure.database.models import Agent  # noqa: E402

# Columns a client must never write: the lifecycle owns them (archive /
# delete / health) and the toolkit owns those (the kit + package
# adoption flows have dedicated endpoints).
SERVER_MANAGED = {
    "id", "created_at", "updated_at",
    "workspace_key",     # the disk identity — set once at provisioning
    "template_id",       # set by the apply path
    "cognitive_profile_name", "cognitive_profile_depth",  # readouts
    "archived_path", "deleted_at", "health_dismissed_at", "is_builtin",
    "kit_id", "llm_spec", "package_id",
}

# Names the frontend still PUTs that the backend does not declare. They
# are dropped in silence today; listed here so a NEW one fails the test
# instead of hiding. Each is a candidate for removal or a real field.
KNOWN_FRONTEND_PHANTOMS = {
    "tools",    # superseded by the kit (the tool surface)
    "memory",
    "options",
}


class TestAgentWriteContract:
    def test_every_writable_column_is_updatable(self):
        """PUT can write every column a client legitimately owns."""
        writable = {c.name for c in Agent.__table__.columns} - SERVER_MANAGED
        missing = sorted(writable - set(AgentUpdate.model_fields))
        assert missing == [], (
            f"AgentUpdate silently drops: {missing}. Add them to the "
            f"schema (and to SERVER_MANAGED if a client must not write them)."
        )

    def test_every_writable_column_is_creatable(self):
        writable = {c.name for c in Agent.__table__.columns} - SERVER_MANAGED
        missing = sorted(writable - set(AgentCreate.model_fields))
        assert missing == [], f"AgentCreate silently drops: {missing}"

    def test_the_image_and_the_skills_are_writable(self):
        """The two fields this bug was about, named explicitly."""
        assert "profile_image_url" in AgentUpdate.model_fields
        assert "skills" in AgentUpdate.model_fields
        assert "profile_image_url" in AgentCreate.model_fields

    def test_the_workspace_key_is_never_client_writable(self):
        """A rename must not move files — the disk identity is ours."""
        assert "workspace_key" in SERVER_MANAGED

    def test_frontend_field_names_match_the_backend(self):
        """What the UI PUTs must be declared — a mismatch is silent."""
        from audit_agent_schema import check_frontend_names

        bad = set(check_frontend_names())
        new = sorted(bad - KNOWN_FRONTEND_PHANTOMS)
        assert new == [], (
            f"the frontend PUTs {new}, which AgentUpdate does not declare — "
            f"Pydantic will drop them silently. Map the name or add the field."
        )
