#!/bin/bash
#
# Database Recovery Execution Script
#
# Automates the complete database recovery process:
# 1. Backs up corrupted database
# 2. Creates working copy of backup
# 3. Creates fresh schema with Alembic
# 4. Migrates data from backup
# 5. Verifies recovery
#
# Usage:
#   ./scripts/recover_database.sh
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Paths
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
CORRUPTED_DB="$BACKEND_DIR/app/cogitate.db"
BACKUP_DB="$PROJECT_ROOT/backend/cogitate.db"
RECOVERY_BACKUP="$PROJECT_ROOT/backend/cogitate-backup-20260328-recovery.db"
TARGET_DB="$CORRUPTED_DB"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}       COGITATE DATABASE RECOVERY${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo "Date: $(date)"
echo "Project: $PROJECT_ROOT"
echo ""

# Function to print section headers
print_header() {
    echo ""
    echo -e "${BLUE}------------------------------------------------------------${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}------------------------------------------------------------${NC}"
}

# Function to print success
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Function to print error
print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Step 1: Verify backup exists
print_header "STEP 1: Verifying backup database"

if [ ! -f "$BACKUP_DB" ]; then
    print_error "Backup database not found: $BACKUP_DB"
    echo ""
    echo "Please ensure the backup exists at:"
    echo "  $BACKUP_DB"
    exit 1
fi

BACKUP_SIZE=$(stat -c%s "$BACKUP_DB" 2>/dev/null || stat -f%z "$BACKUP_DB" 2>/dev/null || echo "0")
if [ "$BACKUP_SIZE" -lt 1000000 ]; then
    print_error "Backup database seems too small ($BACKUP_SIZE bytes)"
    echo "Expected at least 1MB for a valid backup"
    exit 1
fi

print_success "Backup database found ($BACKUP_SIZE bytes)"

# Step 2: Backup corrupted file
print_header "STEP 2: Backing up corrupted database"

if [ -f "$CORRUPTED_DB" ]; then
    CORRUPTED_SIZE=$(stat -c%s "$CORRUPTED_DB" 2>/dev/null || stat -f%z "$CORRUPTED_DB" 2>/dev/null || echo "0")
    if [ "$CORRUPTED_SIZE" -gt 0 ]; then
        mv "$CORRUPTED_DB" "${CORRUPTED_DB}.corrupted"
        print_success "Corrupted database backed up to: ${CORRUPTED_DB}.corrupted"
    else
        rm -f "$CORRUPTED_DB"
        print_success "Removed empty corrupted database file"
    fi
else
    print_warning "No corrupted database file found (already removed?)"
fi

# Step 3: Create working copy of backup
print_header "STEP 3: Creating working copy of backup"

cp "$BACKUP_DB" "$RECOVERY_BACKUP"
print_success "Created recovery backup: $RECOVERY_BACKUP"

# Step 4: Verify backup integrity
print_header "STEP 4: Verifying backup integrity"

python3 << 'PYTHON_EOF'
import sqlite3
import sys

backup_db = sys.argv[1] if len(sys.argv) > 1 else "backend/cogitate-backup-20260328-recovery.db"

try:
    conn = sqlite3.connect(backup_db)
    cur = conn.cursor()
    
    # Integrity check
    cur.execute("PRAGMA integrity_check")
    result = cur.fetchone()[0]
    
    if result != "ok":
        print(f"❌ Backup integrity check failed: {result}")
        sys.exit(1)
    
    # Count tables
    cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
    table_count = cur.fetchone()[0]
    
    print(f"✅ Backup integrity: OK ({table_count} tables)")
    conn.close()
except Exception as e:
    print(f"❌ Backup verification failed: {e}")
    sys.exit(1)
PYTHON_EOF

print_success "Backup integrity verified"

# Step 5: Create fresh schema with Alembic
print_header "STEP 5: Creating fresh database schema"

cd "$BACKEND_DIR"

# Remove target db if it exists
rm -f "$TARGET_DB"

echo "Running Alembic migrations..."
if uv run alembic upgrade head; then
    print_success "Schema created successfully"
else
    print_error "Alembic migration failed"
    echo ""
    echo "You can try manual recovery:"
    echo "  1. cp $RECOVERY_BACKUP $TARGET_DB"
    echo "  2. cd backend && uv run uvicorn app.main:app --reload"
    exit 1
fi

cd "$PROJECT_ROOT"

# Verify schema was created
if [ ! -f "$TARGET_DB" ]; then
    print_error "Target database was not created"
    exit 1
fi

TARGET_SIZE=$(stat -c%s "$TARGET_DB" 2>/dev/null || stat -f%z "$TARGET_DB" 2>/dev/null || echo "0")
print_success "Target database created ($TARGET_SIZE bytes)"

# Step 6: Migrate data from backup
print_header "STEP 6: Migrating data from backup"

python3 scripts/maintenance/migrate_from_backup.py

if [ $? -eq 0 ]; then
    print_success "Data migration completed"
else
    print_error "Data migration failed"
    echo ""
    echo "You can try direct restore:"
    echo "  cp $RECOVERY_BACKUP $TARGET_DB"
    exit 1
fi

# Step 7: Verify recovery
print_header "STEP 7: Verifying recovery"

python3 scripts/maintenance/verify_recovery.py

if [ $? -eq 0 ]; then
    print_success "Recovery verification passed"
else
    print_warning "Recovery verification had some issues"
    echo ""
    echo "Review the verification output above."
    echo "The database may still be usable."
fi

# Step 8: Summary
print_header "RECOVERY COMPLETE"

echo ""
echo "Database recovery has been completed."
echo ""
echo "Files created:"
echo "  - $TARGET_DB (recovered database)"
echo "  - $RECOVERY_BACKUP (backup copy)"
echo "  - ${CORRUPTED_DB}.corrupted (corrupted original)"
echo ""
echo "Next steps:"
echo "  1. Start backend: cd backend && uv run uvicorn app.main:app --reload"
echo "  2. Test API: curl http://localhost:8000/api/v1/agents"
echo "  3. Start frontend: cd frontend && npm run dev"
echo ""
echo "If you encounter issues:"
echo "  - Review verification output above"
echo "  - Check backend logs for errors"
echo "  - Consider direct restore: cp $RECOVERY_BACKUP $TARGET_DB"
echo ""
print_success "Recovery complete!"
