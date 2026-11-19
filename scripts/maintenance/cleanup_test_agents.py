#!/usr/bin/env python3
"""
Cleanup Test Agents Script

Deletes test agents from the database while preserving:
- 13 keeper agents (IDs 15-25, 36, 37) — agents with profile images

Uses ON DELETE CASCADE to clean up dependent records (usage_logs, agent_tools, etc.)

Usage:
    python3 scripts/maintenance/cleanup_test_agents.py          # Dry run (default)
    python3 scripts/maintenance/cleanup_test_agents.py --apply  # Actually delete
    python3 scripts/maintenance/cleanup_test_agents.py --verbose # Show all agents
"""

import argparse
import sqlite3
import sys
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent.parent / "cogitate.db"

# Agents to preserve: 13 keepers with profile images + 1 built-in
KEEPER_IDS = {15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 36, 37}


def get_connection():
    """Get database connection with foreign keys enabled."""
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def analyze(conn, verbose=False):
    """Analyze the database and report on agents to delete."""
    cursor = conn.cursor()

    # Total counts
    cursor.execute("SELECT COUNT(*) FROM agents")
    total = cursor.fetchone()[0]

    # Keepers
    placeholders = ",".join("?" for _ in KEEPER_IDS)
    cursor.execute(f"SELECT id, name, provider, model, profile_image_url FROM agents WHERE id IN ({placeholders}) ORDER BY id", list(KEEPER_IDS))
    keepers = cursor.fetchall()
    print(f"\n=== KEEPER AGENTS ({len(keepers)}) ===")
    for k in keepers:
        print(f"  ID {k['id']:>3}: {k['name']:<20} {k['provider']:<12} {k['model']:<40} img={k['profile_image_url'] is not None}")

    # Built-in
    cursor.execute("SELECT id, name, provider, model FROM agents WHERE is_builtin = 1")
    builtins = cursor.fetchall()
    print(f"\n=== BUILT-IN AGENTS ({len(builtins)}) ===")
    for b in builtins:
        print(f"  ID {b['id']:>3}: {b['name']:<20} {b['provider']:<12} {b['model']}")

    # Test agents to delete
    cursor.execute("""
        SELECT id, name, provider, model, created_at
        FROM agents
        WHERE (profile_image_url IS NULL OR profile_image_url = '')
          AND is_builtin = 0
        ORDER BY id
    """)
    to_delete = cursor.fetchall()
    print(f"\n=== AGENTS TO DELETE ({len(to_delete)}) ===")
    if verbose:
        for d in to_delete:
            print(f"  ID {d['id']:>3}: {d['name']:<25} {d['provider']:<12} {d['model']:<40} created={d['created_at']}")
    else:
        # Show summary by name pattern
        from collections import Counter
        name_counts = Counter(d['name'] for d in to_delete)
        for name, count in name_counts.most_common():
            print(f"  {name:<25} x{count}")

    # Dependent data
    cursor.execute("""
        SELECT COUNT(*) FROM usage_logs ul
        JOIN agents a ON ul.agent_id = a.id
        WHERE (a.profile_image_url IS NULL OR a.profile_image_url = '')
          AND a.is_builtin = 0
    """)
    usage_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM agent_tools at
        JOIN agents a ON at.agent_id = a.id
        WHERE (a.profile_image_url IS NULL OR a.profile_image_url = '')
          AND a.is_builtin = 0
    """)
    tools_count = cursor.fetchone()[0]

    print(f"\n=== DEPENDENT DATA TO BE CASCADE-DELETED ===")
    print(f"  Usage logs:     {usage_count}")
    print(f"  Tool assignments: {tools_count}")

    return len(to_delete), usage_count, tools_count


def cleanup(conn, dry_run=True):
    """Delete test agents from the database."""
    cursor = conn.cursor()

    # Delete test agents (cascade will handle usage_logs, agent_tools, etc.)
    cursor.execute("""
        DELETE FROM agents
        WHERE (profile_image_url IS NULL OR profile_image_url = '')
          AND is_builtin = 0
    """)
    deleted = cursor.rowcount

    if dry_run:
        conn.rollback()
        print(f"\n  DRY RUN — would delete {deleted} agents")
        print(f"  Run with --apply to execute")
    else:
        conn.commit()
        print(f"\n  DELETED {deleted} agents")

    return deleted


def verify(conn):
    """Verify the cleanup results."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM agents")
    remaining = cursor.fetchone()[0]
    print(f"\n=== VERIFICATION ===")
    print(f"  Remaining agents: {remaining}")

    # Verify keepers still exist
    placeholders = ",".join("?" for _ in KEEPER_IDS)
    cursor.execute(f"SELECT id, name FROM agents WHERE id IN ({placeholders}) ORDER BY id", list(KEEPER_IDS))
    remaining_keepers = cursor.fetchall()
    print(f"  Keepers preserved: {len(remaining_keepers)}/{len(KEEPER_IDS)}")
    for k in remaining_keepers:
        print(f"    ID {k['id']}: {k['name']}")

    # Verify no test agents remain
    cursor.execute("""
        SELECT COUNT(*) FROM agents
        WHERE (profile_image_url IS NULL OR profile_image_url = '')
          AND is_builtin = 0
    """)
    remaining_test = cursor.fetchone()[0]
    print(f"  Test agents remaining: {remaining_test}")

    return remaining, remaining_test


def main():
    parser = argparse.ArgumentParser(description="Cleanup test agents from the database")
    parser.add_argument("--apply", action="store_true", help="Actually delete agents (default: dry run)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all agent details")
    args = parser.parse_args()

    conn = get_connection()

    print("=" * 60)
    print("  AGENT CLEANUP")
    print("=" * 60)

    # Phase 1: Analyze
    print("\n📊 ANALYSIS")
    to_delete, usage_count, tools_count = analyze(conn, verbose=args.verbose)

    if to_delete == 0:
        print("\n✅ No test agents to delete. Nothing to do.")
        conn.close()
        return

    # Phase 2: Execute
    print(f"\n{'=' * 60}")
    print(f"  {'🧪 DRY RUN' if not args.apply else '🗑️  EXECUTING DELETE'}")
    print(f"  {'(use --apply to execute)' if not args.apply else ''}")
    print(f"{'=' * 60}")

    deleted = cleanup(conn, dry_run=not args.apply)

    # Phase 3: Verify
    print(f"\n{'=' * 60}")
    print("  ✅ VERIFICATION")
    print(f"{'=' * 60}")
    remaining, remaining_test = verify(conn)

    print(f"\n{'=' * 60}")
    if args.apply:
        print(f"  ✅ CLEANUP COMPLETE")
        print(f"  Deleted: {deleted} test agents")
        print(f"  Remaining: {remaining} agents (13 keepers)")
    else:
        print(f"  📝 DRY RUN COMPLETE — no changes made")
        print(f"  Run with --apply to execute")
    print(f"{'=' * 60}")

    conn.close()


if __name__ == "__main__":
    main()
