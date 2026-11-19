"""The per-agent state store and workspace provisioning tests.

THE SHALLOW-AGENT PROVISIONING (the user's ask): Bob (and any
agent) gains a workspace folder + a personal state store INSIDE it
(location/facts + sources) — per-agent files, NOT central cogitate.db
tables (the minimal-DB shipping direction). The agent can then WRITE
its own state via the keyed tools (the needs_workspace base_path
injection — writes land in agents/<key>/, never outside).
"""
import json
import os
import pytest
from pathlib import Path

from app.infrastructure.database.models import Agent

# ---------------------------------------------------------------------------
# 1. provision_workspace — the existing-row scaffold
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_provision_workspace_gives_key_and_folder(test_session, tmp_path, monkeypatch):
    """Provisioning an existing row assigns the stable key + scaffolds
    the folder (agent.json derived + skills/) + the state store."""
    from app.domain.agents.workspace import AGENTS_ROOT
    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)

    a = Agent(name="shallow-probe", provider="deepseek", model="deepseek-v4-flash", is_active=True)
    test_session.add(a)
    await test_session.commit()
    await test_session.refresh(a)

    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(test_session)
    result = await repo.provision_workspace(a.id)

    assert result is not None
    assert result.workspace_key == "shallow-probe"
    ws = tmp_path / "shallow-probe"
    assert (ws / "agent.json").exists()
    assert (ws / "skills").is_dir()
    blob = json.loads((ws / "agent.json").read_text())
    assert blob["name"] == "shallow-probe"
    assert blob["_derived"] is True


@pytest.mark.anyio
async def test_provision_workspace_idempotent(test_session, tmp_path, monkeypatch):
    """A second provision is a no-op — never a second folder or a
    key change (the workspace identity is stable)."""
    from app.domain.agents.workspace import AGENTS_ROOT
    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)

    a = Agent(name="shallow-probe", provider="deepseek", model="deepseek-v4-flash", is_active=True)
    test_session.add(a)
    await test_session.commit()
    await test_session.refresh(a)

    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(test_session)
    await repo.provision_workspace(a.id)
    await repo.provision_workspace(a.id)

    ws = tmp_path / "shallow-probe"
    assert result_ok(ws)


def result_ok(ws: Path) -> bool:
    return (ws / "agent.json").exists() and len(list((ws / "skills").iterdir())) == 0


# ---------------------------------------------------------------------------
# 2. the per-agent STATE STORE — facts + sources in the workspace
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_state_store_read_write_roundtrip(test_session, tmp_path, monkeypatch):
    """The store lives at agents/<key>/state.json — facts + sources
    survive a write/read roundtrip."""
    from app.domain.agents.workspace import AGENTS_ROOT
    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)

    a = Agent(name="shallow-probe", provider="deepseek", model="deepseek-v4-flash", is_active=True)
    test_session.add(a)
    await test_session.commit()
    await test_session.refresh(a)

    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(test_session)
    await repo.provision_workspace(a.id)

    from app.domain.agents.agent_state import AgentStateStore
    store = AgentStateStore(a.workspace_key)

    # an empty store reads clean
    state = store.read()
    assert state == {"facts": {}, "sources": []}

    # write a fact (the location example) — the record carries the
    # value + the source + the timestamp (the traceability)
    store.set_fact("location", "Omaha, Nebraska (user-told)")
    store.set_fact("timezone", "America/Chicago")
    store.update_sources(["https://www.ketv.com", "https://www.wowt.com"])
    state = store.read()
    assert state["facts"]["location"]["value"] == "Omaha, Nebraska (user-told)"
    assert state["facts"]["location"]["source"] == "user"
    assert state["facts"]["timezone"]["value"] == "America/Chicago"
    assert "https://www.ketv.com" in state["sources"]

    # a second store instance (the next turn) sees the SAME state
    store2 = AgentStateStore(a.workspace_key)
    state2 = store2.read()
    assert state2["facts"]["location"]["value"] == "Omaha, Nebraska (user-told)"
    assert len(state2["sources"]) == 2


