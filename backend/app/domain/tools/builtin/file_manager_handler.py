"""
FileManagerTool - Sandboxed file write operations.

Provides move, mkdir, copy, and delete operations with strict sandbox enforcement.
All operations must resolve within a mandatory base_path.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Raised when a sandbox security constraint is violated."""
    pass


class FileManagerTool:
    """
    Sandboxed file management tool with write operations.

    Operations: move, mkdir, copy, delete (single file only).
    All operations are validated against a mandatory base_path sandbox.
    """

    name = "File Manager"
    slug = "file-manager"
    capability = "file-write"
    # THE WORKSPACE GRANT (2026-09-10, the News Team arc): every
    # workspace-aware tool declares needs_workspace so the execution
    # service injects the AGENT'S OWN folder as config["base_path"].
    # This one never did — so every operation failed with "base_path is
    # required in config for all file-manager operations" (reads looked
    # fine because file-info has the flag) and an agent could describe an
    # edit but never make one. The sandbox IS the grant: the agent's own
    # folder, never outside it.
    needs_workspace = True
    description = (
        "Manage files and directories inside YOUR OWN workspace "
        "(write, read, mkdir, move, copy, delete) — sandboxed to your folder"
    )
    tags = ["op:write", "purpose:development", "purpose:system", "source:local-file", "sandboxed"]
    icon = "folder"
    color = "#DC3545"  # Red - signals write operations

    config_schema = {
        "type": "object",
        "properties": {
            "base_path": {
                "type": "string",
                "description": "Mandatory sandbox root — all operations must resolve within this path"
            },
            "dry_run": {
                "type": "boolean",
                "default": False,
                "description": "If true, returns what would happen without executing"
            }
        },
        "required": ["base_path"]
    }

    arguments_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["move", "mkdir", "copy", "delete", "write"],
                "description": "File operation to execute"
            },
            "source": {
                "type": "string",
                "description": "Source file path (required for move and copy)"
            },
            "destination": {
                "type": "string",
                "description": "Destination file path (required for move and copy)"
            },
            "content": {
                "type": "string",
                "description": (
                    "The file TEXT to write (required for operation 'write'). "
                    "This is the content itself — NOT `source`, which is the "
                    "copy/move input. A write with no content is refused."
                ),
            },
            "path": {
                "type": "string",
                "description": "File or directory path (required for mkdir, delete and write)"
            },
            "parents": {
                "type": "boolean",
                "default": False,
                "description": "If true and operation is mkdir, creates parent directories as needed"
            }
        },
        "required": ["operation"]
    }

    # =========================================================================
    # Path Validation (Sandbox Enforcement)
    # =========================================================================

    def _validate_path(self, path: str, base_path: str) -> Path:
        """
        Validate that a resolved path is within the sandbox base_path.

        Args:
            path: The path to validate (can be relative or absolute)
            base_path: The sandbox root

        Returns:
            Resolved Path object

        Raises:
            SecurityError: If path escapes sandbox
        """
        # If path is relative, join it with base_path before resolving
        path_obj = Path(path)
        if not path_obj.is_absolute():
            path_obj = Path(base_path) / path
        
        resolved = path_obj.resolve()
        base = Path(base_path).resolve()

        if not str(resolved).startswith(str(base)):
            raise SecurityError(
                f"Path escapes sandbox: '{path}' resolves to '{resolved}', "
                f"which is outside '{base}'"
            )

        return resolved

    def _validate_paths(self, base_path: str, **paths: str) -> Dict[str, Path]:
        """
        Validate multiple paths against the sandbox.

        Args:
            base_path: The sandbox root
            **paths: Named paths to validate (e.g., source, destination, path)

        Returns:
            Dict mapping path names to resolved Path objects
        """
        validated = {}
        for name, path in paths.items():
            validated[name] = self._validate_path(path, base_path)
        return validated

    def _check_no_symlink(self, path: Path):
        """
        Check that a path does not contain symlinks.

        Args:
            path: Path to check

        Raises:
            SecurityError: If path contains symlinks
        """
        # Check each component of the path for symlinks
        current = Path(path.anchor)
        for part in Path(path).relative_to(path.anchor).parts:
            current = current / part
            if current.is_symlink():
                raise SecurityError(
                    f"Path contains symlink: '{current}' — symlinks not allowed on write operations"
                )

    # =========================================================================
    # Permission Checks
    # =========================================================================

    def _check_write_permission(self, path: Path):
        """
        Check that the filesystem allows writing at a path.

        Args:
            path: Path to check

        Raises:
            PermissionError: If write is not allowed
        """
        # For existing paths, check writable
        if path.exists():
            if not os.access(path, os.W_OK):
                raise PermissionError(f"No write permission: '{path}'")
        else:
            # For non-existing paths, check parent directory is writable
            parent = path.parent
            if parent.exists() and not os.access(parent, os.W_OK):
                raise PermissionError(f"No write permission in parent directory: '{parent}'")

    # =========================================================================
    # Operations
    # =========================================================================

    async def _op_move(
        self,
        source: str,
        destination: str,
        base_path: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Move or rename a file.

        Args:
            source: Source file path
            destination: Destination file path
            base_path: Sandbox root
            dry_run: If true, don't actually move

        Returns:
            Operation result
        """
        validated = self._validate_paths(base_path, source=source, destination=destination)
        src_path = validated["source"]
        dst_path = validated["destination"]

        # Check no symlinks
        if src_path.exists():
            self._check_no_symlink(src_path)
        self._check_no_symlink(dst_path)

        # Check source exists
        if not src_path.exists():
            return {
                "success": False,
                "error": f"Source file does not exist: '{source}'",
                "error_type": "not_found"
            }

        # Source must be a file (not directory)
        if src_path.is_dir():
            return {
                "success": False,
                "error": f"Source is a directory, not a file: '{source}'",
                "error_type": "invalid_type"
            }

        # Check write permissions
        try:
            self._check_write_permission(src_path)
            self._check_write_permission(dst_path)
        except PermissionError as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "permission_denied"
            }

        # Collision handling
        if dst_path.exists():
            return {
                "success": False,
                "error": f"Destination already exists: '{destination}'",
                "error_type": "collision",
                "suggestion": "Rename or delete existing file first"
            }

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "operation": "move",
                "would_execute": {
                    "source": str(src_path),
                    "destination": str(dst_path)
                }
            }

        # Execute move
        try:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(dst_path))
            logger.info(f"Moved '{src_path}' -> '{dst_path}'")
            return {
                "success": True,
                "operation": "move",
                "source": str(src_path),
                "destination": str(dst_path)
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Move failed: {str(e)}",
                "error_type": "operation_error"
            }

    async def _op_mkdir(
        self,
        path: str,
        base_path: str,
        parents: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a directory.

        Args:
            path: Directory path to create
            base_path: Sandbox root
            parents: If true, create parent directories as needed
            dry_run: If true, don't actually create

        Returns:
            Operation result
        """
        validated = self._validate_paths(base_path, path=path)
        dir_path = validated["path"]

        # Check no symlinks in path
        self._check_no_symlink(dir_path)

        # Check write permissions
        try:
            self._check_write_permission(dir_path)
        except PermissionError as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "permission_denied"
            }

        # Already exists
        if dir_path.exists():
            if dir_path.is_dir():
                return {
                    "success": False,
                    "error": f"Directory already exists: '{path}'",
                    "error_type": "already_exists"
                }
            else:
                return {
                    "success": False,
                    "error": f"Path exists but is not a directory: '{path}'",
                    "error_type": "invalid_type"
                }

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "operation": "mkdir",
                "would_execute": {
                    "path": str(dir_path),
                    "parents": parents
                }
            }

        # Execute mkdir
        try:
            dir_path.mkdir(parents=parents, exist_ok=False)
            logger.info(f"Created directory: '{dir_path}' (parents={parents})")
            return {
                "success": True,
                "operation": "mkdir",
                "path": str(dir_path),
                "parents": parents
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"mkdir failed: {str(e)}",
                "error_type": "operation_error"
            }

    async def _op_copy(
        self,
        source: str,
        destination: str,
        base_path: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Copy a file to a new location.

        Args:
            source: Source file path
            destination: Destination file path
            base_path: Sandbox root
            dry_run: If true, don't actually copy

        Returns:
            Operation result
        """
        validated = self._validate_paths(base_path, source=source, destination=destination)
        src_path = validated["source"]
        dst_path = validated["destination"]

        # Check no symlinks
        if src_path.exists():
            self._check_no_symlink(src_path)
        self._check_no_symlink(dst_path)

        # Check source exists
        if not src_path.exists():
            return {
                "success": False,
                "error": f"Source file does not exist: '{source}'",
                "error_type": "not_found"
            }

        # Source must be a file
        if src_path.is_dir():
            return {
                "success": False,
                "error": f"Source is a directory, not a file: '{source}'",
                "error_type": "invalid_type"
            }

        # Check write permissions
        try:
            self._check_write_permission(dst_path)
        except PermissionError as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "permission_denied"
            }

        # Collision handling
        if dst_path.exists():
            return {
                "success": False,
                "error": f"Destination already exists: '{destination}'",
                "error_type": "collision",
                "suggestion": "Rename or delete existing file first"
            }

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "operation": "copy",
                "would_execute": {
                    "source": str(src_path),
                    "destination": str(dst_path)
                }
            }

        # Execute copy
        try:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_path), str(dst_path))
            logger.info(f"Copied '{src_path}' -> '{dst_path}'")
            return {
                "success": True,
                "operation": "copy",
                "source": str(src_path),
                "destination": str(dst_path)
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Copy failed: {str(e)}",
                "error_type": "operation_error"
            }

    async def _op_write(self, path: str, content: str, base_path: str, dry_run: bool = False) -> Dict[str, Any]:
        """Write content to a file within the sandbox (THE DELIVERABLE
        GAP, 2026-08-22): the tag-layer-sweeper could read + analyze
        but never WRITE the manifest — the smoke test's decisive
        finding. Mirrors the read fix: widen the declared
        file-write capability, don't add a new tool.

        Sandboxed (the _validate_path SecurityError), creates parent
        dirs, and honors dry_run. The manifest/out pattern: an agent
        writes its deliverable to its own workspace, then WE apply it
        after review.
        """
        if dry_run:
            return {
                "success": True,
                "operation": "write",
                "path": path,
                "dry_run": True,
                "message": "Would write content (dry run)",
                "chars": len(content),
            }
        if not path:
            return {"success": False, "error": "No path specified for write", "error_type": "missing_argument"}
        if not isinstance(content, str):
            return {"success": False, "error": "content must be a string", "error_type": "invalid_argument"}
        if not content.strip():
            # AN EMPTY WRITE IS A FAILURE, NOT A SUCCESS (2026-09-10):
            # the LLM passed the file text in `source` (the copy input),
            # so `content` defaulted to "" and this wrote an empty file
            # while reporting success. The caller believed the file was
            # updated. Refuse loudly instead — say which parameter to use.
            return {
                "success": False,
                "error": (
                    "No content to write — pass the file text in `content`. "
                    "(`source` is the copy/move input, not the text.) "
                    "Refusing to overwrite a file with nothing."
                ),
                "error_type": "missing_argument",
            }

        resolved = self._validate_path(path, base_path)
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
        except SecurityError:
            raise
        except Exception as e:
            logger.error(f"FileManagerTool write error: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Write failed: {e}",
                "error_type": "write_error",
            }

        return {
            "success": True,
            "operation": "write",
            "path": str(resolved),
            "chars": len(content),
            "message": f"Wrote {len(content)} chars to {resolved.name}",
        }

    async def _op_delete(
        self,
        path: str,
        base_path: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Delete a single file (NO recursive directory deletion).

        Args:
            path: File path to delete
            base_path: Sandbox root
            dry_run: If true, don't actually delete

        Returns:
            Operation result
        """
        validated = self._validate_paths(base_path, path=path)
        file_path = validated["path"]

        # Check no symlinks
        self._check_no_symlink(file_path)

        # Check file exists
        if not file_path.exists():
            return {
                "success": False,
                "error": f"File does not exist: '{path}'",
                "error_type": "not_found"
            }

        # Must be a file, NOT a directory
        if file_path.is_dir():
            return {
                "success": False,
                "error": f"Cannot delete directory: '{path}' — recursive deletion not allowed",
                "error_type": "directory_deletion_denied"
            }

        # Check write permissions
        try:
            self._check_write_permission(file_path)
        except PermissionError as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "permission_denied"
            }

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "operation": "delete",
                "would_execute": {
                    "path": str(file_path)
                }
            }

        # Execute delete
        try:
            file_path.unlink()
            logger.info(f"Deleted file: '{file_path}'")
            return {
                "success": True,
                "operation": "delete",
                "path": str(file_path)
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Delete failed: {str(e)}",
                "error_type": "operation_error"
            }

    # =========================================================================
    # Main Execute Entry Point
    # =========================================================================

    async def execute(self, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Execute a file manager operation.

        Args:
            config: Tool configuration (must include base_path)
            **kwargs: Operation-specific arguments (operation, source, destination, path, etc.)

        Returns:
            Operation result
        """
        # Extract base_path from config
        base_path = config.get("base_path")
        if not base_path:
            return {
                "success": False,
                "error": "base_path is required in config for all file-manager operations",
                "error_type": "missing_config"
            }

        # Validate base_path exists
        base = Path(base_path)
        if not base.exists():
            return {
                "success": False,
                "error": f"base_path does not exist: '{base_path}'",
                "error_type": "invalid_config"
            }

        if not base.is_dir():
            return {
                "success": False,
                "error": f"base_path is not a directory: '{base_path}'",
                "error_type": "invalid_config"
            }

        # Extract dry_run flag
        dry_run = config.get("dry_run", False)

        # Extract operation
        operation = kwargs.get("operation")
        if not operation:
            return {
                "success": False,
                "error": "No operation specified. Required: move, mkdir, copy, delete, or write",
                "error_type": "missing_argument",
                "required_argument": "operation",
                "valid_operations": ["move", "mkdir", "copy", "delete", "write"]
            }

        # Dispatch to operation handler
        try:
            if operation == "move":
                return await self._op_move(
                    source=kwargs.get("source", ""),
                    destination=kwargs.get("destination", ""),
                    base_path=base_path,
                    dry_run=dry_run,
                )
            elif operation == "mkdir":
                return await self._op_mkdir(
                    path=kwargs.get("path", ""),
                    base_path=base_path,
                    parents=kwargs.get("parents", False),
                    dry_run=dry_run,
                )
            elif operation == "copy":
                return await self._op_copy(
                    source=kwargs.get("source", ""),
                    destination=kwargs.get("destination", ""),
                    base_path=base_path,
                    dry_run=dry_run,
                )
            elif operation == "write":
                return await self._op_write(
                    path=kwargs.get("path", ""),
                    content=kwargs.get("content", ""),
                    base_path=base_path,
                    dry_run=dry_run,
                )
            elif operation == "delete":
                return await self._op_delete(
                    path=kwargs.get("path", ""),
                    base_path=base_path,
                    dry_run=dry_run,
                )
            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: '{operation}'",
                    "error_type": "invalid_operation",
                    "valid_operations": ["move", "mkdir", "copy", "delete", "write"]
                }
        except SecurityError as e:
            logger.warning(f"Sandbox security violation: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "security_violation"
            }
        except Exception as e:
            logger.error(f"FileManagerTool unexpected error: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "error_type": "internal_error"
            }
