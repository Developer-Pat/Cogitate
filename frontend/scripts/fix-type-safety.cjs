#!/usr/bin/env node

/**
 * Phase 4: Type Safety Automation Script
 * 
 * Automates common type safety improvements:
 * 1. Replaces `: any` with `: unknown` (safer default)
 * 2. Replaces `as any` with `as unknown as <Type>` patterns
 * 3. Adds proper type annotations to event handlers
 * 4. Fixes common React type patterns
 * 
 * Usage: node scripts/fix-type-safety.js [directory]
 */

const fs = require('fs');
const path = require('path');

// Patterns to skip (files that should not be modified)
const SKIP_PATTERNS = [
  /node_modules/,
  /\.next/,
  /dist/,
  /build/,
  /__tests__/,
  /\.test\./,
  /\.spec\./,
];

// Safe replacements for : any
const ANY_REPLACEMENTS = [
  // Event handlers - use React types
  { 
    pattern: /\(event: any\)/g, 
    replacement: '(event: React.FormEvent<HTMLFormElement>)',
    description: 'Form event'
  },
  { 
    pattern: /\(e: any\)/g, 
    replacement: '(e: React.ChangeEvent<HTMLInputElement>)',
    description: 'Change event'
  },
  { 
    pattern: /onChange=\{.*\(e: any\)/g, 
    replacement: 'onChange={(e: React.ChangeEvent<HTMLInputElement>)',
    description: 'Input change event'
  },
  
  // Error handling - use Error type
  { 
    pattern: /\(error: any\)/g, 
    replacement: '(error: Error)',
    description: 'Error type'
  },
  { 
    pattern: /\(err: any\)/g, 
    replacement: '(err: Error)',
    description: 'Error type'
  },
  
  // Callback parameters - use unknown
  { 
    pattern: /callback: \(.*: any\)/g, 
    replacement: 'callback: (...args: unknown[])',
    description: 'Callback with unknown args'
  },
  
  // Function parameters that should be unknown
  { 
    pattern: /value: any(?=\s*[),}])/g, 
    replacement: 'value: unknown',
    description: 'Generic value parameter'
  },
  { 
    pattern: /data: any(?=\s*[),}])/g, 
    replacement: 'data: unknown',
    description: 'Generic data parameter'
  },
  { 
    pattern: /item: any(?=\s*[),}])/g, 
    replacement: 'item: unknown',
    description: 'Generic item parameter'
  },
  { 
    pattern: /props: any(?=\s*[),}])/g, 
    replacement: 'props: Record<string, unknown>',
    description: 'Props object'
  },
  
  // Array types - use unknown[]
  { 
    pattern: /: any\[\]/g, 
    replacement: ': unknown[]',
    description: 'Array of unknown'
  },
  
  // Record types
  { 
    pattern: /Record<string, any>/g, 
    replacement: 'Record<string, unknown>',
    description: 'Record with unknown values'
  },
  
  // Generic function types
  { 
    pattern: /<T extends any>/g, 
    replacement: '<T>',
    description: 'Remove unnecessary any constraint'
  },
];

// Safe replacements for 'as any'
const AS_ANY_REPLACEMENTS = [
  // Common API response patterns
  {
    pattern: /response\.data as any/g,
    replacement: 'response.data as Record<string, unknown>',
    description: 'API response data'
  },
  {
    pattern: /result as any/g,
    replacement: 'result as unknown',
    description: 'Generic result'
  },
  {
    pattern: /data as any/g,
    replacement: 'data as unknown',
    description: 'Generic data'
  },
  
  // JSON parsing
  {
    pattern: /JSON\.parse\(([^)]+)\) as any/g,
    replacement: 'JSON.parse($1) as unknown',
    description: 'JSON parse result'
  },
  
  // Default fallback - use unknown (safer)
  {
    pattern: / as any(?!\s*as)/g,
    replacement: ' as unknown',
    description: 'Type assertion to unknown'
  },
];