@pytest.mark.anyio
async def test_state_store_validation(test_session, tmp_path, monkeypatch):
    """update_sources validates URL-ish entries; remove drops them."""
    from app.domain.agents.workspace import AGENTS_ROOT
    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)

    a = Agent(name="shallow-probe", provider="deepseek", model="deepseek-v4-flash", is_active=True)
    test_session.add(a)
    await test_session.commit()
    await test_session.refresh(a)
    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(test_session)
    await repo.provision_workspace(a.id)

    from app.domain.agents.agent_state import AgentStateStore
    store = AgentStateStore(a.workspace_key)

    # invalid sources are rejected (no protocol/domain)
    with pytest.raises(ValueError):
        store.update_sources(["not-a-url"])

    store.update_sources(["https://www.ketv.com", "https://www.wowt.com"])
    store.remove_sources(["https://www.ketv.com"])
    state = store.read()
    assert state["sources"] == ["https://www.wowt.com"]


# ---------------------------------------------------------------------------
# 3. the keyed WRITE tools (update-sources / update-state)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_update_sources_tool_writes_to_own_workspace(tmp_path):
    """The tool with the injected base_path writes the agent's own
    state.json and returns the VERIFIED read-back."""
    from app.domain.tools.builtin.agent_state_handler import UpdateSourcesTool
    tool = UpdateSourcesTool()

    ws = tmp_path / "agents" / "bob"
    ws.mkdir(parents=True)
    config = {"base_path": str(ws)}

    result = await tool.execute(config, action="add", sources=["https://www.ketv.com", "https://www.wowt.com"])
    assert result["success"] is True
    assert result["verified"] == ["https://www.ketv.com", "https://www.wowt.com"]

    # the file physically landed in the workspace
    state_file = ws / "state.json"
    assert state_file.exists()
    import json
    data = json.loads(state_file.read_text())
    assert data["sources"] == ["https://www.ketv.com", "https://www.wowt.com"]

    # remove works + returns the verified remainder
    result2 = await tool.execute(config, action="remove", sources=["https://www.ketv.com"])
    assert result2["success"] is True
    assert result2["verified"] == ["https://www.wowt.com"]


@pytest.mark.anyio
async def test_update_sources_tool_rejects_bad_urls(tmp_path):
    from app.domain.tools.builtin.agent_state_handler import UpdateSourcesTool
    tool = UpdateSourcesTool()
    ws = tmp_path / "agents" / "bob"
    ws.mkdir(parents=True)
    config = {"base_path": str(ws)}

    result = await tool.execute(config, action="add", sources=["ketv dot com"])
    assert result["success"] is False
    assert result["error_type"] == "validation"


@pytest.mark.anyio
async def test_update_sources_tool_requires_workspace():
    """No workspace yet → the tool says so (provision first) — no
    silent fallback, no writes outside the sandbox."""
    from app.domain.tools.builtin.agent_state_handler import UpdateSourcesTool
    tool = UpdateSourcesTool()
    result = await tool.execute({}, action="add", sources=["https://www.ketv.com"])
    assert result["success"] is False
    assert "no workspace" in result["error"].lower()


@pytest.mark.anyio
async def test_update_state_tool_stores_location_fact(tmp_path):
    """The user-told location lands in the agent's state with its
    source-of-truth note; the read-back verifies it."""
    from app.domain.tools.builtin.agent_state_handler import UpdateStateTool
    tool = UpdateStateTool()
    ws = tmp_path / "agents" / "bob"
    ws.mkdir(parents=True)
    config = {"base_path": str(ws)}

    result = await tool.execute(config, key="location", value="Omaha, Nebraska", source="user")
    assert result["success"] is True
    assert result["verified"] == {"location": "Omaha, Nebraska"}
    assert result["source"] == "user"

    import json
    data = json.loads((ws / "state.json").read_text())
    assert data["facts"]["location"]["value"] == "Omaha, Nebraska"
    assert data["facts"]["location"]["source"] == "user"


@pytest.mark.anyio
async def test_update_state_tool_rejects_bad_key(tmp_path):
    from app.domain.tools.builtin.agent_state_handler import UpdateStateTool
    tool = UpdateStateTool()
    ws = tmp_path / "agents" / "bob"
    ws.mkdir(parents=True)
    config = {"base_path": str(ws)}
    result = await tool.execute(config, key="Location With Spaces", value="x")
    assert result["success"] is False
    assert result["error_type"] == "validation"


# ---------------------------------------------------------------------------
# 4. the STATE-BLOCK injection (the prompt reflects the store)
# ---------------------------------------------------------------------------

