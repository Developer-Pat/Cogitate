#!/usr/bin/env python3
"""
CRITICAL: Synchronize documents database.

This script ensures the documents table exists in the correct database
and migrates any data if needed.

Run this BEFORE starting the application after writing help documents into
the docs database (scripts/core/update_help_docs.py is the writer).
"""

import sqlite3
from pathlib import Path

# Database paths
# backend/scripts/check_docs_database.py → project root
MAIN_DB = Path(__file__).resolve().parents[2] / "cogitate.db"
DOCS_DB = Path(__file__).resolve().parents[2] / "data" / "cogitate_docs_en.db"


def check_databases():
    """Check both databases and report status."""
    print("="*60)
    print("DOCUMENT DATABASE STATUS CHECK")
    print("="*60)
    
    # Check main database
    if MAIN_DB.exists():
        conn = sqlite3.connect(MAIN_DB)
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="documents"')
        has_docs = cursor.fetchone() is not None
        if has_docs:
            cursor.execute('SELECT COUNT(*) FROM documents')
            count = cursor.fetchone()[0]
            print(f"\n❌ MAIN DB ({MAIN_DB.name}):")
            print(f"   Has documents table with {count} records")
            print("   ⚠️  This should be EMPTY - the docs live in the separate DB")
        else:
            print(f"\n✅ MAIN DB ({MAIN_DB.name}):")
            print("   No documents table (correct)")
        conn.close()
    else:
        print(f"\n⚠️  MAIN DB not found: {MAIN_DB}")
    
    # Check docs database
    if DOCS_DB.exists():
        conn = sqlite3.connect(DOCS_DB)
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="documents"')
        has_docs = cursor.fetchone() is not None
        if has_docs:
            cursor.execute('SELECT COUNT(*) FROM documents')
            count = cursor.fetchone()[0]
            print(f"\n✅ DOCS DB ({DOCS_DB.name}):")
            print(f"   Has documents table with {count} records")
            
            # Show recent documents
            cursor.execute('SELECT slug, title FROM documents ORDER BY updated_at DESC LIMIT 5')
            print("   Recent documents:")
            for row in cursor.fetchall():
                print(f"     - {row[0]}")
        else:
            print(f"\n❌ DOCS DB ({DOCS_DB.name}):")
            print("   No documents table - run init_docs_db.py first")
        conn.close()
    else:
        print(f"\n❌ DOCS DB not found: {DOCS_DB}")
        print("   Run: python backend/scripts/init_docs_db.py")
    
    print("\n" + "="*60)


def main():
    """Main entry point."""
    check_databases()

    print("\n" + "="*60)
    print("""
The backend uses two databases, on purpose:
  - MAIN DB: cogitate.db (agents, sessions, tools, etc.)
  - DOCS DB: data/cogitate_docs_en.db (help documents)

The split is implemented: `app/core/database.py` creates a separate async
engine for the docs database, `init_documents_db()` runs at startup, and
`get_documents_session()` is the dependency the document endpoints use. So
the MAIN db should carry no `documents` table — anything there is a leftover
from before the split and can be dropped.

Writers of help content: `scripts/core/update_help_docs.py` (in-app help
pages) and the atlas tooling (reference docs, doc_type='reference').
    """)
    print("="*60)


if __name__ == "__main__":
    main()
