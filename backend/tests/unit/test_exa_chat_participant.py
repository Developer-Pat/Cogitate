"""An Exa session carries a null agent id through the schema, the service and the API.

- the session creation accepts agent_id=null with source='exa'
  (the external surface — the migration made the column nullable)
- the ExternalAgentConfig carries the image (the face)
- the config update handler passes the image through
"""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.core.config import Paths, get_settings

app = create_app()


@pytest.fixture
def test_client():
    with TestClient(app) as tc:
        yield tc


from app.domain.sessions.schemas import SessionCreate
from app.domain.external_agent.schemas import ExternalAgentConfig, ExternalAgentConfigUpdate


def test_exa_session_schema_allows_null_agent():
    s = SessionCreate(agent_id=None, title="Exa chat", source="exa")
    assert s.agent_id is None
    assert s.source == "exa"


def test_exa_session_create_via_service():
    # the service path — the API-level models are loaded by the
    # test suite's fixtures; here we verify the schema+service contract
    from app.domain.sessions.services import SessionService
    # (the service's create is exercised end-to-end in the API tests;
    # this asserts the schema accepts the exa shape)
    s = SessionCreate(agent_id=None, title="Exa chat", source="exa")
    assert s.model_dump()["agent_id"] is None


def test_config_carries_image():
    cfg = ExternalAgentConfig(command="hermes acp", cwd="", fix_mode=False,
                              max_turn_seconds=300, image="/static/alien-rocky.png")
    assert cfg.image == "/static/alien-rocky.png"
    upd = ExternalAgentConfigUpdate(image="/static/alien-01.png")
    assert upd.image == "/static/alien-01.png"


def test_chat_sessions_agent_id_nullable_in_db():
    import sqlite3
    from app.core.config import Paths
    con = sqlite3.connect(str(Paths.from_settings(get_settings()).shared_db))
    try:
        cols = {d[1]: d for d in con.execute("PRAGMA table_info(chat_sessions)").fetchall()}
    finally:
        con.close()
    assert cols["agent_id"][3] == 0, "agent_id must be nullable (the migration)"


@pytest.mark.asyncio
async def test_exa_session_created_via_api(test_client):
    # the API path — create an exa session + verify the row
    r = test_client.post("/api/v1/sessions", json={
        "agent_id": None, "title": "Exa test", "source": "exa",
    })
    assert r.status_code == 201
    d = r.json()
    assert d["agent_id"] is None
    assert d["id"] > 0
    # cleanup
    test_client.delete(f"/api/v1/sessions/{d['id']}")


def test_exa_message_persistence_via_api(test_client):
    # the bridge's save path: create an exa session + POST messages
    r = test_client.post("/api/v1/sessions", json={
        "agent_id": None, "title": "Exa msgs", "source": "exa",
    })
    assert r.status_code == 201
    sid = r.json()["id"]
    try:
        for role, content in [("user", "hello exa"), ("assistant", "hi there")]:
            mr = test_client.post(
                f"/api/v1/sessions/{sid}/messages",
                json={"role": role, "content": content},
            )
            assert mr.status_code == 201
            d = mr.json()
            assert d["role"] == role
            assert d["content"] == content
            assert d["session_id"] == sid
        # the session now carries the messages
        sr = test_client.get(f"/api/v1/sessions/{sid}")
        assert sr.status_code == 200
        roles = [m["role"] for m in sr.json()["messages"]]
        assert roles == ["user", "assistant"]
    finally:
        test_client.delete(f"/api/v1/sessions/{sid}")
