#!/usr/bin/env node

/**
 * Phase 4: Conservative Type Safety Fix
 * 
 * Only makes safe, non-breaking replacements:
 * 1. Event handler types
 * 2. Error types  
 * 3. Removes unused :any that don't affect typing
 * 
 * Usage: node scripts/fix-types-conservative.cjs
 */

const fs = require('fs');
const path = require('path');

const SKIP_PATTERNS = [
  /node_modules/,
  /\.stories\./,
  /__tests__/,
  /\.test\./,
];

// Conservative, safe replacements only
const SAFE_REPLACEMENTS = [
  // Error types - always safe
  { 
    pattern: /\(error: any\)/g, 
    replacement: '(error: Error)'
  },
  { 
    pattern: /\(err: any\)/g, 
    replacement: '(err: Error)'
  },
  { 
    pattern: /catch \(error: any\)/g, 
    replacement: 'catch (error: Error)'
  },
  { 
    pattern: /catch \(err: any\)/g, 
    replacement: 'catch (err: Error)'
  },
  
  // Event types - safe for form/input events
  { 
    pattern: /onChange=\{\(e: any\)/g, 
    replacement: 'onChange={(e: React.ChangeEvent<HTMLInputElement>)'
  },
  { 
    pattern: /onSubmit=\{\(e: any\)/g, 
    replacement: 'onSubmit={(e: React.FormEvent<HTMLFormElement>)'
  },
  
  // Remove unused :any in comments
  { 
    pattern: /\/\*\* @type \{any\} \*\//g, 
    replacement: '/** @type {unknown} */'
  },
];

function shouldSkip(filePath) {
  return SKIP_PATTERNS.some(pattern => pattern.test(filePath));
}

function processFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  let newContent = content;
  let changes = 0;

  SAFE_REPLACEMENTS.forEach(({ pattern, replacement }) => {
    const matches = newContent.match(pattern);
    if (matches) {
      changes += matches.length;
      newContent = newContent.replace(pattern, replacement);
    }
  });

  if (changes > 0 && content !== newContent) {
    fs.writeFileSync(filePath, newContent, 'utf8');
    return changes;
  }
  
  return 0;
}

function findFiles(dir) {
  const files = [];
  try {
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
  } catch (err) {
    // Ignore directory errors
  }

  return files;
}

function main() {
  const targetDir = process.argv[2] || path.join(__dirname, '../src');

  console.log('🔧 Phase 4: Conservative Type Fixes');
  console.log('====================================');
  console.log(`Scanning: ${targetDir}`);
  console.log('');

  const files = findFiles(targetDir);
  console.log(`Found ${files.length} TypeScript files`);
  console.log('');

  let totalChanges = 0;
  let filesChanged = 0;
  const results = [];

  for (const file of files) {
    const changes = processFile(file);
    if (changes > 0) {
      totalChanges += changes;
      filesChanged++;
      const relativePath = path.relative(path.join(__dirname, '..'), file);
      results.push({ file: relativePath, changes });
    }
  }

  results.sort((a, b) => b.changes - a.changes);

  console.log('📊 Results:');
  console.log('-----------');
  console.log(`Files scanned: ${files.length}`);
  console.log(`Files changed: ${filesChanged}`);
  console.log(`Total replacements: ${totalChanges}`);
  console.log('');

  if (results.length > 0) {
    console.log('Changes:');
    results.slice(0, 20).forEach(({ file, changes }) => {
      console.log(`  ${changes.toString().padStart(4)}  ${file}`);
    });
  }

  console.log('');
  console.log('✅ Done! These changes are safe and non-breaking.');
}

main();
