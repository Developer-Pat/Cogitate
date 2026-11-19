"""
Workflow templates router.

Provides REST API endpoints for workflow template management.
"""

import sqlite3
import json
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

router = APIRouter(prefix="/workflows/templates", tags=["workflow-templates"])

# Database path — the canonical locator (the parent×5 arithmetic
# was OFF BY ONE: it resolved to a phantom <install-root>.db —
# an empty database beside the real one. Fixed 2026-08-17 via the locator.)
from app.core.config import Paths, get_settings
DB_PATH = Paths.from_settings(get_settings()).shared_db


def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============== Response Models ==============

class TemplateCategoryResponse(BaseModel):
    """Workflow template category."""
    id: str
    name: str
    description: Optional[str] = None
    template_count: int = 0


class TemplateTagResponse(BaseModel):
    """Workflow template tag."""
    name: str
    count: int = 0


class CategoriesResponse(BaseModel):
    """Workflow template categories and tags."""
    categories: List[TemplateCategoryResponse]
    tags: List[TemplateTagResponse]


class TemplateListResponse(BaseModel):
    """List of workflow templates."""
    templates: List[Dict[str, Any]]
    total: int


# ============== API Endpoints ==============

@router.get("/categories", response_model=CategoriesResponse)
async def get_workflow_template_categories() -> CategoriesResponse:
    """
    Get workflow template categories and tags.

    Returns list of categories and tags for organizing workflow templates.
    Categories are extracted from the 'category' column.
    Tags are extracted from the JSON 'tags' column.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Get distinct categories with counts
        cursor.execute("""
            SELECT 
                category as id,
                category as name,
                NULL as description,
                COUNT(*) as template_count
            FROM workflow_templates
            WHERE category IS NOT NULL AND category != ''
            GROUP BY category
            ORDER BY category
        """)
        category_rows = cursor.fetchall()
        
        categories = [
            TemplateCategoryResponse(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                template_count=row["template_count"]
            )
            for row in category_rows
        ]

        # Get all tags with counts
        cursor.execute("""
            SELECT tags
            FROM workflow_templates
            WHERE tags IS NOT NULL AND tags != ''
        """)
        tag_rows = cursor.fetchall()
        
        # Aggregate tag counts
        tag_counts: Dict[str, int] = {}
        for row in tag_rows:
            tags = json.loads(row["tags"]) if row["tags"] else []
            for tag in tags:
                tag_lower = tag.lower()
                tag_counts[tag_lower] = tag_counts.get(tag_lower, 0) + 1
        
        tags = [
            TemplateTagResponse(name=tag, count=count)
            for tag, count in sorted(tag_counts.items())
        ]

        return CategoriesResponse(categories=categories, tags=tags)
    finally:
        conn.close()


@router.get("", response_model=TemplateListResponse)
async def get_workflow_templates(
    category: Optional[str] = None,
    tags: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Get workflow templates.

    Returns list of available workflow templates from the database.
    Supports filtering by category and tags.
    
    Args:
        category: Filter by category
        tags: Comma-separated list of tags to filter by
        limit: Maximum number of results
        offset: Offset for pagination
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT t.id, t.name, t.description, t.category, t.version,
                   t.author, t.tags, t.workflow_type, t.config,
                   t.is_public, t.is_customizable, t.created_at,
                   t.updated_at, t.inputs, t.kind_id, k.name AS kind_name
            FROM workflow_templates t
            LEFT JOIN workflow_kinds k ON k.id = t.kind_id
            ORDER BY t.name
            LIMIT ? OFFSET ?
        """, (limit, offset))

        rows = cursor.fetchall()
        templates = []

        # Parse tags if provided
        tag_list = None
        if tags:
            tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]

        for row in rows:
            # Filter by category if specified
            if category and row["category"] != category:
                continue
            
            # Parse template tags
            raw_tags = row["tags"] or ""
            try:
                template_tags = json.loads(raw_tags)
                if not isinstance(template_tags, list):
                    # tolerate plain-string tags (e.g. "monitor,rss,digest")
                    template_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
            except json.JSONDecodeError:
                template_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
            template_tags_lower = [t.lower() for t in template_tags]
            
            # Filter by tags if specified (match any tag)
            if tag_list:
                if not any(tag in template_tags_lower for tag in tag_list):
                    continue

            templates.append({
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "category": row["category"],
                "version": row["version"],
                "author": row["author"],
                "tags": template_tags,
                "workflow_type": row["workflow_type"],
                "kind_id": row["kind_id"],
                "kind_name": row["kind_name"],
                "config": json.loads(row["config"]) if row["config"] else {},
                "inputs": json.loads(row["inputs"]) if row["inputs"] else [],
                "is_public": bool(row["is_public"]),
                "is_customizable": bool(row["is_customizable"]),
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
                "executionCount": 0,
                "successRate": 0.0,
                "averageExecutionTime": 0,
                "metadata": {
                    "complexity": "simple" if row["workflow_type"] == "simple" else "advanced"
                }
            })

        return {
            "templates": templates,
            "total": len(templates)
        }
    finally:
        conn.close()


