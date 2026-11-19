-- ============================================================================
-- Document Management System Schema
-- ============================================================================
-- Unified document storage with FTS5 full-text search support.
-- Supports multiple document types via doc_type field (help_page, user_guide, manual, etc.)
-- Database: cogitate_docs_en.db (separate from main cogitate.db)
-- ============================================================================

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================================================
-- Documents Table
-- ============================================================================
-- Unified table for all document types.
-- doc_type values: 'help_page', 'user_guide', 'manual', 'tutorial', 'faq', etc.
-- ============================================================================

CREATE TABLE IF NOT EXISTS documents (
    -- Primary key
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Core identification
    slug TEXT NOT NULL UNIQUE,              -- URL-friendly identifier (e.g., 'chat-sending-messages')
    title TEXT NOT NULL,                     -- Document title
    doc_type TEXT NOT NULL DEFAULT 'help_page', -- Document type for categorization
    category TEXT,                           -- Category for grouping (e.g., 'Chat', 'Logs', 'Sessions')
    context TEXT,                            -- Page context for contextual help (e.g., 'chat', 'logs')
    
    -- Content
    content TEXT NOT NULL,                   -- Markdown content
    summary TEXT,                            -- Short summary/description
    keywords TEXT,                           -- Comma-separated search keywords
    
    -- Metadata
    author TEXT,                             -- Content author
    version TEXT DEFAULT '1.0',              -- Content version
    is_published INTEGER DEFAULT 1 NOT NULL, -- Publication status (0=draft, 1=published)
    is_featured INTEGER DEFAULT 0 NOT NULL,  -- Featured documents appear first
    
    -- SEO/Discovery
    search_keywords TEXT,                    -- Additional search terms (not displayed)
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Indexes
    CHECK (doc_type IN ('help_page', 'user_guide', 'manual', 'tutorial', 'faq', 'reference', 'quickstart'))
);

-- Indexes for documents
CREATE INDEX IF NOT EXISTS idx_documents_slug ON documents(slug);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);
CREATE INDEX IF NOT EXISTS idx_documents_context ON documents(context);
CREATE INDEX IF NOT EXISTS idx_documents_published ON documents(is_published);
CREATE INDEX IF NOT EXISTS idx_documents_featured ON documents(is_featured DESC);
CREATE INDEX IF NOT EXISTS idx_documents_type_category ON documents(doc_type, category);
CREATE INDEX IF NOT EXISTS idx_documents_updated_at ON documents(updated_at DESC);

-- ============================================================================
-- Document Relations Table
-- ============================================================================
-- Links related documents together (e.g., "See also", "Related articles")
-- ============================================================================

CREATE TABLE IF NOT EXISTS document_relations (
    -- Primary key
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Foreign keys
    document_id INTEGER NOT NULL,
    related_document_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL DEFAULT 'related', -- 'related', 'see_also', 'prerequisite', 'next_step'
    
    -- Metadata
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Foreign key constraints
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (related_document_id) REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Prevent self-relation and duplicates
    UNIQUE(document_id, related_document_id, relation_type),
    CHECK (document_id != related_document_id)
);

-- Indexes for relations
CREATE INDEX IF NOT EXISTS idx_relations_document_id ON document_relations(document_id);
CREATE INDEX IF NOT EXISTS idx_relations_related_id ON document_relations(related_document_id);
CREATE INDEX IF NOT EXISTS idx_relations_type ON document_relations(relation_type);

-- ============================================================================
-- Document Analytics Table (Optional)
-- ============================================================================
-- Tracks document views, feedback, and usage patterns
-- ============================================================================

CREATE TABLE IF NOT EXISTS document_analytics (
    -- Primary key
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Foreign key
    document_id INTEGER NOT NULL,
    
    -- View tracking
    view_count INTEGER DEFAULT 0 NOT NULL,
    unique_views INTEGER DEFAULT 0 NOT NULL,
    
    -- Feedback tracking
    helpful_count INTEGER DEFAULT 0 NOT NULL,
    not_helpful_count INTEGER DEFAULT 0 NOT NULL,
    feedback_score REAL DEFAULT 0.0,  -- Calculated: helpful / (helpful + not_helpful)
    
    -- Last viewed timestamp
    last_viewed_at DATETIME,
    
    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Foreign key constraint
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Unique constraint (one analytics record per document)
    UNIQUE(document_id)
);

-- Indexes for analytics
CREATE INDEX IF NOT EXISTS idx_analytics_document_id ON document_analytics(document_id);
CREATE INDEX IF NOT EXISTS idx_analytics_score ON document_analytics(feedback_score DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_views ON document_analytics(view_count DESC);

-- ============================================================================
-- Full-Text Search (FTS5) Virtual Table
-- ============================================================================
-- Provides fast full-text search across document content
-- ============================================================================

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    -- Indexed columns
    title,
    content,
    summary,
    keywords,
    search_keywords,
    slug,
    category,
    subtopic,
    doc_type,
    context,

    -- Contentless mode - we manage the base table separately
    -- This is a standalone FTS index, not linked to documents table
);

-- ============================================================================
-- Triggers for FTS5 Sync
-- ============================================================================
-- Automatically keep FTS index in sync with base table
-- ============================================================================

-- Trigger: Insert into documents -> Insert into FTS
CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(
        rowid,
        title,
        content,
        summary,
        keywords,
        search_keywords,
        slug,
        category,
        subtopic,
        doc_type,
        context
    ) VALUES (
        NEW.id,
        NEW.title,
        NEW.content,
        NEW.summary,
        NEW.keywords,
        NEW.search_keywords,
        NEW.slug,
        NEW.category,
        NEW.subtopic,
        NEW.doc_type,
        NEW.context
    );
END;

-- Trigger: Update documents -> Update FTS
CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
    UPDATE documents_fts SET
        title = NEW.title,
        content = NEW.content,
        summary = NEW.summary,
        keywords = NEW.keywords,
        search_keywords = NEW.search_keywords,
        slug = NEW.slug,
        category = NEW.category,
        subtopic = NEW.subtopic,
        doc_type = NEW.doc_type,
        context = NEW.context
    WHERE rowid = NEW.id;
END;

-- Trigger: Delete documents -> Delete from FTS
CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
    DELETE FROM documents_fts WHERE rowid = OLD.id;
END;

-- ============================================================================
-- Additional Indexes for FTS Performance
-- ============================================================================

-- Compound index for common query patterns
CREATE INDEX IF NOT EXISTS idx_documents_type_published ON documents(doc_type, is_published);
CREATE INDEX IF NOT EXISTS idx_documents_context_published ON documents(context, is_published);

-- ============================================================================
-- Schema Version Tracking
-- ============================================================================
-- Track schema version for migrations
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    description TEXT
);

-- Insert initial version
INSERT OR IGNORE INTO schema_version (version, description) VALUES (1, 'Initial schema with documents, relations, analytics, and FTS5');

-- ============================================================================
-- End of Schema
-- ============================================================================
