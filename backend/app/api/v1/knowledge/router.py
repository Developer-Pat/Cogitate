"""Knowledge Graph API Router.

THE EXPERTISE WIRING (2026-08-22): the graph-query handler was a closure
inside the tool registry (unreachable by Exa's Hermes session). This
exposes the same capability over HTTP: query the system topology graph
(the derived FK walk + the wiki link graph) for an entity's neighbors.

Mounted at /api/v1/knowledge/graph via the parent router.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class GraphQueryResponse(BaseModel):
    success: bool
    entity: dict
    edges: list[dict]
    note: str


@router.get("/graph", response_model=GraphQueryResponse)
async def graph_query(entity: str = ""):
    """Query the system topology graph — the neighbors/edges of an entity.

    The derived FK walk (DB) + the wiki link graph, behind the
    GraphService seam. Mirrors the registry's graph_query_handler.
    """
    entity = entity.strip()
    if not entity:
        raise HTTPException(status_code=400, detail="entity is required.")
    try:
        from app.domain.graph import GraphService
        from app.domain.graph.derived import DerivedGraphProvider
        from app.domain.graph.wiki import WikiGraphProvider

        svc = GraphService([DerivedGraphProvider(), WikiGraphProvider()])
        found = svc.get_entity(entity)
        if found is None:
            raise HTTPException(status_code=404, detail=f"No entity '{entity}' in the graph.")
        neighbors = svc.get_neighbors(entity)
        return GraphQueryResponse(
            success=True,
            entity=found,
            edges=neighbors.get("edges", []),
            note="The edges are read from the DB (FK graph) + the wiki (link graph) — the verified topology.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("graph query failed for entity=%s", entity)
        raise HTTPException(status_code=500, detail=f"Graph query failed: {e}")
