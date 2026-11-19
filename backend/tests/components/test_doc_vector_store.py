"""
DocVectorStore chunking — heading splits, nesting, and oversized sections.

Covers:
    - Task 6.1: Heading-aware chunking, oversized sections, empty doc
    - Task 6.2: DocVectorStore init, embed, search, re-index
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from app.domain.providers.embeddings import EmbeddingService
from app.domain.tools.builtin.doc_vector_store import (
    DocVectorStore,
    chunk_document,
)

# =============================================================================
# Fixtures
# =============================================================================


def _test_embedding(dims: int = 4) -> EmbeddingService:
    """A RESOLVED embedding service for these tests — the store's one required dependency.

    It is no longer a default inside the store: the address, the model and the width come from the
    `embeddings` capability (`resolve_embedding_service`), which needs a configured install. These
    tests are about the STORE, so the service is supplied directly; the model name is the real one and
    the width is small (4) to keep the vec0 tables cheap.
    """
    return EmbeddingService(address="http://127.0.0.1:11434", model="nomic-embed-text", dims=dims)


# =============================================================================


@pytest.fixture
def temp_db_path() -> str:
    """Provide a temporary database file path and clean up after the test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def store(temp_db_path: str) -> DocVectorStore:
    """Create a fresh DocVectorStore with a temp database and no singleton state."""
    DocVectorStore.reset_instance()
    s = DocVectorStore.get_instance(
        db_path=temp_db_path,
        embedding=_test_embedding(4),  # small dims for fast tests
    )
    s.init_db()
    return s


# =============================================================================
# Task 6.1 — Chunking Tests
# =============================================================================


class TestChunkDocument:
    """Tests for the ``chunk_document()`` function."""

    def test_empty_content(self):
        """Empty content returns an empty list."""
        assert chunk_document("", "test.md") == []
        assert chunk_document("   \n\n  ", "test.md") == []

    def test_no_headings_single_chunk(self):
        """Content without headings becomes a single chunk."""
        content = "This is a simple document with no headings.\n\nJust some text."
        chunks = chunk_document(content, "test.md")
        assert len(chunks) == 1
        assert chunks[0]["source_path"] == "test.md"
        assert chunks[0]["heading"] == ""
        assert chunks[0]["heading_ancestry"] == ""

    def test_single_heading(self):
        """A single heading produces one chunk with that heading."""
        content = "# Introduction\n\nThis is the intro text."
        chunks = chunk_document(content, "doc.md")
        assert len(chunks) == 1
        assert chunks[0]["heading"] == "Introduction"
        assert "intro text" in chunks[0]["chunk_text"]

    def test_multiple_headings(self):
        """Multiple headings produce separate chunks with correct ancestry."""
        content = """# Title

Overview text.

## Section 1

Section 1 content.

## Section 2

Section 2 content."""
        chunks = chunk_document(content, "multi.md")
        assert len(chunks) == 3  # Title, Section 1, Section 2
        assert chunks[0]["heading"] == "Title"
        assert chunks[1]["heading"] == "Section 1"
        assert chunks[1]["heading_ancestry"] == "Title"
        assert chunks[2]["heading"] == "Section 2"
        assert chunks[2]["heading_ancestry"] == "Title"

    def test_nested_headings_ancestry(self):
        """Deeply nested headings produce correct ancestry chain."""
        content = """# Root

Root text.

## Level 2

Level 2 text.

### Level 3

Level 3 text."""
        chunks = chunk_document(content, "nested.md")
        assert len(chunks) == 3
        assert chunks[2]["heading"] == "Level 3"
        assert "Level 2" in chunks[2]["heading_ancestry"]
        assert "Root" in chunks[2]["heading_ancestry"]

    def test_oversized_section_split_on_paragraphs(self):
        """Oversized sections are split on paragraph boundaries."""
        # Create content with a section that exceeds max_chunk_chars
        para_a = "A" * 500
        para_b = "B" * 500
        para_c = "C" * 500
        content = f"# Big Section\n\n{para_a}\n\n{para_b}\n\n{para_c}"
        chunks = chunk_document(content, "big.md", max_chunk_chars=600)
        # Should split into 2+ chunks at paragraph boundaries
        assert len(chunks) >= 2
        assert all(c["heading"] == "Big Section" for c in chunks)

    def test_checksum_consistency(self):
        """Same content produces the same checksum."""
        content = "# Stable\n\nSame text."
        c1 = chunk_document(content, "a.md")
        c2 = chunk_document(content, "a.md")
        assert c1[0]["checksum"] == c2[0]["checksum"]

    def test_different_content_different_checksum(self):
        """Different content produces different checksums."""
        c1 = chunk_document("# A\n\naaa", "doc.md")
        c2 = chunk_document("# A\n\nbbb", "doc.md")
        assert c1[0]["checksum"] != c2[0]["checksum"]

    def test_char_position_tracking(self):
        """Char positions are tracked correctly."""
        content = "# Header\n\nBody text here."
        chunks = chunk_document(content, "pos.md")
        assert len(chunks) == 1
        assert chunks[0]["char_start"] >= 0
        assert chunks[0]["char_end"] > chunks[0]["char_start"]
        assert chunks[0]["char_end"] <= len(content)

    def test_source_path_preserved(self):
        """Source path is preserved in each chunk."""
        content = "# A\n\na\n\n# B\n\nb"
        chunks = chunk_document(content, "path/to/doc.md")
        for c in chunks:
            assert c["source_path"] == "path/to/doc.md"

    def test_heading_only_document(self):
        """Document with only headings produces empty-text chunks."""
        content = "# Only\n\n## Headings\n\n### No Text"
        chunks = chunk_document(content, "heads.md")
        # Each heading section will exist but may have empty chunk_text
        assert len(chunks) == 3
        # Verify all headings are captured
        headings = [c["heading"] for c in chunks]
        assert "Only" in headings
        assert "Headings" in headings
        assert "No Text" in headings


