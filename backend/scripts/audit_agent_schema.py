"""THE CLASS AUDIT: model columns vs the write schemas.

The image bug was not one missing field — it was the PATTERN: a column
exists on the model, the schema omits it, and the endpoint silently
drops whatever the client sent. `create_template` had it. `AgentUpdate`
had it. This finds every instance so the fix is the class, not the site.

Run: cd backend && ../.venv/bin/python3 scripts/audit_agent_schema.py
"""
import sys

sys.path.insert(0, ".")

from app.domain.agents.schemas import AgentCreate, AgentUpdate  # noqa: E402
from app.infrastructure.database.models import Agent  # noqa: E402

SERVER_MANAGED = {
    "id", "created_at", "updated_at",
    "workspace_key",       # the disk identity — set once at provisioning
    "template_id",         # set by the apply path
    "cognitive_profile_name", "cognitive_profile_depth",  # readouts
    # the lifecycle: owned by the archive / delete / health flows, never a client
    "archived_path", "deleted_at", "health_dismissed_at", "is_builtin",
    # the toolkit: owned by the kit / package adoption flows (dedicated endpoints)
    "kit_id", "llm_spec", "package_id",
}


def main() -> int:
    model_cols = {c.name for c in Agent.__table__.columns}
    writable = model_cols - SERVER_MANAGED
    update_fields = set(AgentUpdate.model_fields)
    create_fields = set(AgentCreate.model_fields)

    print("=" * 70)
    print(f"writable model columns : {len(writable)}")
    print(f"AgentUpdate fields     : {len(update_fields)}")
    print(f"AgentCreate fields     : {len(create_fields)}")
    print("=" * 70)

    upd_missing = sorted(writable - update_fields)
    crt_missing = sorted(writable - create_fields)

    print("\n[PUT /agents/{id}] writable on the model, ABSENT from AgentUpdate")
    print("  -> the client can send these and they are SILENTLY DROPPED")
    if upd_missing:
        for c in upd_missing:
            print(f"     ✗ {c}")
    else:
        print("     ✓ none")

    print("\n[POST /agents] writable on the model, ABSENT from AgentCreate")
    if crt_missing:
        for c in crt_missing:
            print(f"     ✗ {c}")
    else:
        print("     ✓ none")

    print("\nschema-only readouts (correctly not writable):")
    for c in sorted(update_fields - model_cols):
        print(f"     · {c}")

    return 1 if (upd_missing or crt_missing) else 0


def check_frontend_names() -> list[str]:
    """The names the frontend PUTs vs the names AgentUpdate declares.

    A FIELD-NAME mismatch is silent in both directions: the frontend
    sends `image_url`, the backend expects `profile_image_url`, and
    Pydantic drops the unknown field without a word. This is how the
    image-assignment bug hid.
    """
    import re
    from pathlib import Path as _P

    # resolve from this file (scripts/ -> backend/ -> repo root), so the
    # check works from any cwd — the tests run it from several
    src = _P(__file__).resolve().parents[2] / "frontend/src/services/domain/ProfileService.ts"
    if not src.exists():
        return []
    text = src.read_text(encoding="utf-8")
    i = text.find("async updateProfile(")
    seg = text[i:i + 3000]
    sent = sorted(set(re.findall(r"backendData\.([a-z_]+)\s*=", seg)))
    declared = set(AgentUpdate.model_fields)
    return [f for f in sent if f not in declared]


if __name__ == "__main__":
    bad = check_frontend_names()
    print("\n[frontend -> backend] names PUT but NOT declared in AgentUpdate")
    print("  -> sent by the UI, silently dropped by Pydantic")
    if bad:
        for name in bad:
            print(f"     ✗ {name}")
    else:
        print("     ✓ none")
    raise SystemExit(main() or (1 if bad else 0))
