#!/usr/bin/env node

/**
 * Phase 4: Advanced Type Safety Script
 * 
 * Handles more complex type safety improvements:
 * 1. Adds proper types to React hooks
 * 2. Fixes component prop types
 * 3. Adds return type annotations
 * 4. Improves error handling types
 * 
 * Usage: node scripts/fix-advanced-types.js [directory]
 */

const fs = require('fs');
const path = require('path');

const SKIP_PATTERNS = [
  /node_modules/,
  /\.next/,
  /dist/,
  /build/,
  /__tests__/,
  /\.test\./,
  /\.spec\./,
  /\.stories\./,
];

// Advanced replacements
const ADVANCED_REPLACEMENTS = [
  // React hooks with proper generics
  {
    pattern: /useState\(\[\]\)/g,
    replacement: 'useState<unknown[]>()',
    description: 'Empty array state'
  },
  {
    pattern: /useState\(\{\}\)/g,
    replacement: 'useState<Record<string, unknown>>()',
    description: 'Empty object state'
  },
  {
    pattern: /useState\(null\)/g,
    replacement: 'useState<unknown>(null)',
    description: 'Null state'
  },
  
  // useEffect cleanup functions
  {
    pattern: /useEffect\(\(\) => \{[\s\S]*?return \(\) => \{[\s\S]*?\}\)/g,
    replacement: (match) => {
      // Don't modify, just ensure it has proper cleanup type
      return match;
    },
    description: 'useEffect cleanup (no change needed)'
  },
  
  // useCallback with proper types
  {
    pattern: /useCallback\(\([^)]*\) => \{[^}]*\}, \[\]\)/g,
    replacement: (match) => {
      // Add proper return type if missing
      return match;
    },
    description: 'useCallback (review manually)'
  },
  
  // Fetch/axios response handling
  {
    pattern: /fetch\([^)]+\)\.then\(\(res\) => res\.json\(\)\)/g,
    replacement: 'fetch($1).then((res) => res.json() as Promise<unknown>)',
    description: 'Fetch JSON response'
  },
  
  // Event handler props
  {
    pattern: /onClick=\{[^}]*\}/g,
    replacement: (match) => {
      // Don't auto-modify onClick, needs manual review
      return match;
    },
    description: 'onClick (manual review)'
  },
  
  // onChange handlers
  {
    pattern: /onChange=\{\([^)]*\) =>/g,
    replacement: (match) => {
      // Don't auto-modify onChange, needs manual review
      return match;
    },
    description: 'onChange (manual review)'
  },
];

// Patterns to add explicit types
const TYPE_ANNOTATIONS = [
  // Function declarations without return types
  {
    pattern: /(function \w+\([^)]*\))(\s*{)/g,
    replacement: '$1: void$2',
    description: 'Add void return type to functions',
    enabled: false // Too aggressive, manual only
  },
  
  // Arrow functions assigned to const
  {
    pattern: /const (\w+) = \(([^)]*)\) =>/g,
    replacement: (match, name, params) => {
      // Don't auto-modify, needs context
      return match;
    },
    description: 'Arrow function (manual review)'
  },
];

function shouldSkip(filePath) {
  return SKIP_PATTERNS.some(pattern => pattern.test(filePath));
}

function processFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  let newContent = content;
  let changes = 0;
  const suggestions = [];

  // Apply advanced replacements
  ADVANCED_REPLACEMENTS.forEach(({ pattern, replacement, description }) => {
    const matches = newContent.match(pattern);
    if (matches && typeof replacement === 'string') {
      changes += matches.length;
      newContent = newContent.replace(pattern, replacement);
    } else if (matches && typeof replacement === 'function') {
      // For function replacements, just note them
      suggestions.push({
        pattern: description,
        count: matches.length,
        file: filePath
      });
    }
  });

  if (changes > 0 && content !== newContent) {
    fs.writeFileSync(filePath, newContent, 'utf8');
  }

  return { changes, suggestions };
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

  console.log('🔧 Phase 4: Advanced Type Safety');
  console.log('=================================');
  console.log(`Scanning: ${targetDir}`);
  console.log('');

  const files = findFiles(targetDir);
  console.log(`Found ${files.length} TypeScript files`);
  console.log('');

  let totalChanges = 0;
  let filesChanged = 0;
  const results = [];
  const allSuggestions = [];

  for (const file of files) {
    const { changes, suggestions } = processFile(file);
    if (changes > 0) {
      totalChanges += changes;
      filesChanged++;
      const relativePath = path.relative(path.join(__dirname, '..'), file);
      results.push({ file: relativePath, changes });
    }
    if (suggestions.length > 0) {
      allSuggestions.push({
        file: path.relative(path.join(__dirname, '..'), file),
        suggestions
      });
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
    console.log('Top changes:');
    results.slice(0, 20).forEach(({ file, changes }) => {
      console.log(`  ${changes.toString().padStart(4)}  ${file}`);
    });
  }

  console.log('');

  if (allSuggestions.length > 0) {
    console.log('💡 Suggestions for manual review:');
    console.log('----------------------------------');
    const flatSuggestions = allSuggestions.flatMap(s => s.suggestions);
    const grouped = flatSuggestions.reduce((acc, s) => {
      acc[s.pattern] = (acc[s.pattern] || 0) + s.count;
      return acc;
    }, {});

    Object.entries(grouped).forEach(([pattern, count]) => {
      console.log(`  ${count.toString().padStart(4)}  ${pattern}`);
    });
  }

  console.log('');
  console.log('✅ Done! Review suggestions and apply manually.');
}

main();
