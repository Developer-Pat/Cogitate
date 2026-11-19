"""
Unit tests for CodeVectorStore — chunking, search, and code_search operation.

Covers:
    - Task 1: Python AST chunking (functions, classes, methods, assignments)
    - Task 1: TypeScript regex chunking (exports, classes, interfaces)
    - Task 1: Config file chunking (whole-file)
    - Task 1: CodeVectorStore init, add_document, semantic_search, get_stats
    - Task 2: code_search operation on DocReaderTool
    - Task 4: Fallback error handling (embedding failures, missing files)
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.domain.providers.embeddings import EmbeddingService
from app.domain.tools.builtin.code_vector_store import (
    CodeVectorStore,
    chunk_file,
    chunk_python_file,
    chunk_typescript_file,
    chunk_config_file,
)
from app.domain.tools.builtin.doc_reader import DocReaderTool

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


async def _stub_embedding_service() -> EmbeddingService:
    """`DocReaderTool._embedding_service` stubbed — the tool resolves through a database session."""
    return _test_embedding()


def _with_embedding(tool: DocReaderTool) -> DocReaderTool:
    """A tool whose embedding resolution is stubbed: see `_stub_embedding_service`."""
    tool._embedding_service = _stub_embedding_service  # type: ignore[method-assign]
    return tool


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
def store(temp_db_path: str) -> CodeVectorStore:
    """Create a fresh CodeVectorStore with a temp database and no singleton state."""
    CodeVectorStore.reset_instance()
    s = CodeVectorStore.get_instance(
        db_path=temp_db_path,
        embedding=_test_embedding(4),  # small dims for fast tests
    )
    s.init_db()
    return s


@pytest.fixture
def temp_py_file() -> str:
    """Create a temporary Python source file for chunking tests."""
    content = '''
"""Module docstring."""

import os
import sys

CONSTANT_VALUE = 42
API_BASE_URL = "https://api.example.com"


def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"


async def fetch_data(url: str) -> Dict[str, Any]:
    """Fetch data from a URL."""
    result = await some_async_call(url)
    return result


class UserService:
    """Service for managing users."""

    def __init__(self, db_url: str):
        self.db_url = db_url

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get a user by ID."""
        return {"id": user_id, "name": "test"}

    def delete_user(self, user_id: int) -> bool:
        """Delete a user by ID."""
        return True


class EmptyConfig:
    """Config with no methods."""
    pass
'''
    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def temp_ts_file() -> str:
    """Create a temporary TypeScript source file for chunking tests."""
    content = '''// Module comment
import { Component } from "react";

export const API_URL = "https://api.example.com";

export function formatDate(date: Date): string {
  return date.toISOString();
}

export async function fetchUsers(): Promise<User[]> {
  const response = await fetch("/api/users");
  return response.json();
}

export class UserManager {
  private users: User[] = [];

  constructor(private baseUrl: string) {}

  async load(): Promise<void> {
    this.users = await fetchUsers();
  }

  get(id: number): User | undefined {
    return this.users.find(u => u.id === id);
  }
}

export interface User {
  id: number;
  name: string;
  email: string;
}

export type UserMap = Record<number, User>;

