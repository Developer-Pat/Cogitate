"""Graph service — the topology query surface (Phase 5, 2026-08-19).

The derived memory graph: "how does X connect". The interface is
the repository seam — the SQLite FK walk today, a real graph
store behind the fork (the industrial version swaps the impl,
nothing else changes).

Two sources compose the surface:
- the DERIVED graph: cogitate.db's foreign keys walked on demand
  (a VIEW — reads the DB, always true)
- the WIKI graph: the wiki's pages + hard wikilinks + categories
  (the knowledge graph of the docs)

The GraphService aggregates both behind one contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class GraphProvider(ABC):
    """The topology contract (the seam)."""

    @abstractmethod
    def get_entity(self, entity_id: str) -> Dict[str, Any] | None:
        """A node: {id, kind, name, meta} or None."""

    @abstractmethod
    def get_neighbors(self, entity_id: str, depth: int = 1) -> Dict[str, Any]:
        """The node + its edges: {entity, edges: [{kind, to, via, label}]}."""

    @abstractmethod
    def get_topology(self, kind: str | None = None) -> Dict[str, Any]:
        """The whole graph (optionally filtered by node kind):
        {nodes: [...], edges: [...]}."""


class GraphService:
    """Aggregates the providers behind one surface."""

    def __init__(self, providers: List[GraphProvider]) -> None:
        self._providers = providers

    def get_entity(self, entity_id: str) -> Dict[str, Any] | None:
        for p in self._providers:
            found = p.get_entity(entity_id)
            if found is not None:
                return found
        return None

    def get_neighbors(self, entity_id: str, depth: int = 1) -> Dict[str, Any]:
        combined: Dict[str, Any] = {"entity": entity_id, "edges": []}
        for p in self._providers:
            r = p.get_neighbors(entity_id, depth)
            if r and r.get("edges"):
                combined["edges"].extend(r["edges"])
        combined["entity"] = combined["edges"][0].get("to") if combined["edges"] and False else entity_id
        return combined

    def get_topology(self, kind: str | None = None) -> Dict[str, Any]:
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        for p in self._providers:
            r = p.get_topology(kind)
            nodes.extend(r.get("nodes", []))
            edges.extend(r.get("edges", []))
        return {"nodes": nodes, "edges": edges}