def test_build_state_block_none_without_workspace():
    """No workspace/state → nothing injected (no phantom block)."""
    from app.domain.agents.agent_state import build_state_block
    assert build_state_block(None) is None
    assert build_state_block("") is None


@pytest.mark.anyio
async def test_build_state_block_reflects_the_store(test_session, tmp_path, monkeypatch):
    """The stored facts + sources surface as a compact YOUR-STATE
    block (the ONE home: the store is written by the tools, read by
    the prompt — no duplication)."""
    from app.domain.agents.workspace import AGENTS_ROOT
    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)

    a = Agent(name="shallow-probe", provider="deepseek", model="deepseek-v4-flash", is_active=True)
    test_session.add(a)
    await test_session.commit()
    await test_session.refresh(a)
    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(test_session)
    await repo.provision_workspace(a.id)

    from app.domain.agents.agent_state import AgentStateStore, build_state_block
    store = AgentStateStore(a.workspace_key)
    store.set_fact("location", "Omaha, Nebraska", source="user")
    store.update_sources(["https://www.ketv.com", "https://www.wowt.com"])

    block = build_state_block(a.workspace_key)
    assert block is not None
    assert "YOUR STORED STATE" in block
    assert "location: Omaha, Nebraska" in block
    assert "source: user" in block
    assert "https://www.ketv.com" in block
    assert "https://www.wowt.com" in block


def test_context_injects_state_block_without_name_gates():
    """prepare_chat_context surfaces the stored state for ANY agent
    with a workspace — the call is unconditional (the helper returns
    None without state); no agent-name gates remain."""
    import inspect
    from app.api.v1.chat.context import prepare_chat_context
    src = inspect.getsource(prepare_chat_context)
    assert "build_state_block" in src
    assert 'agent.name == "Bob"' not in src


# ---------------------------------------------------------------------------
# 5. THE FACT-DELETE GAP (Bob's finding, 2026-09-02): update-state had no
#    remove — facts could only be overwritten, never deleted. A test fact
#    (selfupdate-test) is sitting in Bob's state with no cleanup path.
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_store_remove_fact_deletes_the_key(test_session, tmp_path, monkeypatch):
    """remove_fact deletes the key ENTIRELY (not empties it) — the
    verified read-back has no trace of it."""
    from app.domain.agents.workspace import AGENTS_ROOT
    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)

    a = Agent(name="shallow-probe", provider="deepseek", model="deepseek-v4-flash", is_active=True)
    test_session.add(a)
    await test_session.commit()
    await test_session.refresh(a)
    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(test_session)
    await repo.provision_workspace(a.id)

    from app.domain.agents.agent_state import AgentStateStore
    store = AgentStateStore(a.workspace_key)
    store.set_fact("selfupdate-test", "ok — the live write test")
    store.set_fact("location", "Omaha, Nebraska")

    # delete ONE key — the other survives
    remaining = store.remove_fact("selfupdate-test")
    state = store.read()
    assert "selfupdate-test" not in state["facts"]
    assert state["facts"]["location"]["value"] == "Omaha, Nebraska"
    # the file itself has no trace (a true delete, not a tombstone)
    import json
    raw = json.loads((tmp_path / "shallow-probe" / "state.json").read_text())
    assert "selfupdate-test" not in raw["facts"]


@pytest.mark.anyio
async def test_store_remove_fact_unknown_key_noop(test_session, tmp_path, monkeypatch):
    """Removing a key that does not exist is a harmless no-op (the
    remaining state comes back untouched)."""
    from app.domain.agents.workspace import AGENTS_ROOT
    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)

    a = Agent(name="shallow-probe", provider="deepseek", model="deepseek-v4-flash", is_active=True)
    test_session.add(a)
    await test_session.commit()
    await test_session.refresh(a)
    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(test_session)
    await repo.provision_workspace(a.id)

    from app.domain.agents.agent_state import AgentStateStore
    store = AgentStateStore(a.workspace_key)
    store.set_fact("location", "Omaha")
    remaining = store.remove_fact("no-such-key")
    state = store.read()
    assert state["facts"]["location"]["value"] == "Omaha"
    assert len(state["facts"]) == 1


