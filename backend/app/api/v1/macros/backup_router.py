"""
Macros backup API router.

Provides REST endpoints for creating and restoring backups of macro sets and meta topics.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.domain.macros.backup_service import MacroBackupService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", tags=["macros-backup"])


def _get_backup_service(db: AsyncSession) -> MacroBackupService:
    """Get backup service instance."""
    return MacroBackupService(db)


@router.post("")
async def create_backup(
    db: AsyncSession = Depends(get_db_session),
):
    """
    Create a backup of all macro sets and meta topics.

    Creates a JSON backup file containing all macro data. Only one backup
    is kept at a time - each new backup overwrites the previous one.

    **Returns:**
    - Backup file path
    - Creation timestamp
    - Counts of macro sets and meta topics backed up
    - File size in bytes

    **Example Response:**
    ```json
    {
      "success": true,
      "backup_path": "/path/to/backup/macro_backup.json",
      "created_at": "2026-03-14T12:00:00Z",
      "macro_sets_count": 150,
      "meta_topics_count": 6,
      "file_size_bytes": 52480
    }
    ```
    """
    service = _get_backup_service(db)

    try:
        result = await service.create_backup()
        return result
    except IOError as e:
        logger.error(f"Failed to create backup: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create backup: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error creating backup: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create backup: {str(e)}")


@router.get("")
async def get_backup_info(
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get information about the latest backup.

    **Returns:**
    - Backup file path
    - Creation timestamp
    - Backup version
    - Counts of macro sets and meta topics
    - File size in bytes

    **Example Response:**
    ```json
    {
      "exists": true,
      "backup_path": "/path/to/backup/macro_backup.json",
      "created_at": "2026-03-14T12:00:00Z",
      "backup_version": "1.0",
      "macro_sets_count": 150,
      "meta_topics_count": 6,
      "file_size_bytes": 52480
    }
    ```
    """
    service = _get_backup_service(db)

    try:
        result = await service.get_backup_info()

        if result is None:
            return {"exists": False, "message": "No backup found"}

        return result
    except Exception as e:
        logger.error(f"Failed to get backup info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get backup info: {str(e)}")


@router.post("/restore")
async def restore_backup(
    db: AsyncSession = Depends(get_db_session),
):
    """
    Restore macro sets and meta topics from backup.

    **Warning:** This will delete all existing macro sets and meta topics
    and replace them with the backed-up data.

    **Returns:**
    - Success status
    - Counts of restored macro sets and meta topics
    - Original backup creation timestamp

    **Example Response:**
    ```json
    {
      "success": true,
      "macro_sets_restored": 150,
      "meta_topics_restored": 6,
      "backup_created_at": "2026-03-14T12:00:00Z"
    }
    ```
    """
    service = _get_backup_service(db)

    try:
        result = await service.restore_backup()
        return result
    except FileNotFoundError as e:
        logger.warning(f"Backup file not found for restore: {e}")
        raise HTTPException(status_code=404, detail=f"Backup file not found: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to restore backup: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restore backup: {str(e)}")


@router.delete("")
async def delete_backup(
    db: AsyncSession = Depends(get_db_session),
):
    """
    Delete the backup file.

    **Returns:**
    - Success message

    **Example Response:**
    ```json
    {
      "message": "Backup deleted successfully"
    }
    ```
    """
    service = _get_backup_service(db)

    try:
        deleted = await service.delete_backup()

        if not deleted:
            return {"message": "No backup file found", "deleted": False}

        return {"message": "Backup deleted successfully", "deleted": True}
    except Exception as e:
        logger.error(f"Failed to delete backup: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete backup: {str(e)}")
