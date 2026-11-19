#!/usr/bin/env python3
"""
Comment out traceService.trace() calls in TypeScript files.

This script finds all traceService.trace() calls and comments them out,
preserving them for future debugging while disabling them by default.

Usage:
    python scripts/comment_traces.py [--dry-run] [file_or_directory...]

Examples:
    python scripts/comment_traces.py --dry-run
    python scripts/comment_traces.py frontend/src/services/domain/TitleService.ts
    python scripts/comment_traces.py frontend/src/hooks
"""

import argparse
import re
import sys
from pathlib import Path


def comment_trace_calls(content: str) -> tuple[str, int]:
    """
    Comment out all traceService.trace() calls in content.
    Returns (new_content, count_of_commented_traces).
    
    Handles both single-line and multi-line trace calls.
    """
    lines = content.split('\n')
    new_lines = []
    count = 0
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check if this line starts a trace call
        if 'traceService.trace(' in line and not line.strip().startswith('//'):
            # Check if it ends on the same line
            if line.count('(') == line.count(')'):
                # Single line trace - comment it
                indent = len(line) - len(line.lstrip())
                new_lines.append(' ' * indent + '// ' + line.strip())
                count += 1
            else:
                # Multi-line trace - collect all lines until closing paren
                trace_lines = [line]
                open_parens = line.count('(') - line.count(')')
                j = i + 1
                
                while j < len(lines) and open_parens > 0:
                    trace_lines.append(lines[j])
                    open_parens += lines[j].count('(') - lines[j].count(')')
                    j += 1
                
                # Comment out all lines of the trace call
                for trace_line in trace_lines:
                    if trace_line.strip():  # Don't comment empty lines
                        indent = len(trace_line) - len(trace_line.lstrip())
                        new_lines.append(' ' * indent + '// ' + trace_line.strip())
                    else:
                        new_lines.append(trace_line)
                
                count += 1
                i = j - 1  # Skip the lines we already processed
        else:
            new_lines.append(line)
        
        i += 1
    
    return '\n'.join(new_lines), count


def process_file(file_path: Path, dry_run: bool = False) -> tuple[int, int]:
    """Process a single file, returning (found_count, commented_count)."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"  ⚠️  Error reading: {e}")
        return 0, 0
    
    new_content, count = comment_trace_calls(content)
    
    if count == 0:
        return 0, 0
    
    if dry_run:
        print(f"  Would comment {count} trace call(s)")
        return count, 0
    
    # Write back
    file_path.write_text(new_content, encoding='utf-8')
    print(f"  ✅ Commented {count} trace call(s)")
    return count, count


def main():
    parser = argparse.ArgumentParser(
        description='Comment out traceService.trace() calls in TypeScript files'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Show what would be changed without modifying files'
    )
    parser.add_argument(
        'paths',
        nargs='*',
        default=['frontend/src'],
        help='Files or directories to process (default: frontend/src)'
    )
    
    args = parser.parse_args()
    
    total_found = 0
    total_commented = 0
    
    for path_str in args.paths:
        path = Path(path_str)
        if not path.exists():
            print(f"⚠️  Path not found: {path}")
            continue
        
        print(f"\n📁 Processing: {path}")
        
        # Find all .ts and .tsx files
        if path.is_file():
            files = [path]
        else:
            files = sorted(path.rglob('*.ts')) + sorted(path.rglob('*.tsx'))
            # Filter out node_modules and test files
            files = [
                f for f in files
                if 'node_modules' not in str(f)
                and '__tests__' not in str(f)
                and '.test.' not in str(f)
            ]
        
        for file_path in files:
            found, commented = process_file(file_path, args.dry_run)
            if found > 0:
                if args.dry_run:
                    print(f"   {file_path}")
                total_found += found
                total_commented += commented
    
    print(f"\n{'📊 Dry run summary' if args.dry_run else '✅ Summary'}:")
    print(f"   Trace calls found: {total_found}")
    print(f"   Trace calls {'would be commented' if args.dry_run else 'commented'}: {total_commented}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
