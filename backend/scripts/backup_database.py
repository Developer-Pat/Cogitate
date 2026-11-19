#!/usr/bin/env python3
"""
Database backup utility for cogitate.

Creates timestamped backups of the SQLite database before schema modifications.

Usage:
    python scripts/backup_database.py
    python scripts/backup_database.py --dry-run
    python scripts/backup_database.py --list
"""

import sys
from datetime import datetime
from pathlib import Path
import shutil


def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent.parent


def backup_database(dry_run: bool = False) -> str:
    """
    Create a timestamped backup of the database.
    
    Args:
        dry_run: If True, only show what would be done without making changes
        
    Returns:
        Path to backup file (or would-be path if dry_run)
    """
    project_root = get_project_root()
    db_path = project_root / "cogitate.db"
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = project_root / f"cogitate.db.backup.{timestamp}"
    
    # Check if backup already exists (same second)
    if backup_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
        backup_path = project_root / f"cogitate.db.backup.{timestamp}"
    
    if dry_run:
        print("🔍 DRY RUN - Would backup:")
        print(f"   Source: {db_path}")
        print(f"   Target: {backup_path}")
        print(f"   Size: {db_path.stat().st_size} bytes")
        return str(backup_path)
    
    # Create backup
    shutil.copy2(db_path, backup_path)
    
    print("✅ Database backed up successfully")
    print(f"   Source: {db_path} ({db_path.stat().st_size} bytes)")
    print(f"   Target: {backup_path} ({backup_path.stat().st_size} bytes)")
    
    return str(backup_path)


def list_backups() -> None:
    """List all existing database backups."""
    project_root = get_project_root()
    
    backups = sorted(project_root.glob("cogitate.db.backup.*"))
    
    if not backups:
        print("📦 No database backups found")
        return
    
    print(f"📦 Found {len(backups)} backup(s):")
    for backup in backups[-10:]:  # Show last 10
        size = backup.stat().st_size
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        print(f"   {backup.name} ({size} bytes, {mtime.strftime('%Y-%m-%d %H:%M')})")
    
    if len(backups) > 10:
        print(f"   ... and {len(backups) - 10} more")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Database backup utility")
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List existing backups"
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_backups()
    else:
        backup_database(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
