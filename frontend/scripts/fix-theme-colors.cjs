#!/usr/bin/env node

/**
 * Theme Color Automation Script
 * Replaces hardcoded Tailwind colors with DaisyUI design tokens
 * 
 * Usage: node scripts/fix-theme-colors.js [directory]
 */

const fs = require('fs');
const path = require('path');

// Replacement patterns (order matters - more specific patterns first)
const REPLACEMENTS = [
  // Text colors
  { pattern: /\btext-gray-900\b/g, replacement: 'text-base-content' },
  { pattern: /\btext-gray-800\b/g, replacement: 'text-base-content' },
  { pattern: /\btext-gray-700\b/g, replacement: 'text-base-content/90' },
  { pattern: /\btext-gray-600\b/g, replacement: 'text-base-content/70' },
  { pattern: /\btext-gray-500\b/g, replacement: 'text-base-content/60' },
  { pattern: /\btext-gray-400\b/g, replacement: 'text-base-content/50' },
  { pattern: /\btext-gray-300\b/g, replacement: 'text-base-content/40' },
  { pattern: /\btext-gray-200\b/g, replacement: 'text-base-content/30' },
  { pattern: /\btext-gray-100\b/g, replacement: 'text-base-content/20' },
  { pattern: /\btext-black\b/g, replacement: 'text-base-content' },
  { pattern: /\btext-white\b(?!\/)/g, replacement: 'text-base-content' },
  
  // Blue text (often used for links/primary)
  { pattern: /\btext-blue-600\b/g, replacement: 'text-primary' },
  { pattern: /\btext-blue-500\b/g, replacement: 'text-primary' },
  { pattern: /\btext-blue-400\b/g, replacement: 'text-primary/90' },
  
  // Background colors
  { pattern: /\bbg-white\b(?!\/)/g, replacement: 'bg-base-100' },
  { pattern: /\bbg-gray-50\b/g, replacement: 'bg-base-200' },
  { pattern: /\bbg-gray-100\b/g, replacement: 'bg-base-200' },
  { pattern: /\bbg-gray-200\b/g, replacement: 'bg-base-300' },
  { pattern: /\bbg-gray-300\b/g, replacement: 'bg-base-300' },
  { pattern: /\bbg-gray-400\b/g, replacement: 'bg-base-300' },
  { pattern: /\bbg-gray-500\b/g, replacement: 'bg-base-content/50' },
  { pattern: /\bbg-gray-600\b/g, replacement: 'bg-base-content/60' },
  { pattern: /\bbg-gray-700\b/g, replacement: 'bg-base-200' },
  { pattern: /\bbg-gray-800\b/g, replacement: 'bg-base-200' },
  { pattern: /\bbg-gray-900\b/g, replacement: 'bg-base-300' },
  { pattern: /\bbg-black\b/g, replacement: 'bg-base-content' },
  
  // Blue backgrounds (often used for alerts/modals)
  { pattern: /\bbg-blue-900\b/g, replacement: 'bg-info' },
  { pattern: /\bbg-blue-800\b/g, replacement: 'bg-info' },
  { pattern: /\bbg-blue-700\b/g, replacement: 'bg-info' },
  { pattern: /\bbg-blue-600\b/g, replacement: 'bg-primary' },
  { pattern: /\bbg-blue-500\b/g, replacement: 'bg-primary' },
  { pattern: /\bbg-blue-100\b/g, replacement: 'bg-primary/10' },
  { pattern: /\bbg-blue-50\b/g, replacement: 'bg-primary/10' },
  
  // Border colors
  { pattern: /\bborder-gray-700\b/g, replacement: 'border-base-content/20' },
  { pattern: /\bborder-gray-600\b/g, replacement: 'border-base-content/20' },
  { pattern: /\bborder-gray-500\b/g, replacement: 'border-base-content/20' },
  { pattern: /\bborder-gray-400\b/g, replacement: 'border-base-content/20' },
  { pattern: /\bborder-gray-300\b/g, replacement: 'border-base-content/20' },
  { pattern: /\bborder-gray-200\b/g, replacement: 'border-base-content/20' },
  { pattern: /\bborder-gray-100\b/g, replacement: 'border-base-content/10' },
  
  // Divide colors
  { pattern: /\bdivide-gray-700\b/g, replacement: 'divide-base-content/20' },
  { pattern: /\bdivide-gray-600\b/g, replacement: 'divide-base-content/20' },
  { pattern: /\bdivide-gray-500\b/g, replacement: 'divide-base-content/20' },
  { pattern: /\bdivide-gray-400\b/g, replacement: 'divide-base-content/20' },
  { pattern: /\bdivide-gray-300\b/g, replacement: 'divide-base-content/20' },
  { pattern: /\bdivide-gray-200\b/g, replacement: 'divide-base-content/20' },
  
  // Ring colors
  { pattern: /\bring-gray-500\b/g, replacement: 'ring-base-content/20' },
  { pattern: /\bring-gray-400\b/g, replacement: 'ring-base-content/20' },
  { pattern: /\bring-gray-300\b/g, replacement: 'ring-base-content/20' },
  { pattern: /\bring-gray-200\b/g, replacement: 'ring-base-content/20' },
  
  // Placeholder colors
  { pattern: /\bplaceholder-gray-500\b/g, replacement: 'placeholder-base-content/50' },
  { pattern: /\bplaceholder-gray-400\b/g, replacement: 'placeholder-base-content/50' },
  
  // Shadow colors (convert to base shadow)
  { pattern: /\bshadow-gray-500\b/g, replacement: 'shadow-md' },
  { pattern: /\bshadow-gray-400\b/g, replacement: 'shadow-md' },
];

// Patterns to skip (files that should not be modified)
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

function shouldSkip(filePath) {
  return SKIP_PATTERNS.some(pattern => pattern.test(filePath));
}

function processFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  let newContent = content;
  let changes = 0;
  
  REPLACEMENTS.forEach(({ pattern, replacement }) => {
    const matches = newContent.match(pattern);
    if (matches) {
      changes += matches.length;
      newContent = newContent.replace(pattern, replacement);
    }
  });
  
  if (changes > 0 && content !== newContent) {
    fs.writeFileSync(filePath, newContent, 'utf8');
  }
  
  return changes;
}

function findFiles(dir) {
  const files = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    
    if (shouldSkip(fullPath)) continue;
    
    if (entry.isDirectory()) {
      files.push(...findFiles(fullPath));
    } else if (entry.isFile() && /\.(tsx|ts|jsx|js)$/.test(entry.name)) {
      files.push(fullPath);
    }
  }
  
  return files;
}

function main() {
  const targetDir = process.argv[2] || path.join(__dirname, '../src');
  
  console.log('🎨 Theme Color Automation Script');
  console.log('================================');
  console.log(`Scanning: ${targetDir}`);
  console.log('');
  
  const files = findFiles(targetDir);
  console.log(`Found ${files.length} source files`);
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
  console.log('✅ Done! Please review changes and test the application.');
}

main();