# =============================================================================
# Task 6.2 — DocVectorStore Tests
# =============================================================================


class TestDocVectorStoreInit:
    """Tests for DocVectorStore initialization."""

    def test_singleton_pattern(self, temp_db_path: str):
        """get_instance() returns the same instance; reset_instance() clears it."""
        DocVectorStore.reset_instance()
        s1 = DocVectorStore.get_instance(db_path=temp_db_path, embedding=_test_embedding())
        s2 = DocVectorStore.get_instance(db_path=temp_db_path, embedding=_test_embedding())
        assert s1 is s2

        DocVectorStore.reset_instance()
        s3 = DocVectorStore.get_instance(db_path=temp_db_path, embedding=_test_embedding())
        assert s3 is not s1

    def test_init_db_creates_tables(self, store: DocVectorStore):
        """init_db() creates the doc_chunks and vec_docs tables."""
        db = store._get_connection()
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('doc_chunks', 'vec_docs')"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        assert "doc_chunks" in tables
        assert "vec_docs" in tables

    def test_init_db_is_idempotent(self, store: DocVectorStore):
        """Calling init_db() twice does not raise."""
        store.init_db()  # second call
        assert store._initialized


class TestDocVectorStoreEmbedding:
    """Tests for embedding methods with mocked Ollama API."""

    @patch("app.domain.tools.builtin.doc_vector_store.httpx.Client")
    def test_call_ollama_embed_success(self, mock_client, store: DocVectorStore):
        """_call_ollama_embed returns embedding vector on success."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3, 0.4]}
        mock_response.raise_for_status.return_value = None
        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.post.return_value = mock_response
        mock_client.return_value = mock_instance

        result = store._call_ollama_embed("test text")
        assert result == [0.1, 0.2, 0.3, 0.4]

    @patch("app.domain.tools.builtin.doc_vector_store.httpx.Client")
    def test_call_ollama_embed_failure_returns_none(self, mock_client, store: DocVectorStore):
        """_call_ollama_embed returns None on HTTP error."""
        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.post.side_effect = Exception("Connection refused")
        mock_client.return_value = mock_instance

        result = store._call_ollama_embed("test")
        assert result is None

    @patch("app.domain.tools.builtin.doc_vector_store.httpx.Client")
    def test_embed_chunks_batching(self, mock_client, store: DocVectorStore):
        """embed_chunks processes all chunks through the embedding API."""
        store.batch_size = 2
        call_count = 0

        def side_effect(url, *, json=None, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "embedding": [float(call_count)] * store.embedding_dims
            }
            mock_resp.raise_for_status.return_value = None
            return mock_resp

        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.post.side_effect = side_effect
        mock_client.return_value = mock_instance

        texts = ["chunk1", "chunk2", "chunk3"]
        results = store.embed_chunks(texts)
        assert len(results) == 3
        assert all(r is not None for r in results)
        assert call_count == 3  # Ollama API is sequential per text


class TestDocVectorStoreIndexAndSearch:
    """Tests for indexing and search with mocked embeddings."""

    @patch("app.domain.tools.builtin.doc_vector_store.httpx.Client")
    def test_index_document(self, mock_client, store: DocVectorStore):
        """Indexing a document inserts chunks and embeddings."""
        # Mock embedding responses
        responses = iter([
            {"embedding": [0.1, 0.2, 0.3, 0.4]},
            {"embedding": [0.5, 0.6, 0.7, 0.8]},
        ])

        def mock_post(url, *, json=None, **kwargs):
            mock_resp = MagicMock()
            mock_resp.json.return_value = next(responses)
            mock_resp.raise_for_status.return_value = None
            return mock_resp

        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.post.side_effect = mock_post
        mock_client.return_value = mock_instance

        content = "# Section 1\n\nContent A.\n\n# Section 2\n\nContent B."
        inserted = store.index_document("test/doc.md", content)
        assert inserted == 2

    @patch("app.domain.tools.builtin.doc_vector_store.httpx.Client")
    def test_reindex_document_replaces_old(self, mock_client, store: DocVectorStore):
        """Re-indexing the same source path replaces old entries."""
        embedding_a = [0.1, 0.2, 0.3, 0.4]
        embedding_b = [0.5, 0.6, 0.7, 0.8]

        def mock_post(url, *, json=None, **kwargs):
            mock_resp = MagicMock()
            prompt = (json or {}).get("prompt", "")
            mock_resp.json.return_value = {
                "embedding": embedding_a if "A" in prompt else embedding_b
            }
            mock_resp.raise_for_status.return_value = None
            return mock_resp

        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.post.side_effect = mock_post
        mock_client.return_value = mock_instance

        content1 = "# Title\n\nVersion A"
        content2 = "# Title\n\nVersion B"

        inserted1 = store.index_document("test/doc.md", content1)
        inserted2 = store.index_document("test/doc.md", content2)
        assert inserted1 == 1
        assert inserted2 == 1

        # Only 1 chunk should remain (replaced)
        db = store._get_connection()
        cursor = db.execute("SELECT COUNT(*) as cnt FROM doc_chunks WHERE source_path = ?", ("test/doc.md",))
        assert cursor.fetchone()["cnt"] == 1

    @patch("app.domain.tools.builtin.doc_vector_store.httpx.Client")
    def test_index_empty_document(self, mock_client, store: DocVectorStore):
        """Indexing an empty document returns 0."""
        """Indexing an empty document returns 0."""
        inserted = store.index_document("empty.md", "")
        assert inserted == 0

    @patch("app.domain.tools.builtin.doc_vector_store.httpx.Client")
    def test_search_returns_results(self, mock_client, store: DocVectorStore):
        """Search returns results after indexing."""
        def mock_post(url, *, json=None, **kwargs):
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3, 0.4]}
            mock_resp.raise_for_status.return_value = None
            return mock_resp

        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.post.side_effect = mock_post
        mock_client.return_value = mock_instance

        store.index_document("test/doc.md", "# Hello\n\nWorld content here.")

        # Search with the same embedding (matches itself)
        results = store.search([0.1, 0.2, 0.3, 0.4], top_k=5)
        assert len(results) >= 1
        assert results[0]["source_path"] == "test/doc.md"
        assert "similarity_score" in results[0]

    @patch("app.domain.tools.builtin.doc_vector_store.httpx.Client")
    def test_search_with_source_filter(self, mock_client, store: DocVectorStore):
        """Search respects source filter glob."""
        def mock_post(url, *, json=None, **kwargs):
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3, 0.4]}
            mock_resp.raise_for_status.return_value = None
            return mock_resp

        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.post.side_effect = mock_post
        mock_client.return_value = mock_instance

        store.index_document("docs/atlas/doc1.md", "# A\n\naaa")
        store.index_document("docs/other/doc2.md", "# B\n\nbbb")

        results = store.search([0.1, 0.2, 0.3, 0.4], top_k=10, source_filter="docs/atlas/%")
        assert all(r["source_path"].startswith("docs/atlas/") for r in results)

    @patch("app.domain.tools.builtin.doc_vector_store.httpx.Client")
    def test_search_removes_stale_documents(self, mock_client, store: DocVectorStore):
        """remove_stale_documents cleans up entries for non-existent paths."""
        def mock_post(url, *, json=None, **kwargs):
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3, 0.4]}
            mock_resp.raise_for_status.return_value = None
            return mock_resp

        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.post.side_effect = mock_post
        mock_client.return_value = mock_instance

        store.index_document("docs/stale.md", "# Stale\n\nGone.")
        store.index_document("docs/keep.md", "# Keep\n\nStay.")

        removed = store.remove_stale_documents({"docs/keep.md"})
        assert removed > 0

        db = store._get_connection()
        cursor = db.execute("SELECT COUNT(*) as cnt FROM doc_chunks")
        remaining = cursor.fetchone()["cnt"]
        assert remaining == 1  # only the kept doc

    def test_search_empty_index_returns_empty(self, store: DocVectorStore):
        """Search on an empty index returns an empty list."""
        results = store.search([0.1, 0.2, 0.3, 0.4], top_k=5)
        assert results == []


# =============================================================================
# The width guard — the embedding-configuration ruling, option C (2026-10-12)
#
# The vec table is declared from the resolved dims with IF NOT EXISTS, so an index keeps the width it
# was CREATED at. A model change to another width therefore leaves the index behind, and a RESTART does
# not repair it: the store has to refuse and say the index needs rebuilding rather than insert a vector
# the table cannot hold.
# =============================================================================


def _an_index_created_at(temp_db_path: str, dims: int) -> None:
    """Build an index whose vec table was CREATED at `dims`, then drop the singleton."""
    DocVectorStore.reset_instance()
    builder = DocVectorStore.get_instance(db_path=temp_db_path, embedding=_test_embedding(dims))
    builder.init_db()
    DocVectorStore.reset_instance()


def test_the_index_reports_the_width_it_was_created_at(temp_db_path: str) -> None:
    """The width is read off the INDEX — the service's own number is not evidence about the table."""
    _an_index_created_at(temp_db_path, dims=4)
    store = DocVectorStore.get_instance(db_path=temp_db_path, embedding=_test_embedding(8))

    assert store.embedding_dims == 8  # what the configuration says
    assert store._declared_width() == 4  # what the table actually is


