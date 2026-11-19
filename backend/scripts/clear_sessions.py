#!/usr/bin/env python3
"""
Clear all chat sessions and messages from the database.

Usage:
    python scripts/clear_sessions.py

This is useful for:
- Resetting test data during development
- Clearing corrupted sessions
- Debugging session lifecycle issues
"""

import sqlite3
from pathlib import Path

# Database is at project root, not backend/
# backend/scripts/ -> parent = scripts/ -> parent.parent = backend/ -> parent.parent.parent = project_root
PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / "cogitate.db"

if not DB_PATH.exists():
    print(f"Database not found: {DB_PATH}")
    exit(1)

print(f"Using database: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Show current state
print("\n=== BEFORE CLEAR ===")
cursor.execute("SELECT COUNT(*) FROM chat_sessions")
session_count = cursor.fetchone()[0]
print(f"Sessions: {session_count}")

cursor.execute("SELECT COUNT(*) FROM chat_messages")
message_count = cursor.fetchone()[0]
print(f"Messages: {message_count}")

# Clear
confirm = input(f"\nDelete {session_count} sessions and {message_count} messages? [y/N] ")
if confirm.lower() != 'y':
    print("Cancelled.")
    exit(0)

print("\n=== CLEARING ===")
cursor.execute("DELETE FROM chat_messages")
cursor.execute("DELETE FROM chat_sessions")
conn.commit()

# Verify
cursor.execute("SELECT COUNT(*) FROM chat_sessions")
session_count = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM chat_messages")
message_count = cursor.fetchone()[0]

print("\n=== AFTER CLEAR ===")
print(f"Sessions: {session_count}")
print(f"Messages: {message_count}")

conn.close()
print("\nDone!")