@pytest.mark.anyio
async def test_update_state_tool_remove_action(tmp_path):
    """The tool's remove action deletes the key and returns the
    VERIFIED read-back (no value argument needed for remove)."""
    from app.domain.tools.builtin.agent_state_handler import UpdateStateTool
    tool = UpdateStateTool()
    ws = tmp_path / "agents" / "bob"
    ws.mkdir(parents=True)
    config = {"base_path": str(ws)}

    # store a fact first (the tool's set path — action defaults to set)
    r1 = await tool.execute(config, key="selfupdate-test", value="ok")
    assert r1["success"] is True

    # remove it via the action
    r2 = await tool.execute(config, action="remove", key="selfupdate-test")
    assert r2["success"] is True
    assert r2["removed"] == "selfupdate-test"
    assert r2["verified"] == {}

    import json
    raw = json.loads((ws / "state.json").read_text())
    assert "selfupdate-test" not in raw["facts"]

    # removing again is a no-op success
    r3 = await tool.execute(config, action="remove", key="selfupdate-test")
    assert r3["success"] is True


# ---------------------------------------------------------------------------
# 6. THE WORKSPACE-FIRST MIGRATION (2026-09-02, the user's partition call):
#    Bob's persona + beat move to HIS folder; the DB row keeps registry
#    fields + a sync'd fallback. The inventory must survive (nothing
#    dropped) — the outlets stay in the sources store, the role/method
#    sentences stay in the persona.
# ---------------------------------------------------------------------------

# ---- the persona text: role/method stay, the BEAT OUTLET NAMES go ----

PERSONA_ROLE_ONLY = (
    "You are Bob, a news scout and reporter — the user's eyes on the world. "
    "You monitor the news, the weather, and what is happening in the world, "
    "and you report it back: briefly, clearly, and with the source attached.\n"
    "\n"
    "## Who you are\n"
    "- A scout, not a pundit: you find and report what is happening — you do "
    "not editorialize or speculate.\n"
    "- Attribution first: every item you report names the source that "
    "reported it. No source, no claim.\n"
    "- Your beat = the sources list in YOUR STORED STATE (the one home — "
    "update it with the update-sources tool when the beat changes).\n"
    "- When a topic matters, check the beat before answering.\n"
    "- Your locus is Omaha, Nebraska (US Central). \"Where am I\" = Omaha; "
    "\"what time is it\" = the local Central time — the current date and "
    "time are injected into your context every turn; state them exactly, "
    "never from memory.\n"
    "\n"
    "## How you chat\n"
    "- No emojis. Ever. Plain text carries the warmth — the emoji habit is "
    "banned.\n"
    "- Be warm and conversational. Plain language, a natural tone — never "
    "robotic or corporate.\n"
    "- Be a reporter in chat: lead with the lede, keep it short and "
    "scannable, and stop.\n"
    "- Match the person's level: casual when they are casual, thorough when "
    "they want depth.\n"
    "- Be honest and direct. If you do not know something, say so — then go "
    "find out.\n"
    "\n"
    "## How you search\n"
    "- Free and open-source tools first: duckduckgo for web searches, "
    "wikipedia for encyclopedic topics, jina_reader to fetch a page, the "
    "project's knowledge base for internal questions.\n"
    "- Before using any paid source or API-key tool: ASK first. Never spend "
    "without permission.\n"
    "- The loop: clarify the question, pick the right tool, search, read the "
    "results, fetch the promising sources, verify important claims against a "
    "second source, and report with the sources — or honestly say what you "
    "could not find.\n"
    "- Never invent a source. A real-but-vague answer beats a fabricated "
    "citation.\n"
    "\n"
    "## What you are not\n"
    "- You are not a software engineer by default. If someone wants coding "
    "help, you can still search and answer — but your home is conversation, "
    "news, research, and explaining things clearly."
)

# the OLD text carried the outlet NAMES (Reuters/AP/Drudge/Antiwar) —
# the migration MUST drop them from the persona and point at the store
BEAT_OUTLETS = ["Reuters", "Drudge", "Antiwar", "ketv.com", "wowt.com"]


def test_persona_drops_beat_outlet_names():
    """THE BEAT SINGLE-HOME: the persona text names NO outlets — the
    beat lives in the sources store (state.json), pointed to by the
    YOUR STORED STATE line. Prose naming outlets = the drift."""
    for outlet in BEAT_OUTLETS:
        assert outlet.lower() not in PERSONA_ROLE_ONLY.lower()
    assert "sources list in YOUR STORED STATE" in PERSONA_ROLE_ONLY
    # the role + method sentences SURVIVE (nothing dropped)
    for keep in ("news scout", "Attribution first", "lede", "jina_reader",
                 "Never invent a source", "Omaha, Nebraska"):
        assert keep.lower() in PERSONA_ROLE_ONLY.lower()


