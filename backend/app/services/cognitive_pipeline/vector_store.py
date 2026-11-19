"""Vector Store — pipeline component for semantic turn retrieval.

Provides an abstract ``VectorStore`` interface and a concrete
``TurnVectorStore`` implementation backed by sqlite-vec.

Following the same architecture as MemoryManager, ContextBuilder, etc.:
- Abstract interface in the component module
- Registry for runtime resolution
- Concrete implementations registered by name
"""
from __future__ import annotations

import logging
import os
import sqlite3
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

from app.domain.providers.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

# NO ADDRESS, MODEL OR DIMS HERE (the service-literals arc's model half, 2026-10-10): this module used
# to carry the same three values the two tool vector stores carried (`DEFAULT_OLLAMA_BASE`,
# `nomic-embed-text`, 768). Which server embeds, which model runs and how wide the vectors are is ONE
# decision, made in the `embeddings` capability and answered by `resolve_embedding_service`; the store
# takes that answer and refuses to work without it (`_refuse_unconfigured`).
MAX_CHARS_PER_CHUNK = 1500

# ── Interface ────────────────────────────────────────────────────────────────


class VectorStore(ABC):
    """Abstract interface for vector-based semantic retrieval.

    Implementations should store embeddings and support similarity search.
    """

    @abstractmethod
    def index_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        turn_index: int = 0,
    ) -> bool:
        """Index a single conversation turn for later retrieval."""
        ...

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search for semantically similar turns.

        Returns:
            List of dicts with keys: session_id, role, content,
            turn_index, distance.
        """
        ...

    @abstractmethod
    def remove_session(self, session_id: str) -> int:
        """Remove all turns for a given session. Returns count."""
        ...

    @abstractmethod
    def clear_all(self) -> int:
        """Remove ALL indexed turns. Returns count."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release any held resources."""
        ...


# ── Concrete Implementation: sqlite-vec ──────────────────────────────────────