function internalHelper(): void {
  // non-exported function
}
'''
    fd, path = tempfile.mkstemp(suffix=".ts")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def temp_toml_file() -> str:
    """Create a temporary config file for whole-file chunking tests."""
    content = """[tool.pytest.ini_options]
minversion = "6.0"
addopts = "-ra -q"
testpaths = ["tests"]
"""
    fd, path = tempfile.mkstemp(suffix=".toml")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


# =============================================================================
# Task 1 — Python AST Chunking Tests
# =============================================================================


class TestPythonChunking:
    """Tests for ``chunk_python_file()`` — AST-based Python chunking."""

    def test_functions_extracted(self, temp_py_file: str):
        """Top-level functions are extracted as separate chunks."""
        chunks = chunk_python_file(Path(temp_py_file))
        function_chunks = [c for c in chunks if c["chunk_type"] == "function"]
        function_names = {c["symbol_name"] for c in function_chunks}
        assert "greet" in function_names
        assert "fetch_data" in function_names

    def test_class_extracted(self, temp_py_file: str):
        """Top-level classes are extracted as separate chunks."""
        chunks = chunk_python_file(Path(temp_py_file))
        class_chunks = [c for c in chunks if c["chunk_type"] == "class"]
        class_names = {c["symbol_name"] for c in class_chunks}
        assert "UserService" in class_names
        assert "EmptyConfig" in class_names

    def test_methods_extracted(self, temp_py_file: str):
        """Methods inside classes are extracted as separate chunks."""
        chunks = chunk_python_file(Path(temp_py_file))
        method_chunks = [c for c in chunks if c["chunk_type"] == "method"]
        method_names = {c["symbol_name"] for c in method_chunks}
        assert "UserService.__init__" in method_names
        assert "UserService.get_user" in method_names
        assert "UserService.delete_user" in method_names

    def test_top_level_assignments(self, temp_py_file: str):
        """Module-level constants are extracted as assignment chunks."""
        chunks = chunk_python_file(Path(temp_py_file))
        assignment_chunks = [c for c in chunks if c["chunk_type"] == "assignment"]
        assignment_names = {c["symbol_name"] for c in assignment_chunks}
        assert "CONSTANT_VALUE" in assignment_names
        assert "API_BASE_URL" in assignment_names

    def test_syntax_error_fallback(self, tmp_path: Path):
        """A file with syntax errors falls back to a whole-module chunk."""
        bad_file = tmp_path / "bad_syntax.py"
        bad_file.write_text("def broken(\n    pass\n")
        chunks = chunk_python_file(bad_file)
        assert len(chunks) == 1
        assert chunks[0]["chunk_type"] == "module"
        assert chunks[0]["symbol_name"] == "bad_syntax"

    def test_empty_file(self, tmp_path: Path):
        """An empty file returns an empty module chunk."""
        empty_file = tmp_path / "empty.py"
        empty_file.write_text("")
        chunks = chunk_python_file(empty_file)
        assert len(chunks) == 1
        assert chunks[0]["chunk_type"] == "module"

    def test_chunk_metadata(self, temp_py_file: str):
        """Each chunk has the required metadata fields."""
        chunks = chunk_python_file(Path(temp_py_file))
        assert len(chunks) > 0
        for chunk in chunks:
            assert "source_path" in chunk
            assert "content" in chunk
            assert "language" in chunk and chunk["language"] == "python"
            assert "symbol_name" in chunk
            assert "chunk_type" in chunk
            assert chunk["chunk_type"] in ("function", "class", "method", "assignment", "module")
            assert "line_start" in chunk
            assert "line_end" in chunk
            assert "checksum" in chunk


# =============================================================================
# Task 1 — TypeScript Regex Chunking Tests
# =============================================================================


class TestTypeScriptChunking:
    """Tests for ``chunk_typescript_file()`` — regex-based TypeScript chunking."""

    def test_exported_functions_extracted(self, temp_ts_file: str):
        """Exported functions are extracted as separate chunks."""
        chunks = chunk_typescript_file(Path(temp_ts_file))
        function_chunks = [c for c in chunks if c["chunk_type"] == "function"]
        function_names = {c["symbol_name"] for c in function_chunks}
        assert "formatDate" in function_names
        assert "fetchUsers" in function_names

    def test_class_extracted(self, temp_ts_file: str):
        """Exported classes are extracted as chunks."""
        chunks = chunk_typescript_file(Path(temp_ts_file))
        class_chunks = [c for c in chunks if c["chunk_type"] == "class"]
        class_names = {c["symbol_name"] for c in class_chunks}
        assert "UserManager" in class_names

    def test_interface_extracted(self, temp_ts_file: str):
        """Exported interfaces are extracted as chunks."""
        chunks = chunk_typescript_file(Path(temp_ts_file))
        iface_chunks = [c for c in chunks if c["chunk_type"] == "interface"]
        iface_names = {c["symbol_name"] for c in iface_chunks}
        assert "User" in iface_names

    def test_type_alias_extracted(self, temp_ts_file: str):
        """Exported type aliases are extracted as chunks."""
        chunks = chunk_typescript_file(Path(temp_ts_file))
        type_chunks = [c for c in chunks if c["chunk_type"] == "type"]
        type_names = {c["symbol_name"] for c in type_chunks}
        assert "UserMap" in type_names

    def test_const_export_extracted(self, temp_ts_file: str):
        """Exported const declarations are extracted as assignment chunks."""
        chunks = chunk_typescript_file(Path(temp_ts_file))
        assign_chunks = [c for c in chunks if c["chunk_type"] == "assignment"]
        assign_names = {c["symbol_name"] for c in assign_chunks}
        assert "API_URL" in assign_names

    def test_non_exported_functions_extracted(self, temp_ts_file: str):
        """Non-exported top-level functions are also extracted."""
        chunks = chunk_typescript_file(Path(temp_ts_file))
        function_names = {c["symbol_name"] for c in chunks if c["chunk_type"] == "function"}
        assert "internalHelper" in function_names

    def test_chunk_metadata(self, temp_ts_file: str):
        """Each TypeScript chunk has the required metadata fields."""
        chunks = chunk_typescript_file(Path(temp_ts_file))
        assert len(chunks) > 0
        for chunk in chunks:
            assert "source_path" in chunk
            assert "content" in chunk
            assert "language" in chunk and chunk["language"] == "typescript"
            assert "symbol_name" in chunk
            assert chunk["chunk_type"] in ("function", "class", "interface", "type", "assignment", "module")
            assert "line_start" in chunk
            assert "line_end" in chunk
            assert "checksum" in chunk


# =============================================================================
# Task 1 — Config File Chunking Tests
# =============================================================================


class TestConfigChunking:
    """Tests for ``chunk_config_file()`` — whole-file config chunking."""

    def test_whole_file_chunk(self, temp_toml_file: str):
        """Config files are chunked as a single whole-file chunk."""
        chunks = chunk_config_file(Path(temp_toml_file))
        assert len(chunks) == 1
        assert chunks[0]["chunk_type"] == "module"
        assert chunks[0]["language"] == "config"

    def test_empty_config(self, tmp_path: Path):
        """Empty config files return an empty list (not chunked)."""
        empty_file = tmp_path / "empty.toml"
        empty_file.write_text("")
        chunks = chunk_config_file(empty_file)
        assert len(chunks) == 0


# =============================================================================
# Task 1 — Language Dispatcher Tests
# =============================================================================


class TestChunkFile:
    """Tests for the ``chunk_file()`` language dispatcher."""

    def test_python_dispatched(self, temp_py_file: str):
        """Python files are dispatched to the AST chunker."""
        chunks = chunk_file(Path(temp_py_file))
        assert all(c["language"] == "python" for c in chunks)

    def test_typescript_dispatched(self, temp_ts_file: str):
        """TypeScript files are dispatched to the regex chunker."""
        chunks = chunk_file(Path(temp_ts_file))
        assert all(c["language"] == "typescript" for c in chunks)

    def test_config_dispatched(self, temp_toml_file: str):
        """Config files are dispatched to the config chunker."""
        chunks = chunk_file(Path(temp_toml_file))
        assert all(c["language"] == "config" for c in chunks)

    def test_unknown_extension_falls_back_to_config(self, tmp_path: Path):
        """Unknown extensions fall back to config chunking."""
        unknown = tmp_path / "somefile.xyz"
        unknown.write_text("some content")
        chunks = chunk_file(unknown)
        assert len(chunks) > 0
        assert all(c["language"] == "config" for c in chunks)

    def test_explicit_language_override(self, temp_py_file: str):
        """Explicit language parameter overrides extension detection."""
        chunks = chunk_file(Path(temp_py_file), language="typescript")
        # When forced to typescript, the regex chunker runs on Python content
        # It may or may not find exports, but it shouldn't use AST chunking
        assert all(c["language"] == "typescript" for c in chunks)


# =============================================================================
# Task 1 — CodeVectorStore Tests
# =============================================================================


class TestCodeVectorStore:
    """Tests for ``CodeVectorStore`` singleton and database operations."""

    def test_singleton(self, temp_db_path: str):
        """``get_instance()`` returns the same instance when called twice."""
        CodeVectorStore.reset_instance()
        s1 = CodeVectorStore.get_instance(db_path=temp_db_path, embedding=_test_embedding())
        s2 = CodeVectorStore.get_instance(db_path="/other/path.db", embedding=_test_embedding())
        assert s1 is s2
        assert s1.db_path == temp_db_path  # first-call params win
        CodeVectorStore.reset_instance()

    def test_init_db_creates_tables(self, store: CodeVectorStore):
        """``init_db()`` creates the expected tables."""
        db = store._get_connection()
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        assert "code_chunks" in tables
        assert "vec_code" in tables

    def test_add_document_missing_file(self, store: CodeVectorStore):
        """``add_document()`` returns 0 for a non-existent file."""
        count = store.add_document("/nonexistent/file.py")
        assert count == 0

    def test_add_document_empty_file(self, store: CodeVectorStore, tmp_path: Path):
        """``add_document()`` returns 0 for an empty file."""
        empty = tmp_path / "empty.py"
        empty.write_text("")
        count = store.add_document(str(empty))
        assert count == 0

    @patch("app.domain.tools.builtin.code_vector_store.CodeVectorStore._call_ollama_embed")
    def test_add_document_with_mocked_embedding(
        self,
        mock_embed: MagicMock,
        store: CodeVectorStore,
        temp_py_file: str,
    ):
        """``add_document()`` indexes chunks with mocked embeddings."""
        mock_embed.return_value = [0.1, 0.2, 0.3, 0.4]
        count = store.add_document(temp_py_file)
        assert count > 0
        # Verify data was written to the DB
        db = store._get_connection()
        cursor = db.execute("SELECT COUNT(*) AS cnt FROM code_chunks")
        total = cursor.fetchone()["cnt"]
        assert total == count

    @patch("app.domain.tools.builtin.code_vector_store.CodeVectorStore._call_ollama_embed")
    def test_get_stats(
        self,
        mock_embed: MagicMock,
        store: CodeVectorStore,
        temp_py_file: str,
        temp_ts_file: str,
    ):
        """``get_stats()`` returns accurate counts."""
        mock_embed.return_value = [0.1, 0.2, 0.3, 0.4]
        store.add_document(temp_py_file)  # python
        store.add_document(temp_ts_file)  # typescript

        stats = store.get_stats()
        assert stats["file_count"] == 2
        assert stats["chunk_count"] > 0
        assert "python" in stats["languages"]
        assert "typescript" in stats["languages"]

    @patch("app.domain.tools.builtin.code_vector_store.CodeVectorStore._call_ollama_embed")
    def test_remove_document(
        self,
        mock_embed: MagicMock,
        store: CodeVectorStore,
        temp_py_file: str,
    ):
        """``_remove_document()`` removes all chunks for a path."""
        mock_embed.return_value = [0.1, 0.2, 0.3, 0.4]
        store.add_document(temp_py_file)

        db = store._get_connection()
        cursor = db.execute("SELECT COUNT(*) AS cnt FROM code_chunks")
        before = cursor.fetchone()["cnt"]
        assert before > 0

        store._remove_document(temp_py_file)
        cursor = db.execute("SELECT COUNT(*) AS cnt FROM code_chunks")
        after = cursor.fetchone()["cnt"]
        assert after == 0

    @patch("app.domain.tools.builtin.code_vector_store.CodeVectorStore._call_ollama_embed")
    def test_search_returns_results(
        self,
        mock_embed: MagicMock,
        store: CodeVectorStore,
        temp_py_file: str,
    ):
        """``search()`` returns results with correct metadata."""
        mock_embed.return_value = [0.1, 0.2, 0.3, 0.4]
        store.add_document(temp_py_file)

        # Search with the same embedding
        results = store.search([0.1, 0.2, 0.3, 0.4], top_k=5)
        assert len(results) > 0
        for r in results:
            assert "file_path" in r
            assert "language" in r
            assert "symbol_name" in r
            assert "chunk_type" in r
            assert "content" in r
            assert "similarity" in r
            assert 0.0 <= r["similarity"] <= 1.0

    @patch("app.domain.tools.builtin.code_vector_store.CodeVectorStore._call_ollama_embed")
    def test_search_with_language_filter(
        self,
        mock_embed: MagicMock,
        store: CodeVectorStore,
        temp_py_file: str,
        temp_ts_file: str,
    ):
        """``search()`` with language filter only returns matching results."""
        mock_embed.return_value = [0.1, 0.2, 0.3, 0.4]
        store.add_document(temp_py_file)
        store.add_document(temp_ts_file)

        results = store.search([0.1, 0.2, 0.3, 0.4], top_k=10, language_filter="python")
        assert len(results) > 0
        assert all(r["language"] == "python" for r in results)

    @patch("app.domain.tools.builtin.code_vector_store.CodeVectorStore._call_ollama_embed")
    def test_semantic_search_with_mocked_embedding(
        self,
        mock_embed: MagicMock,
        store: CodeVectorStore,
        temp_py_file: str,
    ):
        """``semantic_search()`` embeds query and returns results."""
        mock_embed.return_value = [0.1, 0.2, 0.3, 0.4]
        store.add_document(temp_py_file)

        results = store.semantic_search("test query", top_k=5)
        assert len(results) > 0

    @patch("app.domain.tools.builtin.code_vector_store.CodeVectorStore._call_ollama_embed")
    def test_semantic_search_embedding_failure(
        self,
        mock_embed: MagicMock,
        store: CodeVectorStore,
    ):
        """``semantic_search()`` returns empty list when embedding fails."""
        mock_embed.return_value = None  # simulate embedding failure
        results = store.semantic_search("test query", top_k=5)
        assert results == []

    @patch("app.domain.tools.builtin.code_vector_store.CodeVectorStore._call_ollama_embed")
    def test_reindex_replaces_existing(
        self,
        mock_embed: MagicMock,
        store: CodeVectorStore,
        temp_py_file: str,
    ):
        """Re-adding a document replaces existing index entries."""
        mock_embed.return_value = [0.1, 0.2, 0.3, 0.4]
        store.add_document(temp_py_file)

        db = store._get_connection()
        cursor = db.execute("SELECT COUNT(*) AS cnt FROM code_chunks")
        first_count = cursor.fetchone()["cnt"]

        # Re-index same file
        store.add_document(temp_py_file)

        cursor = db.execute("SELECT COUNT(*) AS cnt FROM code_chunks")
        second_count = cursor.fetchone()["cnt"]
        # Count should be the same (replaced, not duplicated)
        assert second_count == first_count


# =============================================================================
# Task 2 — DocReaderTool code_search Operation Tests
# =============================================================================


class TestDocReaderCodeSearch:
    """Tests for the ``code_search`` operation on ``DocReaderTool``."""

    @patch("app.domain.tools.builtin.code_vector_store.CodeVectorStore")
    async def test_code_search_operation_registered(self, mock_cvs):
        """``code_search`` appears in the schema as a valid operation."""
        from app.domain.tools.builtin.doc_reader import DocReaderTool

        tool = DocReaderTool()
        ops = tool.arguments_schema["properties"]["operation"]["enum"]
        assert "code_search" in ops

    @patch("app.domain.tools.builtin.code_vector_store.CodeVectorStore")
    async def test_code_search_requires_query(self, mock_cvs):
        """``code_search`` without a query returns a validation error."""
        from app.domain.tools.builtin.doc_reader import DocReaderTool

        tool = DocReaderTool()
        result = await tool.execute(
            {"max_file_size": 102400, "max_search_results": 20},
            path="backend",
            operation="code_search",
            query="",
        )
        assert result["success"] is True
        assert result["result_count"] == 0
        assert result["results"] == []
        assert "No query provided" in result["summary"]

    @patch("app.domain.tools.builtin.code_vector_store.CodeVectorStore.get_instance")
    async def test_code_search_returns_results(self, mock_get_instance):
        """``code_search`` returns formatted results from CodeVectorStore."""
        # Mock CodeVectorStore
        mock_store = MagicMock()
        mock_store.semantic_search.return_value = [
            {
                "file_path": "backend/app/main.py",
                "language": "python",
                "symbol_name": "app",
                "chunk_type": "assignment",
                "content": "app = FastAPI()",
                "similarity": 0.85,
                "line_start": 10,
                "line_end": 10,
            },
            {
                "file_path": "backend/app/routes.py",
                "language": "python",
                "symbol_name": "setup_routes",
                "chunk_type": "function",
                "content": "def setup_routes(): ...",
                "similarity": 0.72,
                "line_start": 5,
                "line_end": 20,
            },
        ]
        mock_store.embed_query.return_value = [0.1, 0.2, 0.3, 0.4]
        mock_get_instance.return_value = mock_store

        tool = _with_embedding(DocReaderTool())
        result = await tool.execute(
            {"max_file_size": 102400, "max_search_results": 20},
            path="backend",
            operation="code_search",
            query="how does the app start",
        )
        assert result["success"]
        assert result["operation"] == "code_search"
        assert result["result_count"] == 2
        assert len(result["results"]) == 2
        assert result["results"][0]["file_path"] == "backend/app/main.py"
        assert result["results"][0]["symbol_name"] == "app"

    @patch("app.domain.tools.builtin.code_vector_store.CodeVectorStore.get_instance")
    async def test_code_search_with_language_filter(self, mock_get_instance):
        """``code_search`` passes language filter to the vector store."""
        from app.domain.tools.builtin.doc_reader import DocReaderTool

        mock_store = MagicMock()
        mock_store.embed_query.return_value = [0.1, 0.2, 0.3, 0.4]
        mock_store.semantic_search.return_value = []
        mock_get_instance.return_value = mock_store

        tool = _with_embedding(DocReaderTool())
        await tool.execute(
            {"max_file_size": 102400, "max_search_results": 20},
            path="backend",
            operation="code_search",
            query="react components",
            language="typescript",
            max_results=3,
        )
        # Verify the filter was passed through
        mock_store.semantic_search.assert_called_once_with(
            query="react components",
            top_k=3,
            language_filter="typescript",
        )

    @patch("app.domain.tools.builtin.code_vector_store.CodeVectorStore.get_instance")
    async def test_code_search_embedding_failure(self, mock_get_instance):
        """``code_search`` handles embedding service failure gracefully."""
        from app.domain.tools.builtin.doc_reader import DocReaderTool

        mock_store = MagicMock()
        mock_store.semantic_search.return_value = []
        mock_store.embed_query.return_value = None  # embedding unavailable
        mock_get_instance.return_value = mock_store

        tool = _with_embedding(DocReaderTool())
        result = await tool.execute(
            {"max_file_size": 102400, "max_search_results": 20},
            path="backend",
            operation="code_search",
            query="test query",
        )
        assert result["success"]
        assert result["result_count"] == 0
        assert "embedding_service_unavailable" in result.get("note", "")

    @patch("app.domain.tools.builtin.code_vector_store.CodeVectorStore.get_instance")
    async def test_code_search_schema_visible_to_llm(self, mock_get_instance):
        """The code_search operation appears in the tool description for the LLM."""
        from app.domain.tools.builtin.doc_reader import DocReaderTool

        tool = DocReaderTool()
        # The tool description mentions the operation
        assert "code_search" in tool.description
        # The operation enum includes it
        assert "code_search" in tool.arguments_schema["properties"]["operation"]["enum"]
        # The language parameter exists
        assert "language" in tool.arguments_schema["properties"]
        # The max_results parameter exists
        assert "max_results" in tool.arguments_schema["properties"]


# =============================================================================
# Task 4 — SEARCH Fast-Path Integration Verification
# =============================================================================


class TestSearchFastPath:
    """Verify the SEARCH fast-path surfaces code_search correctly."""

    def test_doc_reader_slug_unchanged(self):
        """The doc-reader slug is unchanged — fast-path filtering still works."""
        from app.domain.tools.builtin.doc_reader import DocReaderTool

        tool = DocReaderTool()
        assert tool.slug == "doc-reader"

    def test_code_search_on_same_tool(self):
        """code_search is on doc-reader, so it's available via fast-path tool restriction."""
        from app.domain.tools.builtin.doc_reader import DocReaderTool

        tool = DocReaderTool()
        # The fast-path restricts to doc-reader by slug. Since code_search
        # is an operation on doc-reader, it's automatically available.
        ops = tool.arguments_schema["properties"]["operation"]["enum"]
        assert "semantic_search" in ops
        assert "code_search" in ops
