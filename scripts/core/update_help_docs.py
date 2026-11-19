#!/usr/bin/env python3
"""
Update in-app help documents to reflect the current UI state.

Updates the `data/cogitate_docs_en.db` database with accurate help content
for Dashboard, Agent Chat, Sessions, and Logs pages.

Usage:
    uv run python3 scripts/core/update_help_docs.py

Notes:
    - Uses INSERT OR REPLACE so it's safe to run multiple times
    - Only modifies documents with the specified slugs
    - Does NOT modify Atlas reference docs (doc_type='reference')
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent.parent.parent / "data" / "cogitate_docs_en.db"


def get_connection() -> sqlite3.Connection:
    """Get connection to the documents database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def upsert_document(cursor: sqlite3.Cursor, doc: dict) -> None:
    """Insert or replace a document by slug."""
    cursor.execute("""
        INSERT OR REPLACE INTO documents
            (slug, title, doc_type, category, subtopic, context,
             content, summary, keywords, search_keywords,
             is_published, is_featured, display_order, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        doc['slug'], doc['title'], doc.get('doc_type', 'help_page'),
        doc.get('category', ''), doc.get('subtopic', ''),
        doc.get('context', ''),
        doc['content'], doc.get('summary', ''),
        doc.get('keywords', ''), doc.get('search_keywords', ''),
        1, doc.get('is_featured', 0),
        doc.get('display_order', 999),
        datetime.now(timezone.utc).isoformat()
    ))


def update_dashboard_docs(cursor: sqlite3.Cursor) -> None:
    """Update Dashboard help documents."""
    docs = [
        {
            'slug': 'dashboard-overview-introduction',
            'title': 'Introduction',
            'category': 'dashboard',
            'context': 'dashboard',
            'summary': 'Overview of the Cogitate Dashboard with navigation and system status',
            'keywords': 'dashboard, overview, navigation, status, stats, system',
            'search_keywords': 'home page, main page, system overview, quick navigation',
            'is_featured': 1,
            'display_order': 1,
            'content': '''# Dashboard Overview

The Cogitate Dashboard is your central hub for system monitoring and navigation.

## Layout

### Header Bar
The header contains:
- **Cogitate Logo** with tooltip
- **Page Title**: "Cogitate Dashboard"
- **BackendStatusIndicator**: Compact indicator showing system health (🟢 online, 🟡 degraded, 🔴 offline)
- **App Version**: Version number display (vX.X.X)
- **CacheBuster**: "Clear Cache" button to reset frontend state
- **Help Button**: Opens context-sensitive help documentation

### Navigation Cards
Four navigation cards provide quick access to main features:
- **Agent Chat**: Interact with AI agents
- **Sessions**: View and manage conversation history
- **Logs**: Monitor system events and errors

### Quick Stats
The QuickStats section displays key metrics:
- Active sessions count
- Total messages sent
- Active agents count
- System uptime

Values update automatically and change color based on thresholds (green = normal, yellow = warning, red = critical).''',
        },
        {
            'slug': 'dashboard-overview-key-features',
            'title': 'Key Features',
            'category': 'dashboard',
            'context': 'dashboard',
            'summary': 'Key features of the Dashboard page',
            'keywords': 'features, dashboard, navigation, monitoring',
            'search_keywords': 'dashboard features, dashboard capabilities',
            'is_featured': 0,
            'content': '''# Key Features

## System Status at a Glance
The BackendStatusIndicator shows real-time system health:
- **Green**: All systems operational
- **Yellow**: Degraded performance or partial outage
- **Red**: Critical system issues

## Quick Navigation
NavigationCards provide one-click access to all major features. Each card shows:
- Feature name and icon
- Brief description
- Visual feedback on hover

## Cache Management
The CacheBuster button clears frontend state when needed:
- Resets React Query cache
- Clears local storage
- Refreshes component state

## Version Tracking
The app version display helps with debugging and support requests.''',
        },
    ]
    for doc in docs:
        upsert_document(cursor, doc)
    print(f"  Updated {len(docs)} dashboard documents")


def update_chat_docs(cursor: sqlite3.Cursor) -> None:
    """Update Agent Chat help documents."""
    docs = [
        {
            'slug': 'chat-getting-started-starting-your-first-chat',
            'title': 'Starting Your First Chat',
            'category': 'chat',
            'context': 'chat',
            'summary': 'How to start your first conversation with an AI agent',
            'keywords': 'getting started, first chat, agent, conversation',
            'search_keywords': 'start chat, begin conversation, new chat',
            'is_featured': 1,
            'display_order': 1,
            'content': '''# Starting Your First Chat

## Getting Started
The Agent Chat page lets you converse with AI agents for various tasks.

### Selecting an Agent
1. Use the **Agent Selector** dropdown at the top of the page
2. Browse available agents and their descriptions
3. Select an agent to start a conversation

### Sending Messages
- Type your message in the chat input box
- Press **Enter** to send
- Use **Shift+Enter** for multi-line messages
- View real-time streaming responses

### Session Management
- Your conversations are automatically saved as sessions
- Use the **Session Manager** sidebar to switch between conversations
- Sessions persist across page reloads''',
        },
        {
            'slug': 'chat-advanced-features-tool-usage',
            'title': 'Tool Usage',
            'category': 'chat',
            'context': 'chat',
            'summary': 'Using tools and the Tool Widget in Agent Chat',
            'keywords': 'tools, widget, actions, agent, tool execution',
            'search_keywords': 'tool widget, agent tools, tool panel',
            'display_order': 2,
            'content': '''# Tool Usage

## Tool Widget

The Agent Chat page features a **Tool Widget** panel that displays available tools for the selected agent. The widget shows tool cards with descriptions and execution status.

### Accessing the Tool Widget
- The Tool Widget is located in the right sidebar of the Agent Chat page
- It shows tools available for the currently selected agent
- Tools are displayed as cards with name, description, and parameters

### Tool Execution
1. Select an agent that has tools configured
2. The Tool Widget displays available tools
3. Tools appear as action cards in the conversation
4. Click to expand and see tool execution details
5. Results display inline or as attachments
6. Some tools may require your confirmation before running

### Example Tools
- **Web Search**: Look up current information
- **Code Execution**: Run code snippets
- **File Operations**: Read, write, and manage files
- **Database Queries**: Execute database operations

## Agent List Selector
Located at the top of the page, the agent selector lets you:
- Switch between different teams/collections
- Select specific agents within a team
- View agent capabilities and available tools

## Session Manager
The collapsible sidebar on the right manages your chat sessions:
- View session history
- Switch between active sessions
- Start new conversations
- Access session settings''',
            'is_featured': 1
        },
        {
            'slug': 'chat-sending-messages-composing-a-message',
            'title': 'Composing a Message',
            'category': 'chat',
            'context': 'chat',
            'summary': 'How to compose and send messages in Agent Chat',
            'keywords': 'compose, message, send, chat, input',
            'search_keywords': 'type message, write message, chat input',
            'display_order': 3,
            'content': '''# Composing a Message

## Chat Interface
The Agent Chat page provides a full-featured chat interface for conversing with AI agents.

### Message Input
- Type your message in the chat input box at the bottom of the chat window
- Press **Enter** or click the **Send** button to submit your message
- Use **Shift+Enter** for multi-line messages

### Response Stream
Agent responses appear in real-time via the **ResponseStream** component:
- Streaming responses show as they're generated
- Supports markdown formatting (code blocks, lists, tables)
- Code blocks include syntax highlighting and copy buttons

### Theater Mode
Toggle **Theater Mode** to expand the chat area full-width, hiding sidebars for focused conversation.

### Keyboard Macros
Use the **Macro Keyboard** to insert predefined prompts and templates:
- Quick access to common patterns
- Macro sets organized by topic
- Click a macro to insert it into the input''',
            'is_featured': 1
        },
    ]
    for doc in docs:
        upsert_document(cursor, doc)
    print(f"  Updated {len(docs)} chat documents")


def update_sessions_docs(cursor: sqlite3.Cursor) -> None:
    """Update Sessions help documents to reflect current UI."""
    docs = [
        {
            'slug': 'sessions-session-management-viewing-session-history',
            'title': 'Viewing Session History',
            'category': 'sessions',
            'context': 'sessions',
            'summary': 'Browse and view your conversation session history',
            'keywords': 'sessions, history, view, browse, table',
            'search_keywords': 'session list, view sessions, browse sessions',
            'display_order': 1,
            'content': '''# Viewing Session History

## Sessions Page
The **Sessions** page displays all your conversation sessions in a table format.

### Session Table
The table shows:
- **Title**: Session name (click to view details)
- **Agent**: Which agent was used
- **Date**: When the session was created or last active
- **Messages**: Message count

### Session Details Modal
Click the **View Details** button on any session row to open the **Session Details Modal**, which shows:
- Full session title and agent information
- Creation and last activity timestamps
- Message count and summary
- Options to rename or delete the session

### Actions
- **Rename**: Edit the session title
- **Delete**: Remove the session permanently
- **View Details**: Open the details modal for more options''',
            'is_featured': 1
        },
        {
            'slug': 'sessions-session-management-organizing-sessions',
            'title': 'Organizing Sessions',
            'category': 'sessions',
            'context': 'sessions',
            'summary': 'Filter, sort, and organize your sessions',
            'keywords': 'organize, filter, sort, search, sessions',
            'search_keywords': 'session organization, filter sessions, sort sessions',
            'content': '''# Organizing Sessions

## Session Filters
The **SessionFilters** bar at the top of the page provides:

### Search
- Text search across session titles and content
- Real-time filtering as you type

### Sort By
- **Date**: Sort by creation or last activity date
- **Title**: Sort alphabetically by title
- **Count**: Sort by message count

### Sort Order
- **Ascending**: Oldest or A-Z first
- **Descending**: Newest or Z-A first

### Date Range
- **All**: Show all sessions
- **Today**: Only today's sessions
- **This Week**: Sessions from the current week
- **This Month**: Sessions from the current month

### Agent Filter
- Filter by specific agent
- Shows sessions for selected agent only

## Refresh
Click the **Refresh** button in the top-right action bar to reload the session list from the server.''',
            'is_featured': 0
        },
    ]
    for doc in docs:
        upsert_document(cursor, doc)
    print(f"  Updated {len(docs)} sessions documents")


def update_logs_docs(cursor: sqlite3.Cursor) -> None:
    """Update Logs help documents to reflect current UI."""
    docs = [
        {
            'slug': 'logs-overview-introduction',
            'title': 'Introduction',
            'category': 'logs',
            'context': 'logs',
            'summary': 'Overview of the Logs page and its features',
            'keywords': 'logs, overview, introduction, monitoring',
            'search_keywords': 'log page, log viewer, application logs',
            'display_order': 1,
            'content': '''# Introduction

## Logs Page Overview
The **Logs** page provides centralized log viewing and management for all application components.

### Status Indicator Cards
At the top of the page, status cards show storage usage for each log source:
- **Backend Logs**: Server-side operations and API calls (size in MB)
- **Frontend Logs**: Browser-based events and errors (size in MB)
- **Archives**: Rotated/archived log files (size in MB)
- **Total**: Combined size of all log storage

Each card has a **Clear** button to purge logs from that source.

### Action Buttons
Dedicated clear buttons for each log source:
- **Clear Frontend Logs**
- **Clear Backend Logs**
- **Clear All Logs**
- **Clear Archives**

Each shows a loading spinner while in progress.

### Log Table
Logs are displayed in a table with columns:
- **Timestamp**: When the event occurred
- **Level**: Severity with color-coded badge
- **Source**: Component that generated the log
- **Message**: Description of the event
- **Actions**: View Details button

### Log Details Modal
Click **View Details** on any log entry to see:
- Full log message
- Complete metadata and context
- Stack trace (if available)
- Source file and line number''',
            'is_featured': 1
        },
        {
            'slug': 'logs-overview-key-features',
            'title': 'Key Features',
            'category': 'logs',
            'context': 'logs',
            'summary': 'Key features of the Logs page',
            'keywords': 'features, logs, filtering, clearing, monitoring',
            'search_keywords': 'log features, log capabilities',
            'content': '''# Key Features

## Log Sources
Logs are organized by source with individual storage tracking:
- **Backend**: Server operations, API calls, database queries
- **Frontend**: Browser events, UI interactions, client errors
- **Archives**: Rotated log files from all sources

## Storage Monitoring
Each source card shows current storage size in MB, giving you at-a-glance insight into log volume.

## One-Click Clearing
Clear logs from any source with a single click. Each clear action:
- Shows a loading spinner during operation
- Confirms completion
- Updates the storage size immediately

## Filtering
The **LogFilters** bar provides:
- Filter by log level (DEBUG, INFO, WARNING, ERROR)
- Filter by source component
- Filter by time range (presets or custom)
- Text search across log messages
- Pagination controls for navigating results

## Detailed View
The **Log Details Modal** provides comprehensive information about each log entry, including full message, metadata, and stack traces.''',
            'is_featured': 0
        },
        {
            'slug': 'logs-using-the-logs-page-viewing-recent-logs',
            'title': 'Viewing Recent Logs',
            'category': 'logs',
            'context': 'logs',
            'summary': 'View and navigate recent log entries',
            'keywords': 'recent logs, view, navigate, pagination',
            'search_keywords': 'see logs, recent entries, log navigation',
            'content': '''# Viewing Recent Logs

## Log Table
Logs are displayed in reverse chronological order (newest first) in a table format.

### Columns
- **Timestamp**: Date and time of the event
- **Level**: Color-coded severity badge (DEBUG=gray, INFO=blue, WARNING=yellow, ERROR=red)
- **Source**: Component name that generated the log
- **Message**: Brief description of the event
- **Actions**: View Details button

### Pagination
Navigate through log results using pagination controls below the table:
- **Previous/Next** page buttons
- **Page number** selector
- Configurable results per page

## Status Cards
The status indicator cards at the top show:
- Current storage size for each log source
- Quick visual overview of log volume distribution''',
            'is_featured': 0
        },
        {
            'slug': 'logs-using-the-logs-page-filtering-by-level',
            'title': 'Filtering by Level',
            'category': 'logs',
            'context': 'logs',
            'summary': 'Filter logs by severity level',
            'keywords': 'filter, level, severity, DEBUG, INFO, WARNING, ERROR',
            'search_keywords': 'filter by level, log severity, debug filter',
            'content': '''# Filtering by Level

## Log Level Filter
Use the **LogFilters** bar to narrow down logs by severity level.

### Available Levels
- **DEBUG**: Detailed diagnostic information for developers
- **INFO**: Normal operational messages
- **WARNING**: Potential issues that don't stop operation
- **ERROR**: Errors and failures that need attention

### How to Filter
1. Click the **Level** dropdown in the LogFilters bar
2. Select one or more levels
3. The log table updates to show only matching entries

### Level Hierarchy
When viewing logs, setting a level shows that level and all higher severity levels:
```
DEBUG < INFO < WARNING < ERROR
```''',
            'is_featured': 0
        },
        {
            'slug': 'logs-using-the-logs-page-filtering-by-source',
            'title': 'Filtering by Source',
            'category': 'logs',
            'context': 'logs',
            'summary': 'Filter logs by source component',
            'keywords': 'filter, source, component, backend, frontend',
            'search_keywords': 'filter by source, component filter',
            'content': '''# Filtering by Source

## Source Filter
Use the **LogFilters** bar to find logs from specific components.

### How to Filter
1. Click the **Source** dropdown in the LogFilters bar
2. Select the component (e.g., ChatInterface, API, Database)
3. View only logs from that source

### Common Sources
- **Backend**: Server-side operations
- **Frontend**: Browser-based events
- **API**: API requests and responses
- **Database**: Database operations

## Combined Filtering
You can combine source filters with level filters and time range for precise log analysis.''',
            'is_featured': 0
        },
        {
            'slug': 'logs-using-the-logs-page-searching-logs',
            'title': 'Searching Logs',
            'category': 'logs',
            'context': 'logs',
            'summary': 'Search log messages for specific text',
            'keywords': 'search, find, text search, log messages',
            'search_keywords': 'search logs, find in logs, text search',
            'content': '''# Searching Logs

## Text Search
Use the search bar in the **LogFilters** to find logs containing specific text.

### How to Search
1. Enter search terms in the search box
2. Press **Enter**
3. Logs matching your search are displayed

### Search Tips
- Searches are case-insensitive
- Matches against the log message field
- Combine with level and source filters for precise results

## Clear Filters
Click **Clear All Filters** to reset all filter options and show all logs.''',
            'is_featured': 0
        },
        {
            'slug': 'logs-advanced-features-time-range-selection',
            'title': 'Time Range Selection',
            'category': 'logs',
            'context': 'logs',
            'summary': 'Filter logs by time range',
            'keywords': 'time range, date filter, preset, custom range',
            'search_keywords': 'filter by time, date range, time period',
            'content': '''# Time Range Selection

## Time Range Filter
Use the **Time Range** selector in the LogFilters bar to view logs from a specific time period.

### Preset Ranges
- **Last Hour**: Logs from the past 60 minutes
- **Last 24 Hours**: Logs from the past day
- **Last 7 Days**: Logs from the past week
- **Last 30 Days**: Logs from the past month

### How to Use
1. Click the **Time Range** selector
2. Choose a preset range
3. Logs update to show only entries in that range

## Combined with Other Filters
Time range can be combined with level, source, and text search filters for targeted log analysis.''',
            'is_featured': 0
        },
    ]
    for doc in docs:
        upsert_document(cursor, doc)
    print(f"  Updated {len(docs)} logs documents")




def main() -> None:
    """Main entry point."""
    print(f"Updating help documents in: {DB_PATH}")
    
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        print("\n--- Dashboard Documents ---")
        update_dashboard_docs(cursor)
        
        print("\n--- Chat Documents ---")
        update_chat_docs(cursor)
        
        print("\n--- Sessions Documents ---")
        update_sessions_docs(cursor)
        
        print("\n--- Logs Documents ---")
        update_logs_docs(cursor)
        
        
        
        conn.commit()
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM documents")
        total = cursor.fetchone()[0]
        print(f"\nTotal documents in database: {total}")
        
        cursor.execute("SELECT context, COUNT(*) FROM documents GROUP BY context ORDER BY context")
        for row in cursor.fetchall():
            print(f"  {row['context']}: {row['COUNT(*)']} docs")
            
    finally:
        conn.close()
    
    print("\nDone.")


if __name__ == "__main__":
    main()
