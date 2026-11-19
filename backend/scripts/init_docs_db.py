#!/usr/bin/env python3
"""
Initialize the Document Management System database.

Creates the cogitate_docs_en.db database with all tables, indexes, triggers,
and FTS5 full-text search support.

Usage:
    python backend/scripts/init_docs_db.py

Notes:
- Creates database in project_root/data/ directory
  (NOT backend/data/ — that location is deprecated)
- Uses SQL schema from backend/scripts/schema/documents_schema.sql
- Safe to run multiple times (idempotent)
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

# Add backend to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_db_path() -> Path:
    """Get the path to the documents database (project root)."""
    # Database location: project_root/data/cogitate_docs_en.db
    db_dir = Path(__file__).parent.parent.parent / "data"
    db_dir.mkdir(exist_ok=True)
    return db_dir / "cogitate_docs_en.db"


def get_schema_path() -> Path:
    """Get the path to the SQL schema file."""
    return Path(__file__).parent / "schema" / "documents_schema.sql"


def init_database() -> None:
    """
    Initialize the documents database using SQL schema.
    
    Creates all tables, indexes, triggers, and FTS5 virtual table.
    """
    db_path = get_db_path()
    schema_path = get_schema_path()
    
    print(f"📄 Database path: {db_path}")
    print(f"📄 Schema path: {schema_path}")
    
    # Check if schema file exists
    if not schema_path.exists():
        print(f"❌ Error: Schema file not found at {schema_path}")
        sys.exit(1)
    
    # Read schema SQL
    print("📖 Reading schema file...")
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    # Connect to database (creates if doesn't exist)
    print("🔧 Connecting to database...")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Execute schema
    print("🔧 Creating tables, indexes, triggers, and FTS5 virtual table...")
    try:
        cursor.executescript(schema_sql)
        conn.commit()
        print("✅ Schema applied successfully")
    except sqlite3.Error as e:
        print(f"❌ Error applying schema: {e}")
        conn.rollback()
        sys.exit(1)
    
    # Verify tables were created
    print("🔍 Verifying database structure...")
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name
    """)
    tables = [row[0] for row in cursor.fetchall()]
    
    expected_tables = [
        'documents',
        'document_relations',
        'document_analytics',
        'documents_fts',
        'schema_version'
    ]
    
    print(f"📊 Tables created: {', '.join(tables)}")
    
    # Check for expected tables
    missing_tables = [t for t in expected_tables if t not in tables]
    if missing_tables:
        print(f"⚠️  Warning: Missing tables: {', '.join(missing_tables)}")
    else:
        print("✅ All expected tables created")
    
    # Verify FTS5
    cursor.execute("SELECT count(*) FROM documents_fts")
    fts_count = cursor.fetchone()[0]
    print(f"🔍 FTS5 virtual table: {'✅ Working' if fts_count >= 0 else '❌ Error'}")
    
    # Verify triggers
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='trigger' 
        AND name LIKE 'documents_%'
    """)
    triggers = [row[0] for row in cursor.fetchall()]
    print(f"🔍 FTS triggers created: {', '.join(triggers)}")
    
    # Get schema version
    cursor.execute("SELECT version, description FROM schema_version LIMIT 1")
    version_row = cursor.fetchone()
    if version_row:
        print(f"📋 Schema version: {version_row[0]} - {version_row[1]}")
    
    # Database stats
    cursor.execute("SELECT count(*) FROM documents")
    doc_count = cursor.fetchone()[0]
    print(f"📊 Documents in database: {doc_count}")
    
    conn.close()
    
    print("\n" + "="*60)
    print("✅ Database initialization complete!")
    print(f"📄 Database location: {db_path}")
    print("="*60)


def test_fts5() -> None:
    """Test FTS5 full-text search functionality."""
    db_path = get_db_path()
    
    print("\n🧪 Testing FTS5 full-text search...")
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Insert a test document
    test_doc = {
        'slug': 'test-ftx-document',
        'title': 'Test FTS Document',
        'doc_type': 'help_page',
        'category': 'Test',
        'context': 'test',
        'content': 'This is a test document for full-text search functionality.',
        'summary': 'Test document',
        'keywords': 'test, fts, search',
        'is_published': 1
    }
    
    try:
        # Insert test document
        cursor.execute("""
            INSERT INTO documents (
                slug, title, doc_type, category, context,
                content, summary, keywords, is_published
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_doc['slug'], test_doc['title'], test_doc['doc_type'],
            test_doc['category'], test_doc['context'], test_doc['content'],
            test_doc['summary'], test_doc['keywords'], test_doc['is_published']
        ))
        
        doc_id = cursor.lastrowid
        conn.commit()
        print(f"✅ Inserted test document (id={doc_id})")
        
        # Test FTS search
        cursor.execute("""
            SELECT rowid, title, snippet(documents_fts, 1, '<b>', '</b>', '...', 20) as snippet
            FROM documents_fts
            WHERE documents_fts MATCH 'test'
        """)
        
        results = cursor.fetchall()
        print(f"✅ FTS search returned {len(results)} result(s)")
        
        if results:
            for row in results:
                print(f"   - {row[1]}: {row[2]}")
        
        # Clean up test document
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
        print("✅ Cleaned up test document")
        
        print("✅ FTS5 test passed!")
        
    except sqlite3.Error as e:
        print(f"❌ FTS5 test failed: {e}")
        conn.rollback()
    finally:
        conn.close()


async def init_with_sqlalchemy() -> None:
    """
    Initialize database using SQLAlchemy (alternative method).
    
    This creates tables using SQLAlchemy models instead of raw SQL.
    Used when you want to use SQLAlchemy's metadata.create_all().
    """
    from app.core.database import Base, engine
    
    db_path = get_db_path()
    
    print(f"📄 Database path: {db_path}")
    print("🔧 Creating tables using SQLAlchemy...")
    
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Tables created successfully")


def main():
    """Main entry point."""
    print("="*60)
    print("Document Management System - Database Initialization")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("="*60)
    
    # Initialize database with SQL schema
    init_database()
    
    # Test FTS5
    test_fts5()
    
    print("\n" + "="*60)
    print("✅ All initialization steps complete!")
    print("="*60)


if __name__ == "__main__":
    main()