# ---- the persona FILE read path (folder-first, row fallback) ----

@pytest.mark.anyio
async def test_read_persona_prefers_the_folder_file(test_session, tmp_path, monkeypatch):
    """The context builder reads persona.md from the agent's folder
    when it exists; falls back to the row's system_prompt otherwise."""
    from app.domain.agents.workspace import AGENTS_ROOT
    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)

    a = Agent(name="shallow-probe", provider="deepseek", model="deepseek-v4-flash",
              is_active=True, system_prompt="ROW PERSONA (fallback text)")
    test_session.add(a)
    await test_session.commit()
    await test_session.refresh(a)
    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(test_session)
    await repo.provision_workspace(a.id)

    from app.domain.agents.persona import read_persona
    # no persona.md yet -> the row fallback
    assert read_persona(a) == "ROW PERSONA (fallback text)"

    # write persona.md in the folder -> the FILE wins
    (tmp_path / "shallow-probe" / "persona.md").write_text(PERSONA_ROLE_ONLY, encoding="utf-8")
    assert read_persona(a) == PERSONA_ROLE_ONLY


# ---- the persona WRITE path (update syncs the file) ----

@pytest.mark.anyio
async def test_update_syncs_persona_file(test_session, tmp_path, monkeypatch):
    """Updating the system_prompt via the service syncs persona.md
    when the agent has a workspace (folder-first, row fallback)."""
    from app.domain.agents.workspace import AGENTS_ROOT
    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)

    a = Agent(name="shallow-probe", provider="deepseek", model="deepseek-v4-flash",
              is_active=True, system_prompt="OLD")
    test_session.add(a)
    await test_session.commit()
    await test_session.refresh(a)
    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(test_session)
    await repo.provision_workspace(a.id)

    from app.domain.agents.schemas import AgentUpdate
    from app.domain.agents.services import AgentService
    svc = AgentService(test_session)
    await svc.update(a.id, AgentUpdate(system_prompt=PERSONA_ROLE_ONLY))

    await test_session.refresh(a)
    assert a.system_prompt == PERSONA_ROLE_ONLY  # the row fallback is synced
    pfile = tmp_path / "shallow-probe" / "persona.md"
    assert pfile.exists()  # the file is written (the workspace home)
    assert pfile.read_text(encoding="utf-8") == PERSONA_ROLE_ONLY


# ---- the SKILLS partition: agent skills readable through skill-reader ----

@pytest.mark.anyio
async def test_skill_reader_falls_back_to_agent_folder(tmp_path, monkeypatch):
    """Agent-specific skills (agents/<key>/skills/) are readable
    through the skill reader when the global lookup misses — the
    generic-vs-specific partition wired into the tool surface."""
    import app.domain.tools.builtin.skill_reader_handler as mod

    global_root = tmp_path / "skills-global"
    (global_root / "generic").mkdir(parents=True)
    (global_root / "generic" / "shared-procedure.skill.md").write_text(
        "---\nname: shared-procedure\ndescription: A generic skill\n---\nBODY\n"
    )
    agent_root = tmp_path / "agents" / "bob" / "skills"
    agent_root.mkdir(parents=True)
    (agent_root / "self-state-maintenance.skill.md").write_text(
        "---\nname: self-state-maintenance\ndescription: Bob's personal skill\n---\nBODY\n"
    )
    monkeypatch.setattr(mod, "SKILLS_ROOT", str(global_root))

    tool = mod.SkillReaderTool()
    config = {"base_path": str(tmp_path / "agents" / "bob")}
    # global lookup hits a generic skill
    r = await tool.execute(config, skill_name="shared-procedure")
    assert r.get("success") is True
    # the agent's personal skill is found via the folder fallback
    r2 = await tool.execute(config, skill_name="self-state-maintenance")
    assert r2.get("success") is True, r2
    assert "Bob's personal skill" in r2.get("skill", {}).get("description", "")
    # unknown still fails cleanly
    r3 = await tool.execute(config, skill_name="no-such-skill")
    assert r3.get("success") is False
