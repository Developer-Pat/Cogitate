"""
Chat Attachments API.

Provides REST API for uploading and managing file attachments in chat sessions.
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.infrastructure.database.models import ChatAttachment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat/{session_id}/attachments", tags=["chat-attachments"])

# Configuration
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB default
ALLOWED_MIME_TYPES = {
    # Text files (readable inline)
    "text/markdown",
    "text/plain",
    "text/x-python",
    "application/json",
    "text/csv",
    "text/x-yaml",
    "application/x-yaml",
    # Binary files (stored, path provided)
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/svg+xml",
}

# Extension fallback (when MIME type detection fails)
ALLOWED_EXTENSIONS = {
    ".md", ".txt", ".py", ".json", ".csv", ".yaml", ".yml",
    ".pdf", ".docx", ".xlsx",
    ".png", ".jpg", ".jpeg", ".gif", ".svg",
}


def get_upload_dir(session_id: int) -> Path:
    """Get the upload directory for a session."""
    upload_dir = Path("data") / "uploads" / str(session_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _validate_file(file: UploadFile) -> None:
    """
    Validate uploaded file type and size.
    
    Args:
        file: Uploaded file
        
    Raises:
        HTTPException: If file is invalid
    """
    # Check file extension
    if file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type '{ext}' not allowed. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
            )
    
    # Check MIME type if available
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        # Allow if extension is valid but MIME type is generic
        if file.filename:
            ext = Path(file.filename).suffix.lower()
            if ext in ALLOWED_EXTENSIONS:
                # Generic MIME types are OK (e.g., application/octet-stream)
                if file.content_type not in ("application/octet-stream", "binary/octet-stream"):
                    logger.warning(
                        f"Unexpected MIME type: {file.content_type} for file {file.filename}"
                    )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type '{file.content_type}' not allowed",
            )


async def _save_file(file: UploadFile, session_id: int) -> tuple[str, int, str]:
    """
    Save uploaded file to disk.
    
    Args:
        file: Uploaded file
        session_id: Chat session ID
        
    Returns:
        Tuple of (filename, file_size, file_path_str)
        
    Raises:
        HTTPException: If file is too large
    """
    upload_dir = get_upload_dir(session_id)
    
    # Generate unique filename while preserving original extension
    original_filename = file.filename or "unnamed"
    ext = Path(original_filename).suffix.lower()
    unique_id = uuid.uuid4().hex[:8]
    safe_filename = f"{unique_id}_{Path(original_filename).stem}{ext}"
    filepath = upload_dir / safe_filename
    
    # Read and save file
    content = await file.read()
    
    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({len(content)} bytes). Max: {MAX_FILE_SIZE} bytes ({MAX_FILE_SIZE // 1024 // 1024}MB)",
        )
    
    # Write to disk
    with open(filepath, "wb") as f:
        f.write(content)
    
    logger.info(f"📎 File uploaded: {safe_filename} ({len(content)} bytes) for session {session_id}")
    
    return safe_filename, len(content), str(filepath)


# Schemas
class AttachmentMetadata(BaseModel):
    """Response schema for attachment metadata."""
    
    model_config = {"from_attributes": True}
    
    id: int
    session_id: int
    original_filename: str
    stored_filename: str
    file_type: str
    file_size: int
    file_path: str
    mime_type: Optional[str] = None
    created_at: datetime


class AttachmentListResponse(BaseModel):
    """Response schema for listing attachments."""
    
    attachments: List[AttachmentMetadata]
    total: int


@router.post("", response_model=AttachmentMetadata, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    session_id: int,
    file: UploadFile = File(..., description="File to attach to chat session"),
    db: AsyncSession = Depends(get_db),
) -> AttachmentMetadata:
    """
    Upload a file attachment to a chat session.
    
    Supported file types: .md, .txt, .py, .json, .csv, .yaml, .yml, .pdf, .docx, .xlsx, images
    Maximum file size: 10MB
    """
    # Validate file
    _validate_file(file)
    
    # Save file
    stored_filename, file_size, file_path = await _save_file(file, session_id)
    
    # Create database record
    attachment = ChatAttachment(
        session_id=session_id,
        original_filename=file.filename or "unnamed",
        stored_filename=stored_filename,
        file_type=Path(stored_filename).suffix.lower().lstrip("."),
        file_size=file_size,
        file_path=file_path,
        mime_type=file.content_type,
    )
    
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    
    return AttachmentMetadata.model_validate(attachment)


@router.post("/batch", response_model=AttachmentListResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachments_batch(
    session_id: int,
    files: List[UploadFile] = File(..., description="Files to attach to chat session"),
    db: AsyncSession = Depends(get_db),
) -> AttachmentListResponse:
    """
    Upload multiple file attachments to a chat session in one request.
    """
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files per batch upload",
        )
    
    attachments = []
    
    for file in files:
        # Validate file
        _validate_file(file)
        
        # Save file
        stored_filename, file_size, file_path = await _save_file(file, session_id)
        
        # Create database record
        attachment = ChatAttachment(
            session_id=session_id,
            original_filename=file.filename or "unnamed",
            stored_filename=stored_filename,
            file_type=Path(stored_filename).suffix.lower().lstrip("."),
            file_size=file_size,
            file_path=file_path,
            mime_type=file.content_type,
        )
        
        db.add(attachment)
        attachments.append(attachment)
    
    await db.commit()
    
    for attachment in attachments:
        await db.refresh(attachment)
    
    return AttachmentListResponse(
        attachments=[AttachmentMetadata.model_validate(a) for a in attachments],
        total=len(attachments),
    )


@router.get("", response_model=AttachmentListResponse)
async def list_attachments(
    session_id: int,
    db: AsyncSession = Depends(get_db),
) -> AttachmentListResponse:
    """
    List all file attachments for a chat session.
    """
    result = await db.execute(
        select(ChatAttachment)
        .where(ChatAttachment.session_id == session_id)
        .order_by(ChatAttachment.created_at.desc())
    )
    attachments = result.scalars().all()
    
    return AttachmentListResponse(
        attachments=[AttachmentMetadata.model_validate(a) for a in attachments],
        total=len(attachments),
    )


@router.get("/{attachment_id}", response_model=AttachmentMetadata)
async def get_attachment(
    session_id: int,
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
) -> AttachmentMetadata:
    """
    Get metadata for a specific attachment.
    """
    result = await db.execute(
        select(ChatAttachment).where(
            ChatAttachment.id == attachment_id,
            ChatAttachment.session_id == session_id,
        )
    )
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    
    return AttachmentMetadata.model_validate(attachment)


@router.get("/{attachment_id}/download")
async def download_attachment(
    session_id: int,
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """
    Download the actual file.
    """
    result = await db.execute(
        select(ChatAttachment).where(
            ChatAttachment.id == attachment_id,
            ChatAttachment.session_id == session_id,
        )
    )
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    
    file_path = Path(attachment.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment file not found on disk",
        )
    
    return FileResponse(
        path=str(file_path),
        filename=attachment.original_filename,
        media_type=attachment.mime_type,
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    session_id: int,
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete an attachment (both database record and file).
    """
    result = await db.execute(
        select(ChatAttachment).where(
            ChatAttachment.id == attachment_id,
            ChatAttachment.session_id == session_id,
        )
    )
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    
    # Delete file from disk
    file_path = Path(attachment.file_path)
    if file_path.exists():
        file_path.unlink()
        logger.info(f"🗑️  Deleted attachment file: {file_path}")
    
    # Delete database record
    await db.delete(attachment)
    await db.commit()
    
    logger.info(f"🗑️  Deleted attachment {attachment_id} from session {session_id}")
