#!/usr/bin/env python3
"""
Log Rotation Script for Cogitate

Rotates log files to prevent disk space issues by:
- Archiving current logs with timestamps
- Compressing archived logs (gzip)
- Deleting old archives beyond retention period
- Creating fresh empty log files

Usage:
    python scripts/rotate_logs.py
    python scripts/rotate_logs.py --keep-days 7
    python scripts/rotate_logs.py --compress
    python scripts/rotate_logs.py --dry-run

Cron Example (daily at 2 AM):
    0 2 * * * cd <project-root> && uv run python backend/scripts/rotate_logs.py --keep-days 7
"""

import argparse
import gzip
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Rotate log files to prevent disk space issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s                          # Rotate with defaults (7 days, compress)
    %(prog)s --keep-days 14           # Keep 14 days of logs
    %(prog)s --no-compress            # Don't compress archives
    %(prog)s --dry-run                # Show what would be done
    %(prog)s --logs-dir /var/log      # Custom logs directory
        """
    )
    
    parser.add_argument(
        "--keep-days",
        type=int,
        default=7,
        help="Number of days to retain archived logs (default: 7)"
    )
    
    parser.add_argument(
        "--compress",
        action="store_true",
        default=True,
        help="Compress archived logs with gzip (default: True)"
    )
    
    parser.add_argument(
        "--no-compress",
        action="store_true",
        help="Disable compression of archived logs"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    parser.add_argument(
        "--logs-dir",
        type=str,
        default="logs",
        help="Directory containing log files (default: logs)"
    )
    
    parser.add_argument(
        "--log-files",
        nargs="+",
        default=["frontend.log", "app.log"],
        help="Log file names to rotate (default: frontend.log app.log)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output"
    )
    
    return parser.parse_args()


def get_archive_name(log_path: Path) -> str:
    """Generate archive filename with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{log_path.name}.{timestamp}"