# ============== CRUD (2026-08-14) ==============
# The WorkflowTemplates page's editor calls these; they were MISSING
# (POST 405 / PUT / DELETE 404) — the "New template" flow was dead
# end-to-end. GET list/categories existed; create/update/delete did
# not. The DB table has been there all along (seeded templates).

class TemplateCreateRequest(BaseModel):
    """Body for POST /workflows/templates.

    Accepts the frontend WorkflowTemplate shape (minus id/timestamps);
    config is a free-form JSON blob (workflow steps/params live in it).
    """

    name: str
    description: Optional[str] = ""
    category: Optional[str] = "General"
    version: Optional[str] = "1.0.0"
    author: Optional[str] = "user"
    tags: Optional[List[str]] = []
    workflow_type: Optional[str] = "simple"
    config: Optional[Dict[str, Any]] = {}
    is_public: Optional[bool] = False
    is_customizable: Optional[bool] = True
    inputs: Optional[List[Dict[str, Any]]] = []


class TemplateUpdateRequest(BaseModel):
    """Body for PUT /workflows/templates/{id} — all fields optional."""

    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[List[str]] = None
    workflow_type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None
    is_customizable: Optional[bool] = None
    inputs: Optional[List[Dict[str, Any]]] = None


def _serialize_template(row) -> Dict[str, Any]:
    """One DB row -> the API template shape (same as GET list)."""
    raw_tags = row["tags"] or ""
    try:
        template_tags = json.loads(raw_tags)
        if not isinstance(template_tags, list):
            template_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
    except json.JSONDecodeError:
        template_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "category": row["category"],
        "version": row["version"],
        "author": row["author"],
        "tags": template_tags,
        "workflow_type": row["workflow_type"],
        "config": json.loads(row["config"]) if row["config"] else {},
        "inputs": json.loads(row["inputs"]) if row["inputs"] else [],
        "is_public": bool(row["is_public"]),
        "is_customizable": bool(row["is_customizable"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "executionCount": 0,
        "successRate": 0.0,
        "averageExecutionTime": 0,
        "metadata": {
            "complexity": "simple" if row["workflow_type"] == "simple" else "advanced"
        },
    }


@router.post("", response_model=Dict[str, Any])
async def create_workflow_template(request: TemplateCreateRequest):
    """Create a workflow template. NEW (2026-08-14) — the missing half
    of the CRUD the WorkflowTemplates editor needs."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        from datetime import datetime
        now = datetime.utcnow().isoformat()
        template_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO workflow_templates (
                id, name, description, category, version, author, tags,
                workflow_type, config, is_public, is_customizable,
                created_at, updated_at, inputs
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template_id,
                request.name,
                request.description or "",
                request.category or "General",
                request.version or "1.0.0",
                request.author or "user",
                json.dumps(request.tags or []),
                request.workflow_type or "simple",
                json.dumps(request.config or {}),
                1 if request.is_public else 0,
                1 if request.is_customizable else 0,
                now,
                now,
                json.dumps(request.inputs or []),
            ),
        )
        conn.commit()
        row = cursor.execute(
            "SELECT * FROM workflow_templates WHERE id = ?",
            (template_id,),
        ).fetchone()
        return _serialize_template(row)
    finally:
        conn.close()


@router.put("/{template_id}", response_model=Dict[str, Any])
async def update_workflow_template(template_id: str, request: TemplateUpdateRequest):
    """Update a workflow template. NEW (2026-08-14)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        from datetime import datetime
        existing = cursor.execute(
            "SELECT * FROM workflow_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Template not found")

        new_tags = (
            json.dumps(request.tags)
            if request.tags is not None
            else existing["tags"]
        )
        new_config = (
            json.dumps(request.config)
            if request.config is not None
            else existing["config"]
        )
        new_inputs = (
            json.dumps(request.inputs)
            if request.inputs is not None
            else existing["inputs"]
        )
        new_is_public = (
            1 if request.is_public else 0
            if request.is_public is not None
            else existing["is_public"]
        )
        new_is_customizable = (
            1 if request.is_customizable else 0
            if request.is_customizable is not None
            else existing["is_customizable"]
        )

        cursor.execute(
            """
            UPDATE workflow_templates SET
                name = ?, description = ?, category = ?, version = ?,
                author = ?, tags = ?, workflow_type = ?, config = ?,
                is_public = ?, is_customizable = ?, updated_at = ?,
                inputs = ?
            WHERE id = ?
            """,
            (
                request.name if request.name is not None else existing["name"],
                request.description if request.description is not None else existing["description"],
                request.category if request.category is not None else existing["category"],
                request.version if request.version is not None else existing["version"],
                request.author if request.author is not None else existing["author"],
                new_tags,
                request.workflow_type if request.workflow_type is not None else existing["workflow_type"],
                new_config,
                new_is_public,
                new_is_customizable,
                datetime.utcnow().isoformat(),
                new_inputs,
                template_id,
            ),
        )
        conn.commit()
        row = cursor.execute(
            "SELECT * FROM workflow_templates WHERE id = ?", (template_id,)
        ).fetchone()
        return _serialize_template(row)
    finally:
        conn.close()


@router.delete("/{template_id}", response_model=Dict[str, Any])
async def delete_workflow_template(template_id: str):
    """Delete a workflow template. NEW (2026-08-14)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        existing = cursor.execute(
            "SELECT * FROM workflow_templates WHERE id = ?", (template_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Template not found")
        cursor.execute(
            "DELETE FROM workflow_templates WHERE id = ?", (template_id,)
        )
        conn.commit()
        return {"message": "deleted", "id": template_id}
    finally:
        conn.close()


# ============== Validation (2026-08-14) ==============
# The WorkflowTemplates editor calls POST /templates/validate before
# EVERY save and POST /templates/{id}/validate-execution before
# executing. Both were MISSING (405/404) — the editor could never
# save or execute. Minimal honest checks: template needs a name and
# a parseable steps/config; execution inputs must satisfy the
# template's declared inputs (required keys present).

class TemplateValidateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = ""
    category: Optional[str] = None
    workflow_type: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = []
    config: Optional[Dict[str, Any]] = {}
    inputs: Optional[List[Dict[str, Any]]] = []


class ValidateResponse(BaseModel):
    isValid: bool
    errors: List[str] = []
    warnings: List[str] = []


@router.post("/validate", response_model=ValidateResponse)
async def validate_workflow_template(request: TemplateValidateRequest):
    """Validate a template BEFORE saving (the editor's save gate)."""
    errors: List[str] = []
    warnings: List[str] = []
    if not (request.name or "").strip():
        errors.append("Name is required")
    desc = request.description or ""
    if desc and len(desc) > 500:
        errors.append("Description is too long (max 500)")
    steps = request.steps or []
    if not steps and not (request.config or {}):
        warnings.append("Template has no steps or config — it will do nothing when executed")
    return ValidateResponse(isValid=len(errors) == 0, errors=errors, warnings=warnings)


class ValidateExecutionRequest(BaseModel):
    """The frontend wraps inputs: POST {inputs: {...}}."""

    inputs: Dict[str, Any] = {}


@router.post("/{template_id}/validate-execution", response_model=ValidateResponse)
async def validate_workflow_execution_inputs(
    template_id: str, request: ValidateExecutionRequest
):
    """Validate execution inputs against the template's declared inputs.

    NOTE (2026-08-14): the frontend sends the body WRAPPED —
    ``{inputs: {...}}`` (workflowService.validateExecution posts
    ``{inputs}``). Binding the raw body directly would see
    ``{"inputs": {...}}`` and every required-key check would fail.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        row = cursor.execute(
            "SELECT inputs FROM workflow_templates WHERE id = ?", (template_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    declared = json.loads(row["inputs"]) if row["inputs"] else []
    provided = request.inputs or {}
    errors: List[str] = []
    for inp in declared:
        key = inp.get("name") or inp.get("key")
        if not key:
            continue
        required = inp.get("required", False)
        if required and (key not in provided or provided[key] in (None, "")):
            errors.append(f"Missing required input: {key}")
    return ValidateResponse(isValid=len(errors) == 0, errors=errors)
