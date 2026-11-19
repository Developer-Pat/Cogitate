"""
Macros export/import API router.

Provides REST endpoints for exporting and importing macro sets and meta topics.
"""

import json
import logging
from typing import Any, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.macros.export_service import MacroExportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export-import", tags=["macros-export"])

# Templates directory - backend/templates/macros/
# Go up from: backend/app/api/v1/macros/ to backend/
from app.core.config import Paths, get_settings
TEMPLATES_DIR = Paths.from_settings(get_settings()).macro_templates_dir


def _get_export_service(db: AsyncSession) -> MacroExportService:
    """Get export service instance."""
    return MacroExportService(db)


# =============================================================================
# Export Endpoints
# =============================================================================


@router.get("/macro-sets/{macro_set_id}")
async def export_macro_set(
    macro_set_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Export a single macro set as JSON.

    **Parameters:**
    - `macro_set_id`: ID of the macro set to export

    **Returns:**
    - Export data in JSON format

    **Example:**
    ```json
    {
      "export_type": "macro_set",
      "version": "1.0",
      "data": {
        "topic": "Algebra",
        "name": "Basic Algebra",
        "f1_macro": "...",
        ...
      }
    }
    ```
    """
    service = _get_export_service(db)

    try:
        result = await service.export_macro_set(macro_set_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to export macro set: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export: {str(e)}")


@router.get("/meta-topics/{meta_topic_id}")
async def export_meta_topic(
    meta_topic_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Export a meta topic with referenced macro sets.

    **Parameters:**
    - `meta_topic_id`: ID of the meta topic to export

    **Returns:**
    - Export data in JSON format including referenced macro sets
    """
    service = _get_export_service(db)

    try:
        result = await service.export_meta_topic(meta_topic_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to export meta topic: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export: {str(e)}")


@router.get("/all")
async def export_all_macro_sets(
    user_key: Optional[str] = Query(None, description="User identifier"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Export all macro sets for a user.

    **Parameters:**
    - `user_key`: User identifier (default: "default")

    **Returns:**
    - All macro sets in JSON format
    """
    key_to_use = user_key or "default"
    service = _get_export_service(db)

    try:
        result = await service.export_all_macro_sets(key_to_use)
        return result
    except Exception as e:
        logger.error(f"Failed to export all macro sets: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export: {str(e)}")


# =============================================================================
# Import Endpoints
# =============================================================================


@router.post("/import")
async def import_macro_set(
    file: UploadFile = File(..., description="JSON export file"),
    user_key: Optional[str] = Query(None, description="User identifier"),
    conflict_strategy: Literal["skip", "overwrite", "merge"] = Query(
        "skip", description="How to handle conflicts"
    ),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Import macro set(s) from a JSON file.

    **Parameters:**
    - `file`: JSON export file
    - `user_key`: User identifier (default: "default")
    - `conflict_strategy`: How to handle conflicts
      - `skip`: Don't import if already exists
      - `overwrite`: Replace existing
      - `merge`: Update existing

    **Returns:**
    - Import result with counts

    **Example Response:**
    ```json
    {
      "success": true,
      "imported": 5,
      "skipped": 2,
      "type": "all_macro_sets"
    }
    ```
    """
    key_to_use = user_key or "default"

    # Validate file
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid file type. Expected JSON.")

    try:
        # Read file content
        content = await file.read()
        data = json.loads(content.decode("utf-8"))

        service = _get_export_service(db)
        export_type = data.get("export_type")

        if export_type == "macro_set":
            imported: Any = await service.import_macro_set(
                data, key_to_use, conflict_strategy
            )
            return {
                "success": imported is not None,
                "imported": 1 if imported else 0,
                "skipped": 0 if imported else 1,
                "type": "macro_set",
            }
        elif export_type == "meta_topic":
            imported = await service.import_meta_topic(
                data, key_to_use, conflict_strategy
            )
            return {
                "success": imported is not None,
                "imported": 1 if imported else 0,
                "skipped": 0 if imported else 1,
                "type": "meta_topic",
            }
        elif export_type == "all_macro_sets":
            imported = 0
            skipped = 0

            for ms_data in data.get("data", []):
                export_wrapper = {
                    "export_type": "macro_set",
                    "version": "1.0",
                    "data": ms_data,
                }

                result = await service.import_macro_set(
                    export_wrapper,
                    key_to_use,
                    conflict_strategy
                )

                if result:
                    imported += 1
                else:
                    skipped += 1

            return {
                "success": True,
                "imported": imported,
                "skipped": skipped,
                "type": "all_macro_sets",
            }
        else:
            raise HTTPException(status_code=400, detail=f"Unknown export type: {export_type}")

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in upload: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except ValueError as e:
        logger.error(f"Invalid export data: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to import: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to import: {str(e)}")


@router.post("/macro-sets/import")
async def import_single_macro_set(
    file: UploadFile = File(..., description="JSON export file"),
    user_key: Optional[str] = Query(None, description="User identifier"),
    conflict_strategy: Literal["skip", "overwrite", "merge"] = Query(
        "skip", description="How to handle conflicts"
    ),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Import a single macro set from JSON file.

    This is a specialized endpoint for importing individual macro sets.

    **Parameters:**
    - `file`: JSON export file
    - `user_key`: User identifier (default: "default")
    - `conflict_strategy`: How to handle conflicts

    **Returns:**
    - Import result
    """
    key_to_use = user_key or "default"

    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid file type. Expected JSON.")

    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))

        service = _get_export_service(db)
        result = await service.import_macro_set(data, key_to_use, conflict_strategy)

        return {
            "success": result is not None,
            "imported": 1 if result else 0,
            "skipped": 0 if result else 1,
            "macro_set": {
                "topic": result.topic,
                "name": result.name,
            } if result else None,
        }
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to import macro set: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to import: {str(e)}")


@router.post("/meta-topics/import")
async def import_meta_topic_endpoint(
    file: UploadFile = File(..., description="JSON export file"),
    user_key: Optional[str] = Query(None, description="User identifier"),
    conflict_strategy: Literal["skip", "overwrite", "merge"] = Query(
        "skip", description="How to handle conflicts"
    ),
    import_referenced_macros: bool = Query(
        True, description="Whether to import referenced macro sets"
    ),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Import a meta topic from JSON file.

    **Parameters:**
    - `file`: JSON export file
    - `user_key`: User identifier (default: "default")
    - `conflict_strategy`: How to handle conflicts
    - `import_referenced_macros`: Whether to import referenced macro sets

    **Returns:**
    - Import result
    """
    key_to_use = user_key or "default"

    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid file type. Expected JSON.")

    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))

        service = _get_export_service(db)
        result = await service.import_meta_topic(
            data,
            key_to_use,
            conflict_strategy,
            import_referenced_macros
        )

        return {
            "success": result is not None,
            "imported": 1 if result else 0,
            "skipped": 0 if result else 1,
            "meta_topic": {
                "name": result.name,
                "id": result.id,
            } if result else None,
        }
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to import meta topic: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to import: {str(e)}")


# =============================================================================
# Templates Endpoints
# =============================================================================


@router.get("/templates")
async def list_templates():
    """
    List available macro templates.

    **Returns:**
    - List of template metadata
    """
    templates = []

    if TEMPLATES_DIR.exists():
        for file in TEMPLATES_DIR.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                templates.append({
                    "name": data.get("data", {}).get("name", file.stem),
                    "description": data.get("description", "No description"),
                    "filename": file.name,
                    "export_type": data.get("export_type", "unknown"),
                })
            except Exception as e:
                logger.warning(f"Failed to read template {file.name}: {e}")

    return {"templates": templates, "total": len(templates)}


@router.get("/templates/{filename}")
async def get_template(filename: str):
    """
    Get a specific template by filename.

    **Parameters:**
    - `filename`: Template filename (e.g., "llm_benchmark.json")

    **Returns:**
    - Template JSON data
    """
    file_path = TEMPLATES_DIR / filename

    # Security check: ensure filename doesn't contain path separators
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Template not found: {filename}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data
    except json.JSONDecodeError as e:
        logger.error(f"Invalid template JSON: {filename}: {e}")
        raise HTTPException(status_code=500, detail="Invalid template file")
    except Exception as e:
        logger.error(f"Failed to read template: {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read template: {str(e)}")
