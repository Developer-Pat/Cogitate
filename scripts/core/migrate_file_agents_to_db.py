"""
Migration script: convert file-based agents to DB-backed agent packages.

This script scans a directory of Python agent files and imports them
into the frontend_agent_packages table.

Usage:
    # Scan and import all .py files from a directory
    uv run python scripts/core/migrate_file_agents_to_db.py --dir ./agents

    # Dry run (show what would be imported)
    uv run python scripts/core/migrate_file_agents_to_db.py --dir ./agents --dry-run

    # Import a single file
    uv run python scripts/core/migrate_file_agents_to_db.py --file ./agents/my_agent.py
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, ".")

from app.core.database import AsyncSessionLocal, init_db
from app.domain.agent_registry.service import AgentRegistryService
from app.domain.agent_registry.schemas import AgentPackageCreate

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def extract_metadata_from_file(filepath: Path) -> dict:
    """
    Extract agent metadata from a Python file.

    Looks for module-level docstrings and comments to infer
    name, role, version, and status.

    Args:
        filepath: Path to the Python file

    Returns:
        Dict with extracted metadata
    """
    content = filepath.read_text(encoding="utf-8")
    name = filepath.stem  # filename without .py

    # Try to extract a name from the first line comment
    # e.g., "# agent: my_cool_agent" or "# name: My Agent"
    metadata = {
        "name": name,
        "role": "generic",
        "version": "1.0.0",
        "status": "experimental",
        "code": content,
    }

    for line in content.splitlines()[:20]:  # Check first 20 lines
        line_lower = line.lower().strip()
        if line_lower.startswith("# name:"):
            metadata["name"] = line.split(":", 1)[1].strip()
        elif line_lower.startswith("# role:"):
            metadata["role"] = line.split(":", 1)[1].strip()
        elif line_lower.startswith("# version:"):
            metadata["version"] = line.split(":", 1)[1].strip()
        elif line_lower.startswith("# status:"):
            status = line.split(":", 1)[1].strip().lower()
            if status in ("active", "experimental", "archived", "deprecated"):
                metadata["status"] = status

    return metadata


async def migrate_file(
    filepath: Path,
    service: AgentRegistryService,
    dry_run: bool = False,
) -> bool:
    """
    Migrate a single file-based agent to the database.

    Args:
        filepath: Path to the Python agent file
        service: AgentRegistryService instance
        dry_run: If True, only log what would be done

    Returns:
        True if migrated, False if skipped
    """
    metadata = extract_metadata_from_file(filepath)

    # Check if already exists
    existing = await service.get_by_name(metadata["name"])
    if existing:
        logger.info(
            "Skipping '%s' (already exists in DB, id=%d)",
            metadata["name"], existing.id,
        )
        return False

    pkg_data = AgentPackageCreate(
        name=metadata["name"],
        role=metadata["role"],
        version=metadata["version"],
        status=metadata["status"],
        code=metadata["code"],
        package_metadata={"source_file": str(filepath), "migrated": True},
    )

    if dry_run:
        logger.info(
            "[DRY RUN] Would import: %s (role=%s, version=%s, status=%s) from %s",
            pkg_data.name, pkg_data.role, pkg_data.version,
            pkg_data.status, filepath,
        )
        return True

    try:
        package = await service.create(pkg_data)
        logger.info(
            "Imported: %s (id=%d, role=%s, version=%s, status=%s) from %s",
            package.name, package.id, package.role,
            package.version, package.status, filepath,
        )
        return True
    except ValueError as e:
        logger.warning("Failed to import '%s': %s", metadata["name"], e)
        return False


async def migrate_directory(
    directory: Path,
    dry_run: bool = False,
) -> int:
    """
    Migrate all .py files from a directory to the database.

    Args:
        directory: Directory containing Python agent files
        dry_run: If True, only log what would be done

    Returns:
        Number of files migrated
    """
    await init_db()

    py_files = sorted(directory.glob("*.py"))
    if not py_files:
        logger.warning("No .py files found in %s", directory)
        return 0

    logger.info("Found %d agent file(s) in %s", len(py_files), directory)

    async with AsyncSessionLocal() as db:
        service = AgentRegistryService(db)
        migrated = 0

        for filepath in py_files:
            success = await migrate_file(filepath, service, dry_run=dry_run)
            if success:
                migrated += 1

        if not dry_run:
            await db.commit()

        return migrated


def main():
    parser = argparse.ArgumentParser(
        description="Migrate file-based agents to DB-backed agent packages"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--dir", "-d",
        type=str,
        help="Directory containing Python agent files",
    )
    source.add_argument(
        "--file", "-f",
        type=str,
        help="Single Python agent file to import",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be imported without writing",
    )
    args = parser.parse_args()

    if args.file:
        filepath = Path(args.file)
        if not filepath.exists():
            logger.error("File not found: %s", filepath)
            sys.exit(1)

        migrated = asyncio.run(
            migrate_single_file(filepath, dry_run=args.dry_run)
        )
    else:
        directory = Path(args.dir)
        if not directory.is_dir():
            logger.error("Directory not found: %s", directory)
            sys.exit(1)

        migrated = asyncio.run(
            migrate_directory(directory, dry_run=args.dry_run)
        )

    if args.dry_run:
        logger.info("[DRY RUN] Would migrate %d file(s)", migrated)
    else:
        logger.info("Migrated %d file(s)", migrated)


async def migrate_single_file(filepath: Path, dry_run: bool = False) -> int:
    """Migrate a single file."""
    await init_db()
    async with AsyncSessionLocal() as db:
        service = AgentRegistryService(db)
        success = await migrate_file(filepath, service, dry_run=dry_run)
        if not dry_run:
            await db.commit()
        return 1 if success else 0


if __name__ == "__main__":
    main()
