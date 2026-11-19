#!/usr/bin/env python3
"""
Load Tool Tests 00 Macro Sets into Database

Creates 5 macro sets for tool testing under the "Tool Tests 00" meta topic.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

# Database is at project root
DB_PATH = Path(__file__).parent.parent / 'cogitate.db'

# Macro sets data
MACRO_SETS = [
    {
        'topic': 'Tool Tests 00',
        'name': 'Tool Tests 00 - DateTime',
        'description': 'Test datetime tool with all format options',
        'f1_macro': 'What time is it?',
        'f2_macro': "What's the time in ISO format?",
        'f3_macro': 'Give me the timestamp',
        'f4_macro': "What's today's date?",
        'f5_macro': 'What time is it right now?',
    },
    {
        'topic': 'Tool Tests 00',
        'name': 'Tool Tests 00 - Calculator',
        'description': 'Test calculator with basic math operations',
        'f1_macro': 'Calculate 2 + 2',
        'f2_macro': 'What is 123 * 456?',
        'f3_macro': 'Divide 100 by 4',
        'f4_macro': "What's 15 minus 7?",
        'f5_macro': 'Calculate 2 to the power of 10',
    },
    {
        'topic': 'Tool Tests 00',
        'name': 'Tool Tests 00 - Text Tools',
        'description': 'Test text transformation and clipboard tools',
        'f1_macro': 'Convert "hello world" to uppercase',
        'f2_macro': 'Make "HELLO" lowercase',
        'f3_macro': 'Reverse the text "abc123"',
        'f4_macro': 'Read from clipboard',
        'f5_macro': 'Write "test" to clipboard',
    },
    {
        'topic': 'Tool Tests 00',
        'name': 'Tool Tests 00 - File Info',
        'description': 'Test file-info and web-search tools',
        'f1_macro': 'Get info about current directory',
        'f2_macro': "What's in /home?",
        'f3_macro': 'Search for "test query"',
        'f4_macro': 'Look up "Python programming"',
        'f5_macro': 'Search the web for latest news',
    },
    {
        'topic': 'Tool Tests 00',
        'name': 'Tool Tests 00 - Productivity',
        'description': 'Test todo-list and line-editor tools',
        'f1_macro': 'List my todos',
        'f2_macro': 'Add "test task" to todos',
        'f3_macro': 'Edit line 5 of this text',
        'f4_macro': 'Show me line 10',
        'f5_macro': 'Delete line 3',
    },
]


def load_macro_sets():
    """Load macro sets into database."""
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if topic already exists
    cursor.execute(
        "SELECT COUNT(*) FROM macro_sets WHERE topic = ?",
        ('Tool Tests 00',)
    )
    existing_count = cursor.fetchone()[0]
    
    if existing_count > 0:
        print(f"\n⚠️  Found {existing_count} existing macro sets for 'Tool Tests 00'")
        response = input("Delete existing sets and reload? (y/n): ").strip().lower()
        if response == 'y':
            cursor.execute(
                "DELETE FROM macro_sets WHERE topic = ?",
                ('Tool Tests 00',)
            )
            conn.commit()
            print("✅ Deleted existing macro sets")
        else:
            print("❌ Aborted - no changes made")
            conn.close()
            return
    
    # Get max sort_order
    cursor.execute("SELECT MAX(sort_order) FROM macro_sets")
    max_order = cursor.fetchone()[0] or 0
    
    # Insert macro sets
    print(f"\n📝 Loading {len(MACRO_SETS)} macro sets...")
    
    for i, macro_set in enumerate(MACRO_SETS, 1):
        cursor.execute("""
            INSERT INTO macro_sets (
                user_key, topic, name, description,
                f1_macro, f2_macro, f3_macro, f4_macro, f5_macro,
                is_active, sort_order, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'default',  # user_key
            macro_set['topic'],
            macro_set['name'],
            macro_set['description'],
            macro_set['f1_macro'],
            macro_set['f2_macro'],
            macro_set['f3_macro'],
            macro_set['f4_macro'],
            macro_set['f5_macro'],
            True,  # is_active
            max_order + i,  # sort_order
            datetime.now(),  # created_at
            datetime.now(),  # updated_at
        ))
        
        print(f"  ✅ Loaded: {macro_set['name']}")
    
    conn.commit()
    
    # Verify
    cursor.execute(
        "SELECT id, name, topic FROM macro_sets WHERE topic = ? ORDER BY sort_order",
        ('Tool Tests 00',)
    )
    loaded = cursor.fetchall()
    
    print(f"\n✅ Successfully loaded {len(loaded)} macro sets:")
    for macro in loaded:
        print(f"  - {macro[1]}")
    
    conn.close()
    print(f"\n💾 Database saved: {DB_PATH}")
    print("\n🎯 Next steps:")
    print("  1. Open chat at http://localhost:5173")
    print("  2. Select agent (O Tool or Tooled Up)")
    print("  3. Open Macro Keyboard (F-keys)")
    print("  4. Select 'Tool Tests 00' topic")
    print("  5. Press F1-F5 to test tools!")


if __name__ == "__main__":
    load_macro_sets()
