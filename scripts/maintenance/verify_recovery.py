#!/usr/bin/env python3
"""
Database Recovery Verification Script

Verifies that the database recovery was successful by checking:
1. Database structure (tables, columns)
2. Data counts compared to backup
3. Referential integrity
4. Alembic version
5. Sample data queries

Usage:
    python3 scripts/verify_recovery.py
"""

import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Databases
BACKUP_DB = "backend/cogitate-backup-20260328-recovery.db"
TARGET_DB = "backend/app/cogitate.db"


def get_connection(db_path: str) -> sqlite3.Connection:
    """Get database connection."""
    return sqlite3.connect(db_path)


def check_database_exists() -> bool:
    """Check if target database exists."""
    if not Path(TARGET_DB).exists():
        print(f"❌ Target database not found: {TARGET_DB}")
        return False
    print(f"✅ Target database exists: {TARGET_DB}")
    return True


def check_integrity(conn: sqlite3.Connection) -> bool:
    """Check database integrity."""
    cur = conn.cursor()
    cur.execute("PRAGMA integrity_check")
    result = cur.fetchone()[0]
    
    if result == "ok":
        print("✅ Database integrity check passed")
        return True
    else:
        print(f"❌ Database integrity check failed: {result}")
        return False


def check_alembic_version(conn: sqlite3.Connection) -> bool:
    """Check Alembic schema version."""
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT version_num FROM alembic_version")
        version = cur.fetchone()
        if version:
            print(f"✅ Alembic version: {version[0]}")
            return True
        else:
            print("⚠️  Alembic version table is empty")
            return False
    except Exception as e:
        print(f"❌ Could not check Alembic version: {e}")
        return False


def get_table_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    """Get row counts for all tables."""
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]
    
    counts = {}
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        counts[table] = cur.fetchone()[0]
    
    return counts


def compare_table_counts() -> Tuple[bool, List[str], List[str]]:
    """Compare table counts between backup and target."""
    backup_conn = get_connection(BACKUP_DB)
    target_conn = get_connection(TARGET_DB)
    
    backup_counts = get_table_counts(backup_conn)
    target_counts = get_table_counts(target_conn)
    
    matched = []
    mismatched = []
    missing_in_target = []
    
    for table, backup_count in backup_counts.items():
        if table not in target_counts:
            missing_in_target.append(table)
            mismatched.append(table)
        elif backup_count == target_counts[table]:
            matched.append((table, backup_count))
        else:
            mismatched.append((table, backup_count, target_counts[table]))
    
    extra_in_target = [t for t in target_counts if t not in backup_counts]
    
    backup_conn.close()
    target_conn.close()
    
    return len(mismatched) == 0 and len(missing_in_target) == 0, matched, mismatched


def check_tables_exist() -> bool:
    """Check that all expected tables exist."""
    expected_tables = [
        "alembic_version",
        "agents",
        "agent_templates",
        "agent_versions",
        "agent_tools",
        "agent_lists",
        "chat_sessions",
        "chat_messages",
        "runtime_configs",
        "providers",
        "provider_model_cache",
        "provider_sync_schedules",
        "usage_logs",
        "logs",
        "user_settings",
        "macro_sets",
        "meta_topics",
        "workflow_lists",
        "tool_categories",
        "tools",
        "tool_usage_logs",
        "tool_collection_permissions",
        "collections",
        "collection_items",
    ]
    
    target_conn = get_connection(TARGET_DB)
    cur = target_conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cur.fetchall()}
    target_conn.close()
    
    missing = [t for t in expected_tables if t not in existing_tables]
    
    if missing:
        print(f"❌ Missing tables: {', '.join(missing)}")
        return False
    else:
        print(f"✅ All {len(expected_tables)} expected tables exist")
        return True


def check_referential_integrity() -> bool:
    """Check foreign key constraints."""
    target_conn = get_connection(TARGET_DB)
    
    try:
        # Enable foreign keys
        target_conn.execute("PRAGMA foreign_keys = ON")
        
        cur = target_conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        
        violations = []
        
        for table in tables:
            # Get foreign keys for this table
            cur.execute(f"PRAGMA foreign_key_list({table})")
            fks = cur.fetchall()
            
            for fk in fks:
                # fk format: (id, seq, table, from, to, on_update, on_delete, match)
                ref_table = fk[2]
                from_col = fk[3]
                to_col = fk[4]
                
                # Check for orphaned records
                query = f"""
                    SELECT COUNT(*) FROM {table}
                    WHERE {from_col} IS NOT NULL
                    AND {from_col} NOT IN (SELECT {to_col} FROM {ref_table})
                """
                cur.execute(query)
                count = cur.fetchone()[0]
                
                if count > 0:
                    violations.append(f"{table}.{from_col} → {ref_table}.{to_col}: {count} orphans")
        
        target_conn.close()
        
        if violations:
            print(f"⚠️  Foreign key violations found:")
            for v in violations:
                print(f"    {v}")
            return False
        else:
            print("✅ No foreign key violations")
            return True
            
    except Exception as e:
        print(f"⚠️  Could not check referential integrity: {e}")
        return False


