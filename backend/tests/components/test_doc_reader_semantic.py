"""
Unit tests for DocReaderTool._semantic_search operation.

Covers Task 6.3:
    - Basic semantic search (with mocked embeddings)
    - Empty/missing query
    - No results case
    - Source filter validation (security)
    - Min score clamping
    - Graceful degradation when embedding service is unreachable
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.domain.providers.embeddings import EmbeddingService
from app.domain.tools.builtin.doc_reader import DocReaderTool


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tool() -> DocReaderTool:
    """Create a fresh DocReaderTool instance."""
    return DocReaderTool()


@pytest.fixture
def tool_with_config(tool: DocReaderTool, monkeypatch: pytest.MonkeyPatch) -> DocReaderTool:
    """A tool whose embedding service RESOLVES — the shape a configured install runs in.

    This fixture used to hang a mock `SystemManagerConfig` on the tool
    (``tool._system_manager_config``), which the tool never read: the attribute was assigned ``None``
    and never anything else, so every ``getattr`` fell through to the literal beside it. The service
    is now the `embeddings` capability's answer — resolved through a database session — so the
    resolution itself is what gets stubbed here.
    """

    async def _embedding() -> EmbeddingService:
        return EmbeddingService(
            address="http://127.0.0.1:11434", model="nomic-embed-text", dims=768
        )

    monkeypatch.setattr(tool, "_embedding_service", _embedding)
    return tool


# =============================================================================
# Task 6.3 — Semantic Search Tests
# =============================================================================


class TestSemanticSearchValidation:
    """Tests for query validation and error handling."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty_results(self, tool_with_config: DocReaderTool):
        """Empty query returns empty results gracefully (not an error)."""
        result = await tool_with_config._semantic_search(query="")
        assert result["success"] is True
        assert result["result_count"] == 0
        assert result["results"] == []
        assert "No query provided" in result["summary"]

    @pytest.mark.asyncio
    async def test_invalid_source_filter_returns_error(self, tool_with_config: DocReaderTool):
        """Invalid source_filter path returns PathError."""
        result = await tool_with_config._semantic_search(
            query="test", source_filter="/../../../etc/passwd"
        )
        assert result["success"] is False
        assert result["error_type"] == "PathError"

    @pytest.mark.asyncio
    async def test_source_filter_outside_whitelist_returns_security_error(
        self, tool_with_config: DocReaderTool
    ):
        """source_filter pointing outside whitelist returns SecurityError."""
        result = await tool_with_config._semantic_search(
            query="test", source_filter="local/sessions/session_plan.md"
        )
        assert result["success"] is False
        assert result["error_type"] == "SecurityError"