def test_a_width_change_is_refused_rather_than_written_into(temp_db_path: str) -> None:
    _an_index_created_at(temp_db_path, dims=4)
    store = DocVectorStore.get_instance(db_path=temp_db_path, embedding=_test_embedding(8))

    assert store._refuse() is True

    with patch("app.domain.tools.builtin.doc_vector_store.httpx.Client") as http:
        assert store._call_ollama_embed("anything") is None
    http.assert_not_called()  # refused BEFORE a call is spent on it


def test_the_same_width_is_not_refused(temp_db_path: str) -> None:
    """The control: the guard is about a DIFFERENT width, not about an index existing at all."""
    _an_index_created_at(temp_db_path, dims=4)
    store = DocVectorStore.get_instance(db_path=temp_db_path, embedding=_test_embedding(4))

    assert store._refuse() is False


def test_an_index_that_does_not_exist_yet_is_not_a_mismatch(temp_db_path: str) -> None:
    """Nothing has created the table, so there is nothing for the service to disagree with."""
    DocVectorStore.reset_instance()
    store = DocVectorStore.get_instance(db_path=temp_db_path, embedding=_test_embedding(8))

    assert store._declared_width() is None
    assert store._refuse() is False


# =============================================================================
# The reset's two modes — option A of the embedding-configuration ruling (2026-10-12)
#
# The capability write RESETS both stores, because a saved embedding model has to reach the process.
# An ingest may be mid-flight on one of those connections, so the production reset clears the
# singleton WITHOUT closing it: that run finishes against the service it started with. `close=True`
# stays the default, and is what the tests use.
# =============================================================================


def test_the_default_reset_closes_the_connection(temp_db_path: str) -> None:
    """The control: `close=True` (the default) really closes — tests do not leak handles."""
    import sqlite3

    DocVectorStore.reset_instance()
    store = DocVectorStore.get_instance(db_path=temp_db_path, embedding=_test_embedding(4))
    store.init_db()
    db = store._get_connection()

    DocVectorStore.reset_instance()

    assert DocVectorStore.current_service() is None
    with pytest.raises(sqlite3.ProgrammingError):
        db.execute("SELECT 1")


def test_the_capability_write_leaves_the_connection_open_for_a_running_ingest(
    temp_db_path: str,
) -> None:
    """`close=False`: the singleton is forgotten, and an in-flight run's connection stays usable."""
    DocVectorStore.reset_instance()
    store = DocVectorStore.get_instance(db_path=temp_db_path, embedding=_test_embedding(4))
    store.init_db()
    db = store._get_connection()

    DocVectorStore.reset_instance(close=False)

    assert DocVectorStore.current_service() is None  # the next use builds a fresh one
    assert db.execute("SELECT 1").fetchone()[0] == 1  # ...and the running one is not broken

    db.close()