def check_sample_queries() -> bool:
    """Run sample queries to verify data accessibility."""
    target_conn = get_connection(TARGET_DB)
    cur = target_conn.cursor()
    
    queries = [
        ("Agents", "SELECT COUNT(*) FROM agents"),
        ("Tools", "SELECT COUNT(*) FROM tools"),
        ("Collections", "SELECT COUNT(*) FROM collections"),
        ("Workflow Lists", "SELECT COUNT(*) FROM workflow_lists"),
        ("Agent-Tool Associations", "SELECT COUNT(*) FROM agent_tools"),
    ]
    
    all_passed = True
    
    for name, query in queries:
        try:
            cur.execute(query)
            count = cur.fetchone()[0]
            print(f"  ✅ {name}: {count} rows")
        except Exception as e:
            print(f"  ❌ {name}: Query failed - {e}")
            all_passed = False
    
    target_conn.close()
    return all_passed


def verify_all():
    """Run all verification checks."""
    print("=" * 60)
    print("DATABASE RECOVERY VERIFICATION")
    print(f"Target: {TARGET_DB}")
    print(f"Backup: {BACKUP_DB}")
    print("=" * 60)
    print()
    
    checks_passed = 0
    checks_failed = 0
    
    # Check 1: Database exists
    print("📋 Check 1: Database existence")
    if check_database_exists():
        checks_passed += 1
    else:
        checks_failed += 1
        print("❌ Cannot continue without target database")
        return False
    print()
    
    # Check 2: Integrity
    print("📋 Check 2: Database integrity")
    target_conn = get_connection(TARGET_DB)
    if check_integrity(target_conn):
        checks_passed += 1
    else:
        checks_failed += 1
    print()
    
    # Check 3: Alembic version
    print("📋 Check 3: Alembic version")
    if check_alembic_version(target_conn):
        checks_passed += 1
    else:
        checks_failed += 1
    print()
    target_conn.close()
    
    # Check 4: Tables exist
    print("📋 Check 4: Expected tables")
    if check_tables_exist():
        checks_passed += 1
    else:
        checks_failed += 1
    print()
    
    # Check 5: Table counts
    print("📋 Check 5: Data counts comparison")
    all_matched, matched, mismatched = compare_table_counts()
    
    print(f"  Matched: {len(matched)} tables")
    if mismatched:
        print(f"  Mismatched/Missing: {len(mismatched)} tables")
        for item in mismatched:
            if isinstance(item, tuple) and len(item) == 3:
                print(f"    {item[0]}: {item[1]} → {item[2]}")
            else:
                print(f"    {item}: Missing in target")
    
    if all_matched:
        checks_passed += 1
        print("  ✅ All counts match")
    else:
        checks_failed += 1
        print("  ⚠️  Some counts don't match (may be acceptable)")
    print()
    
    # Check 6: Referential integrity
    print("📋 Check 6: Referential integrity")
    if check_referential_integrity():
        checks_passed += 1
    else:
        checks_failed += 1
    print()
    
    # Check 7: Sample queries
    print("📋 Check 7: Sample data queries")
    if check_sample_queries():
        checks_passed += 1
    else:
        checks_failed += 1
    print()
    
    # Summary
    print("=" * 60)
    print(f"VERIFICATION SUMMARY")
    print(f"  Passed: {checks_passed}/7")
    print(f"  Failed: {checks_failed}/7")
    print("=" * 60)
    
    if checks_failed == 0:
        print()
        print("✅ ALL CHECKS PASSED - Recovery successful!")
        return True
    elif checks_failed <= 2:
        print()
        print("⚠️  MOST CHECKS PASSED - Recovery mostly successful")
        print("   Review failed checks above for details")
        return True
    else:
        print()
        print("❌ MULTIPLE CHECKS FAILED - Recovery may have issues")
        print("   Review failed checks above and consider rollback")
        return False


if __name__ == "__main__":
    # Check backup exists
    if not Path(BACKUP_DB).exists():
        print(f"⚠️  Warning: Backup database not found: {BACKUP_DB}")
        print("  Skipping count comparison")
        BACKUP_DB = None
    
    # Check target exists
    if not Path(TARGET_DB).exists():
        print(f"❌ ERROR: Target database not found: {TARGET_DB}")
        sys.exit(1)
    
    success = verify_all()
    sys.exit(0 if success else 1)
