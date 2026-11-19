#!/bin/bash
# archive_atlas.sh
# Moves the current Application Atlas to the archive directory.
# Preserves assessment.md and plan/ for reference during the rebuild.
#
# Usage: ./scripts/archive_atlas.sh
# Dry run: ./scripts/archive_atlas.sh --dry-run

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ATLAS_DIR="$PROJECT_ROOT/docs/atlas"
ARCHIVE_DIR="$PROJECT_ROOT/_archive/docs/atlas-old-$(date +%Y-%m-%dT%H-%M)"

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" || "${1:-}" == "-n" ]]; then
    DRY_RUN=true
fi

echo "============================================"
echo "  Application Atlas Archive Script"
echo "============================================"
echo ""

# Check atlas exists
if [ ! -d "$ATLAS_DIR" ]; then
    echo "❌ Application Atlas directory not found at: $ATLAS_DIR"
    exit 1
fi

# Count current files
FILE_COUNT=$(find "$ATLAS_DIR" -type f | wc -l)
DIR_COUNT=$(find "$ATLAS_DIR" -mindepth 1 -type d | wc -l)

echo "Current Application Atlas at: $ATLAS_DIR"
echo "  Files: $FILE_COUNT"
echo "  Directories: $DIR_COUNT"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo "🔍 DRY RUN — Would archive to: $ARCHIVE_DIR"
    echo ""
    echo "Files that would be moved:"
    find "$ATLAS_DIR" -type f | sort | while read f; do
        echo "  $(basename "$f")"
    done
    echo ""
    echo "Run without --dry-run to execute."
    exit 0
fi

# Create archive directory
echo "📦 Creating archive directory: $ARCHIVE_DIR"
mkdir -p "$ARCHIVE_DIR"

# Move everything except assessment.md and plan/
echo "📦 Moving Application Atlas files to archive..."

# Handle files at the top level
for item in "$ATLAS_DIR"/*; do
    BASENAME=$(basename "$item")
    
    # Keep these in place
    if [[ "$BASENAME" == "assessment.md" ]]; then
        echo "  ✅ Keeping: assessment.md"
        continue
    fi
    if [[ "$BASENAME" == "plan" ]]; then
        echo "  ✅ Keeping: plan/"
        continue
    fi
    
    # Move everything else
    if [ -e "$item" ]; then
        mv "$item" "$ARCHIVE_DIR/"
        echo "  📦 Archived: $BASENAME"
    fi
done

echo ""
echo "✅ Archive complete!"
echo "   Archived to: $ARCHIVE_DIR"
echo ""
echo "Remaining in docs/atlas/:"
ls -la "$ATLAS_DIR/"
echo ""
echo "Next step: Run Phase 1 of the rebuild plan."
echo "   See: docs/atlas/plan/00-master-plan.md"
