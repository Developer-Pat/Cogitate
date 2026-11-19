#!/usr/bin/env python3
"""
Database Recovery Migration Script

Migrates data from backup database to newly created schema.
Handles schema differences between backup and current models.

Usage:
    python3 scripts/migrate_from_backup.py
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import create_engine, text

# Source (backup) database
BACKUP_DB = "backend/cogitate-backup-20260328-recovery.db"
# Target (new) database
TARGET_DB = "backend/app/cogitate.db"

# Create sync engine for migration
sync_engine = create_engine(f"sqlite:///{TARGET_DB}")

# Migration order (respecting foreign key dependencies)
MIGRATION_ORDER = [
    # Base tables (no FK dependencies)
    ("providers", [
        "id", "name", "display_name", "base_url",
        "is_active", "priority", "is_default", "provider_type",
        "config", "created_at", "updated_at"
    ]),
    ("provider_sync_schedules", [
        "id", "provider_id", "sync_interval_hours", "last_sync_at",
        "next_sync_at", "sync_enabled", "last_sync_status",
        "created_at", "updated_at"
    ]),
    ("provider_model_cache", [
        "id", "provider_id", "model_id", "name", "display_name",
        "description", "context_length", "pricing_prompt",
        "pricing_completion", "top_provider", "architecture",
        "modality", "tokenizer", "in_context_training",
        "function_calling", "is_cached", "cached_at", "expires_at",
        "raw_data"
    ]),
    
    # Core agent data
    ("agent_templates", [
        "id", "name", "description", "provider", "model",
        "system_prompt", "parameters", "is_public",
        "created_by", "tags", "usage_count", "created_at", "updated_at"
    ]),
    ("agents", [
        "id", "name", "description", "provider", "model",
        "system_prompt", "is_active", "profile_image_url",
        "parameters", "template_id", "fallback_enabled",
        "preferred_providers", "created_at", "updated_at"
    ]),
    ("agent_versions", [
        "id", "agent_id", "version_number", "name", "description",
        "provider", "model", "system_prompt", "parameters",
        "created_by", "created_at"
    ]),
    
    # Chat data
    ("chat_sessions", [
        "id", "title", "agent_id", "is_active", "created_at", "updated_at"
    ]),
    ("chat_messages", [
        "id", "session_id", "role", "content", "token_count",
        "model", "provider", "total_time_ms", "tokens_per_second",
        "created_at"
    ]),
    ("runtime_configs", [
        "id", "session_id", "agent_id", "temperature", "max_tokens",
        "top_p", "system_prompt_override", "model_override",
        "additional_params", "created_at", "updated_at"
    ]),
    
    # Usage and logs
    ("usage_logs", [
        "id", "session_id", "agent_id", "provider", "model",
        "prompt_tokens", "completion_tokens", "total_tokens",
        "cost_usd", "response_time_ms", "success", "error_message",
        "created_at"
    ]),
    ("logs", [
        "id", "timestamp", "level", "source", "message",
        "context", "user_agent", "url", "session_id", "trace_id",
        "log_type", "created_at"
    ]),
    
    # User settings and macros
    ("user_settings", [
        "id", "user_key", "settings", "created_at", "updated_at"
    ]),
    ("macro_sets", [
        "id", "user_key", "topic", "name", "description",
        "f1_macro", "f2_macro", "f3_macro", "f4_macro", "f5_macro",
        "is_active", "sort_order", "created_at", "updated_at"
    ]),
    ("meta_topics", [
        "id", "user_key", "name", "description", "topic_mappings",
        "is_active", "created_at", "updated_at"
    ]),
    
    # Agent lists and workflows
    ("agent_lists", [
        "id", "name", "description", "user_key", "agent_ids",
        "is_default", "created_at", "updated_at"
    ]),
    ("workflow_lists", [
        "id", "name", "description", "user_key", "workflow_ids",
        "is_default", "tags", "created_at", "updated_at"
    ]),
    
    # Phase 3: Tools (must come after agents)
    ("tool_categories", [
        "id", "parent_id", "name", "slug", "description",
        "icon", "sort_order", "created_at", "updated_at"
    ]),
    ("tools", [
        "id", "name", "slug", "description", "version",
        "category_id", "provider", "type", "config_schema",
        "arguments_schema",
        "endpoint", "timeout_ms", "requires_auth", "icon",
        "color", "tags", "is_active", "is_builtin", "usage_count",
        "created_at", "updated_at"
    ]),
    ("agent_tools", [
        "id", "agent_id", "tool_id", "is_enabled", "priority",
        "config", "created_at", "updated_at"
    ]),
    ("tool_usage_logs", [
        "id", "tool_id", "agent_id", "session_id", "success",
        "execution_time_ms", "error_message", "log_metadata",
        "created_at"
    ]),
    
    # Phase 3: Collections
    ("collections", [
        "id", "user_key", "name", "description", "entity_type",
        "color", "icon", "is_active", "created_at", "updated_at"
    ]),
    ("collection_items", [
        "id", "collection_id", "entity_id", "entity_type",
        "entity_name", "added_at"
    ]),
    ("tool_collection_permissions", [
        "id", "tool_id", "collection_id", "permission_level",
        "created_at", "updated_at"
    ]),
]


def get_backup_connection():
    """Get connection to backup database."""
    return sqlite3.connect(BACKUP_DB)


def migrate_table(table_name, columns):
    """
    Migrate a single table from backup to target.
    
    Args:
        table_name: Name of the table to migrate
        columns: List of column names to migrate
    
    Returns:
        Number of rows migrated, or 0 if failed
    """
    backup_conn = get_backup_connection()
    target_conn = sync_engine.connect()
    
    try:
        # Check if table exists in backup
        backup_cur = backup_conn.cursor()
        backup_cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        if not backup_cur.fetchone():
            print(f"  ⚠️  {table_name}: Table not found in backup, skipping")
            backup_conn.close()
            target_conn.close()
            return 0
        
        # Get data from backup
        backup_cur.execute(f"SELECT {', '.join(columns)} FROM {table_name}")
        rows = backup_cur.fetchall()
        
        if not rows:
            print(f"  ⚠️  {table_name}: No data to migrate")
            backup_conn.close()
            target_conn.close()
            return 0
        
        # Check which columns exist in target table
        target_cur = target_conn.execute(
            text(f"PRAGMA table_info({table_name})")
        )
        target_columns = {row[1] for row in target_cur.fetchall()}
        
        # Filter columns to only those that exist in target
        valid_columns = [col for col in columns if col in target_columns]
        missing_columns = [col for col in columns if col not in target_columns]
        
        if missing_columns:
            print(f"  ℹ️  {table_name}: Skipping columns not in target: {', '.join(missing_columns)}")
        
        if not valid_columns:
            # Debug: print what we found
            print(f"  ❌ {table_name}: No valid columns to migrate (target has: {target_columns})")
            backup_conn.close()
            target_conn.close()
            return 0
        
        # Insert into target
        placeholders = ", ".join([f":{col}" for col in valid_columns])
        insert_sql = f"INSERT OR REPLACE INTO {table_name} ({', '.join(valid_columns)}) VALUES ({placeholders})"
        
        # Convert rows to list of dicts
        row_dicts = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(valid_columns):
                value = row[i] if i < len(row) else None
                row_dict[col] = value
            row_dicts.append(row_dict)
        
        target_conn.execute(text(insert_sql), row_dicts)
        target_conn.commit()
        
        print(f"  ✅ {table_name}: Migrated {len(rows)} rows")
        return len(rows)
        
    except Exception as e:
        print(f"  ❌ {table_name}: Migration failed - {e}")
        target_conn.rollback()
        return 0
    finally:
        backup_conn.close()
        target_conn.close()


def verify_migration():
    """Verify migrated data counts match backup."""
    backup_conn = get_backup_connection()
    target_conn = sync_engine.connect()
    
    backup_cur = backup_conn.cursor()
    backup_cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in backup_cur.fetchall()]
    
    mismatches = []
    matched = []
    
    for table in tables:
        backup_cur.execute(f"SELECT COUNT(*) FROM {table}")
        backup_count = backup_cur.fetchone()[0]
        
        try:
            target_cur = target_conn.execute(
                text(f"SELECT COUNT(*) FROM {table}")
            )
            target_count = target_cur.fetchone()[0]
            
            if backup_count != target_count:
                mismatches.append((table, backup_count, target_count))
                print(f"  ⚠️  {table}: Backup={backup_count}, Target={target_count}")
            else:
                matched.append((table, target_count))
                print(f"  ✅ {table}: {target_count} rows")
        except Exception as e:
            mismatches.append((table, backup_count, f"Error: {e}"))
            print(f"  ❌ {table}: Error - {e}")
    
    backup_conn.close()
    target_conn.close()
    
    print()
    print("=" * 60)
    if mismatches:
        print(f"⚠️  WARNING: {len(mismatches)} tables have mismatched counts or errors")
        for table, backup, target in mismatches:
            print(f"    {table}: {backup} → {target}")
        print()
        print("  This may be OK if some tables weren't migrated.")
        print("  Review manually if needed.")
    else:
        print(f"✅ All {len(matched)} tables match!")
    print("=" * 60)
    
    return len(mismatches) == 0


def migrate_all():
    """Run full migration."""
    print("=" * 60)
    print("DATABASE RECOVERY MIGRATION")
    print(f"Source: {BACKUP_DB}")
    print(f"Target: {TARGET_DB}")
    print("=" * 60)
    print()
    
    total_rows = 0
    successful_tables = 0
    failed_tables = 0
    
    for table_name, columns in MIGRATION_ORDER:
        try:
            count = migrate_table(table_name, columns)
            total_rows += count
            if count > 0:
                successful_tables += 1
            else:
                failed_tables += 1
        except Exception as e:
            print(f"  ❌ {table_name}: Unexpected error - {e}")
            failed_tables += 1
    
    print()
    print("=" * 60)
    print(f"MIGRATION COMPLETE")
    print(f"  Tables migrated: {successful_tables}")
    print(f"  Tables skipped/failed: {failed_tables}")
    print(f"  Total rows: {total_rows}")
    print("=" * 60)
    
    # Verify migration
    print("\n🔍 Verifying migration...")
    verify_migration()


if __name__ == "__main__":
    # Check backup exists
    if not Path(BACKUP_DB).exists():
        print(f"❌ ERROR: Backup database not found: {BACKUP_DB}")
        print()
        print("Make sure you've created the backup copy:")
        print("  cp backend/cogitate.db backend/cogitate-backup-20260328-recovery.db")
        sys.exit(1)
    
    # Check target exists
    if not Path(TARGET_DB).exists():
        print(f"❌ ERROR: Target database not found: {TARGET_DB}")
        print()
        print("Make sure you've created the target database with Alembic:")
        print("  cd backend && uv run alembic upgrade head")
        sys.exit(1)
    
    migrate_all()