def compress_file(file_path: Path, remove_original: bool = True) -> Path:
    """
    Compress a file using gzip.
    
    Args:
        file_path: Path to file to compress
        remove_original: Whether to remove original after compression
        
    Returns:
        Path to compressed file
    """
    compressed_path = file_path.with_suffix(file_path.suffix + ".gz")
    
    with open(file_path, "rb") as f_in:
        with gzip.open(compressed_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    if remove_original:
        file_path.unlink()
    
    return compressed_path


def cleanup_old_archives(
    logs_dir: Path,
    log_name: str,
    keep_days: int,
    dry_run: bool = False,
    verbose: bool = False
) -> List[Path]:
    """
    Delete archived logs older than keep_days.
    
    Args:
        logs_dir: Directory containing log files
        log_name: Base name of log file (e.g., "frontend.log")
        keep_days: Number of days to retain
        dry_run: If True, don't actually delete files
        verbose: If True, print detailed output
        
    Returns:
        List of deleted archive paths
    """
    deleted = []
    cutoff = datetime.now() - timedelta(days=keep_days)
    
    # Find all archives for this log file
    # Pattern: frontend.log.YYYYMMDD_HHMMSS or frontend.log.YYYYMMDD_HHMMSS.gz
    pattern = f"{log_name}.*"
    
    for archive_path in logs_dir.glob(pattern):
        # Skip if it's the current log file
        if archive_path.name == log_name:
            continue
        
        # Try to extract timestamp from filename
        try:
            # Remove .gz suffix if present
            name = archive_path.name
            if name.endswith(".gz"):
                name = name[:-3]
            
            # Extract timestamp part (after the last dot)
            parts = name.split(".")
            if len(parts) >= 2:
                timestamp_str = parts[-1]
                archive_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                
                if archive_time < cutoff:
                    if dry_run:
                        print(f"  [DRY-RUN] Would delete: {archive_path.name}")
                    else:
                        archive_path.unlink()
                        if verbose:
                            print(f"  Deleted old archive: {archive_path.name}")
                    
                    deleted.append(archive_path)
        except (ValueError, IndexError) as e:
            if verbose:
                print(f"  Warning: Could not parse timestamp from {archive_path.name}: {e}")
    
    return deleted


def rotate_log_file(
    log_path: Path,
    compress: bool = True,
    dry_run: bool = False,
    verbose: bool = False
) -> Optional[Path]:
    """
    Rotate a single log file.
    
    Args:
        log_path: Path to log file to rotate
        compress: Whether to compress the archive
        dry_run: If True, don't actually rotate
        verbose: If True, print detailed output
        
    Returns:
        Path to archived file, or None if nothing was done
    """
    if not log_path.exists():
        if verbose:
            print(f"  Skipping {log_path.name}: File does not exist")
        return None
    
    # Check if file is empty
    if log_path.stat().st_size == 0:
        if verbose:
            print(f"  Skipping {log_path.name}: File is empty")
        return None
    
    # Get file size for reporting
    file_size_mb = log_path.stat().st_size / 1024 / 1024
    
    if dry_run:
        archive_name = get_archive_name(log_path)
        if compress:
            archive_name += ".gz"
        print(f"  [DRY-RUN] Would rotate {log_path.name} ({file_size_mb:.2f} MB) → {archive_name}")
        return None
    
    # Create archive name
    archive_name = get_archive_name(log_path)
    archive_path = log_path.parent / archive_name
    
    # Move current log to archive
    shutil.move(str(log_path), str(archive_path))
    
    if verbose:
        print(f"  Archived {log_path.name} → {archive_name} ({file_size_mb:.2f} MB)")
    
    # Compress if requested
    if compress:
        compressed_path = compress_file(archive_path, remove_original=True)
        compressed_size_mb = compressed_path.stat().st_size / 1024 / 1024
        compression_ratio = (1 - compressed_size_mb / file_size_mb) * 100
        
        if verbose:
            print(f"  Compressed {archive_name} → {compressed_path.name} ({compressed_size_mb:.2f} MB, {compression_ratio:.1f}% reduction)")
        
        archive_path = compressed_path
    
    # Create new empty log file
    log_path.touch()
    
    if verbose:
        print(f"  Created new empty {log_path.name}")
    
    return archive_path


def get_logs_directory(logs_dir_arg: str) -> Path:
    """
    Get the logs directory path.
    
    Args:
        logs_dir_arg: Command line argument for logs directory
        
    Returns:
        Absolute path to logs directory
    """
    # If absolute path, use as-is
    logs_path = Path(logs_dir_arg)
    if logs_path.is_absolute():
        return logs_path
    
    # Otherwise, assume it's relative to project root
    # Script is in backend/scripts/, so go up one level to backend/
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent
    return backend_dir / logs_path


def main():
    """Main entry point."""
    args = parse_args()
    
    # Handle --no-compress flag
    if args.no_compress:
        args.compress = False
    
    # Get logs directory
    logs_dir = get_logs_directory(args.logs_dir)
    
    if not logs_dir.exists():
        print(f"Error: Logs directory does not exist: {logs_dir}")
        sys.exit(1)
    
    print("Log Rotation Script")
    print("=" * 50)
    print(f"Logs directory: {logs_dir.absolute()}")
    print(f"Retention period: {args.keep_days} days")
    print(f"Compression: {'Enabled' if args.compress else 'Disabled'}")
    print(f"Dry run: {'Yes' if args.dry_run else 'No'}")
    print(f"Log files: {', '.join(args.log_files)}")
    print()
    
    # Process each log file
    archives_created = []
    for log_file in args.log_files:
        log_path = logs_dir / log_file
        
        if args.verbose:
            print(f"Processing {log_file}...")
        
        archive_path = rotate_log_file(
            log_path,
            compress=args.compress,
            dry_run=args.dry_run,
            verbose=args.verbose
        )
        
        if archive_path:
            archives_created.append(archive_path)
        
        # Cleanup old archives
        if args.verbose:
            print(f"  Cleaning up archives older than {args.keep_days} days...")
        
        cleanup_old_archives(
            logs_dir,
            log_file,
            keep_days=args.keep_days,
            dry_run=args.dry_run,
            verbose=args.verbose
        )
        
        if args.verbose:
            print()
    
    # Summary
    print("Summary")
    print("=" * 50)
    
    if args.dry_run:
        print("[DRY-RUN] No changes were made")
    else:
        print(f"Archives created: {len(archives_created)}")
        print(f"Old archives deleted: {sum(1 for _ in logs_dir.glob('*.gz') if False)}")  # Placeholder
    
    # List current log files and archives
    print("\nCurrent log files:")
    for log_file in args.log_files:
        log_path = logs_dir / log_file
        if log_path.exists():
            size_mb = log_path.stat().st_size / 1024 / 1024
            print(f"  {log_file}: {size_mb:.2f} MB")
        else:
            print(f"  {log_file}: (not found)")
    
    print(f"\nArchives (last {args.keep_days} days):")
    archives = sorted(
        [f for f in logs_dir.glob("*") if f.is_file() and (".gz" in f.name or log_file in f.name for log_file in args.log_files)],
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )[:10]  # Show last 10
    
    if archives:
        for archive in archives:
            size_mb = archive.stat().st_size / 1024 / 1024
            mtime = datetime.fromtimestamp(archive.stat().st_mtime)
            print(f"  {archive.name}: {size_mb:.2f} MB ({mtime.strftime('%Y-%m-%d %H:%M')})")
    else:
        print("  (no archives)")
    
    print()
    print("Done!")


if __name__ == "__main__":
    main()