class TurnVectorStore(VectorStore):
    """Vector store for conversation turns, backed by sqlite-vec.

    One store per deep agent, at ``agents/{name}/vector_index/chunks.db``.

    Reuses the Ollama embedding client (httpx) from the RAG system.
    """

    def __init__(
        self,
        agent_folder: str,
        embedding: "EmbeddingService",
    ) -> None:
        self.agent_folder = agent_folder
        # THE EMBEDDING SERVICE IS PASSED IN — the caller resolved it (this class holds no session, the
        # same rule the pipeline's `Context.capability_chains` follows). The three values are read OFF
        # it; an UNRESOLVED service leaves them empty and every use refuses loudly.
        self.embedding = embedding
        self.ollama_base = (embedding.address or "").rstrip("/")
        self.embedding_model = embedding.model or ""
        self.embedding_dims = embedding.dims or 0
        self._db_path: str | None = None
        self._conn: sqlite3.Connection | None = None

    def _refuse_unconfigured(self) -> bool:
        """Refuse to index or search when nothing resolved — loudly, one wording.

        ``agents/{folder}/vector_index/chunks.db`` is built with the model's width, so an install with
        no embedding model has no table to create and no call to make. The store reports the gap
        (``EmbeddingService.report``, the same line `/rag/status` shows) rather than embedding with a
        guessed address or a 768-wide default.
        """
        if self.embedding.resolved:
            return False
        logger.error("TurnVectorStore '%s' unusable — %s", self.agent_folder, self.embedding.report())
        return True

    @property
    def db_path(self) -> str:
        if self._db_path is None:
            from app.core.config import Paths, get_settings
            base = str(Paths.from_settings(get_settings()).agents_dir / self.agent_folder / "vector_index")
            os.makedirs(base, exist_ok=True)
            self._db_path = os.path.join(base, "chunks.db")
        return self._db_path

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._init_db()
        return self._conn

    def _init_db(self) -> None:
        import sqlite_vec
        if self._refuse_unconfigured():
            return  # the width IS the model's; with no model there is no table to declare
        conn = self._get_conn()
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS turn_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                turn_index INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_turns USING vec0(
                chunk_id INTEGER PRIMARY KEY,
                embedding float[{self.embedding_dims}] distance_metric=cosine
            )
        """)
        conn.commit()

    def _embed(self, text: str) -> Optional[List[float]]:
        if self._refuse_unconfigured():
            return None
        truncated = text[:MAX_CHARS_PER_CHUNK]
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{self.ollama_base}/api/embed",
                    json={"model": self.embedding_model, "input": truncated},
                )
                resp.raise_for_status()
                data = resp.json()
                embeddings = data.get("embeddings", [])
                return embeddings[0] if embeddings else None
        except Exception as exc:
            logger.warning("Embedding failed for '%s...': %s", truncated[:50], exc)
            return None

    def index_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        turn_index: int = 0,
    ) -> bool:
        embedding = self._embed(content)
        if embedding is None:
            return False
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "INSERT INTO turn_chunks (session_id, role, content, turn_index) VALUES (?, ?, ?, ?)",
                (session_id, role, content, turn_index),
            )
            chunk_id = cursor.lastrowid
            vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
            conn.execute(
                "INSERT INTO vec_turns (chunk_id, embedding) VALUES (?, ?)",
                (chunk_id, vec_str),
            )
            conn.commit()
            return True
        except Exception as exc:
            logger.warning("Failed to index turn: %s", exc)
            return False

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        embedding = self._embed(query)
        if embedding is None:
            return []
        vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
        conn = self._get_conn()
        try:
            rows = conn.execute(
                f"""
                SELECT tc.session_id, tc.role, tc.content, tc.turn_index, vt.distance
                FROM vec_turns AS vt
                JOIN turn_chunks AS tc ON tc.id = vt.chunk_id
                WHERE vt.embedding MATCH ?
                  AND k = ?
                ORDER BY vt.distance
                """,
                (vec_str, top_k),
            ).fetchall()
            return [
                {
                    "session_id": r[0],
                    "role": r[1],
                    "content": r[2],
                    "turn_index": r[3],
                    "distance": r[4],
                }
                for r in rows
            ]
        except Exception as exc:
            logger.warning("Vector search failed: %s", exc)
            return []

    def remove_session(self, session_id: str) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT id FROM turn_chunks WHERE session_id = ?", (session_id,)
            )
            ids = [r[0] for r in cursor.fetchall()]
            if not ids:
                return 0
            placeholders = ",".join("?" for _ in ids)
            conn.execute(
                f"DELETE FROM vec_turns WHERE chunk_id IN ({placeholders})", ids
            )
            conn.execute("DELETE FROM turn_chunks WHERE session_id = ?", (session_id,))
            conn.commit()
            return len(ids)
        except Exception as exc:
            logger.warning("Failed to remove session: %s", exc)
            return 0

    def clear_all(self) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM turn_chunks")
            count = int(cursor.fetchone()[0])
            conn.execute("DELETE FROM vec_turns")
            conn.execute("DELETE FROM turn_chunks")
            conn.commit()
            return count
        except Exception as exc:
            logger.warning("Failed to clear vector store: %s", exc)
            return 0

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


# ── Registry ─────────────────────────────────────────────────────────────────

class VectorStoreRegistry:
    """Registry for ``VectorStore`` implementations.

    Follows the same pattern as ``MemoryManagerRegistry`` and
    ``ContextBuilderRegistry`` in the cognitive pipeline.
    """

    def __init__(self) -> None:
        self._stores: dict[str, VectorStore] = {}

    def register(self, name: str, store: VectorStore) -> None:
        if not isinstance(store, VectorStore):
            raise TypeError(f"Expected VectorStore, got {type(store).__name__}")
        self._stores[name] = store

    def get(self, name: str) -> VectorStore:
        if name not in self._stores:
            raise KeyError(f"VectorStore '{name}' not registered. Available: {list(self._stores)}")
        return self._stores[name]

    def list(self) -> list[str]:
        return sorted(self._stores.keys())


def create_default_vector_store_registry(
    embedding: Optional[EmbeddingService] = None,
) -> VectorStoreRegistry:
    """Create a registry with the ``turn`` implementation — when there is an embedding service to give it.

    A vector store cannot embed without an address, a model and a width, so an unresolved (or absent)
    service registers NOTHING rather than a store that would silently fail per call. The pipeline's
    recall step already treats a missing ``turn`` store as "skip recall"
    (``pipeline.py``, ``self.vector_stores.get(...)``), which is the honest behaviour for an install
    that has configured no embedding model — and it is logged here, so the skip is not a mystery.
    """
    registry = VectorStoreRegistry()
    if embedding is not None and embedding.resolved:
        registry.register("turn", TurnVectorStore(agent_folder="default", embedding=embedding))
    else:
        logger.warning(
            "no 'turn' vector store registered — %s",
            (embedding or EmbeddingService()).report(),
        )
    return registry
