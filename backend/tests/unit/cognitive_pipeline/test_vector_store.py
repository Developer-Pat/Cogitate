"""The turn vector store and its registry, including the type guard.

Tests cover:
- Registry operations (register, get, list, error cases)
- The default registry's own rule: a store needs an embedding service, so one is registered ONLY
  when the install has resolved one (the service-literals arc's model half)
- VectorStore DB creation and lifecycle
- Turn indexing (graceful failure when the embedding server is down)
- Search (graceful empty results)
- Session removal and clear all

The store's embedding service is no longer defaulted inside it (`DEFAULT_OLLAMA_BASE`,
`DEFAULT_EMBEDDING_MODEL`, `DEFAULT_EMBEDDING_DIMS` were three copies of one decision): it is passed
in, and these tests supply it — a resolved one where the store must work, an UNRESOLVED one where the
point is the refusal.
"""
import os
import sqlite3
import tempfile
import pytest
from app.domain.providers.embeddings import EmbeddingService
from app.services.cognitive_pipeline.vector_store import (
    TurnVectorStore,
    VectorStoreRegistry,
    create_default_vector_store_registry,
)


def _test_embedding(address: str = "http://127.0.0.1:11434", dims: int = 768) -> EmbeddingService:
    """A RESOLVED embedding service — the address, model and width a store works with."""
    return EmbeddingService(address=address, model="nomic-embed-text", dims=dims)


# ── Registry Tests ────────────────────────────────────────────────────────────


class TestVectorStoreRegistry:
    def test_register_and_get(self):
        reg = VectorStoreRegistry()
        store = TurnVectorStore(agent_folder="test_reg", embedding=_test_embedding())
        reg.register("test", store)
        assert reg.get("test") is store

    def test_list(self):
        reg = VectorStoreRegistry()
        reg.register("a", TurnVectorStore(agent_folder="a", embedding=_test_embedding()))
        reg.register("b", TurnVectorStore(agent_folder="b", embedding=_test_embedding()))
        assert reg.list() == ["a", "b"]

    def test_get_missing_raises(self):
        reg = VectorStoreRegistry()
        with pytest.raises(KeyError, match="not registered"):
            reg.get("nonexistent")

    def test_register_duplicate_overwrites(self):
        reg = VectorStoreRegistry()
        s1 = TurnVectorStore(agent_folder="s1", embedding=_test_embedding())
        s2 = TurnVectorStore(agent_folder="s2", embedding=_test_embedding())
        reg.register("x", s1)
        reg.register("x", s2)
        assert reg.get("x") is s2

    def test_register_rejects_non_vectorstore(self):
        reg = VectorStoreRegistry()
        with pytest.raises(TypeError, match="Expected VectorStore"):
            reg.register("bad", "not_a_store")  # type: ignore

    def test_default_registry_has_turn_when_the_embeddings_capability_resolves(self):
        reg = create_default_vector_store_registry(_test_embedding())
        assert "turn" in reg.list()
        assert isinstance(reg.get("turn"), TurnVectorStore)

    def test_default_registry_registers_NOTHING_without_an_embedding_service(self):
        """An install with no embedding model gets no turn store, so recall SKIPS rather than fails.

        The pipeline's recall step already reads a missing `turn` store as "skip" — which is the
        honest behaviour, and the alternative here would be a store that embeds with a default nobody
        configured.
        """
        assert create_default_vector_store_registry(None).list() == []
        assert create_default_vector_store_registry(EmbeddingService()).list() == []


# ── TurnVectorStore Tests ─────────────────────────────────────────────────────


class TestTurnVectorStoreInit:
    def test_db_path_is_under_vector_index(self):
        store = TurnVectorStore(agent_folder="test_store", embedding=_test_embedding())
        assert "test_store" in store.db_path
        assert "vector_index" in store.db_path
        assert store.db_path.endswith("chunks.db")

    def test_db_creates_tables(self):
        store = TurnVectorStore(agent_folder="test_store_tables", embedding=_test_embedding())
        conn = store._get_conn()
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        names = {r[0] for r in tables}
        assert "turn_chunks" in names
        assert "vec_turns" in names

    def test_index_turn_ollama_unavailable_returns_false(self):
        """Should return False gracefully when the embedding server is not running."""
        store = TurnVectorStore(
            agent_folder="test_fail",
            embedding=_test_embedding(address="http://localhost:19999"),  # wrong port
        )
        result = store.index_turn(
            session_id="s1", role="user", content="Hello", turn_index=1
        )
        assert result is False

    def test_search_empty_when_ollama_down(self):
        store = TurnVectorStore(
            agent_folder="test_search_empty",
            embedding=_test_embedding(address="http://localhost:19999"),
        )
        results = store.search("test query", top_k=3)
        assert results == []

    def test_an_unresolved_service_refuses_instead_of_embedding(self):
        """An unresolved service embeds NOTHING — no address, no model, no width, no call."""
        store = TurnVectorStore(agent_folder="test_unresolved", embedding=EmbeddingService())

        assert store.index_turn(session_id="s1", role="user", content="Hello") is False
        assert store.search("test query") == []

    def test_remove_session_noop_on_empty_db(self):
        store = TurnVectorStore(agent_folder="test_remove_empty", embedding=_test_embedding())
        count = store.remove_session("nonexistent_session")
        assert count == 0

    def test_clear_all_noop_on_empty_db(self):
        store = TurnVectorStore(agent_folder="test_clear_empty", embedding=_test_embedding())
        count = store.clear_all()
        assert count == 0  # or whatever the initial state is


# ── Cleanup ───────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def cleanup_test_dirs():
    """Remove test agent directories after each test."""
    yield
    # Paths, not a crawl: the cleanup must target the TEMPORARY agents root it
    # created, never production's.
    from app.core.config import Paths, get_settings

    base = str(Paths.from_settings(get_settings()).agents_dir)
    for name in [
        "test_reg", "a", "b", "s1", "s2",
        "test_store", "test_store_tables",
        "test_fail", "test_search_empty", "test_unresolved",
        "test_remove_empty", "test_clear_empty",
        "default",
    ]:
        vec_dir = os.path.join(base, name, "vector_index")
        db_file = os.path.join(vec_dir, "chunks.db")
        if os.path.exists(db_file):
            os.unlink(db_file)
        if os.path.exists(vec_dir):
            os.rmdir(vec_dir)
        agent_dir = os.path.join(base, name)
        if os.path.exists(agent_dir):
            os.rmdir(agent_dir)