class TestSemanticSearchExecution:
    """Tests for the main execution path with mocked vector store."""

    @pytest.mark.asyncio
    async def test_basic_semantic_search_returns_results(self, tool_with_config: DocReaderTool):
        """Basic query returns results with correct structure."""
        with patch(
            "app.domain.tools.builtin.doc_vector_store.DocVectorStore"
        ) as MockStore:
            # Mock the singleton
            mock_instance = MagicMock()
            MockStore.get_instance.return_value = mock_instance

            # Mock embedding
            mock_instance.embed_query.return_value = [0.1] * 768

            # Mock search results
            mock_instance.search.return_value = [
                {
                    "source_path": "wiki/entities/backend-architecture.md",
                    "chunk_text": "The system uses a layered architecture.",
                    "heading": "Architecture",
                    "heading_ancestry": "Overview",
                    "similarity_score": 0.92,
                },
                {
                    "source_path": "wiki/entities/backend-architecture.md",
                    "chunk_text": "Each layer has distinct responsibilities.",
                    "heading": "Layers",
                    "heading_ancestry": "Architecture",
                    "similarity_score": 0.85,
                },
            ]

            result = await tool_with_config._semantic_search(query="architecture", top_k=5)

        assert result["success"] is True
        assert result["operation"] == "semantic_search"
        assert result["query"] == "architecture"
        assert result["result_count"] == 2
        assert len(result["results"]) == 2
        assert result["results"][0]["similarity_score"] == 0.92
        assert result["results"][0]["source_path"] == "wiki/entities/backend-architecture.md"

    @pytest.mark.asyncio
    async def test_no_results_returns_empty_list(self, tool_with_config: DocReaderTool):
        """Query with no matches returns empty results list."""
        with patch(
            "app.domain.tools.builtin.doc_vector_store.DocVectorStore"
        ) as MockStore:
            mock_instance = MagicMock()
            MockStore.get_instance.return_value = mock_instance
            mock_instance.embed_query.return_value = [0.1] * 768
            mock_instance.search.return_value = []

            result = await tool_with_config._semantic_search(query="nonexistent topic")

        assert result["success"] is True
        assert result["result_count"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_source_filter_is_applied(self, tool_with_config: DocReaderTool):
        """Source filter restricts results to matching paths."""
        with patch(
            "app.domain.tools.builtin.doc_vector_store.DocVectorStore"
        ) as MockStore:
            mock_instance = MagicMock()
            MockStore.get_instance.return_value = mock_instance
            mock_instance.embed_query.return_value = [0.1] * 768
            # The store.search call should receive the resolved source_filter
            mock_instance.search.return_value = []

            await tool_with_config._semantic_search(
                query="test", source_filter="wiki/entities"
            )

            # Verify search was called with a source_filter LIKE pattern
            _call_kwargs = mock_instance.search.call_args[1]
            assert "source_filter" in _call_kwargs
            assert _call_kwargs["source_filter"] is not None
            assert "wiki/entities" in _call_kwargs["source_filter"]

    @pytest.mark.asyncio
    async def test_min_score_filters_low_similarity(self, tool_with_config: DocReaderTool):
        """Min score parameter is passed through to the store search."""
        with patch(
            "app.domain.tools.builtin.doc_vector_store.DocVectorStore"
        ) as MockStore:
            mock_instance = MagicMock()
            MockStore.get_instance.return_value = mock_instance
            mock_instance.embed_query.return_value = [0.1] * 768
            mock_instance.search.return_value = []

            await tool_with_config._semantic_search(query="test", min_score=0.5)

            _, call_kwargs = mock_instance.search.call_args
            assert call_kwargs["min_score"] == 0.5

    @pytest.mark.asyncio
    async def test_top_k_is_passed_through(self, tool_with_config: DocReaderTool):
        """Top_k parameter is passed through to the store search."""
        with patch(
            "app.domain.tools.builtin.doc_vector_store.DocVectorStore"
        ) as MockStore:
            mock_instance = MagicMock()
            MockStore.get_instance.return_value = mock_instance
            mock_instance.embed_query.return_value = [0.1] * 768
            mock_instance.search.return_value = []

            await tool_with_config._semantic_search(query="test", top_k=3)

            _, call_kwargs = mock_instance.search.call_args
            assert call_kwargs["top_k"] == 3


class TestSemanticSearchDegradation:
    """Tests for graceful degradation when dependencies are unavailable."""

    @pytest.mark.asyncio
    async def test_embedding_failure_returns_empty_with_note(
        self, tool_with_config: DocReaderTool
    ):
        """When embedding service is unreachable, returns empty results with a note."""
        with patch(
            "app.domain.tools.builtin.doc_vector_store.DocVectorStore"
        ) as MockStore:
            mock_instance = MagicMock()
            MockStore.get_instance.return_value = mock_instance
            mock_instance.embed_query.return_value = None  # embedding failed

            result = await tool_with_config._semantic_search(query="test")

        assert result["success"] is True
        assert result["result_count"] == 0
        assert result["note"] == "embedding_service_unavailable"
        assert "Ollama" in result["summary"]

    @pytest.mark.asyncio
    async def test_an_unconfigured_install_reports_and_searches_nothing(
        self, tool: DocReaderTool, monkeypatch: pytest.MonkeyPatch
    ):
        """No `embeddings` answer: the tool says so and touches NO index.

        This replaces `test_without_config_falls_back_to_defaults`, which pinned the opposite
        behaviour — the tool fell back to `nomic-embed-text`/768 and searched an index built at a
        width nobody chose. The four literals that made that possible are gone (the service-literals
        arc's model half); the capability's report is what a caller gets instead.
        """

        async def _unresolved() -> EmbeddingService:
            return EmbeddingService()

        monkeypatch.setattr(tool, "_embedding_service", _unresolved)

        with patch(
            "app.domain.tools.builtin.doc_vector_store.DocVectorStore"
        ) as MockStore:
            result = await tool._semantic_search(query="test")

        assert result["success"] is True
        assert result["result_count"] == 0
        assert result["results"] == []
        assert result["note"] == "embedding_unconfigured"
        assert "no embedding model" in result["summary"]
        MockStore.get_instance.assert_not_called()