// Patterns that need manual review (don't auto-fix)
const MANUAL_REVIEW_PATTERNS = [
  /useState<any>/,
  /useReducer<any>/,
  /Promise<any>/,
  /Observable<any>/,
];

function shouldSkip(filePath) {
  return SKIP_PATTERNS.some(pattern => pattern.test(filePath));
}

function processFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  let newContent = content;
  let changes = 0;
  const manualReviews = [];

  // Apply : any replacements
  ANY_REPLACEMENTS.forEach(({ pattern, replacement, description }) => {
    const matches = newContent.match(pattern);
    if (matches) {
      changes += matches.length;
      newContent = newContent.replace(pattern, replacement);
    }
  });

  // Apply as any replacements
  AS_ANY_REPLACEMENTS.forEach(({ pattern, replacement, description }) => {
    const matches = newContent.match(pattern);
    if (matches) {
      changes += matches.length;
      newContent = newContent.replace(pattern, replacement);
    }
  });

  // Check for patterns needing manual review
  MANUAL_REVIEW_PATTERNS.forEach(pattern => {
    const matches = content.match(pattern);
    if (matches) {
      manualReviews.push(...matches.map(m => ({
        pattern: pattern.toString(),
        match: m,
        note: 'Requires manual type specification'
      })));
    }
  });

  if (changes > 0 && content !== newContent) {
    fs.writeFileSync(filePath, newContent, 'utf8');
  }

  return { changes, manualReviews };
}

function findFiles(dir) {
  const files = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);

    if (shouldSkip(fullPath)) continue;

    if (entry.isDirectory()) {
      files.push(...findFiles(fullPath));
    } else if (entry.isFile() && /\.(tsx|ts)$/.test(entry.name)) {
      files.push(fullPath);
    }
  }

  return files;
}

function main() {
  const targetDir = process.argv[2] || path.join(__dirname, '../src');

  console.log('🔧 Phase 4: Type Safety Automation');
  console.log('==================================');
  console.log(`Scanning: ${targetDir}`);
  console.log('');

  const files = findFiles(targetDir);
  console.log(`Found ${files.length} TypeScript files`);
  console.log('');

  let totalChanges = 0;
  let filesChanged = 0;
  const results = [];
  const allManualReviews = [];

  for (const file of files) {
    const { changes, manualReviews } = processFile(file);
    if (changes > 0) {
      totalChanges += changes;
      filesChanged++;
      const relativePath = path.relative(path.join(__dirname, '..'), file);
      results.push({ file: relativePath, changes });
    }
    if (manualReviews.length > 0) {
      allManualReviews.push({
        file: path.relative(path.join(__dirname, '..'), file),
        reviews: manualReviews
      });
    }
  }

  // Sort by most changes first
  results.sort((a, b) => b.changes - a.changes);

  console.log('📊 Results:');
  console.log('-----------');
  console.log(`Files scanned: ${files.length}`);
  console.log(`Files changed: ${filesChanged}`);
  console.log(`Total replacements: ${totalChanges}`);
  console.log('');

  if (results.length > 0) {
    console.log('Top changes:');
    results.slice(0, 20).forEach(({ file, changes }) => {
      console.log(`  ${changes.toString().padStart(4)}  ${file}`);
    });
  }

  console.log('');

  if (allManualReviews.length > 0) {
    console.log('⚠️  Files requiring manual review:');
    console.log('----------------------------------');
    allManualReviews.slice(0, 10).forEach(({ file, reviews }) => {
      console.log(`  ${file}`);
      reviews.forEach(r => {
        console.log(`    - ${r.note}: ${r.match}`);
      });
    });
    if (allManualReviews.length > 10) {
      console.log(`  ... and ${allManualReviews.length - 10} more files`);
    }
  }

  console.log('');
  console.log('✅ Done! Review changes and run TypeScript compiler.');
  console.log('');
  console.log('Next steps:');
  console.log('1. Run: npm run build');
  console.log('2. Fix remaining :any types manually');
  console.log('3. Enable "noImplicitAny": true in tsconfig.json');
}

main();
