"""Workflow kinds router (Phase A of the canonical upgrade).

The kind registry is CODE-DEFINED (domain/workflows/kinds/registry.py)
— the DB `kinds` table is a catalog mirror for browsing/UI. These
endpoints serve the registry; the catalog join happens in Phase B
when rows carry kind_id.

GET /api/v1/workflow-kinds            — list (with optional filters)
GET /api/v1/workflow-kinds/{name}     — detail
"""

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.workflows.kinds.registry import (
    get_kind,
    list_kinds,
    WorkflowKind,
)

router = APIRouter(prefix="/workflow-kinds", tags=["workflow-kinds"])


class KindInputResponse(BaseModel):
    name: str
    type: str
    description: str = ""
    default: Any = None
    required: bool = False


class KindResponse(BaseModel):
    name: str
    description: str
    builder_key: str
    product_type: str
    inputs: List[KindInputResponse]


class KindListResponse(BaseModel):
    kinds: List[KindResponse]
    total: int


def _to_response(kind: WorkflowKind) -> KindResponse:
    return KindResponse(
        name=kind.name,
        description=kind.description,
        builder_key=kind.builder_key,
        product_type=kind.product_type,
        inputs=[
            KindInputResponse(
                name=f.name, type=f.type, description=f.description,
                default=f.default, required=f.required,
            )
            for f in kind.inputs
        ],
    )


@router.get("", response_model=KindListResponse)
async def get_workflow_kinds(
    q: Optional[str] = None,
    product_type: Optional[str] = None,
) -> KindListResponse:
    """List workflow kinds (the canonical process shapes).

    Optional filters: q (substring on name/description) and
    product_type (report | file | index).
    """
    kinds = list_kinds()
    if q:
        kinds = [k for k in kinds if q.lower() in k.name.lower()
                 or q.lower() in k.description.lower()]
    if product_type:
        kinds = [k for k in kinds if k.product_type == product_type]
    return KindListResponse(
        kinds=[_to_response(k) for k in kinds],
        total=len(kinds),
    )


@router.get("/{name}", response_model=KindResponse)
async def get_workflow_kind(name: str) -> KindResponse:
    """Get one kind by name."""
    kind = get_kind(name)
    if not kind:
        raise HTTPException(status_code=404, detail=f"Kind not found: {name}")
    return _to_response(kind)
